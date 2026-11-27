#!/usr/bin/env python3
"""Hardened system Unix-socket daemon for local IR facial verification.

Security properties:
- Designed to run as a root-isolated systemd service with read-only /opt/face-auth
  and root-only 0600 /var/lib/face-auth/embeddings.npz.
- Verifies client UID via kernel SO_PEERCRED (only root or authorized user allowed).
- Enforces failed-attempt lockout (5 consecutive fails -> 60s cooldown).
- Keeps buffalo_sc ONNX models pre-loaded in RAM (~65 MB, 0% CPU idle, 0% GPU).
"""

from __future__ import annotations

import os
import pwd
import signal
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

from face_engine import (
    DEFAULT_DEVICE,
    DEFAULT_REQUIRED_MATCHES,
    DEFAULT_THRESHOLD,
    DEFAULT_TOP3_THRESHOLD,
    EMBEDDINGS_PATH,
    FaceEngine,
    load_embeddings,
    verify_live,
)

TARGET_USER = os.environ.get("FACE_AUTH_USER", "sygurd")
try:
    _PW = pwd.getpwnam(TARGET_USER)
    TARGET_UID = _PW.pw_uid
    TARGET_HOME = Path(_PW.pw_dir)
except KeyError:
    TARGET_UID = os.getuid()
    TARGET_HOME = Path.home()

SOCK_PATH = Path(os.environ.get("FACE_AUTH_SOCK", "/run/face-auth/face-auth.sock"))
ENROLLED_MARKER = SOCK_PATH.parent / "enrolled"
ENABLED_FILE = TARGET_HOME / ".config" / "dotfiles" / "face_auth_enabled"

MAX_CONSECUTIVE_FAILS = 5
LOCKOUT_SECONDS = 60.0


def is_enabled() -> bool:
    if not ENABLED_FILE.exists():
        return True
    try:
        return ENABLED_FILE.read_text().strip().lower() != "off"
    except OSError:
        return True


def get_peer_uid(conn: socket.socket) -> Optional[int]:
    try:
        creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", creds)
        return int(uid)
    except OSError:
        return None


