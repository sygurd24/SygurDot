#!/bin/bash

# Get the ID of the currently focused window
wid=$(bspc query -N -n)

if [ -z "$wid" ]; then
    exit 1
fi

# Get the current opacity value
opacity=$(xprop -id "$wid" _NET_WM_WINDOW_OPACITY | awk '{print $3}')

# Define opacity levels (32-bit hex for xprop)
OPAQUE="0xFFFFFFFF"
TRANSPARENT="0xD8888888" # Approx 85%

if [ "$opacity" == "4294967295" ] || [ -z "$opacity" ]; then
    # Currently opaque or not set -> Make transparent
    xprop -id "$wid" -f _NET_WM_WINDOW_OPACITY 32c -set _NET_WM_WINDOW_OPACITY "$TRANSPARENT"
else
    # Currently transparent -> Make opaque
    xprop -id "$wid" -f _NET_WM_WINDOW_OPACITY 32c -set _NET_WM_WINDOW_OPACITY "$OPAQUE"
fi
