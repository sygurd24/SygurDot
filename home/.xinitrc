#!/bin/sh

# Load environment and startup services from .xprofile
if [ -f "$HOME/.xprofile" ]; then
    . "$HOME/.xprofile"
fi

if [ -f "$HOME/.Xresources" ]; then
    xrdb -merge "$HOME/.Xresources"
fi

exec bspwm
