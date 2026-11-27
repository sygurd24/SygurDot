#!/usr/bin/env python3
"""CLI tool for enrolling, testing, and managing hardened local IR facial unlock."""

from __future__ import annotations

import argparse
import os
import pwd
import socket
import sys
import time
from pathlib import Path

# Prefer root-isolated /opt/face-auth venv when installed, else user venv
OPT_VENV_DIR = Path("/opt/face-auth/venv")
USER_VENV_DIR = Path.home() / ".local" / "share" / "face-auth" / "venv"
VENV_DIR = OPT_VENV_DIR if (OPT_VENV_DIR / "bin" / "python").exists() else USER_VENV_DIR
VENV_PY = VENV_DIR / "bin" / "python"
if VENV_PY.exists() and Path(sys.prefix).resolve() != VENV_DIR.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])

# Import engine from /opt/face-auth if present, else alongside this script
if (Path("/opt/face-auth/face_engine.py")).exists():
    sys.path.insert(0, "/opt/face-auth")
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from face_engine import (  # noqa: E402
    EMBEDDINGS_PATH,
    FaceEngine,
    detect_ir_device,
    load_embeddings,
    open_ir_camera,
    prepare_ir_frame,
    save_embeddings,
    verify_live,
)

SOCK_PATH = Path("/run/face-auth/face-auth.sock")

# Resolve target user's home even when run under sudo
_SUDO_USER = os.environ.get("SUDO_USER")
if _SUDO_USER:
    TARGET_HOME = Path(pwd.getpwnam(_SUDO_USER).pw_dir)
else:
    TARGET_HOME = Path.home()
ENABLED_FILE = TARGET_HOME / ".config" / "dotfiles" / "face_auth_enabled"


def daemon_query(cmd: str) -> str | None:
    if not SOCK_PATH.exists():
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(8.0)
            s.connect(str(SOCK_PATH))
            s.sendall((cmd + "\n").encode("utf-8"))
            return s.recv(256).decode("utf-8", errors="ignore").strip()
    except OSError:
        return None


def cmd_enroll(samples: int, append: bool) -> int:
    if EMBEDDINGS_PATH.parent == Path("/var/lib/face-auth") and os.geteuid() != 0:
        print("Por seguridad, registrar o modificar rostros requiere permisos de administrador:")
        print(f"  sudo face-auth enroll{' --append' if append else ''}")
        return 1

    print("Cargando modelos ONNX (buffalo_sc)...")
    engine = FaceEngine()

    existing = load_embeddings(EMBEDDINGS_PATH) if append else None
    collected: list[np.ndarray] = []

    ir_dev = detect_ir_device()
    print(f"\nAbriendo cámara infrarroja ({ir_dev})...")
    print("Mira a la cámara y mueve ligeramente la cabeza (centro, un poco izq/der/arriba/abajo).")
    cap = open_ir_camera(ir_dev)
    if not cap.isOpened():
        print(f"Error: no se pudo abrir {ir_dev}", file=sys.stderr)
        return 1

    t0 = time.monotonic()
    last_capture = 0.0
    try:
        while len(collected) < samples and (time.monotonic() - t0) < 25.0:
            ok, raw = cap.read()
            if not ok:
                time.sleep(0.02)
                continue
            frame_bgr = prepare_ir_frame(raw)
            if frame_bgr is None:
                continue

            now = time.monotonic()
            if now - last_capture < 0.18:
                continue

            res = engine.extract_embedding(frame_bgr, score_thresh=0.65, check_liveness=True)
            if res is None:
                continue
            emb, det_score, box, live_reason = res
            if emb is None:
                continue

            collected.append(emb)
            last_capture = now
            w = int(box[2] - box[0])
            h = int(box[3] - box[1])
            print(f"  [{len(collected):2d}/{samples}] Capturado (det={det_score:.2f}, tamaño={w}x{h}px, liveness={live_reason})")
    finally:
        cap.release()

    if len(collected) < 5:
        print("Error: no se capturaron suficientes rostros válidos. Intenta frente a la cámara.", file=sys.stderr)
        return 1

    arr = np.stack(collected, axis=0)
    sim_matrix = arr @ arr.T
    mean_self_sim = float((sim_matrix.sum() - len(collected)) / max(len(collected) * (len(collected) - 1), 1))

    if existing is not None and existing.size > 0:
        arr = np.concatenate([existing, arr], axis=0)

    save_embeddings(arr, EMBEDDINGS_PATH)
    daemon_query("RELOAD")
    print(f"\nRegistro completado: {len(arr)} muestras guardadas en {EMBEDDINGS_PATH} (root:root 0600)")
    print(f"Consistencia interna: {mean_self_sim:.3f}")
    return 0


