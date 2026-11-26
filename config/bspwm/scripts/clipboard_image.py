#!/usr/bin/env python3
"""Safe X11 PNG clipboard owner using GTK3 (avoids xclip 0.13 INCR deadlocks).

Usage:
  clipboard_image.py /path/to/image.png

Validates the PNG file with GdkPixbuf, takes ownership of the X11 CLIPBOARD
selection via Gtk.Clipboard.set_image() (pure C GTK3 implementation that
properly handles X11 INCR transfers and concurrent readers such as greenclip
+ browsers/Electron), and exits cleanly as soon as another application takes
clipboard ownership.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/clipimg-{os.getuid()}")
PID_FILE = RUNTIME_DIR / "clipboard_image.pid"
LOG_FILE = Path("/tmp/screenshot_copy.log")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def is_valid_png_file(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 67:
            return False
        with open(path, "rb") as f:
            return f.read(8) == PNG_MAGIC
    except OSError:
        return False


def stop_previous_owners() -> None:
    """Terminate any previous clipboard_image.py or wedged `xclip -t image/png`."""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if old_pid > 0 and old_pid != os.getpid():
                os.kill(old_pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except OSError:
            pass

    # Kill any wedged xclip image/png processes left behind by xclip 0.13 INCR bugs
    try:
        subprocess.run(
            ["pkill", "-f", "xclip -selection clipboard -t image/png"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
        )
    except Exception:
        pass


def serve_with_gtk(png_bytes: bytes, selection_name: str | None = None) -> bool:
    # Validate full PNG decoding using GdkPixbuf ONLY (does not open an X11 display)
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        loader = GdkPixbuf.PixbufLoader.new_with_type("png")
        loader.write(png_bytes)
        loader.close()
        pixbuf = loader.get_pixbuf()
        if pixbuf is None or pixbuf.get_width() <= 0 or pixbuf.get_height() <= 0:
            log("Invalid PNG: GdkPixbuf returned empty pixbuf")
            return False
        w, h = pixbuf.get_width(), pixbuf.get_height()
    except Exception as exc:
        log(f"Invalid PNG decode failed: {exc}")
        return False

    # Fork BEFORE importing Gtk/Gdk so the child opens its own fresh X11 connection
    r_fd, w_fd = os.pipe()
    pid = os.fork()
    if pid > 0:
        os.close(w_fd)
        status = os.read(r_fd, 16)
        os.close(r_fd)
        ok = status == b"OK"
        log(f"GTK clipboard holder fork pid={pid} ({w}x{h}, {len(png_bytes)}B) -> {'OK' if ok else status!r}")
        return ok

    # Child process: detach completely from caller's stdio/session and close any
    # inherited file descriptors (such as flock fd 9 from screenshot_copy.sh!)
    os.close(r_fd)
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        try:
            os.dup2(devnull, fd)
        except OSError:
            pass
    if devnull > 2:
        os.close(devnull)
    if w_fd > 3:
        os.closerange(3, w_fd)
    os.closerange(w_fd + 1, 1024)

    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, GLib, Gtk

        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        if selection_name is None:
            PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

        def quit_safe() -> bool:
            if Gtk.main_level() > 0:
                Gtk.main_quit()
            return False

        def handle_term(_sig, _frame):
            GLib.idle_add(quit_safe)

        signal.signal(signal.SIGTERM, handle_term)
        signal.signal(signal.SIGINT, handle_term)

        sel_atom = Gdk.Atom.intern(selection_name, False) if selection_name else Gdk.SELECTION_CLIPBOARD
        clipboard = Gtk.Clipboard.get(sel_atom)

        armed = {"ready": False}

        def on_owner_change(_clip, event):
            # In GDK3 X11, event.owner is a GdkWindow only when owned by THIS process;
            # when an external process takes clipboard ownership, event.owner is None.
            if armed["ready"] and event.owner is None:
                log(f"Clipboard ownership lost via owner-change (pid={os.getpid()}), exiting cleanly.")
                GLib.idle_add(quit_safe)

        def poll_owner() -> bool:
            if armed["ready"] and Gdk.selection_owner_get(sel_atom) is None:
                log(f"Clipboard ownership lost via poll (pid={os.getpid()}), exiting cleanly.")
                quit_safe()
                return False
            return True

        clipboard.connect("owner-change", on_owner_change)
        clipboard.set_image(pixbuf)
        Gdk.flush()
        GLib.timeout_add(150, lambda: (armed.__setitem__("ready", True), False)[1])
        GLib.timeout_add(500, poll_owner)

        os.write(w_fd, b"OK")
        os.close(w_fd)

        Gtk.main()
    except Exception as exc:
        log(f"Child GTK error: {exc}")
        try:
            os.write(w_fd, b"ERR")
            os.close(w_fd)
        except OSError:
            pass
    finally:
        try:
            if selection_name is None and PID_FILE.exists():
                if PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    PID_FILE.unlink()
        except OSError:
            pass
        os._exit(0)
    return True


def serve_with_xclip_fallback(png_bytes: bytes) -> bool:
    if not shutil.which("xclip"):
        return False
    fd, tmp = tempfile.mkstemp(prefix="clipimg_", suffix=".png")
    try:
        os.write(fd, png_bytes)
        os.close(fd)
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-i", tmp],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        proc.wait(timeout=3)
        return proc.returncode == 0
    except Exception:
        return False
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def main() -> int:
    args = sys.argv[1:]
    sel_name = None
    if len(args) == 3 and args[0] == "--selection":
        sel_name = args[1]
        args = [args[2]]

    if len(args) != 1:
        print("Usage: clipboard_image.py [--selection NAME] <image.png>", file=sys.stderr)
        return 2

    img_path = Path(args[0])
    if not is_valid_png_file(img_path):
        log(f"Rejected invalid/empty PNG: {img_path}")
        return 1

    png_bytes = img_path.read_bytes()
    if sel_name is None:
        stop_previous_owners()

    if serve_with_gtk(png_bytes, selection_name=sel_name):
        return 0
    if sel_name is None:
        log("GTK clipboard failed; falling back to xclip")
        if serve_with_xclip_fallback(png_bytes):
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
