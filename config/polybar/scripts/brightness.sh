#!/bin/bash

# Configuration
# Increase/Decrease step in percentage
STEP=5
# Minimum brightness percentage to prevent black screen
MIN_PERCENT=5

# Function to send notification
send_notification() {
    brightness=$(brightnessctl i | grep -oP '\(\d+%\)' | tr -d '()%')
    
    # Send notification with 2.5s timeout (2500ms)
    # Using replace-id 991042 to update existing notification
    if command -v dunstify &> /dev/null; then
        dunstify -a "Brightness" -u low -r 991042 -t 2500 -h int:value:"$brightness" -i "brightness-display" "Brightness: ${brightness}%"
    else
        notify-send -u low -t 2500 -h int:value:"$brightness" "Brightness: ${brightness}%"
    fi
}

case "$1" in
    up)
        current=$(brightnessctl i | grep -oP '\(\d+%\)' | tr -d '()%')
        
        if [ "$current" -lt 3 ]; then
            brightnessctl set 3%
        elif [ "$current" -lt 5 ]; then
            brightnessctl set 5%
        else
            # Calculate next multiple of 5
            # If current is 5, next is 10. If current is 6 (weird), next is 10.
            next_val=$(( (current / 5 + 1) * 5 ))
            if [ "$next_val" -gt 100 ]; then
                brightnessctl set 100%
            else
                brightnessctl set "${next_val}%"
            fi
        fi
        send_notification
        ;;
    down)
        # Check current brightness to prevent going below min
        current=$(brightnessctl i | grep -oP '\(\d+%\)' | tr -d '()%')
        
        if [ "$current" -gt 5 ]; then
             # If strictly greater than 5, go down by step, but floor at 5
             next_val=$((current - STEP))
             if [ "$next_val" -lt 5 ]; then
                 brightnessctl set 5%
             else
                 brightnessctl set "${STEP}%-"
             fi
        elif [ "$current" -gt 3 ]; then
             # If 4 or 5, go to 3
             brightnessctl set 3%
        elif [ "$current" -gt 1 ]; then
             # If 2 or 3, go to 1
             brightnessctl set 1%
        else
             # If 1 or 0 (shouldn't be 0), stay at 1
             brightnessctl set 1%
        fi
        send_notification
        ;;
esac
