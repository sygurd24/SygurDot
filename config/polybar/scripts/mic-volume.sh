#!/bin/bash
python3 -c '
import subprocess
import sys

# Get all source names, excluding monitor sources
sources = subprocess.check_output(["pactl", "list", "short", "sources"], text=True).splitlines()
sources = [s.split("\t")[1] for s in sources if "monitor" not in s]
mode = "'"$1"'"

for source in sources:
    if mode == "toggle":
        subprocess.run(["pactl", "set-source-mute", source, "toggle"])
    elif mode in ["up", "down"]:
        # Get volume
        vol_info = subprocess.check_output(["pactl", "get-source-volume", source], text=True)
        vol = int(vol_info.split("%")[0].split("/")[-1].strip())
        
        if mode == "up":
            vol = min(vol + 5, 200)
        else:
            vol = max(vol - 5, 0)
        subprocess.run(["pactl", "set-source-volume", source, f"{vol}%"])
'
