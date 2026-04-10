#!/bin/bash

# Lock screen using i3lock-color with Tokyo Night / Turquoise theme
# Falls back to standard i3lock if i3lock-color is not installed

# Colors (Tokyo Night palette / Dynamic)
BG="1a1b26"
FG=$(cat /tmp/lock_foreground_color 2>/dev/null || echo "c0caf5")
OUTLINE=$(cat /tmp/lock_outline_color 2>/dev/null || echo "1a1b26")
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

# Adjust blue for date font based on FG brightness for extra readability
if [ "$FG" = "333333" ]; then
    BLUE="1a1b26" # Darker blue for light BG
else
    BLUE="7aa2f7" # Tokyo blue for dark BG
fi

# Ensure DISPLAY is set (crucial for xss-lock/lid close events)
export DISPLAY="${DISPLAY:-:0}"

# 1. Try pre-generated blurred wallpaper (fastest)
img="/tmp/current_wallpaper_blurred.png"

if [ ! -f "$img" ]; then
    # 2. Try to capture current screen and blur if pre-generated is missing
    img="/tmp/screen_locked.png"
    if ! maim "$img"; then
        echo "Capture failed, falling back to static wallpaper" >> /tmp/lock_debug.log
        # 3. Fallback to static wallpaper
        img="$HOME/Pictures/Wallpapers/pantallabloque_debian.png"
        [ ! -f "$img" ] && img="" # If even this fails, we'll use a solid color
    else
        # Frosted Glass effect: scale down -> blur -> scale up -> subtle dimming
        magick "$img" \
            -resize 25% \
            -filter Gaussian -blur 0x4 \
            -resize 400% \
            -fill black -colorize 25% \
            "$img"
    fi
fi

# Binary path (prefer i3lock-color if installed)
I3LOCK_BIN="i3lock"
if [ -x "/usr/local/bin/i3lock" ]; then
    I3LOCK_BIN="/usr/local/bin/i3lock"
fi

# Debug logging
exec 2>> /tmp/lock_debug.log
echo "--- Lock attempt at $(date) ---" >> /tmp/lock_debug.log
echo "Binary: $I3LOCK_BIN" >> /tmp/lock_debug.log
echo "Image: $img" >> /tmp/lock_debug.log
[ -f "$img" ] && echo "Image exists" >> /tmp/lock_debug.log || echo "Image MISSING" >> /tmp/lock_debug.log

# Ensure no other instances are running
killall -q i3lock
sleep 0.2

if $I3LOCK_BIN --version 2>&1 | grep -qE "color|Raymond Li|Cassandra Fox"; then
    echo "Using i3lock-color logic" >> /tmp/lock_debug.log
    # i3lock-color: truly minimal rice
    # Use --color as a safety net if image fails
    $I3LOCK_BIN \
        --nofork \
        --image="$img" \
        --color="${BG}" \
        --clock \
        --indicator \
        --radius=140 \
        --ring-width=8 \
        \
        --inside-color="${TRANSPARENT}" \
        --ring-color="${TRANSPARENT}" \
        --line-uses-inside \
        --separator-color="${TRANSPARENT}" \
        --keyhl-color="${MAGENTA}ff" \
        --bshl-color="${PINK}ff" \
        \
        --insidever-color="${TRANSPARENT}" \
        --ringver-color="${BLUE}ff" \
        --verif-color="${FG}ff" \
        --verif-text="${VERIF_TEXT}" \
        \
        --insidewrong-color="${TRANSPARENT}" \
        --ringwrong-color="${PINK}ff" \
        --wrong-color="${PINK}ff" \
        --wrong-text="${WRONG_TEXT}" \
        \
        --noinput-text="" \
        --lock-text="" \
        --lockfailed-text="" \
        \
        --time-color="${FG}ff" \
        --time-font="JetBrainsMono Nerd Font" \
        --time-size=80 \
        --time-str="%H:%M" \
        --timeoutline-color="${OUTLINE}ff" \
        --timeoutline-width=2 \
        \
        --date-color="${BLUE}bb" \
        --date-font="JetBrainsMono Nerd Font" \
        --date-size=20 \
        --date-str="%A, %d %B" \
        --dateoutline-color="${OUTLINE}88" \
        --dateoutline-width=1 \
        \
        --pass-media-keys \
        --pass-volume-keys
else
    # Fallback: standard i3lock
    i3lock -n -i "$img"
fi
