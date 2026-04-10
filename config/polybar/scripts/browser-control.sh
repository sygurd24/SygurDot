#!/bin/bash

# Simple Polybar script to control Firefox via playerctl
# Only displays if Firefox is running, playing/paused, AND visibility is enabled

# Visibility State (Default: Hidden)
VISIBILITY_FILE="/tmp/polybar_browser_control_visible"

# Function to get player status
get_player() {
    playerctl -l 2>/dev/null | grep -i "firefox" | head -n 1
}

PLAYER=$(get_player)

# --- ARGUMENT HANDLING ---

if [ "$1" = "--toggle-visibility" ]; then
    if [ -f "$VISIBILITY_FILE" ]; then
        rm "$VISIBILITY_FILE"
    else
        touch "$VISIBILITY_FILE"
    fi
    # Force update of the running script instance
    pkill -f "browser-control.sh" 2>/dev/null
    exit 0
fi

if [ "$1" = "--play-pause" ]; then
    if [ -n "$PLAYER" ]; then playerctl -p "$PLAYER" play-pause 2>/dev/null; fi
    exit 0
fi

if [ "$1" = "--next" ]; then
    if [ -n "$PLAYER" ]; then playerctl -p "$PLAYER" next 2>/dev/null; fi
    exit 0
fi

if [ "$1" = "--prev" ]; then
    if [ -n "$PLAYER" ]; then
        # SMART PREVIOUS LOGIC
        # 1. Get current track ID
        ID_BEFORE=$(playerctl -p "$PLAYER" metadata mpris:trackid 2>/dev/null)
        
        # 2. Try to go to previous track
        playerctl -p "$PLAYER" previous 2>/dev/null
        
        # 3. Small sleep to allow player to update
        sleep 0.1
        
        # 4. Get new track ID
        ID_AFTER=$(playerctl -p "$PLAYER" metadata mpris:trackid 2>/dev/null)
        
        # 5. If IDs are the same (didn't change track), restart current track
        # Note: This also handles "Repeat One" gracefully (restarts anyway)
        if [ "$ID_BEFORE" = "$ID_AFTER" ]; then
            playerctl -p "$PLAYER" position 0.0 2>/dev/null
        fi
    fi
    exit 0
fi

# --- MAIN LOGIC ---

# If no player found, wait and exit (Polybar will restart script)
if [ -z "$PLAYER" ]; then
    echo ""
    sleep 30
    exit 0
fi

# Function to update the display
update_display() {
    # Check visibility first
    if [ ! -f "$VISIBILITY_FILE" ]; then
        echo ""
        return
    fi

    STATUS=$(playerctl -p "$PLAYER" status 2>/dev/null)
    
    if [ "$STATUS" = "Playing" ]; then
        ICON=""
    elif [ "$STATUS" = "Paused" ]; then
        ICON=""
    else
        echo "" # Hide if stopped/gone
        return
    fi
    
    # Simple icons
    SCRIPT="$HOME/.config/polybar/scripts/browser-control.sh"
    
    PREV="%{A1:$SCRIPT --prev:}%{A}"
    PLAY="%{A1:$SCRIPT --play-pause:}$ICON%{A}"
    NEXT="%{A1:$SCRIPT --next:}%{A}"
    
    echo "$PREV  $PLAY  $NEXT"
}

# Initial update
update_display

# Use --follow for efficient updates
playerctl -p "$PLAYER" status --follow | while read -r line; do
    update_display
done
