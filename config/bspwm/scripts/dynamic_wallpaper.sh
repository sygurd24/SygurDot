#!/bin/bash

DIR="$HOME/Pictures/Wallpapers"
NOCHE="$DIR/firewatch_noche.png"
TRANSICION_DIA="$DIR/firewatch_madrugada.jpg"
TRANSICION_DIA_NUEVA="$DIR/firewatch_transiciondia.png"
TRANSICION_NOCHE="$DIR/firewatch_transicionnoche.jpeg"
DIA="$DIR/firewatch_dia.jpg"
TARDE="$DIR/firewatch_tarde.jpg"
TARDE_NOCHE="$DIR/firewatch_tardenoche.jpeg"

MODE_FILE="$HOME/.config/dotfiles/wallpaper_mode"
CUSTOM_FILE="$HOME/.config/dotfiles/custom_wallpaper_path"
STATE_FILE="/tmp/current_wallpaper_state"

update_wallpaper() {
    MODE="dynamic"
    if [ -f "$MODE_FILE" ]; then
        MODE=`cat "$MODE_FILE"`
    fi

    if [ "$MODE" == "custom" ]; then
        if [ -f "$CUSTOM_FILE" ]; then
            IMG=`cat "$CUSTOM_FILE"`
        else
            IMG="$DIA" # Fallback
        fi
    else
        # Dynamic mode logic
        CURRENT_TIME=`date +"%H%M"`
        TIME_VAL=$((10#$CURRENT_TIME))
        
        if [ "$TIME_VAL" -ge 0 ] && [ "$TIME_VAL" -le 550 ]; then IMG="$NOCHE"
        elif [ "$TIME_VAL" -ge 551 ] && [ "$TIME_VAL" -le 651 ]; then IMG="$TRANSICION_DIA"
        elif [ "$TIME_VAL" -ge 652 ] && [ "$TIME_VAL" -le 800 ]; then IMG="$TRANSICION_DIA_NUEVA"
        elif [ "$TIME_VAL" -ge 801 ] && [ "$TIME_VAL" -le 1600 ]; then IMG="$DIA"
        elif [ "$TIME_VAL" -ge 1601 ] && [ "$TIME_VAL" -le 1840 ]; then IMG="$TARDE"
        elif [ "$TIME_VAL" -ge 1841 ] && [ "$TIME_VAL" -le 1930 ]; then IMG="$TARDE_NOCHE"
        elif [ "$TIME_VAL" -ge 1931 ] && [ "$TIME_VAL" -le 2030 ]; then IMG="$TRANSICION_NOCHE"
        elif [ "$TIME_VAL" -ge 2031 ]; then IMG="$NOCHE"
        fi
    fi

    LAST_IMG=""
    if [ -f "$STATE_FILE" ]; then
        LAST_IMG=`cat "$STATE_FILE" 2>/dev/null`
    fi

    if [ "$IMG" != "$LAST_IMG" ] || [ ! -f "$STATE_FILE" ]; then
        if [ -f "$IMG" ]; then
            feh --bg-fill --no-fehbg "$IMG"
            echo "$IMG" > "$STATE_FILE"
            (
                magick "$IMG" -resize 1920x1080^ -gravity center -extent 1920x1080 -modulate 100,120 -filter Gaussian -blur 0x10 /tmp/lock_blur.png && \
                mv /tmp/lock_blur.png /tmp/current_wallpaper_blurred.png
                
                BRIGHTNESS=`magick "$IMG" -colorspace Gray -format "%[fx:int(mean*100)]" info: 2>/dev/null || echo "0"`
                if [ "$BRIGHTNESS" -gt 60 ]; then
                    echo "333333" > /tmp/lock_foreground_color
                    echo "ffffff" > /tmp/lock_outline_color
                else
                    echo "c0caf5" > /tmp/lock_foreground_color
                    echo "1a1b26" > /tmp/lock_outline_color
                fi
                echo "Wallpaper: `basename "$IMG"` | Brightness: $BRIGHTNESS | Mode: $MODE" >> /tmp/wallpaper_debug.log
            ) &
        fi
    fi
}

trap 'update_wallpaper' USR1

update_wallpaper

while true; do
    sleep 5 &
    wait $!
    update_wallpaper
done
