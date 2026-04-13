#!/bin/bash

# Network Status for Polybar
# Logic:
# - Ethernet Connected: Bright Green-Cyan Ethernet Icon
# - Radio Off: Gray Strikethrough
# - Disconnected (But On): Standard Empty Icon
# - Connected: Bright Green-Cyan Icon (Signal Strength)

# 0. Check Ethernet
if LC_ALL=C nmcli -t -f TYPE,STATE dev 2>/dev/null | grep -Eq '^(ethernet|802-3-ethernet):connected'; then
    # Bright Green-Cyan
    echo "%{F#00FFB3}󰈀%{F-}"
    exit 0
fi

# 1. Check Radio Status
# Force C locale so nmcli output is consistent regardless of system language.
radio_status=$(LC_ALL=C nmcli radio wifi)

if [ "$radio_status" = "disabled" ] || [ "$radio_status" = "deshabilitado" ]; then
    # Gray Strikethrough
    echo "%{F#707880}󰖪 %{F-}"
    exit 0
fi

# 2. Check Connection
# Format nmcli -t: active:signal
# Force C locale so "yes" is stable; also accept localized "sí" just in case.
active_info=$(LC_ALL=C nmcli -t -f active,signal dev wifi 2>/dev/null | grep -E '^(yes|sí):' | sort -t: -k2 -nr | head -n1)

if [ -n "$active_info" ]; then
    signal=$(echo "$active_info" | cut -d: -f2)
    
    # Map input signal to icon
    if [ "$signal" -ge 80 ]; then
        icon="󰤨"
    elif [ "$signal" -ge 60 ]; then
        icon="󰤥"
    elif [ "$signal" -ge 40 ]; then
        icon="󰤢"
    elif [ "$signal" -ge 20 ]; then
        icon="󰤟"
    else
        icon="󰤯"
    fi
    
    # Connected -> Bright Green-Cyan (#00FFB3)
    echo "%{F#00FFB3}$icon%{F-}"
else
    # Generic fallback: check if any wireless interface is UP and has an IPv4
    if ip -o -4 route show default 2>/dev/null | grep -E 'wlan|wlo|wl' >/dev/null; then
        echo "%{F#00FFB3}󰤨%{F-}"
        exit 0
    fi
    if ip -o -4 addr show 2>/dev/null | awk '$2 ~ /^(wlan|wlo|wl)/ {print $0}' | grep -qv "127.0.0.1"; then
        echo "%{F#00FFB3}󰤨%{F-}"
        exit 0
    fi

    # Disconnected (But On) -> Standard Color (Inherited), Empty Icon
    echo "󰤯"
fi
