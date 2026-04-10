#!/usr/bin/env python3
import dbus
import os
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import sys
import subprocess
import time

# Instant Battery for Polybar (Fixed Gradient & Optimized)
# - No threads: Using GLib.timeout_add for animations.
# - Direct Monitoring: Targeted at battery_BAT0 for lower latency.
# - Charging Gradient: White -> Green (Smooth interpolation).

# Colors
COLOR_CHARGING = "%{F#00FF00}" # Green
COLOR_DISCHARGING = "%{F#00BCD4}" # Turquoise
COLOR_FULL = "%{F#00FF00}" # Green
COLOR_END = "%{F-}"

# Icons
ICONS_RAMP = ["", "", "", "", ""]
ICON_FULL = ""

def get_lang():
    lang_file = os.path.expanduser("~/.config/dotfiles/language")
    if os.path.exists(lang_file):
        try:
            with open(lang_file, "r") as f:
                return f.read().strip()
        except:
            pass
    # Fallback to system locale
    return os.environ.get("LANG", "en").split("_")[0].split(".")[0]

def L(translations):
    """
    translations is a dict like {'es': 'Hola', 'en': 'Hello', ...}
    """
    lang = get_lang()
    # Fallback order: lang -> en -> first available
    if lang in translations:
        return translations[lang]
    if 'en' in translations:
        return translations['en']
    return list(translations.values())[0]

# Gradient Colors (Turquoise -> Orange -> Red)
# High: Turquoise
COLOR_HIGH_RGB = (0, 188, 212)   # #00BCD4
# Mid: Orange (Warning)
COLOR_MID_RGB = (255, 165, 0)    # #FFA500
# Low: Red (Critical)
COLOR_LOW_RGB = (255, 0, 0)      # #FF0000

# Charging Gradient (White -> Green)
# Starting slightly off-white to make the green transition more obvious
CHARGING_START_RGB = (255, 255, 255) # White
CHARGING_END_RGB = (0, 255, 0)       # Green

# Global State
current_state = 0 # 1=Charging, 2=Discharging, etc.
current_percentage = 0.0
anim_frame = 0
anim_timer_id = 0

# Critical Blink State
critical_blink_state = True # True=Color, False=Empty/Dim
critical_timer_id = 0
critical_notified = False

# Power supply paths (resolved dynamically for portability)
POWER_SUPPLY_BASE = "/sys/class/power_supply"
BAT_PATH = None
AC_PATH = None
BAT_NOW_PATH = None
BAT_FULL_PATH = None
BAT_STATUS_PATH = None
AC_ONLINE_PATH = None

def find_supply_by_type(target_type):
    try:
        for name in os.listdir(POWER_SUPPLY_BASE):
            type_path = os.path.join(POWER_SUPPLY_BASE, name, "type")
            try:
                with open(type_path, "r") as f:
                    if f.read().strip().lower() == target_type.lower():
                        return os.path.join(POWER_SUPPLY_BASE, name)
            except:
                continue
    except:
        pass
    return None

def pick_first_existing(base_path, candidates):
    if not base_path:
        return None
    for fname in candidates:
        path = os.path.join(base_path, fname)
        if os.path.exists(path):
            return path
    return None

def init_power_supply_paths():
    global BAT_PATH, AC_PATH, BAT_NOW_PATH, BAT_FULL_PATH, BAT_STATUS_PATH, AC_ONLINE_PATH
    BAT_PATH = find_supply_by_type("Battery")
    AC_PATH = find_supply_by_type("Mains")
    BAT_NOW_PATH = pick_first_existing(BAT_PATH, ["energy_now", "charge_now"])
    BAT_FULL_PATH = pick_first_existing(
        BAT_PATH,
        ["energy_full", "charge_full", "energy_full_design", "charge_full_design"]
    )
    BAT_STATUS_PATH = os.path.join(BAT_PATH, "status") if BAT_PATH else None
    AC_ONLINE_PATH = os.path.join(AC_PATH, "online") if AC_PATH else None

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def get_discharging_color(pct):
    if pct > 75:
        return COLOR_DISCHARGING
    
    # Gradient Logic:
    # 75% -> 30% : High (Turquoise) -> Mid (Orange)
    # 30% -> 0%  : Mid (Orange) -> Low (Red)
    
    mid_point = 30.0
    high_point = 75.0
    
    if pct > mid_point:
        # Interpolate High -> Mid
        # pct: 75 -> 30
        # t:   0  -> 1
        t = (high_point - pct) / (high_point - mid_point)
        start_c = COLOR_HIGH_RGB
        end_c = COLOR_MID_RGB
    else:
        # Interpolate Mid -> Low
        # pct: 30 -> 0
        # t:   0  -> 1
        t = (mid_point - pct) / mid_point
        start_c = COLOR_MID_RGB
        end_c = COLOR_LOW_RGB

    r = start_c[0] + (end_c[0] - start_c[0]) * t
    g = start_c[1] + (end_c[1] - start_c[1]) * t
    b = start_c[2] + (end_c[2] - start_c[2]) * t
    
    return f"%{{F{rgb_to_hex((r,g,b))}}}"

