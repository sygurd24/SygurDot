#!/usr/bin/env python3
"""Faster-Whisper transcription worker and Unix-socket daemon.

Runs inside the isolated venv at ~/.local/share/dotfiles-whisper/venv with
NVIDIA CUDA library paths pre-populated by whisper_dictate.py.

Modes:
  --once <wav>        Load model, transcribe one file, print JSON, exit (cold mode).
  --daemon            Serve transcription requests over a Unix socket.
                      In 'hybrid' mode, exits cleanly after idle_timeout seconds
                      so NVIDIA releases the entire CUDA context (D3cold).
                      In 'instant' mode, stays resident until stopped.
  --download <model>  Pre-download a model into the local HuggingFace cache.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
import wave

import numpy as np

CONFIG_FILE = Path.home() / ".config/dotfiles/whisper.json"
LANG_FILE = Path.home() / ".config/dotfiles/language"
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/whisper-{os.getuid()}")
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

# Mapping from friendly model name to faster-whisper / HF repo id
MODEL_ALIASES = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large-v3-turbo": "large-v3-turbo",
    "large-v3": "large-v3",
}

# Classic Whisper silence/end-of-audio hallucination phrases (normalized: lowercase, no trailing punctuation)
HALLUCINATION_EXACT = {
    "thank you",
    "thank you very much",
    "thank you so much",
    "thanks",
    "thanks for watching",
    "thank you for watching",
    "thank you for listening",
    "please subscribe",
    "like and subscribe",
    "subscribe",
    "you",
    "bye",
    "bye bye",
    "gracias",
    "muchas gracias",
    "gracias por ver",
    "gracias por ver el video",
    "gracias por ver el vídeo",
    "gracias por escuchar",
    "gracias por acompañarnos",
    "suscríbete",
    "suscribete",
    "obrigado",
    "obrigado por assistir",
    "merci",
    "merci beaucoup",
    "merci d'avoir regardé",
}

HALLUCINATION_SUBSTRINGS = (
    "amara.org",
    "subtítulos realizados por",
    "subtitulos realizados por",
    "subtítulos por",
    "sous-titrage",
    "thanks for watching",
    "thank you for watching",
    "gracias por ver el video",
    "gracias por ver el vídeo",
)

_PUNCT_RE = re.compile(r"[^\w\s']", re.UNICODE)


def _normalize_phrase(text: str) -> str:
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return " ".join(cleaned.split())


def filter_hallucinated_segments(segments: list, audio: np.ndarray, sr: int = 16000) -> list[str]:
    """Filter out Whisper's phantom 'Thank you.' / YouTube outro hallucinations on trailing silence.

    Never modifies or trims the underlying audio; only removes known phantom segments.
    """
    if not segments:
        return []

    seg_rms: list[float] = []
    for seg in segments:
        i0 = max(0, int(seg.start * sr))
        i1 = min(audio.size, int(seg.end * sr))
        if i1 > i0:
            seg_rms.append(float(np.sqrt(np.mean(audio[i0:i1] ** 2))))
        else:
            seg_rms.append(0.0)

    speech_rms_ref = max(seg_rms) if seg_rms else 0.0
    kept: list[str] = []
    n = len(segments)

    for idx, seg in enumerate(segments):
        raw = (seg.text or "").strip()
        if not raw:
            continue
        norm = _normalize_phrase(raw)
        if not norm:
            continue

        no_speech = float(getattr(seg, "no_speech_prob", 0.0) or 0.0)
        avg_lp = float(getattr(seg, "avg_logprob", 0.0) or 0.0)
        rms = seg_rms[idx]
        is_trailing = idx == n - 1 or all(
            _normalize_phrase((s.text or "").strip()) in HALLUCINATION_EXACT
            for s in segments[idx:]
        )

        # 1. Explicit subtitle/YouTube outro hallucinations
        if any(sub in norm for sub in HALLUCINATION_SUBSTRINGS) and (avg_lp < -0.30 or no_speech >= 0.25 or is_trailing):
            log(f"Filtered outro hallucination: {raw!r} (no_speech={no_speech:.2f} avg_lp={avg_lp:.2f})")
            continue

        # 2. Repeated 'Thank you. Thank you. ...' hallucination loop
        words = norm.split()
        is_repeated_thanks = (
            (words.count("thank") >= 2 or words.count("thanks") >= 2 or words.count("gracias") >= 2)
            and all(w in ("thank", "you", "thanks", "gracias", "very", "much", "so") for w in words)
        )
        if is_repeated_thanks:
            log(f"Filtered repeated thanks hallucination: {raw!r}")
            continue

        # 3. Trailing phantom 'Thank you.' / 'Gracias.' tacked onto silence at end of audio
        if norm in HALLUCINATION_EXACT:
            quiet_relative = (n > 1 and speech_rms_ref > 0 and rms < speech_rms_ref * 0.45)
            low_conf = avg_lp < -0.45 or no_speech >= 0.30
            if is_trailing and (low_conf or quiet_relative or (len(kept) > 0 and avg_lp < -0.32)):
                log(
                    f"Filtered trailing phantom phrase: {raw!r} "
                    f"(no_speech={no_speech:.2f} avg_lp={avg_lp:.2f} rms={rms:.4f}/{speech_rms_ref:.4f})"
                )
                continue

        kept.append(raw)

    return kept


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [worker] {msg}\n")
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


def notify(title: str, body: str, icon: str = "audio-input-microphone", timeout_ms: int = 4000) -> None:
    dunstify = shutil.which("dunstify")
    if dunstify:
        cmd = [
            dunstify,
            "-a", "WhisperDictate",
            "-r", NOTIFY_REPLACE_ID,
            "-t", str(timeout_ms),
            "-i", icon,
            title,
            body,
        ]
    elif shutil.which("notify-send"):
        cmd = ["notify-send", "-t", str(timeout_ms), "-i", icon, title, body]
    else:
        return
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


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


def is_model_cached(model_name: str) -> bool:
    """Best-effort check if a faster-whisper model is already in HF cache."""
    hf_hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")) / "hub"
    if not hf_hub.exists():
        return False
    key = model_name.lower()
    suffixes = [f"-{key}"]
    if key == "large-v3-turbo":
        suffixes.append("-turbo")
    for d in hf_hub.glob("models--*whisper*"):
        name = d.name.lower()
        if any(name.endswith(suf) for suf in suffixes):
            snaps = d / "snapshots"
            if snaps.exists() and any((p / "model.bin").exists() for p in snaps.iterdir() if p.is_dir()):
                return True
    return False


def load_audio_float32(audio_path: str) -> np.ndarray:
    """Read a 16kHz mono PCM16 WAV into float32 [-1, 1] without PyAV."""
    p = Path(audio_path)
    if not p.exists() or p.stat().st_size <= 44:
        return np.zeros(0, dtype=np.float32)

    try:
        with wave.open(str(p), "rb") as wf:
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            sr = wf.getframerate()
            nframes = wf.getnframes()
            if ch == 1 and sw == 2 and sr == 16000 and nframes > 0:
                raw = wf.readframes(nframes)
                return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        pass

    # Fallback 1: ffmpeg to raw 16kHz mono s16le (handles any sample rate or unfinalized WAV header)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            proc = subprocess.run(
                [
                    ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-i", str(p), "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1",
                ],
                capture_output=True,
                timeout=15,
            )
            if proc.returncode == 0 and proc.stdout:
                usable = len(proc.stdout) - (len(proc.stdout) % 2)
                if usable > 0:
                    return np.frombuffer(proc.stdout[:usable], dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as exc:
            log(f"ffmpeg decode fallback error: {exc}")

    # Fallback 2: raw PCM16 payload after 44-byte WAV header
    data = p.read_bytes()
    if len(data) > 44:
        payload = data[44:]
        usable = len(payload) - (len(payload) % 2)
        if usable > 0:
            return np.frombuffer(payload[:usable], dtype=np.int16).astype(np.float32) / 32768.0
    return np.zeros(0, dtype=np.float32)


def resolve_device_and_compute(requested_device: str) -> list[tuple[str, str]]:
    """Return ordered list of (device, compute_type) candidates to try."""
    import ctranslate2

    cuda_available = False
    cuda_types: set[str] = set()
    if requested_device in ("auto", "cuda"):
        try:
            if ctranslate2.get_cuda_device_count() > 0:
                cuda_available = True
                cuda_types = set(ctranslate2.get_supported_compute_types("cuda"))
        except Exception as exc:
            log(f"CUDA probe failed: {exc}")

    candidates: list[tuple[str, str]] = []
    if requested_device in ("auto", "cuda") and cuda_available:
        for ct in ("float16", "int8_float16", "bfloat16", "float32"):
            if ct in cuda_types:
                candidates.append(("cuda", ct))
                break
        if not candidates:
            candidates.append(("cuda", "default"))

    if requested_device == "cpu" or requested_device == "auto" or not candidates:
        candidates.append(("cpu", "int8"))
        candidates.append(("cpu", "float32"))
    elif requested_device == "cuda":
        # Even if user forced cuda, keep cpu as emergency fallback if CUDA runtime fails
        candidates.append(("cpu", "int8"))

    return candidates


class WhisperEngine:
    def __init__(self) -> None:
        self.model = None
        self.loaded_model_name: str | None = None
        self.loaded_device: str | None = None
        self.loaded_compute: str | None = None
        self.requested_device: str | None = None

    def unload(self) -> None:
        if self.model is not None:
            log(f"Unloading model {self.loaded_model_name} ({self.loaded_device})")
            self.model = None
            self.loaded_model_name = None
            self.loaded_device = None
            self.loaded_compute = None
            self.requested_device = None
            gc.collect()

    def ensure_loaded(self, model_name: str, requested_device: str, notify_download: bool = True) -> None:
        resolved_name = MODEL_ALIASES.get(model_name, model_name)
        if (
            self.model is not None
            and self.loaded_model_name == resolved_name
            and self.requested_device == requested_device
        ):
            return

        self.unload()

        from faster_whisper import WhisperModel

        if notify_download and not is_model_cached(resolved_name):
            title = L({
                "es": "Dictado Whisper",
                "en": "Whisper Dictation",
                "pt": "Ditado Whisper",
                "fr": "Dictée Whisper",
                "ru": "Диктовка Whisper",
            })
            body = L({
                "es": f"Descargando modelo '{resolved_name}' (primera vez)...",
                "en": f"Downloading model '{resolved_name}' (first time)...",
                "pt": f"Baixando modelo '{resolved_name}' (primeira vez)...",
                "fr": f"Téléchargement du modèle « {resolved_name} » (première fois)...",
                "ru": f"Загрузка модели «{resolved_name}» (первый раз)...",
            })
            notify(title, body, icon="folder-download", timeout_ms=15000)

        candidates = resolve_device_and_compute(requested_device)
        last_err: Exception | None = None
        t0 = time.monotonic()

        for dev, compute in candidates:
            try:
                log(f"Loading model='{resolved_name}' device={dev} compute_type={compute}")
                kwargs: dict = {"device": dev, "compute_type": compute}
                if dev == "cpu":
                    kwargs["cpu_threads"] = max(2, min(8, (os.cpu_count() or 4)))
                self.model = WhisperModel(resolved_name, **kwargs)
                self.loaded_model_name = resolved_name
                self.loaded_device = dev
                self.loaded_compute = compute
                self.requested_device = requested_device
                log(f"Loaded '{resolved_name}' on {dev}/{compute} in {time.monotonic() - t0:.2f}s")
                return
            except Exception as exc:
                last_err = exc
                log(f"Failed loading on {dev}/{compute}: {exc}")

        raise RuntimeError(f"Could not load Whisper model '{resolved_name}': {last_err}")

    def transcribe(self, audio_path: str, cfg: dict) -> dict:
        t0 = time.monotonic()
        model_name = str(cfg.get("model", DEFAULT_CONFIG["model"]))
        device_req = str(cfg.get("device", DEFAULT_CONFIG["device"]))
        language = cfg.get("language", "auto")
        if not language or language == "auto":
            language = None

        self.ensure_loaded(model_name, device_req)

        audio = load_audio_float32(audio_path)
        if audio.size < 1600:  # < 0.1s
            return {
                "ok": True,
                "text": "",
                "language": "",
                "device": self.loaded_device,
                "model": self.loaded_model_name,
                "elapsed": round(time.monotonic() - t0, 2),
            }

        t_infer = time.monotonic()
        # When language is Auto, enable per-segment language detection (multilingual=True)
        # and disable cross-segment text conditioning so speaking English mid-recording
        # does not force subsequent Spanish segments to be translated into English
        # (and prevents end-of-audio "Thank you Thank you..." hallucination loops).
        is_auto_lang = language is None
        transcribe_kwargs = {
            "language": language,
            "task": "transcribe",
            "beam_size": 5,
            "multilingual": is_auto_lang,
            "vad_filter": False,
            "no_speech_threshold": 0.5,
            "condition_on_previous_text": not is_auto_lang,
        }

        try:
            segments_iter, info = self.model.transcribe(audio, **transcribe_kwargs)
            segments_list = list(segments_iter)
            parts = filter_hallucinated_segments(segments_list, audio, sr=16000)
            text = " ".join(parts).strip()
        except Exception as exc:
            # If CUDA failed mid-inference (e.g., OOM or cublas/cudnn error), retry once on CPU
            if self.loaded_device == "cuda":
                log(f"CUDA inference error ({exc}), falling back to CPU...")
                self.ensure_loaded(model_name, "cpu", notify_download=False)
                segments_iter, info = self.model.transcribe(audio, **transcribe_kwargs)
                segments_list = list(segments_iter)
                parts = filter_hallucinated_segments(segments_list, audio, sr=16000)
                text = " ".join(parts).strip()
            else:
                raise

        elapsed_infer = round(time.monotonic() - t_infer, 2)
        elapsed_total = round(time.monotonic() - t0, 2)
        detected_lang = getattr(info, "language", "") or ""
        log(
            f"Transcribed ({self.loaded_model_name}@{self.loaded_device}): "
            f"lang={detected_lang} infer={elapsed_infer}s total={elapsed_total}s chars={len(text)}"
        )
        return {
            "ok": True,
            "text": text,
            "language": detected_lang,
            "device": self.loaded_device,
            "model": self.loaded_model_name,
            "elapsed": elapsed_infer,
            "total_elapsed": elapsed_total,
        }


def run_once(audio_path: str) -> int:
    cfg = load_config()
    engine = WhisperEngine()
    try:
        res = engine.transcribe(audio_path, cfg)
        print(json.dumps(res, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        log(f"run_once error: {exc}\n{traceback.format_exc()}")
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1
    finally:
        engine.unload()


def run_download(model_name: str) -> int:
    resolved_name = MODEL_ALIASES.get(model_name, model_name)
    try:
        from faster_whisper import download_model

        path = download_model(resolved_name)
        print(json.dumps({"ok": True, "model": resolved_name, "path": str(path)}))
        return 0
    except Exception as exc:
        log(f"download error: {exc}")
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


def run_daemon(preload: bool = True) -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if SOCKET_PATH.exists():
        try:
            SOCKET_PATH.unlink()
        except OSError:
            pass

    DAEMON_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(SOCKET_PATH))
    os.chmod(SOCKET_PATH, 0o600)
    srv.listen(8)
    srv.settimeout(2.0)

    running = True

    def handle_sig(signum, _frame):
        nonlocal running
        log(f"Daemon received signal {signum}, shutting down.")
        running = False

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    engine = WhisperEngine()
    last_activity = time.monotonic()
    log(f"Daemon started (pid={os.getpid()}, preload={preload})")

    # Preload model right away so it's warm while user is speaking (or in instant mode)
    if preload:
        try:
            cfg = load_config()
            engine.ensure_loaded(str(cfg.get("model", "large-v3-turbo")), str(cfg.get("device", "auto")))
            last_activity = time.monotonic()
        except Exception as exc:
            log(f"Initial preload failed (will retry on request): {exc}")

    try:
        while running:
            cfg = load_config()
            mode = str(cfg.get("mode", "hybrid"))
            idle_timeout = int(cfg.get("idle_timeout", 300))

            if mode == "cold":
                log("Config switched to cold mode; exiting daemon.")
                break

            if mode == "hybrid" and idle_timeout > 0:
                if (time.monotonic() - last_activity) >= idle_timeout:
                    log(f"Idle timeout ({idle_timeout}s) reached in hybrid mode; exiting to release GPU/RAM.")
                    break

            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                conn.settimeout(600.0)
                raw = b""
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    raw += chunk
                    if b"\n" in raw:
                        break

                req = json.loads(raw.decode("utf-8").strip() or "{}")
                cmd = req.get("cmd", "")
                resp: dict = {"ok": False, "error": f"unknown cmd: {cmd}"}

                if cmd == "ping":
                    resp = {
                        "ok": True,
                        "pid": os.getpid(),
                        "model": engine.loaded_model_name,
                        "device": engine.loaded_device,
                        "mode": mode,
                        "idle_seconds": int(time.monotonic() - last_activity),
                    }
                elif cmd == "transcribe":
                    last_activity = time.monotonic()
                    audio_path = str(req.get("audio", ""))
                    resp = engine.transcribe(audio_path, load_config())
                    last_activity = time.monotonic()
                elif cmd == "reload":
                    last_activity = time.monotonic()
                    new_cfg = load_config()
                    if new_cfg.get("mode") == "cold":
                        resp = {"ok": True, "action": "exiting"}
                        running = False
                    else:
                        engine.ensure_loaded(
                            str(new_cfg.get("model", "large-v3-turbo")),
                            str(new_cfg.get("device", "auto")),
                        )
                        resp = {
                            "ok": True,
                            "model": engine.loaded_model_name,
                            "device": engine.loaded_device,
                        }
                        last_activity = time.monotonic()
                elif cmd == "shutdown":
                    resp = {"ok": True, "action": "shutdown"}
                    running = False

                conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
            except Exception as exc:
                log(f"Request error: {exc}\n{traceback.format_exc()}")
                try:
                    conn.sendall(
                        (json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) + "\n").encode("utf-8")
                    )
                except OSError:
                    pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
    finally:
        engine.unload()
        try:
            srv.close()
        except OSError:
            pass
        for path in (SOCKET_PATH, DAEMON_PID_FILE):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        log("Daemon exited cleanly.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Whisper transcription worker / daemon")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", metavar="WAV_PATH", help="Transcribe one WAV file and exit")
    group.add_argument("--daemon", action="store_true", help="Run Unix socket transcription daemon")
    group.add_argument("--download", metavar="MODEL", help="Pre-download a Whisper model")
    parser.add_argument("--no-preload", action="store_true", help="Do not preload model at daemon startup")
    args = parser.parse_args()

    if args.once:
        return run_once(args.once)
    if args.download:
        return run_download(args.download)
    return run_daemon(preload=not args.no_preload)


if __name__ == "__main__":
    sys.exit(main())
