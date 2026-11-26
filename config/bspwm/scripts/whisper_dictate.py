#!/usr/bin/env python3
"""Toggleable voice-to-clipboard dictation controller for bspwm/sxhkd.

Bound to `super + shift + a`:
  - 1st press: starts recording 16kHz mono WAV via PipeWire (`pw-record`, with
               `parecord`/`ffmpeg` fallback) and warms the daemon in background
               if configured for 'hybrid' or 'instant' mode.
  - 2nd press: stops recording, transcribes with faster-whisper, copies text to
               the X11 clipboard (`xclip`, compatible with greenclip), and
               optionally pastes (`xdotool`).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = Path(__file__).resolve().parent
WORKER_SCRIPT = SCRIPT_DIR / "whisper_worker.py"
VENV_DIR = Path.home() / ".local/share/dotfiles-whisper/venv"
VENV_PYTHON = VENV_DIR / "bin/python"
CONFIG_FILE = Path.home() / ".config/dotfiles/whisper.json"
LANG_FILE = Path.home() / ".config/dotfiles/language"

RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/whisper-{os.getuid()}")
LOCK_FILE = RUNTIME_DIR / "whisper_dictate.lock"
RECORDING_STATE = RUNTIME_DIR / "whisper_recording.json"
SOCKET_PATH = RUNTIME_DIR / "whisper_daemon.sock"
DAEMON_PID_FILE = RUNTIME_DIR / "whisper_daemon.pid"
LOG_FILE = Path("/tmp/whisper_dictate.log")
NOTIFY_REPLACE_ID = "991056"

DEFAULT_CONFIG = {
    "model": "large-v3-turbo",
    "language": "auto",
    "mode": "hybrid",
    "idle_timeout": 300,
    "device": "auto",
    "post_action": "copy",
}

TERMINAL_CLASSES = {
    "kitty", "alacritty", "urxvt", "xterm", "st", "st-256color",
    "gnome-terminal", "xfce4-terminal", "konsole", "wezterm", "foot", "tilix",
}


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [cli] {msg}\n")
    except OSError:
        pass


def get_ui_lang() -> str:
    try:
        if LANG_FILE.exists():
            val = LANG_FILE.read_text(encoding="utf-8").strip()
            if val:
                return val
    except OSError:
        pass
    return os.environ.get("LANG", "en").split("_")[0].split(".")[0] or "en"


def L(translations: dict[str, str]) -> str:
    lang = get_ui_lang()
    return translations.get(lang) or translations.get("en") or next(iter(translations.values()))


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg


def notify(
    title: str,
    body: str,
    icon: str = "audio-input-microphone",
    urgency: str = "normal",
    timeout_ms: int = 3500,
) -> None:
    dunstify = shutil.which("dunstify")
    if dunstify:
        cmd = [
            dunstify,
            "-a", "WhisperDictate",
            "-u", urgency,
            "-r", NOTIFY_REPLACE_ID,
            "-t", str(timeout_ms),
            "-i", icon,
            title,
            body,
        ]
    elif shutil.which("notify-send"):
        cmd = ["notify-send", "-u", urgency, "-t", str(timeout_ms), "-i", icon, title, body]
    else:
        return
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def build_worker_env() -> dict[str, str]:
    """Attach venv NVIDIA CUDA library directories to LD_LIBRARY_PATH."""
    env = dict(os.environ)
    nvidia_dirs: list[str] = []
    lib_root = VENV_DIR / "lib"
    if lib_root.exists():
        for lib_dir in sorted(lib_root.glob("python*/site-packages/nvidia/*/lib")):
            if lib_dir.is_dir():
                nvidia_dirs.append(str(lib_dir))
    if nvidia_dirs:
        existing = env.get("LD_LIBRARY_PATH", "")
        prefix = ":".join(nvidia_dirs)
        env["LD_LIBRARY_PATH"] = f"{prefix}:{existing}" if existing else prefix
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    return env


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def daemon_request(payload: dict, timeout: float = 5.0) -> dict | None:
    if not SOCKET_PATH.exists():
        return None
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(SOCKET_PATH))
        s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        s.shutdown(socket.SHUT_WR)
        chunks: list[bytes] = []
        while True:
            data = s.recv(65536)
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break
        raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None
    finally:
        try:
            s.close()
        except OSError:
            pass


def daemon_status() -> dict:
    resp = daemon_request({"cmd": "ping"}, timeout=1.5)
    if resp and resp.get("ok"):
        resp["running"] = True
        return resp
    # Check if starting up (PID alive, socket not ready yet)
    if DAEMON_PID_FILE.exists():
        try:
            pid = int(DAEMON_PID_FILE.read_text(encoding="utf-8").strip())
            if pid_alive(pid):
                return {"running": True, "starting": True, "pid": pid}
        except Exception:
            pass
    return {"running": False}


def start_daemon(wait_ready: bool = False, timeout: float = 45.0) -> bool:
    if not VENV_PYTHON.exists():
        return False

    st = daemon_status()
    if st.get("running") and not st.get("starting"):
        return True

    if not st.get("running"):
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        log("Starting whisper_worker.py --daemon in background")
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            subprocess.Popen(
                [str(VENV_PYTHON), str(WORKER_SCRIPT), "--daemon"],
                env=build_worker_env(),
                stdin=subprocess.DEVNULL,
                stdout=lf,
                stderr=lf,
                start_new_session=True,
            )

    if not wait_ready:
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = daemon_request({"cmd": "ping"}, timeout=1.5)
        if resp and resp.get("ok"):
            return True
        time.sleep(0.2)
    return False


def stop_daemon() -> bool:
    resp = daemon_request({"cmd": "shutdown"}, timeout=3.0)
    if resp and resp.get("ok"):
        for _ in range(25):
            if not daemon_status().get("running"):
                return True
            time.sleep(0.1)

    if DAEMON_PID_FILE.exists():
        try:
            pid = int(DAEMON_PID_FILE.read_text(encoding="utf-8").strip())
            if pid_alive(pid):
                os.kill(pid, signal.SIGTERM)
                for _ in range(20):
                    if not pid_alive(pid):
                        break
                    time.sleep(0.1)
        except Exception:
            pass

    for p in (SOCKET_PATH, DAEMON_PID_FILE):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass
    return True


def build_record_command(wav_path: Path) -> list[str] | None:
    if shutil.which("pw-record"):
        return ["pw-record", "--format=s16", "--rate=16000", "--channels=1", str(wav_path)]
    if shutil.which("parecord"):
        return ["parecord", "--file-format=wav", "--format=s16le", "--rate=16000", "--channels=1", str(wav_path)]
    if shutil.which("ffmpeg"):
        return [
            "ffmpeg", "-y", "-nostdin", "-f", "pulse", "-i", "default",
            "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(wav_path),
        ]
    return None


def read_recording_state() -> dict | None:
    if not RECORDING_STATE.exists():
        return None
    try:
        data = json.loads(RECORDING_STATE.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
        if pid_alive(pid):
            return data
    except Exception:
        pass
    try:
        RECORDING_STATE.unlink()
    except OSError:
        pass
    return None


def copy_to_clipboard(text: str) -> bool:
    if shutil.which("xclip"):
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        assert proc.stdin is not None
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
        # Also populate PRIMARY selection silently if desired? Keep only CLIPBOARD to avoid surprises.
        return True
    if shutil.which("xsel"):
        proc = subprocess.Popen(
            ["xsel", "--clipboard", "--input"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        assert proc.stdin is not None
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
        return True
    return False


def auto_paste() -> None:
    xdotool = shutil.which("xdotool")
    if not xdotool:
        return
    time.sleep(0.15)
    shortcut = "ctrl+v"
    try:
        wid = subprocess.check_output([xdotool, "getactivewindow"], text=True, stderr=subprocess.DEVNULL).strip()
        if wid and shutil.which("xprop"):
            wm_class = subprocess.check_output(
                ["xprop", "-id", wid, "WM_CLASS"], text=True, stderr=subprocess.DEVNULL
            ).lower()
            if any(term in wm_class for term in TERMINAL_CLASSES):
                shortcut = "ctrl+shift+v"
    except Exception:
        pass
    try:
        subprocess.run(
            [xdotool, "key", "--clearmodifiers", shortcut],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except Exception:
        pass


def transcribe_wav(wav_path: Path, cfg: dict) -> dict:
    mode = str(cfg.get("mode", "hybrid"))

    if mode in ("hybrid", "instant"):
        # If daemon was warmed up while recording, wait for it (model download could take longer on first run)
        if start_daemon(wait_ready=True, timeout=180.0):
            resp = daemon_request({"cmd": "transcribe", "audio": str(wav_path)}, timeout=300.0)
            if resp is not None:
                return resp
            log("Daemon transcription returned None; falling back to one-shot worker.")

    proc = subprocess.run(
        [str(VENV_PYTHON), str(WORKER_SCRIPT), "--once", str(wav_path)],
        env=build_worker_env(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = proc.stdout.strip().splitlines()
    if out:
        try:
            return json.loads(out[-1])
        except Exception:
            pass
    err = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
    return {"ok": False, "error": err[-300:]}


def start_recording(cfg: dict) -> int:
    if not VENV_PYTHON.exists():
        notify(
            L({
                "es": "Whisper no instalado",
                "en": "Whisper not installed",
                "pt": "Whisper não instalado",
                "fr": "Whisper non installé",
                "ru": "Whisper не установлен",
            }),
            L({
                "es": "Ejecuta ~/dotfiles/scripts/setup_whisper.sh o instálalo desde Super+Alt+Espacio.",
                "en": "Run ~/dotfiles/scripts/setup_whisper.sh or install it from Super+Alt+Space.",
                "pt": "Execute ~/dotfiles/scripts/setup_whisper.sh ou instale via Super+Alt+Espaço.",
                "fr": "Lancez ~/dotfiles/scripts/setup_whisper.sh ou installez via Super+Alt+Espace.",
                "ru": "Запустите ~/dotfiles/scripts/setup_whisper.sh или установите через Super+Alt+Space.",
            }),
            icon="dialog-warning",
            urgency="critical",
            timeout_ms=6000,
        )
        return 1

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_wav = tempfile.mkstemp(prefix="whisper_rec_", suffix=".wav", dir=str(RUNTIME_DIR))
    os.close(fd)
    wav_path = Path(tmp_wav)

    cmd = build_record_command(wav_path)
    if not cmd:
        wav_path.unlink(missing_ok=True)
        notify(
            "Whisper",
            L({
                "es": "No se encontró pw-record, parecord ni ffmpeg.",
                "en": "Neither pw-record, parecord, nor ffmpeg was found.",
                "pt": "pw-record, parecord ou ffmpeg não encontrado.",
                "fr": "Aucun enregistreur audio trouvé (pw-record/parecord/ffmpeg).",
                "ru": "Не найден pw-record, parecord или ffmpeg.",
            }),
            icon="dialog-error",
            urgency="critical",
        )
        return 1

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    state = {
        "pid": proc.pid,
        "wav": str(wav_path),
        "started_at": time.time(),
    }
    RECORDING_STATE.write_text(json.dumps(state), encoding="utf-8")
    log(f"Started recording pid={proc.pid} wav={wav_path}")

    # Pre-warm the daemon in background while user is speaking so transcription is instant on stop
    if cfg.get("mode", "hybrid") in ("hybrid", "instant"):
        start_daemon(wait_ready=False)

    notify(
        L({
            "es": "󰍬 Grabando audio...",
            "en": "󰍬 Recording audio...",
            "pt": "󰍬 Gravando áudio...",
            "fr": "󰍬 Enregistrement audio...",
            "ru": "󰍬 Запись аудио...",
        }),
        L({
            "es": "Presiona Super + Shift + A para detener y transcribir",
            "en": "Press Super + Shift + A to stop and transcribe",
            "pt": "Pressione Super + Shift + A para parar e transcrever",
            "fr": "Appuyez sur Super + Shift + A pour arrêter et transcrire",
            "ru": "Нажмите Super + Shift + A для остановки и расшифровки",
        }),
        icon="audio-input-microphone",
        timeout_ms=120000,
    )
    return 0


def stop_and_transcribe(state: dict, cfg: dict) -> int:
    pid = int(state.get("pid", 0))
    wav_path = Path(state.get("wav", ""))

    # Clear recording state first so a second shortcut press doesn't get stuck
    RECORDING_STATE.unlink(missing_ok=True)

    if pid > 0 and pid_alive(pid):
        try:
            os.kill(pid, signal.SIGINT)
        except OSError:
            pass
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and pid_alive(pid):
            time.sleep(0.05)
        if pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            time.sleep(0.1)

    log(f"Stopped recording pid={pid} wav_size={wav_path.stat().st_size if wav_path.exists() else 0}")

    if not wav_path.exists() or wav_path.stat().st_size <= 256:
        wav_path.unlink(missing_ok=True)
        notify(
            L({
                "es": "Dictado Whisper",
                "en": "Whisper Dictation",
                "pt": "Ditado Whisper",
                "fr": "Dictée Whisper",
                "ru": "Диктовка Whisper",
            }),
            L({
                "es": "Grabación demasiado corta o vacía.",
                "en": "Recording too short or empty.",
                "pt": "Gravação muito curta ou vazia.",
                "fr": "Enregistrement trop court ou vide.",
                "ru": "Запись слишком короткая или пустая.",
            }),
            icon="dialog-warning",
        )
        return 0

    model_label = cfg.get("model", "large-v3-turbo")
    notify(
        L({
            "es": "󰍬 Transcribiendo...",
            "en": "󰍬 Transcribing...",
            "pt": "󰍬 Transcrevendo...",
            "fr": "󰍬 Transcription en cours...",
            "ru": "󰍬 Расшифровка...",
        }),
        f"Whisper ({model_label})",
        icon="audio-input-microphone",
        timeout_ms=60000,
    )

    try:
        result = transcribe_wav(wav_path, cfg)
    finally:
        wav_path.unlink(missing_ok=True)

    if not result.get("ok"):
        err = str(result.get("error", "Unknown error"))
        log(f"Transcription failed: {err}")
        notify(
            L({
                "es": "Error en Whisper",
                "en": "Whisper Error",
                "pt": "Erro no Whisper",
                "fr": "Erreur Whisper",
                "ru": "Ошибка Whisper",
            }),
            err[:180],
            icon="dialog-error",
            urgency="critical",
            timeout_ms=6000,
        )
        return 1

    text = str(result.get("text", "")).strip()
    if not text:
        notify(
            L({
                "es": "Dictado Whisper",
                "en": "Whisper Dictation",
                "pt": "Ditado Whisper",
                "fr": "Dictée Whisper",
                "ru": "Диктовка Whisper",
            }),
            L({
                "es": "No se detectó voz en el audio.",
                "en": "No speech detected in audio.",
                "pt": "Nenhuma fala detectada no áudio.",
                "fr": "Aucune voix détectée dans l'audio.",
                "ru": "Речь в аудио не обнаружена.",
            }),
            icon="dialog-information",
        )
        return 0

    copied = copy_to_clipboard(text)
    if copied and cfg.get("post_action") == "copy_paste":
        auto_paste()

    lang_code = str(result.get("language", "")).upper()
    elapsed = result.get("elapsed", 0)
    dev_tag = "GPU" if result.get("device") == "cuda" else "CPU"
    meta_parts = [p for p in (lang_code, f"{elapsed}s", dev_tag) if p]
    meta = " · ".join(meta_parts)

    preview = text if len(text) <= 140 else text[:137] + "..."
    title_base = L({
        "es": "Copiado y pegado" if cfg.get("post_action") == "copy_paste" else "Copiado al portapapeles",
        "en": "Copied and pasted" if cfg.get("post_action") == "copy_paste" else "Copied to clipboard",
        "pt": "Copiado e colado" if cfg.get("post_action") == "copy_paste" else "Copiado para a área de transferência",
        "fr": "Copié et collé" if cfg.get("post_action") == "copy_paste" else "Copié dans le presse-papiers",
        "ru": "Скопировано и вставлено" if cfg.get("post_action") == "copy_paste" else "Скопировано в буфер обмена",
    })
    notify(f"󰍬 {title_base} ({meta})", preview, icon="edit-paste", timeout_ms=4500)
    return 0


def handle_toggle() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w", encoding="utf-8") as lf:
        try:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Toggle ignored: another whisper_dictate invocation is busy.")
            return 0

        cfg = load_config()
        state = read_recording_state()
        if state is None:
            return start_recording(cfg)

        # Spawn transcription in the same locked turn? Release lock only after stopping recording
        # so transcription doesn't block user from seeing clean state, or keep lock to avoid overlap.
        return stop_and_transcribe(state, cfg)


def handle_apply_config() -> int:
    cfg = load_config()
    mode = str(cfg.get("mode", "hybrid"))
    st = daemon_status()

    if mode == "cold":
        if st.get("running"):
            stop_daemon()
        return 0

    if mode == "instant":
        if st.get("running") and not st.get("starting"):
            # Ask daemon to reload new model/device in background
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--daemon-reload"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        else:
            start_daemon(wait_ready=False)
        return 0

    # Hybrid mode: if daemon is running with old model/device, stop it cleanly so
    # it loads the new configuration on next dictation without waking GPU unnecessarily.
    if st.get("running"):
        if st.get("model") != cfg.get("model") or (
            cfg.get("device") in ("cuda", "cpu") and st.get("device") != cfg.get("device")
        ):
            stop_daemon()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Whisper voice dictation controller")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--toggle", action="store_true", help="Toggle recording / transcription")
    group.add_argument("--daemon-start", action="store_true", help="Start background daemon")
    group.add_argument("--daemon-stop", action="store_true", help="Stop background daemon")
    group.add_argument("--daemon-reload", action="store_true", help="Reload model in running daemon")
    group.add_argument("--daemon-status", action="store_true", help="Print daemon status JSON")
    group.add_argument("--apply-config", action="store_true", help="Apply whisper.json changes to daemon")
    group.add_argument("--startup", action="store_true", help="Session startup hook (preloads only in instant mode)")
    group.add_argument("--transcribe-file", metavar="WAV", help="Transcribe a WAV file directly (for testing)")
    args = parser.parse_args()

    if args.toggle:
        return handle_toggle()
    if args.daemon_start:
        return 0 if start_daemon(wait_ready=False) else 1
    if args.daemon_stop:
        stop_daemon()
        return 0
    if args.daemon_reload:
        resp = daemon_request({"cmd": "reload"}, timeout=180.0)
        if not resp or not resp.get("ok"):
            stop_daemon()
            start_daemon(wait_ready=False)
        return 0
    if args.daemon_status:
        print(json.dumps(daemon_status()))
        return 0
    if args.apply_config:
        return handle_apply_config()
    if args.startup:
        cfg = load_config()
        if cfg.get("mode") == "instant" and VENV_PYTHON.exists():
            start_daemon(wait_ready=False)
        return 0
    if args.transcribe_file:
        cfg = load_config()
        res = transcribe_wav(Path(args.transcribe_file), cfg)
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res.get("ok") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
