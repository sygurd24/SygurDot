#!/bin/bash

umask 077

if [ -f "$HOME/.config/dotfiles/timezone" ]; then
    export TZ=$(cat "$HOME/.config/dotfiles/timezone")
fi

# Lock screen using i3lock-color with Tokyo Night / Turquoise theme
# Falls back to standard i3lock if i3lock-color is not installed

# Ensure DISPLAY is set (crucial for xss-lock/lid close events)
export DISPLAY="${DISPLAY:-:0}"

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
LOCK_FILE="$RUNTIME_DIR/lock.sh.lock"
LOG_FILE="$RUNTIME_DIR/lock_debug.log"
MODE_FILE="$HOME/.config/dotfiles/lockscreen_mode"

# Single-instance guard: never kill an active lockscreen or run concurrent instances
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    exit 0
fi
if pgrep -u "$EUID" -x i3lock >/dev/null 2>&1; then
    exit 0
fi

# Lockscreen background mode: "wallpaper" (default) or "screen"
LOCK_MODE="wallpaper"
if [ -f "$MODE_FILE" ]; then
    RAW_MODE=$(tr -d '[:space:]' < "$MODE_FILE")
    if [ "$RAW_MODE" = "screen" ] || [ "$RAW_MODE" = "wallpaper" ]; then
        LOCK_MODE="$RAW_MODE"
    fi
fi

# Colors (Tokyo Night palette / Dynamic)
BG="1a1b26"
FG="c0caf5"
OUTLINE="1a1b26"
BLUE="7aa2f7"
CYAN="7dcfff"
MAGENTA="bb9af7"
PINK="f7768e"
GREY="565f89"
TRANSPARENT="00000000"

# Language detection
if [ -f "$HOME/.config/dotfiles/language" ]; then
    LANGUAGE=$(cat "$HOME/.config/dotfiles/language")
else
    LANGUAGE=$(echo "$LANG" | cut -c1-2)
fi

if [ "$LANGUAGE" == "es" ]; then
    VERIF_TEXT="Verificando..."
    WRONG_TEXT="Error"
    export LC_TIME="es_ES.UTF-8"
else
    VERIF_TEXT="Verifying..."
    WRONG_TEXT="Wrong"
    export LC_TIME="en_US.UTF-8"
fi

# Check if local IR facial unlock is active, enrolled, & installed in PAM
FACE_AUTH_ACTIVE=0
FACE_AUTH_ENABLED_FILE="$HOME/.config/dotfiles/face_auth_enabled"
if [ -S "/run/face-auth/face-auth.sock" ] && \
   [ -f "/run/face-auth/enrolled" ] && \
   [ -f /etc/pam.d/i3lock ] && \
   grep -q "pam_face_auth.so" /etc/pam.d/i3lock 2>/dev/null; then
    if [ ! -f "$FACE_AUTH_ENABLED_FILE" ] || [ "$(tr -d '[:space:]' < "$FACE_AUTH_ENABLED_FILE")" != "off" ]; then
        FACE_AUTH_ACTIVE=1
        if [ "$LANGUAGE" == "es" ]; then
            VERIF_TEXT="Escaneando..."
        else
            VERIF_TEXT="Scanning..."
        fi
    fi
fi

TMP_IMG=""
PAUSED_DUNST=0

cleanup() {
    if [ -n "$TMP_IMG" ] && [ -f "$TMP_IMG" ]; then
        rm -f "$TMP_IMG"
    fi
    if [ "$PAUSED_DUNST" -eq 1 ] && command -v dunstctl >/dev/null 2>&1; then
        dunstctl set-paused false 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Rotate debug log if it gets large (> 500 lines)
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)" -gt 500 ]; then
    tail -n 200 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv -f "${LOG_FILE}.tmp" "$LOG_FILE"
fi

# Debug logging (private log file in $XDG_RUNTIME_DIR)
exec 2>> "$LOG_FILE"

capture_blurred_screen() {
    TMP_IMG=$(mktemp "$RUNTIME_DIR/screen_locked.XXXXXX.png")
    if ! maim "$TMP_IMG"; then
        rm -f "$TMP_IMG"
        TMP_IMG=""
        return 1
    fi
    # Frosted Glass effect: scale down -> blur -> scale up -> subtle dimming
    if ! magick "$TMP_IMG" \
        -resize 25% \
        -filter Gaussian -blur 0x4 \
        -resize 400% \
        -fill black -colorize 25% \
        "$TMP_IMG"; then
        rm -f "$TMP_IMG"
        TMP_IMG=""
        return 1
    fi
    img="$TMP_IMG"
    # Adjust clock colors based on actual blurred screenshot brightness
    local brightness
    brightness=$(magick "$TMP_IMG" -colorspace Gray -format "%[fx:int(mean*100)]" info: 2>/dev/null || echo "0")
    if [ "${brightness:-0}" -gt 65 ] 2>/dev/null; then
        FG="333333"
        OUTLINE="ffffff"
        BLUE="1a1b26"
    else
        FG="c0caf5"
        OUTLINE="1a1b26"
        BLUE="7aa2f7"
    fi
    return 0
}

use_static_fallback() {
    img="$HOME/Pictures/Wallpapers/pantallabloqueo_debian.png"
    [ ! -s "$img" ] && img="" # If even this fails, use solid color
    FG="c0caf5"
    OUTLINE="1a1b26"
    BLUE="7aa2f7"
}

