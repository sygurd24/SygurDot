#!/bin/bash
set -euo pipefail

# Reliable selection screenshot -> validated PNG -> deadlock-free X11 clipboard.
# Fixes:
#   1. Uses a temp file + PNG validation so cancelled/failed captures never write
#      0-byte corrupt image/png entries to the clipboard.
#   2. Uses `maim -o` (--noopengl) to avoid OpenGL/slop corruption over picom on
#      hybrid AMD+NVIDIA setups.
#   3. Uses flock so rapid double-presses cannot spawn overlapping slop pointer grabs.
#   4. Copies via GTK3 clipboard_image.py to avoid xclip 0.13 X11 INCR deadlocks
#      with greenclip and browsers/Electron apps.

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
LOCK_FILE="$RUNTIME_DIR/screenshot_copy.lock"
CLIP_HELPER="$HOME/.config/bspwm/scripts/clipboard_image.py"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    exit 0
fi

TMP_PNG="$(mktemp "$RUNTIME_DIR/screenshot_XXXXXX.png")"
cleanup() {
    rm -f "$TMP_PNG"
}
trap cleanup EXIT

# Brief delay so Super+Shift+S key release doesn't cancel slop
sleep 0.2

# Capture selected region (-s), hide cursor (-u), disable OpenGL shader (-o)
if ! maim -s -u -o --quiet "$TMP_PNG" 2>/dev/null; then
    # User cancelled (Esc / right-click) — do NOT touch the clipboard
    exit 0
fi

# Release the slop concurrency lock now that maim has finished
exec 9>&-

# Verify non-empty valid PNG before touching clipboard
if [ ! -s "$TMP_PNG" ] || [ "$(stat -c%s "$TMP_PNG")" -lt 67 ]; then
    notify-send "Screenshot" "Capture failed (empty image)" -u critical -t 2500
    exit 1
fi

if [ -x "$CLIP_HELPER" ] && "$CLIP_HELPER" "$TMP_PNG" 9>&-; then
    notify-send "Screenshot" "Copied to clipboard!" -i camera-photo -t 2000
else
    # Fallback to xclip from file (never piping empty/unvalidated data)
    pkill -f "xclip -selection clipboard -t image/png" 2>/dev/null || true
    if xclip -selection clipboard -t image/png -i "$TMP_PNG" </dev/null >/dev/null 2>&1 9>&-; then
        notify-send "Screenshot" "Copied to clipboard!" -i camera-photo -t 2000
    else
        notify-send "Screenshot" "Failed to copy to clipboard" -u critical -t 2500
        exit 1
    fi
fi
