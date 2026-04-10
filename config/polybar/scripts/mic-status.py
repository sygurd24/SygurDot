#!/usr/bin/env python3
import subprocess
import sys
import time
import re
import select
import os
import json

# Colors matching system aesthetics
COLOR_ACTIVE = "%{F#00FFB3}"     # Bright Green-Cyan (Wifi Connected)
COLOR_PRIMARY = "%{F#00BCD4}"    # Cyan (Processor/Standard Icons)
COLOR_WARN = "%{F#FFC07F}" # Pastel Orange
COLOR_CRIT = "%{F#FF7A7A}" # Pastel Red
COLOR_GRAY = "%{F#707880}"
COLOR_WHITE = "%{F#FFFFFF}"
COLOR_END = "%{F-}"

def load_config():
    config_file = os.path.expanduser("~/.config/polybar/mic.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except:
            pass
    return {"display_mode": "icon_only"}

def get_mic_data():
    try:
        # Get Volume
        vol_out = subprocess.check_output(["pactl", "get-source-volume", "@DEFAULT_SOURCE@"], text=True)
        volume = 0
        match = re.search(r"(\d+)%", vol_out)
        if match:
            volume = int(match.group(1))
            
        # Get Usage
        usage_out = subprocess.check_output(["pactl", "list", "source-outputs"], text=True)
        
        # Filter out 'cava' so it doesn't trigger the microphone active color
        total_outputs = usage_out.count("Source Output #")
        cava_outputs = usage_out.count('application.name = "cava"')
        
        in_use = total_outputs > cava_outputs
        
        return volume, in_use
    except Exception:
        return 0, False

def format_output(volume, in_use, show_numbers):
    # Icons: 󰍬 (Normal), 󰍭 (Muted/0%)
    icon = "󰍭" if volume == 0 else "󰍬"
    
    if volume == 0:
        icon_color = COLOR_GRAY
    elif in_use:
        icon_color = COLOR_ACTIVE
    else:
        icon_color = COLOR_PRIMARY
        
    if not show_numbers:
        return f"{icon_color}{icon}{COLOR_END}"
    
    text_color = COLOR_WHITE
    if volume > 149:
        text_color = COLOR_CRIT
    elif volume > 100:
        text_color = COLOR_WARN
        
    return f"{icon_color}{icon}{COLOR_END} {text_color}{volume}%{COLOR_END}"

def run_loop():
    last_vol, last_use = get_mic_data()
    last_change = 0
    showing = False
    last_printed = ""
    
    subscribe_cmd = ["stdbuf", "-oL", "pactl", "subscribe"]
    process = subprocess.Popen(subscribe_cmd, stdout=subprocess.PIPE, text=True, bufsize=1)
    
    cur_vol, cur_use = last_vol, last_use
    last_config_check = 0
    display_mode = "icon_only"

    while True:
        ready, _, _ = select.select([process.stdout], [], [], 0.2)
        if ready:
            line = process.stdout.readline()
            if not line:
                break
            if "client" in line.lower() or "cliente" in line.lower():
                pass
            else:
                cur_vol, cur_use = get_mic_data()
        
        now = time.time()
        
        if now - last_config_check > 0.5:
            display_mode = load_config().get("display_mode", "icon_only")
            last_config_check = now

        if cur_vol != last_vol:
            last_change = now
            if display_mode == "icon_only":
                showing = True
            last_vol = cur_vol
            
        if display_mode == "always":
            showing = True
        elif display_mode == "icon_only":
            if showing and (now - last_change > 2.0):
                showing = False
            
        out = format_output(cur_vol, cur_use, showing)
        if out != last_printed:
            print(out, flush=True)
            last_printed = out
            
        last_use = cur_use

if __name__ == "__main__":
    try:
        run_loop()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        while True:
            v, u = get_mic_data()
            print(format_output(v, u, True), flush=True)
            time.sleep(1)