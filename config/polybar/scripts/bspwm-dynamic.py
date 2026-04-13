#!/usr/bin/env python3
import subprocess
import json
import socket
import os
import sys
import math

# Dynamic BSPWM for Polybar
# Features:
# - Heatmap color for occupied workspaces (White -> Red) based on window count.
# - Consistent icons with existing config (Filled circle, Open circle, etc.)

# Colors
COLOR_FOCUSED_DEFAULT = "#00BCD4" # Primary Cyan
COLOR_FOCUSED_TEAL = "#00FFB3"    # Teal/Turquoise
COLOR_URGENT = "#cb0e0eff" # Alert
COLOR_EMPTY = "#333333" # Disabled
COLOR_WHITE = (255, 255, 255)
COLOR_RED = (255, 0, 0)
COLOR_CYAN = (0, 188, 212) # #00BCD4

# Icons
ICON_FOCUSED = ""
ICON_OCCUPIED = ""
ICON_EMPTY = ""
ICON_URGENT = ""

def hex_to_rgb(hex_col):
    h = hex_col.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb

def interpolate_color(count, end_color=COLOR_RED):
    # Map count 1..5 to White..EndColor
    # 1 -> 0% EndColor
    # 5 -> 100% EndColor
    
    if count <= 1:
        return rgb_to_hex(COLOR_WHITE)
    if count >= 5:
        return rgb_to_hex(end_color)
        
    t = (count - 1) / 4.0
    
    r = int(COLOR_WHITE[0] + (end_color[0] - COLOR_WHITE[0]) * t)
    g = int(COLOR_WHITE[1] + (end_color[1] - COLOR_WHITE[1]) * t)
    b = int(COLOR_WHITE[2] + (end_color[2] - COLOR_WHITE[2]) * t)
    
    return rgb_to_hex((r, g, b))

def load_config():
    config_file = os.path.expanduser("~/.config/polybar/bspwm.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "style": "circles",
        "color_mode": "heatmap_red_cyan",
        "hide_empty": False
    }

def get_state():
    try:
        output = subprocess.check_output(["bspc", "wm", "-d"], text=True)
        dump = json.loads(output)
        return dump
    except Exception as e:
        return None

def generate_polybar_string(dump):
    if not dump: return ""
    
    config = load_config()
    style_name = config.get("style", "circles")
    color_mode = config.get("color_mode", "heatmap_red_cyan")
    # For backward compatibility with old config:
    if color_mode == "heatmap":
        color_mode = "heatmap_red_cyan"
        
    hide_empty = config.get("hide_empty", False)
    
    # Configure colors based on mode
    if color_mode == "heatmap_red_cyan":
        focus_color = COLOR_FOCUSED_DEFAULT
        gradient_end = COLOR_RED
    elif color_mode == "heatmap_red_teal":
        focus_color = COLOR_FOCUSED_TEAL
        gradient_end = COLOR_RED
    elif color_mode == "heatmap_cyan_teal":
        focus_color = COLOR_FOCUSED_TEAL
        gradient_end = COLOR_CYAN
    elif color_mode == "heatmap_neon":
        focus_color = COLOR_FOCUSED_TEAL
        gradient_end = (255, 0, 255) # Magenta
    elif color_mode == "static":
        focus_color = COLOR_FOCUSED_DEFAULT
        gradient_end = None
    else:
        focus_color = COLOR_FOCUSED_DEFAULT
        gradient_end = COLOR_RED
    
    monitors = dump.get("monitors", [])
    output = []
    
    for mon in monitors:
        focused_desktop_id = mon['focusedDesktopId']
        
        for desk in mon['desktops']:
            name = desk['name']
            
            # Skip hidden desktops (F1-F12)
            if name.startswith('F'):
                continue
            
            is_focused = (desk['id'] == focused_desktop_id) and (mon['id'] == dump['focusedMonitorId'])
            
            root = desk.get('root')
            window_count = 0
            
            if root:
                def count_windows(node):
                    c = 0
                    if not node: return 0
                    if node.get('client'): c += 1
                    c += count_windows(node.get('firstChild'))
                    c += count_windows(node.get('secondChild'))
                    return c
                
                window_count = count_windows(root)
            
            is_occupied = (window_count > 0)
            is_urgent = False
            
            if hide_empty and not is_occupied and not is_focused:
                continue
            
            # Determine icons based on style
            style_icons = {
                "circles": {"focused": "", "occupied": "", "empty": "", "urgent": ""},
                "squares": {"focused": "■", "occupied": "◩", "empty": "□", "urgent": "▨"}
            }
            
            def get_icon(state):
                romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
                
                if style_name == "numbers":
                    if name in romans:
                        return str(romans.index(name) + 1)
                    return name
                elif style_name == "roman":
                    # If already roman from bspwmrc, just return
                    if name in romans:
                        return name
                    try:
                        idx = int(name) - 1
                        if 0 <= idx < 10:
                            return romans[idx]
                    except:
                        pass
                    return name
                elif style_name == "icons_numbers":
                    disp_name = str(romans.index(name) + 1) if name in romans else name
                    ic = style_icons["circles"][state]
                    return f"{disp_name} {ic}"
                elif style_name in style_icons:
                    return style_icons[style_name][state]
                return style_icons["circles"][state]
            
            # Icon & Color
            icon = get_icon("empty")
            color = COLOR_EMPTY
            
            # Priority: Focused > Urgent > Occupied > Empty
            if is_focused:
                icon = get_icon("focused")
                color = focus_color
            elif is_occupied:
                icon = get_icon("occupied")
                if color_mode.startswith("heatmap"):
                    color = interpolate_color(window_count, gradient_end)
                else:
                    color = rgb_to_hex(COLOR_WHITE)
            else:
                icon = get_icon("empty")
                color = COLOR_EMPTY
            
            item = f"%{{A1:bspc desktop -f {name}:}}%{{F{color}}}{icon}%{{F-}}%{{A}}"
            item = f" {item} "
            
            output.append(item)
            
    return "".join(output)

def main():
    # Listen to events
    # We can perform a loop with 'bspc subscribe report' which is efficient
    
    process = subprocess.Popen(
        ["bspc", "subscribe", "report"],
        stdout=subprocess.PIPE,
        text=True
    )
    
    # Initial print
    print(generate_polybar_string(get_state()), flush=True)
    
    for line in process.stdout:
        # On any report event, re-generate string
        # 'report' covers focus change, window open/close/move
        print(generate_polybar_string(get_state()), flush=True)

if __name__ == "__main__":
    main()