def get_charging_text_color(pct):
    # Precise Gradient:
    # Uses the fractional part of the percentage for the color transition.
    # 45.0% -> White
    # 45.9% -> Green
    decimal_part = pct - int(pct)
    t = decimal_part 
    
    r = CHARGING_START_RGB[0] + (CHARGING_END_RGB[0] - CHARGING_START_RGB[0]) * t
    g = CHARGING_START_RGB[1] + (CHARGING_END_RGB[1] - CHARGING_START_RGB[1]) * t
    b = CHARGING_START_RGB[2] + (CHARGING_END_RGB[2] - CHARGING_START_RGB[2]) * t
    return f"%{{F{rgb_to_hex((r,g,b))}}}"

def get_icon_for_percentage(pct):
    idx = int(pct / 20)
    if idx >= 5: idx = 4
    return ICONS_RAMP[idx]

def render():
    global current_state, current_percentage, anim_frame
    
    # Aesthetic Fix:
    # If battery is > 98%, just show 100% to avoid the "stuck at 99%" anxiety
    # caused by trickle charging.
    if current_percentage >= 99.0:
        pct_int = 100
    else:
        pct_int = int(current_percentage)
    
    # Critical Battery Blink (<= 5% and Discharging)
    if pct_int <= 5 and current_state != 1 and current_state != 4:
        icon = ICONS_RAMP[0] # Empty battery
        if critical_blink_state:
            # Critical Red
            color_code = f"%{{F{rgb_to_hex(COLOR_LOW_RGB)}}}"
        else:
            # Dimmed / White for blink effect
            color_code = "%{F#333333}" # Dark Gray for 'off' state of blink
        
        print(f"{color_code}{icon} {pct_int}%{COLOR_END}", flush=True)
        return
    
    if current_state == 1 and pct_int < 99: # Charging
        icon = ICONS_RAMP[anim_frame]
        # Icon -> Green
        # Text -> Precise Fractional Gradient (White -> Green)
        text_color = get_charging_text_color(current_percentage)
        print(f"{COLOR_CHARGING}{icon} {text_color}{pct_int}%{COLOR_END}", flush=True)
    elif current_state == 4 or (current_state == 1 and pct_int >= 99): # Full
        print(f"{COLOR_FULL}{ICON_FULL} {pct_int}%{COLOR_END}", flush=True)
    else: # Discharging / Others
        icon = get_icon_for_percentage(current_percentage)
        color_code = get_discharging_color(current_percentage)
        print(f"{color_code}{icon} {pct_int}%{COLOR_END}", flush=True)

def animation_callback():
    global anim_frame, current_state
    if current_state == 1:
        anim_frame = (anim_frame + 1) % 5
        render()
        return True # Keep timer running
    return False # Stop timer

def critical_anim_callback():
    global critical_blink_state, current_percentage, current_state
    
    # Verify we are still in critical state
    # Ensure consistency with start condition
    if int(current_percentage) > 5 or current_state == 1 or current_state == 4:
        return False
        
    critical_blink_state = not critical_blink_state
    render()
    return True

def update_timer():
    global anim_timer_id, current_state, critical_timer_id, current_percentage
    
    # Charging Animation
    if current_state == 1:
        if anim_timer_id == 0:
            anim_timer_id = GLib.timeout_add(750, animation_callback)
    else:
        if anim_timer_id != 0:
            GLib.source_remove(anim_timer_id)
            anim_timer_id = 0

    # Critical Battery Blink (<= 5% and Discharging)
    if int(current_percentage) <= 5 and current_state != 1 and current_state != 4:
        if critical_timer_id == 0:
            critical_timer_id = GLib.timeout_add(500, critical_anim_callback)
    else:
        if critical_timer_id != 0:
            GLib.source_remove(critical_timer_id)
            critical_timer_id = 0
            critical_blink_state = True # Reset to visible


