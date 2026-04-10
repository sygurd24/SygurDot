#!/usr/bin/env python3
import subprocess
import time
import json
import math
import os

CONFIG_PATH = os.path.expanduser("~/.config/bspwm/border_config.json")

# Perfiles de color
PROFILES = {
    "blue_teal": ("#4682B4", "#40E0D0"), # Ajustado para la preferencia del usuario
    "cyberpunk": ("#FF00FF", "#40E0D0"),
    "sunset": ("#FF8C00", "#9400D3"),
    "ocean": ("#00008B", "#00FFFF")
}

# Intensidades (Multiplicadores de intensidad/saturación de color)
INTENSITIES = {
    "high": 1.0,
    "medium": 0.85,
    "low": 0.7
}

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {"enabled": True, "profile": "blue_teal", "intensity": "medium"}

def interpolate_color(c1, c2, t, intensity_factor):
    """Interpola y aplica factor de intensidad."""
    c1 = [int(c1[i:i+2], 16) for i in (1, 3, 5)]
    c2 = [int(c2[i:i+2], 16) for i in (1, 3, 5)]
    
    # Aplicar factor de intensidad (atenuar si es low)
    # Una forma simple es interpolar hacia un gris medio o simplemente oscurecer
    res = [int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)]
    res = [int(x * intensity_factor) for x in res]
    return "#{:02x}{:02x}{:02x}".format(*res)

def update_border():
    t = 0
    # Guardamos el perfil y velocidad actuales para detectar cambios y resetear 't' si es necesario
    last_profile = None
    
    while True:
        config = load_config()
        
        # Detectar cambio de perfil para resetear la animación
        current_profile = config.get("profile", "blue_teal")
        if current_profile != last_profile:
            t = 0
            last_profile = current_profile
            
        if not config.get("enabled", True):
            subprocess.run(["bspc", "config", "focused_border_color", "#00838F"])
            time.sleep(1)
            continue
            
        intensity_key = config.get("intensity", "medium")
        
        c1, c2 = PROFILES.get(current_profile, PROFILES["blue_teal"])
        factor = INTENSITIES.get(intensity_key, INTENSITIES["medium"])
        
        val = (math.sin(t) + 1) / 2
        current_color = interpolate_color(c1, c2, val, factor)
        
        subprocess.run(["bspc", "config", "focused_border_color", current_color])
        
        t += 0.1
        time.sleep(0.05)

if __name__ == "__main__":
    update_border()
