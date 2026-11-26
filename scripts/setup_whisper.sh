#!/bin/bash
set -euo pipefail

# Self-contained Whisper Dictation setup for SygurDot dotfiles.
# Designed to work out-of-the-box on a fresh Debian netinstall (with or without NVIDIA GPU).

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$HOME/.local/share/dotfiles-whisper/venv"
CONFIG_DIR="$HOME/.config/dotfiles"
CONFIG_FILE="$CONFIG_DIR/whisper.json"
WORKER_SCRIPT="$DOTFILES_DIR/config/bspwm/scripts/whisper_worker.py"

log()  { echo "[INFO] [whisper] $*"; }
warn() { echo "[WARN] [whisper] $*"; }

if [ "$EUID" -eq 0 ]; then
    echo "[ERROR] Run setup_whisper.sh as your normal user, not root."
    exit 1
fi

HAS_NVIDIA=0
if command -v lspci >/dev/null 2>&1 && lspci | grep -iE 'vga|3d|display' | grep -iq 'nvidia'; then
    HAS_NVIDIA=1
fi

DEFAULT_MODEL="small"
if [ "$HAS_NVIDIA" -eq 1 ]; then
    DEFAULT_MODEL="large-v3-turbo"
fi

# 1. Create / update isolated Python venv
mkdir -p "$(dirname "$VENV_DIR")"
if [ ! -x "$VENV_DIR/bin/python" ]; then
    log "Creating isolated Python virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

if ! getent hosts pypi.org >/dev/null 2>&1; then
    warn "Network/DNS unavailable for pypi.org. Skipping Python package installation."
    exit 0
fi

log "Installing faster-whisper..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet faster-whisper

if [ "$HAS_NVIDIA" -eq 1 ]; then
    log "NVIDIA GPU detected. Installing CUDA runtime libraries (cuBLAS + cuDNN)..."
    "$VENV_DIR/bin/pip" install --quiet nvidia-cublas-cu12 nvidia-cudnn-cu12 || \
        warn "Failed to install NVIDIA CUDA wheels; Whisper will fall back to CPU."
else
    log "No NVIDIA GPU detected. Configuring Whisper for CPU (int8)."
fi

# 2. Initialize ~/.config/dotfiles/whisper.json (only if absent)
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_FILE" ]; then
    log "Initializing default configuration ($CONFIG_FILE) with model=$DEFAULT_MODEL, mode=hybrid..."
    cat > "$CONFIG_FILE" <<EOF
{
  "model": "$DEFAULT_MODEL",
  "language": "auto",
  "mode": "hybrid",
  "idle_timeout": 300,
  "device": "auto",
  "post_action": "copy"
}
EOF
fi

# 3. Pre-download default model into local HuggingFace cache (non-fatal if offline)
MODEL_TO_FETCH=$(python3 -c '
import json, pathlib
p = pathlib.Path("'"$CONFIG_FILE"'")
try:
    print(json.loads(p.read_text()).get("model", "'"$DEFAULT_MODEL"'"))
except Exception:
    print("'"$DEFAULT_MODEL"'")
')

if [ -f "$WORKER_SCRIPT" ] && getent hosts huggingface.co >/dev/null 2>&1; then
    log "Pre-downloading Whisper model '$MODEL_TO_FETCH' (so first dictation is instant)..."
    if "$VENV_DIR/bin/python" "$WORKER_SCRIPT" --download "$MODEL_TO_FETCH" >/dev/null; then
        log "Model '$MODEL_TO_FETCH' cached and ready!"
    else
        warn "Model pre-download failed; it will download automatically on first use."
    fi
else
    warn "Skipping model pre-download (offline or worker missing); it will download on first use."
fi

log "Whisper dictation setup complete! Shortcut: Super + Shift + A | Settings: Super + Alt + Space"