class FaceAuthDaemon:
    def __init__(self) -> None:
        self.engine = FaceEngine()
        self.enrolled: Optional[np.ndarray] = None
        self.enrolled_mtime: float = 0.0
        self.verify_lock = threading.Lock()
        self.running = True
        self.consecutive_fails: int = 0
        self.lockout_until: float = 0.0
        self._reload_embeddings_if_needed()

    def _sync_enrolled_marker(self) -> None:
        try:
            ENROLLED_MARKER.parent.mkdir(parents=True, exist_ok=True)
            if self.enrolled is not None and self.enrolled.shape[0] > 0:
                ENROLLED_MARKER.touch(exist_ok=True)
                os.chmod(ENROLLED_MARKER, 0o644)
            elif ENROLLED_MARKER.exists():
                ENROLLED_MARKER.unlink()
        except OSError:
            pass

    def _reload_embeddings_if_needed(self) -> Optional[np.ndarray]:
        if not EMBEDDINGS_PATH.exists():
            self.enrolled = None
            self.enrolled_mtime = 0.0
            self._sync_enrolled_marker()
            return None
        try:
            mtime = EMBEDDINGS_PATH.stat().st_mtime
            if self.enrolled is None or mtime != self.enrolled_mtime:
                self.enrolled = load_embeddings(EMBEDDINGS_PATH)
                self.enrolled_mtime = mtime
        except OSError:
            return None
        self._sync_enrolled_marker()
        return self.enrolled

    def _remaining_lockout(self) -> int:
        rem = self.lockout_until - time.monotonic()
        if rem > 0:
            return int(rem) + 1
        if self.lockout_until > 0:
            self.lockout_until = 0.0
            self.consecutive_fails = 0
        return 0

    def handle_request(self, line: str, peer_uid: int) -> str:
        cmd = line.strip().upper()
        if cmd == "PING":
            return "PONG\n"
        if cmd == "STATUS":
            enrolled = self._reload_embeddings_if_needed()
            count = int(enrolled.shape[0]) if enrolled is not None else 0
            rem = self._remaining_lockout()
            return (
                f"STATUS enabled={int(is_enabled())} enrolled={count} "
                f"threshold={DEFAULT_THRESHOLD:.2f} fails={self.consecutive_fails}/{MAX_CONSECUTIVE_FAILS} "
                f"lockout={rem}s\n"
            )
        if cmd == "RELOAD":
            enrolled = self._reload_embeddings_if_needed()
            count = int(enrolled.shape[0]) if enrolled is not None else 0
            return f"OK enrolled={count}\n"
        if cmd == "RESET_LOCKOUT":
            if peer_uid != 0 and peer_uid != TARGET_UID:
                return "FAIL unauthorized\n"
            self.consecutive_fails = 0
            self.lockout_until = 0.0
            return "OK reset\n"
        if cmd == "VERIFY":
            if not is_enabled():
                return "FAIL disabled\n"
            rem = self._remaining_lockout()
            if rem > 0:
                return f"FAIL locked_out remaining={rem}s\n"
            enrolled = self._reload_embeddings_if_needed()
            if enrolled is None or enrolled.shape[0] == 0:
                return "FAIL not_enrolled\n"
            with self.verify_lock:
                rem = self._remaining_lockout()
                if rem > 0:
                    return f"FAIL locked_out remaining={rem}s\n"
                matched, score, elapsed_ms, reason = verify_live(
                    self.engine,
                    enrolled,
                    threshold=DEFAULT_THRESHOLD,
                    top3_threshold=DEFAULT_TOP3_THRESHOLD,
                    required_matches=DEFAULT_REQUIRED_MATCHES,
                    timeout_sec=1.8,
                )
                if matched:
                    self.consecutive_fails = 0
                    self.lockout_until = 0.0
                    return f"OK score={score:.3f} ms={elapsed_ms}\n"
                if reason == "overexposed_warmup":
                    # Hardware auto-exposure was still settling from white-out; don't trigger brute-force lockout
                    return f"FAIL {reason} fails={self.consecutive_fails}/{MAX_CONSECUTIVE_FAILS} score={score:.3f} ms={elapsed_ms}\n"
                self.consecutive_fails += 1
                if self.consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    self.lockout_until = time.monotonic() + LOCKOUT_SECONDS
                    return f"FAIL locked_out fails={self.consecutive_fails} score={score:.3f} ms={elapsed_ms}\n"
                return f"FAIL {reason} fails={self.consecutive_fails}/{MAX_CONSECUTIVE_FAILS} score={score:.3f} ms={elapsed_ms}\n"
        return "FAIL unknown_cmd\n"

    def serve(self) -> None:
        SOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(SOCK_PATH.parent, 0o755)
        if SOCK_PATH.exists():
            SOCK_PATH.unlink()

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        os.umask(0o000)
        server.bind(str(SOCK_PATH))
        # Allow TARGET_UID (i3lock/PAM) to connect; kernel SO_PEERCRED enforces UID authorization
        os.chmod(SOCK_PATH, 0o666)
        os.umask(0o077)
        server.listen(4)
        server.settimeout(1.0)

        def _stop(_sig: int, _frame: object) -> None:
            self.running = False

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        print(f"face-auth hardened daemon listening on {SOCK_PATH} (user={TARGET_USER}, uid={TARGET_UID})", flush=True)
        try:
            while self.running:
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with conn:
                    conn.settimeout(8.0)
                    peer_uid = get_peer_uid(conn)
                    if peer_uid is None or peer_uid not in (0, TARGET_UID):
                        try:
                            conn.sendall(b"FAIL unauthorized\n")
                        except OSError:
                            pass
                        continue
                    try:
                        data = conn.recv(256).decode("utf-8", errors="ignore")
                        resp = self.handle_request(data, peer_uid)
                        conn.sendall(resp.encode("utf-8"))
                    except OSError:
                        pass
        finally:
            server.close()
            if SOCK_PATH.exists():
                try:
                    SOCK_PATH.unlink()
                except OSError:
                    pass


if __name__ == "__main__":
    FaceAuthDaemon().serve()
