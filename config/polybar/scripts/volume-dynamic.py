#!/usr/bin/env python3
import subprocess
import re
import sys
import time
import shutil
import select
import os
import json

COLOR_NORMAL = "" # Inherit
COLOR_WARN = "%{F#FFC07F}" # Pastel Orange
COLOR_CRIT = "%{F#FF7A7A}" # Pastel Red
COLOR_MUTED = "%{F#707880}" # Gray
COLOR_ACTIVE = "%{F#00FFB3}" # Turquoise
COLOR_END = "%{F-}"

HAVE_PACTL = shutil.which("pactl") is not None

def load_config():
    config_file = os.path.expanduser("~/.config/polybar/volume.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except:
            pass
    return {"display_mode": "icon_only"}

def _format_volume(vol, muted, show_numbers):
    # Icons:  (High), 󰕾 (Medium), 󰖀 (Low),  (Muted/0%)
    if muted or vol == 0:
        icon_str = f"{COLOR_MUTED} {COLOR_END}"
        if not show_numbers:
            return icon_str
        return f"{icon_str}{COLOR_MUTED}muted{COLOR_END}" if muted else f"{icon_str}{COLOR_MUTED}{vol}%{COLOR_END}"

    if vol < 30:
        icon = "󰖀 "
    elif vol < 60:
        icon = "󰕾 "
    else:
        icon = " "

    if vol > 100:
        icon_str = f"{COLOR_ACTIVE}{icon}%{{F-}}"
        color = COLOR_NORMAL
        if vol > 150:
            color = COLOR_CRIT
        elif vol > 100:
            color = COLOR_WARN
    else:
        icon_str = f"%{{F#00BCD4}}{icon}%{{F-}}"
        color = COLOR_NORMAL

    if not show_numbers:
        return icon_str

    return f"{icon_str}{color}{vol}%{COLOR_END}"

def get_volume_data():
    try:
        mute_out = subprocess.check_output(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], text=True).strip()
        muted = "yes" in mute_out
        vol_out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], text=True).strip()
        match = re.search(r"(\d+)%", vol_out)
        if match:
            return int(match.group(1)), muted
    except Exception:
        pass
    return 0, False

def main():
    last_vol, last_muted = get_volume_data()
    last_change = 0
    showing = False
    last_printed = ""
    last_config_check = 0
    display_mode = "icon_only"

    if HAVE_PACTL:
        try:
            subscribe_cmd = ["stdbuf", "-oL", "-eL", "pactl", "subscribe"]
            process = subprocess.Popen(subscribe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            
            cur_vol, cur_muted = last_vol, last_muted
            
            while True:
                ready, _, _ = select.select([process.stdout], [], [], 0.2)
                if ready:
                    line = process.stdout.readline()
                    if not line: break
                    if "client" in line.lower() or "cliente" in line.lower(): continue
                    cur_vol, cur_muted = get_volume_data()

                now = time.time()
                if now - last_config_check > 0.5:
                    display_mode = load_config().get("display_mode", "icon_only")
                    last_config_check = now

                if cur_vol != last_vol or cur_muted != last_muted:
                    last_change = now
                    if display_mode == "icon_only":
                        showing = True
                    last_vol = cur_vol
                    last_muted = cur_muted

                if display_mode == "always":
                    showing = True
                elif display_mode == "icon_only":
                    if showing and (now - last_change > 2.0):
                        showing = False

                out = _format_volume(cur_vol, cur_muted, showing)
                if out != last_printed:
                    print(out, flush=True)
                    last_printed = out
        except Exception:
            pass
    else:
        while True:
            v, m = get_volume_data()
            print(_format_volume(v, m, True), flush=True)
            time.sleep(1)

if __name__ == "__main__":
    main()