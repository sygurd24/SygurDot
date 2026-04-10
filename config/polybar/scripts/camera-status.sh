#!/usr/bin/env bash

# Camera indicator for Polybar
CONFIG_FILE="$HOME/.config/polybar/camera.json"

ICON_FILLED=""
COLOR_END="%{F-}"

get_color() {
    grep -o '"color"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" 2>/dev/null | cut -d'"' -f4 || echo "#00FF00"
}

get_blink() {
    grep -o '"blink"[[:space:]]*:[[:space:]]*false' "$CONFIG_FILE" >/dev/null 2>&1 && echo "false" || echo "true"
}

get_speed() {
    grep -o '"speed"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" 2>/dev/null | cut -d'"' -f4 || echo "medium"
}

state=0

while true; do
    COLOR_HEX=$(get_color)
    COLOR_FMT="%{F${COLOR_HEX}}"
    BLINK=$(get_blink)
    SPEED_TXT=$(get_speed)
    
    if [ "$SPEED_TXT" = "fast" ]; then SPEED=0.3
    elif [ "$SPEED_TXT" = "slow" ]; then SPEED=1.2
    else SPEED=0.6; fi
    
    if fuser /dev/video* >/dev/null 2>&1 || lsof /dev/video* >/dev/null 2>&1; then
        if [ "$BLINK" = "false" ]; then
            echo " ${COLOR_FMT}${ICON_FILLED}${COLOR_END} "
            sleep 2
        else
            if [ $state -eq 0 ]; then
                echo " ${COLOR_FMT}${ICON_FILLED}${COLOR_END} "
                state=1
            else
                echo "   "
                state=0
            fi
            sleep $SPEED
        fi
    else
        echo ""
        state=0
        sleep 2
    fi
done
