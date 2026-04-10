#!/bin/bash
LOG_FILE="/tmp/wallpaper_sync.log"
echo "Starting sync at $(date)" > "$LOG_FILE"

# Start wallpaper immediately so user isn't looking at black screen
"$HOME/.config/bspwm/scripts/dynamic_wallpaper.sh" &

# Wait for internet connection (check every 2 seconds)
MAX_RETRIES=30
COUNT=0

while ! ping -c 1 -W 1 8.8.8.8 &> /dev/null; do
    echo "Waiting for network..." >> "$LOG_FILE"
    sleep 2
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "Network unavailable, giving up." >> "$LOG_FILE"
        break
    fi
done

echo "Network connected." >> "$LOG_FILE"

# Try to nudge systemd-timesyncd to sync
# timedatectl set-ntp false 2>> "$LOG_FILE"
# timedatectl set-ntp true 2>> "$LOG_FILE"
# (Skipped because it hangs without authentication)

echo "Restarting wallpaper script..." >> "$LOG_FILE"
# Restart the wallpaper script to pick up the new time immediately
killall -q dynamic_wallpaper.sh
sleep 1
"$HOME/.config/bspwm/scripts/dynamic_wallpaper.sh" &
echo "Done." >> "$LOG_FILE"
