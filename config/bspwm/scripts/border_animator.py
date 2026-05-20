#!/usr/bin/env python3
import subprocess
import time
import json
import math
import os
import socket

CONFIG_PATH = os.path.expanduser("~/.config/bspwm/border_config.json")

# Perfiles de color
PROFILES = {
    "blue_teal": ("#4682B4", "#40E0D0"),
    "cyberpunk": ("#FF00FF", "#40E0D0"),
    "sunset": ("#FF8C00", "#9400D3"),
    "ocean": ("#00008B", "#00FFFF")
}

INTENSITIES = {
    "high": 1.0,
    "medium": 0.85,
    "low": 0.7
}

last_mtime = 0
cached_config = {"enabled": True, "profile": "blue_teal", "intensity": "medium", "speed": "medium"}

def get_config():
    global last_mtime, cached_config
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if mtime > last_mtime:
            with open(CONFIG_PATH, "r") as f:
                cached_config = json.load(f)
            last_mtime = mtime
    except Exception:
        pass
    return cached_config

def interpolate_color(c1, c2, t, intensity_factor):
    c1 = [int(c1[i:i+2], 16) for i in (1, 3, 5)]
    c2 = [int(c2[i:i+2], 16) for i in (1, 3, 5)]
    res = [int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)]
    res = [int(x * intensity_factor) for x in res]
    return "#{:02x}{:02x}{:02x}".format(*res)

def get_bspwm_socket():
    socket_path = os.environ.get("BSPWM_SOCKET")
    if socket_path and os.path.exists(socket_path):
        return socket_path
    
    display = os.environ.get("DISPLAY", ":0")
    disp_num = display.split(":")[1].split(".")[0] if ":" in display else "0"
    screen_num = display.split(".")[1] if "." in display else "0"
    
    path = f"/tmp/bspwm_{disp_num}_{screen_num}-socket"
    if os.path.exists(path):
        return path
    
    return None

def send_bspc_command(cmd_args):
    socket_path = get_bspwm_socket()
    if socket_path:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(socket_path)
                cmd_bytes = b"".join([arg.encode("utf-8") + b"\x00" for arg in cmd_args])
                s.sendall(cmd_bytes)
                return True
        except Exception:
            pass
    
    subprocess.run(["bspc"] + cmd_args, capture_output=True)

def update_border():
    t = 0.0
    last_profile = None
    last_color = None
    
    while True:
        config = get_config()
        
        current_profile = config.get("profile", "blue_teal")
        if current_profile != last_profile:
            t = 0.0
            last_profile = current_profile
            
        show_border = config.get("show_border", True)
        if not show_border:
            if last_color != "#333333":
                send_bspc_command(["config", "focused_border_color", "#333333"])
                last_color = "#333333"
            time.sleep(1.0)
            continue
            
        c1, c2 = PROFILES.get(current_profile, PROFILES["blue_teal"])
        
        if not config.get("enabled", True):
            if last_color != c1:
                send_bspc_command(["config", "focused_border_color", c1])
                last_color = c1
            time.sleep(1.0)
            continue
            
        intensity_key = config.get("intensity", "medium")
        factor = INTENSITIES.get(intensity_key, INTENSITIES["medium"])
        
        val = (math.sin(t) + 1) / 2
        current_color = interpolate_color(c1, c2, val, factor)
        
        if current_color != last_color:
            send_bspc_command(["config", "focused_border_color", current_color])
            last_color = current_color
            
        speed_str = config.get("speed", "medium")
        if speed_str == "fast":
            sleep_time = 0.05
            t_inc = 0.15
        elif speed_str == "slow":
            sleep_time = 0.2
            t_inc = 0.05
        else: # medium
            sleep_time = 0.1
            t_inc = 0.1
            
        t += t_inc
        time.sleep(sleep_time)

if __name__ == "__main__":
    update_border()
