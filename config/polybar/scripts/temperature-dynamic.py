#!/usr/bin/env python3
import sys
import os
import json

# Configuration
THERMAL_ZONE = None
CONFIG_FILE = os.path.expanduser("~/.config/polybar/temperature.json")
STATE_FILE_OLD = "/tmp/polybar_temp_state"

# Colors
COLOR_CYAN = (0, 188, 212)   # #00BCD4
COLOR_WHITE = (255, 255, 255) # #FFFFFF
COLOR_YELLOW = (255, 235, 59) # #FFEB3B
COLOR_RED = (244, 67, 54)     # #F44336

ICON = ""

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                if "show_text" in config:
                    config["display_mode"] = "always" if config["show_text"] else "never"
                    del config["show_text"]
                if "display_mode" not in config:
                    config["display_mode"] = "never"
                return config
        except:
            pass
    
    # Fallback to old state file for backwards compatibility
    old_state = os.path.exists(STATE_FILE_OLD)
    return {"display_mode": "always" if old_state else "never", "unit": "C"}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def pick_thermal_zone():
    base = "/sys/class/thermal"
    try:
        zones = [z for z in os.listdir(base) if z.startswith("thermal_zone")]
    except:
        return None

    # Prefer CPU-related zones when available
    preferred = ["x86_pkg_temp", "cpu_thermal", "acpitz"]
    for pref in preferred:
        for z in zones:
            type_path = os.path.join(base, z, "type")
            temp_path = os.path.join(base, z, "temp")
            try:
                with open(type_path, "r") as f:
                    if f.read().strip() == pref and os.path.exists(temp_path):
                        return temp_path
            except:
                continue

    # Fallback: first zone with a temp file
    for z in zones:
        temp_path = os.path.join(base, z, "temp")
        if os.path.exists(temp_path):
            return temp_path

    return None

def hex_string(rgb):
    return "#%02x%02x%02x" % rgb

def interpolate(start_color, end_color, t):
    r = int(start_color[0] + (end_color[0] - start_color[0]) * t)
    g = int(start_color[1] + (end_color[1] - start_color[1]) * t)
    b = int(start_color[2] + (end_color[2] - start_color[2]) * t)
    return (r, g, b)

def get_color(temp):
    # 0 - 40: Cyan
    if temp <= 40:
        return COLOR_CYAN
    # 41 - 55: White
    elif temp <= 55:
        return COLOR_WHITE
    # 55 - 75: White -> Yellow
    elif temp <= 75:
        t = (temp - 55) / (75 - 55)
        return interpolate(COLOR_WHITE, COLOR_YELLOW, t)
    # 75 - 90: Yellow -> Red
    elif temp <= 90:
        t = (temp - 75) / (90 - 75)
        return interpolate(COLOR_YELLOW, COLOR_RED, t)
    # > 90: Red
    else:
        return COLOR_RED

def main():
    # Handle click script (toggle state)
    if len(sys.argv) > 1 and sys.argv[1] == "toggle":
        config = load_config()
        # Toggle logic: never -> always -> warning -> never
        current = config.get("display_mode", "never")
        if current == "never": config["display_mode"] = "always"
        elif current == "always": config["display_mode"] = "warning"
        else: config["display_mode"] = "never"
        save_config(config)
        return

    # Read State
    config = load_config()
    display_mode = config.get("display_mode", "never")
    unit = config.get("unit", "C")

    global THERMAL_ZONE
    if THERMAL_ZONE is None:
        THERMAL_ZONE = pick_thermal_zone()
    if THERMAL_ZONE is None:
        return

    try:
        with open(THERMAL_ZONE, 'r') as f:
            temp_millis = int(f.read().strip())
            temp_c = temp_millis / 1000.0
    except:
        return

    color_rgb = get_color(temp_c)
    color_hex = hex_string(color_rgb)
    
    display_temp = temp_c
    unit_str = "°C"
    
    if unit == "F":
        display_temp = (temp_c * 9/5) + 32
        unit_str = "°F"
    elif unit == "K":
        display_temp = temp_c + 273.15
        unit_str = "K"
    
    show_text = False
    if display_mode == "always":
        show_text = True
    elif display_mode == "warning":
        # Show text if temp is 56 or higher (where the color gets yellow and starts interpolating to red)
        if temp_c > 55:
            show_text = True
    
    # Construct Output
    # The whole module is clickable via polybar config, so we just output content
    output = f"%{{F{color_hex}}}{ICON}%{{F-}}"
    
    if show_text:
        output += f" %{{F{color_hex}}}{int(display_temp)}{unit_str}%{{F-}}"
        
    print(output)

if __name__ == "__main__":
    main()