img=""
if [ "$LOCK_MODE" = "screen" ]; then
    if ! capture_blurred_screen; then
        echo "Screen capture failed in screen mode, trying blurred wallpaper fallback" >> "$LOG_FILE"
        if [ -s "/tmp/current_wallpaper_blurred.png" ]; then
            img="/tmp/current_wallpaper_blurred.png"
            FG=$(cat /tmp/lock_foreground_color 2>/dev/null || echo "c0caf5")
            OUTLINE=$(cat /tmp/lock_outline_color 2>/dev/null || echo "1a1b26")
            [ "$FG" = "333333" ] && BLUE="1a1b26" || BLUE="7aa2f7"
        else
            use_static_fallback
        fi
    fi
else
    # Wallpaper mode (default): use pre-generated blurred wallpaper
    if [ -s "/tmp/current_wallpaper_blurred.png" ]; then
        img="/tmp/current_wallpaper_blurred.png"
        FG=$(cat /tmp/lock_foreground_color 2>/dev/null || echo "c0caf5")
        OUTLINE=$(cat /tmp/lock_outline_color 2>/dev/null || echo "1a1b26")
        [ "$FG" = "333333" ] && BLUE="1a1b26" || BLUE="7aa2f7"
    else
        echo "Pre-generated blurred wallpaper missing, falling back to screen capture" >> "$LOG_FILE"
        if ! capture_blurred_screen; then
            echo "Capture failed, falling back to static wallpaper" >> "$LOG_FILE"
            use_static_fallback
        fi
    fi
fi

# Binary path (prefer i3lock-color if installed)
I3LOCK_BIN="i3lock"
if [ -x "/usr/local/bin/i3lock" ]; then
    I3LOCK_BIN="/usr/local/bin/i3lock"
fi

echo "--- Lock attempt at $(date) ---" >> "$LOG_FILE"
echo "Mode: $LOCK_MODE" >> "$LOG_FILE"
echo "Binary: $I3LOCK_BIN" >> "$LOG_FILE"
echo "Image: ${img:-<solid color>}" >> "$LOG_FILE"
[ -n "$img" ] && [ -s "$img" ] && echo "Image exists" >> "$LOG_FILE" || echo "Image MISSING (using solid color)" >> "$LOG_FILE"

# Pause notifications while locked so private alerts don't appear over the lockscreen
if command -v dunstctl >/dev/null 2>&1; then
    if [ "$(dunstctl is-paused 2>/dev/null)" = "false" ]; then
        dunstctl set-paused true 2>/dev/null && PAUSED_DUNST=1
    fi
fi

# Build i3lock arguments safely
I3LOCK_ARGS=()
USE_COLOR=0
if "$I3LOCK_BIN" --version 2>&1 | grep -qE "color|Raymond Li|Cassandra Fox"; then
    USE_COLOR=1
    echo "Using i3lock-color logic" >> "$LOG_FILE"
    if [ -n "$img" ] && [ -s "$img" ]; then
        I3LOCK_ARGS+=(--image="$img")
    fi
    if [ "$FACE_AUTH_ACTIVE" -eq 0 ]; then
        I3LOCK_ARGS+=(--ignore-empty-password)
    fi
    I3LOCK_ARGS+=(
        --color="${BG}"
        --clock
        --indicator
        --radius=140
        --ring-width=8
        --inside-color="${TRANSPARENT}"
        --ring-color="${TRANSPARENT}"
        --line-uses-inside
        --separator-color="${TRANSPARENT}"
        --keyhl-color="${MAGENTA}ff"
        --bshl-color="${PINK}ff"
        --insidever-color="${TRANSPARENT}"
        --ringver-color="${BLUE}ff"
        --verif-color="${FG}ff"
        --verif-text="${VERIF_TEXT}"
        --insidewrong-color="${TRANSPARENT}"
        --ringwrong-color="${PINK}ff"
        --wrong-color="${PINK}ff"
        --wrong-text="${WRONG_TEXT}"
        --noinput-text=""
        --lock-text=""
        --lockfailed-text=""
        --time-color="${FG}ff"
        --time-font="JetBrainsMono Nerd Font"
        --time-size=80
        --time-str="%H:%M"
        --timeoutline-color="${OUTLINE}ff"
        --timeoutline-width=2
        --date-color="${BLUE}bb"
        --date-font="JetBrainsMono Nerd Font"
        --date-size=20
        --date-str="%A, %d %B"
        --dateoutline-color="${OUTLINE}88"
        --dateoutline-width=1
        --pass-media-keys
        --pass-volume-keys
    )
else
    # Fallback: standard i3lock
    I3LOCK_ARGS+=(-e -c "${BG}")
    if [ -n "$img" ] && [ -s "$img" ]; then
        I3LOCK_ARGS+=(-i "$img")
    fi
fi

# Handle xss-lock --transfer-sleep-lock properly so systemd waits until i3lock paints
if [[ -e /dev/fd/${XSS_SLEEP_LOCK_FD:--1} ]]; then
    kill_i3lock() {
        pkill -xu "$EUID" "$@" i3lock
    }
    trap 'kill_i3lock; exit 0' TERM INT

    # Start i3lock in forking mode without inheriting the sleep lock or flock FDs
    "$I3LOCK_BIN" "${I3LOCK_ARGS[@]}" 9>&- {XSS_SLEEP_LOCK_FD}<&-

    # Close our copy of the sleep lock FD to let suspend/hibernate proceed now that screen is locked
    exec {XSS_SLEEP_LOCK_FD}<&-

    while kill_i3lock -0 2>/dev/null; do
        sleep 0.5
    done
else
    if [ "$USE_COLOR" -eq 1 ]; then
        NOFORK_FLAG="--nofork"
    else
        NOFORK_FLAG="-n"
    fi
    "$I3LOCK_BIN" "$NOFORK_FLAG" "${I3LOCK_ARGS[@]}" 9>&- &
    LOCK_PID=$!
    trap 'kill "$LOCK_PID" 2>/dev/null' TERM INT
    wait "$LOCK_PID"
fi
