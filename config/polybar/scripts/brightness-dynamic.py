#!/usr/bin/env python3
import subprocess
import time
import re
import sys
import os
import json
import glob

# Colors matching system aesthetics
COLOR_PRIMARY = "%{F#00BCD4}"    # Cyan (Standard Icons)
COLOR_WARN = "%{F#FFC07F}"       # Pastel Orange
COLOR_CRIT = "%{F#FF7A7A}"       # Pastel Red
COLOR_WHITE = "%{F#FFFFFF}"
COLOR_END = "%{F-}"

def load_config():
    config_file = os.path.expanduser("~/.config/polybar/brightness.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except:
            pass
    return {"display_mode": "icon_only"}

def get_brightness():
    try:
        paths = glob.glob("/sys/class/backlight/*")
        if paths:
            with open(paths[0] + "/brightness", "r") as f:
                b = float(f.read().strip())
            with open(paths[0] + "/max_brightness", "r") as f:
                m = float(f.read().strip())
            return int(round((b / m) * 100))
    except:
        pass
    
    try:
        out = subprocess.check_output(["brightnessctl", "i"], text=True)
        match = re.search(r"\((\d+)%\)", out)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return 0

def format_output(brightness, show_numbers):
    # Icons: 󰃠 (High), 󰃟 (Med), 󰃞 (Low)
    if brightness > 70:
        icon = "󰃠"
    elif brightness > 30:
        icon = "󰃟"
    else:
        icon = "󰃞"
        
    icon_str = f"{COLOR_PRIMARY}{icon}{COLOR_END}"
    
    if not show_numbers:
        return icon_str
        
    text_color = COLOR_WHITE
    if brightness > 90:
        text_color = COLOR_CRIT
    elif brightness > 70:
        text_color = COLOR_WARN
        
    return f"{icon_str} {text_color}{brightness}%{COLOR_END}"

def run_loop():
    last_val = get_brightness()
    last_change = 0
    showing = False
    last_printed = ""
    last_config_check = 0
    display_mode = "icon_only"

    while True:
        time.sleep(0.05) # Super fast polling with sysfs prevents lag
        cur_val = get_brightness()
        
        now = time.time()
        
        if now - last_config_check > 0.5:
            display_mode = load_config().get("display_mode", "icon_only")
            last_config_check = now

        if cur_val != last_val:
            last_change = now
            if display_mode == "icon_only":
                showing = True
            last_val = cur_val
            
        if display_mode == "always":
            showing = True
        elif display_mode == "icon_only":
            if showing and (now - last_change > 2.0):
                showing = False
            
        out = format_output(cur_val, showing)
        if out != last_printed:
            print(out, flush=True)
            last_printed = out

if __name__ == "__main__":
    try:
        run_loop()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        while True:
            print(format_output(get_brightness(), True), flush=True)
            time.sleep(1)