#!/bin/bash

# Wait to ensure key release doesn't interfere
sleep 0.2

# Run maim to select (-s) and hide cursor (-u)
# Pipe to xclip to store in clipboard as PNG
if maim -s -u | xclip -selection clipboard -t image/png; then
    notify-send "Screenshot" "Copied to clipboard!" -t 2000
else
    notify-send "Screenshot" "Cancelled or Failed" -u critical
fi