def update_from_sysfs():
    global current_state, current_percentage, critical_notified
    try:
        # Resolve paths on first run or if hardware changed
        if BAT_PATH is None or BAT_NOW_PATH is None or BAT_FULL_PATH is None or BAT_STATUS_PATH is None:
            init_power_supply_paths()
        if BAT_PATH is None or BAT_NOW_PATH is None or BAT_FULL_PATH is None or BAT_STATUS_PATH is None:
            return

        # Read raw energy values for precision
        with open(BAT_NOW_PATH, "r") as f:
            now = int(f.read().strip())
        with open(BAT_FULL_PATH, "r") as f:
            full = int(f.read().strip())

        if full == 0:
            return
        
        # Calculate precise float percentage
        current_percentage = (now / full) * 100.0
        
        with open(BAT_STATUS_PATH, "r") as f:
            status = f.read().strip()
            
        ac_online = 0
        if AC_ONLINE_PATH and os.path.exists(AC_ONLINE_PATH):
            with open(AC_ONLINE_PATH, "r") as f:
                ac_online = int(f.read().strip())

        if status == "Charging":
            current_state = 1
            if int(current_percentage) > 5:
                 critical_notified = False
        elif status == "Discharging":
            current_state = 2
            if int(current_percentage) <= 5 and not critical_notified:
                 try:
                     title = L({"es": "Batería Baja", "en": "Low Battery", "pt": "Bateria Fraca", "fr": "Batterie Faible", "ru": "Низкий заряд"})
                     msg = L({"es": "5% restante", "en": "5% remaining", "pt": "5% restante", "fr": "5% restant", "ru": "Осталось 5%"})
                     subprocess.run(['notify-send', '-u', 'critical', title, msg])
                     critical_notified = True
                 except:
                     pass
        elif status == "Full":
            current_state = 4
            critical_notified = False
        elif (status == "Not charging" or status == "Unknown") and ac_online == 1:
            # If plugged in but not charging (likely full or threshold), show as Full
            current_state = 4
            critical_notified = False
        else:
            current_state = 0
            
    except Exception as e:
        # Fallback to DBus if sysfs fails
        pass

def handle_properties(changed):
    global current_state, current_percentage
    dirty = False
    
    # Prioritize SYSFS reading whenever a DBus signal comes in
    # DBus signals tell us *when* to update, but SYSFS tells us *what* the precise value is.
    update_from_sysfs()
    
    # Update timer state based on new current_state
    update_timer()
    
    dirty = True
            
    if dirty:
        render()

def signal_handler(*args, **kwargs):
    # Robust handler to prevent "missing positional argument" errors
    # PropertiesChanged usually sends: (interface, changed, invalidated)
    # path_keyword adds 'path' to kwargs.
    
    path = kwargs.get('path')
    if not path:
        return

    # Try to find the 'changed' dict among args
    # usually it's the second argument (index 1)
    if len(args) > 1 and isinstance(args[1], dict):
        changed = args[1]
        handle_properties(changed)
    elif len(args) > 0 and isinstance(args[0], dict):
        # Fallback if interface arg is skipped for some reason
        handle_properties(args[0])

def main():
    global current_state, current_percentage
    
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    
    # Initial Read
    update_from_sysfs()
    
    if current_percentage == 0.0:
        # Emergency DBus Fallback if SysFS didn't work initially
        try:
             upower = dbus.Interface(
                 bus.get_object("org.freedesktop.UPower", "/org/freedesktop/UPower"),
                 "org.freedesktop.UPower"
             )
             for obj_path in upower.EnumerateDevices():
                 up_obj = bus.get_object("org.freedesktop.UPower", obj_path)
                 iface = dbus.Interface(up_obj, "org.freedesktop.DBus.Properties")
                 dev_type = int(iface.Get("org.freedesktop.UPower.Device", "Type"))
                 if dev_type == 2:  # Battery
                     current_percentage = float(iface.Get("org.freedesktop.UPower.Device", "Percentage"))
                     state_int = int(iface.Get("org.freedesktop.UPower.Device", "State"))
                     current_state = state_int
                     break
        except:
             pass

    update_timer()
    render()
    
    # Listen to UPower just for the trigger
    bus.add_signal_receiver(
        signal_handler,
        dbus_interface="org.freedesktop.DBus.Properties",
        signal_name="PropertiesChanged",
        path_keyword="path"
    )
    
    # Also add a slow timer to force update from sysfs occasionally
    # incase signals are missed or micro-charging happens silently
    GLib.timeout_add_seconds(2, lambda: (update_from_sysfs() or True) and (render() or True))
    
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
