#!/bin/bash

# mic-volume.sh [up|down|toggle]

STEP=5
MAX_VOL=200

current_vol=$(pactl get-source-volume @DEFAULT_SOURCE@ | grep -Po '\d+(?=%)' | head -n 1)
if [ -z "$current_vol" ]; then current_vol=0; fi

if [ "$1" == "up" ]; then
    if [ "$current_vol" -lt "$MAX_VOL" ]; then
        # Calculate next multiple of 5
        target=$(( (current_vol / 5 + 1) * 5 ))
        if [ "$target" -gt "$MAX_VOL" ]; then
            target=$MAX_VOL
        fi
        pactl set-source-volume @DEFAULT_SOURCE@ ${target}%
    fi
elif [ "$1" == "down" ]; then
    if [ "$current_vol" -gt 0 ]; then
        # Calculate prev multiple of 5
        target=$(( (current_vol - 1) / 5 * 5 ))
        if [ "$target" -lt 0 ]; then
            target=0
        fi
        pactl set-source-volume @DEFAULT_SOURCE@ ${target}%
    fi
elif [ "$1" == "toggle" ]; then
    pactl set-source-mute @DEFAULT_SOURCE@ toggle
fi
