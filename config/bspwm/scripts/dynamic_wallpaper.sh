#!/bin/bash

DIR="$HOME/Pictures/Wallpapers"
NOCHE="$DIR/firewatch_noche.png"
TRANSICION_DIA="$DIR/firewatch_madrugada.jpg"
TRANSICION_DIA_NUEVA="$DIR/firewatch_transiciondia.png"
TRANSICION_NOCHE="$DIR/firewatch_transicionnoche.jpeg"
DIA="$DIR/firewatch_dia.jpg"
TARDE="$DIR/firewatch_tarde.jpg"
TARDE_NOCHE="$DIR/firewatch_tardenoche.jpeg"

while true; do
    # Get current time in HHMM format
    CURRENT_TIME=$(date +"%H%M")
    
    # Remove leading zeros to prevent octal interpretation errors
    TIME_VAL=$((10#$CURRENT_TIME))
    
    # Logic
    # 00:00 (0) - 05:50 (550): Noche
    # 05:51 (551) - 06:51 (651): Transicion Dia (Madrugada)
    # 06:52 (652) - 08:00 (800): Transicion Dia Nueva
    # 08:01 (801) - 16:00 (1600): Dia
    # 16:01 (1601) - 18:40 (1840): Tarde
    # 18:41 (1841) - 19:30 (1930): Tarde Noche
    # 19:31 (1931) - 20:30 (2030): Transicion Noche
    # 20:31 (2031) - 23:59 (2359): Noche
    
    if [ "$TIME_VAL" -ge 0 ] && [ "$TIME_VAL" -le 550 ]; then
        IMG="$NOCHE"
        
    elif [ "$TIME_VAL" -ge 551 ] && [ "$TIME_VAL" -le 651 ]; then
        IMG="$TRANSICION_DIA"

    elif [ "$TIME_VAL" -ge 652 ] && [ "$TIME_VAL" -le 800 ]; then
        IMG="$TRANSICION_DIA_NUEVA"
        
    elif [ "$TIME_VAL" -ge 801 ] && [ "$TIME_VAL" -le 1600 ]; then
        IMG="$DIA"
        
    elif [ "$TIME_VAL" -ge 1601 ] && [ "$TIME_VAL" -le 1840 ]; then
        IMG="$TARDE"

    elif [ "$TIME_VAL" -ge 1841 ] && [ "$TIME_VAL" -le 1930 ]; then
        IMG="$TARDE_NOCHE"
        
    elif [ "$TIME_VAL" -ge 1931 ] && [ "$TIME_VAL" -le 2030 ]; then
        IMG="$TRANSICION_NOCHE"
        
    elif [ "$TIME_VAL" -ge 2031 ]; then
        IMG="$NOCHE"
    fi

    # Update wallpaper only if it has changed or if it's the first run
    # We use a state file to track the last set image
    STATE_FILE="/tmp/current_wallpaper_state"
    LAST_IMG=$(cat "$STATE_FILE" 2>/dev/null)

    if [ "$IMG" != "$LAST_IMG" ] || [ ! -f "$STATE_FILE" ]; then
        feh --bg-fill --no-fehbg "$IMG"
        echo "$IMG" > "$STATE_FILE"
        # Pre-generate blurred version for the lock screen and calculate brightness in background
        (
            magick "$IMG" -resize 1920x1080^ -gravity center -extent 1920x1080 -modulate 100,120 -filter Gaussian -blur 0x10 /tmp/lock_blur.png && \
            mv /tmp/lock_blur.png /tmp/current_wallpaper_blurred.png
            
            # Calculate optimal contrast color (Light vs Dark)
            BRIGHTNESS=$(magick "$IMG" -colorspace Gray -format "%[fx:int(mean*100)]" info: 2>/dev/null || echo "0")
            if [ "$BRIGHTNESS" -gt 60 ]; then
                echo "333333" > /tmp/lock_foreground_color
                echo "ffffff" > /tmp/lock_outline_color
            else
                echo "c0caf5" > /tmp/lock_foreground_color
                echo "1a1b26" > /tmp/lock_outline_color
            fi
            echo "Wallpaper: $(basename "$IMG") | Brightness: $BRIGHTNESS" >> /tmp/wallpaper_debug.log
        ) &
    fi

    # Check every 5 seconds for better responsiveness after wake
    sleep 5
done