def cmd_test(via_daemon: bool) -> int:
    if via_daemon:
        t0 = time.monotonic()
        resp = daemon_query("VERIFY")
        elapsed = int((time.monotonic() - t0) * 1000)
        if resp is None:
            print("Error: el servicio face-auth.service no está respondiendo en /run/face-auth/face-auth.sock", file=sys.stderr)
            return 1
        print(f"Daemon -> {resp} (tiempo total cliente+daemon: {elapsed} ms)")
        return 0 if resp.startswith("OK") else 1

    enrolled = load_embeddings(EMBEDDINGS_PATH)
    if enrolled is None or enrolled.size == 0:
        print("No hay rostro registrado (o requiere sudo para lectura directa).", file=sys.stderr)
        return 1
    engine = FaceEngine()
    matched, score, ms, reason = verify_live(engine, enrolled)
    print(f"Directo -> {'OK' if matched else 'FAIL'} ({reason}) score={score:.3f} ms={ms}")
    return 0 if matched else 1


def cmd_status() -> int:
    enabled = (not ENABLED_FILE.exists()) or ENABLED_FILE.read_text().strip().lower() != "off"
    pam_ok = Path("/etc/pam.d/i3lock").exists() and "pam_face_auth.so" in Path("/etc/pam.d/i3lock").read_text(errors="ignore")
    daemon_resp = daemon_query("STATUS")

    print(f"Estado:      {'ACTIVADO' if enabled else 'DESACTIVADO'}")
    print(f"Almacén:     {EMBEDDINGS_PATH} (aislado root:root 0600)")
    print(f"Daemon:      {daemon_resp or 'DETENIDO'}")
    print(f"PAM i3lock:  {'INSTALADO (/etc/pam.d/i3lock)' if pam_ok else 'PENDIENTE'}")
    return 0


def cmd_toggle(state: str) -> int:
    ENABLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENABLED_FILE.write_text(f"{state}\n")
    print(f"Reconocimiento facial IR: {'ACTIVADO' if state == 'on' else 'DESACTIVADO'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hardened local IR facial unlock manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_enr = sub.add_parser("enroll", help="Registrar tu rostro usando la cámara IR (requiere sudo)")
    p_enr.add_argument("-n", "--samples", type=int, default=15, help="Número de capturas (default: 15)")
    p_enr.add_argument("--append", action="store_true", help="Agregar muestras a las ya guardadas (ej. con lentes)")

    p_test = sub.add_parser("test", help="Probar reconocimiento y medir velocidad")
    p_test.add_argument("--direct", action="store_true", help="Probar sin pasar por el daemon")

    sub.add_parser("status", help="Ver estado del servicio, lockout y PAM")
    sub.add_parser("enable", help="Activar desbloqueo facial")
    sub.add_parser("disable", help="Desactivar desbloqueo facial")
    sub.add_parser("reset-lockout", help="Reiniciar contador de intentos fallidos")

    args = parser.parse_args()
    if args.command == "enroll":
        return cmd_enroll(args.samples, args.append)
    if args.command == "test":
        return cmd_test(not args.direct)
    if args.command == "status":
        return cmd_status()
    if args.command == "enable":
        return cmd_toggle("on")
    if args.command == "disable":
        return cmd_toggle("off")
    if args.command == "reset-lockout":
        print(daemon_query("RESET_LOCKOUT") or "Daemon no disponible")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
