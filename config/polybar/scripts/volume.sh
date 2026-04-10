#!/bin/bash

# Configuration
# Increase/Decrease step in percentage
STEP=5

# Function to get current volume (average of all channels on default sink)
get_volume() {
    pactl get-sink-volume @DEFAULT_SINK@ | grep -oP '\d+(?=%)' | head -n 1
}

# Function to get mute status
get_mute() {
    pactl get-sink-mute @DEFAULT_SINK@ | grep -o "yes"
}

# Function to send notification
send_notification() {
    volume=$(get_volume)
    mute=$(get_mute)
    
    # Make icon vary by volume
    if [ "$mute" == "yes" ]; then
        icon="audio-volume-muted"
        text="Muted"
    else
        if [ "$volume" -lt 30 ]; then
            icon="audio-volume-low"
        elif [ "$volume" -lt 70 ]; then
            icon="audio-volume-medium"
        else
            icon="audio-volume-high"
        fi
        text="Volume: ${volume}%"
    fi
    
    # Send notification with 2.5s timeout (2500ms)
    # Using replace-id 991043 (separate from brightness)
    if command -v dunstify &> /dev/null; then
        dunstify -a "Volume" -u low -r 991043 -t 2500 -h int:value:"$volume" -i "$icon" "$text"
    else
        notify-send -u low -t 2500 -h int:value:"$volume" "$text"
    fi
}

case "$1" in
    up)
        # Unmute if muted
        pactl set-sink-mute @DEFAULT_SINK@ 0
        
        # Snap logic
        vol=$(get_volume)
        # Calculate next multiple of 5
        # (vol / 5 + 1) * 5
        target=$(( (vol / 5 + 1) * 5 ))
        
        # Safety check: ensure we actually go up
        if [ "$target" -le "$vol" ]; then
             target=$((target + 5))
        fi

        # Limit to 200%
        if [ "$target" -gt 200 ]; then
            target=200
        fi
        
        pactl set-sink-volume @DEFAULT_SINK@ ${target}%
        send_notification
        ;;
    down)
        vol=$(get_volume)
        # Calculate prev multiple of 5
        # ((vol - 1) / 5) * 5
        target=$(( (vol - 1) / 5 * 5 ))
        
        pactl set-sink-volume @DEFAULT_SINK@ ${target}%
        send_notification
        ;;
    mute)
        pactl set-sink-mute @DEFAULT_SINK@ toggle
        send_notification
        ;;
esac
