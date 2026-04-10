#!/usr/bin/env python3
import subprocess
import os
import sys
import json

CONFIG_FILE = os.path.expanduser("~/.config/polybar/temperature.json")
THEME_STR = 'window { width: 500px; } listview { lines: 6; } element-text { font: "JetBrainsMono Nerd Font Mono 12"; }'

ICON_CHECK = ""
ICON_TEMP = ""

def get_lang():
    lang_file = os.path.expanduser("~/.config/dotfiles/language")
    if os.path.exists(lang_file):
        try:
            with open(lang_file, "r") as f:
                return f.read().strip()
        except:
            pass
    return os.environ.get("LANG", "en").split("_")[0].split(".")[0]

def L(translations):
    lang = get_lang()
    if lang in translations:
        return translations[lang]
    if 'en' in translations:
        return translations['en']
    return list(translations.values())[0]

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                # migrate old boolean to string
                if "show_text" in config:
                    config["display_mode"] = "always" if config["show_text"] else "never"
                    del config["show_text"]
                if "display_mode" not in config:
                    config["display_mode"] = "never"
                return config
        except:
            pass
    
    # Fallback to old state file for backwards compatibility
    old_state = os.path.exists("/tmp/polybar_temp_state")
    return {"display_mode": "always" if old_state else "never", "unit": "C"}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    # Trigger Polybar update
    subprocess.run(["polybar-msg", "action", "temperature", "hook", "0"], capture_output=True)

def main():
    config = load_config()
    
    unit = config.get("unit", "C")
    display_mode = config.get("display_mode", "never")
    
    # Options
    # Mode: always
    label_always = L({
        "es": "Mostrar icono y cantidad siempre",
        "en": "Always show icon and value",
        "pt": "Sempre mostrar ícone e valor",
        "fr": "Toujours afficher l'icône et la valeur",
        "ru": "Всегда показывать значок и значение"
    })
    if display_mode == "always": label_always = f"{ICON_CHECK} {label_always}"
    else: label_always = f"  {label_always}"
    
    # Mode: never
    label_never = L({
        "es": "Mostrar solo icono",
        "en": "Show icon only",
        "pt": "Mostrar apenas ícone",
        "fr": "Afficher uniquement l'icône",
        "ru": "Показывать только значок"
    })
    if display_mode == "never": label_never = f"{ICON_CHECK} {label_never}"
    else: label_never = f"  {label_never}"

    # Mode: warning
    label_warning = L({
        "es": "Mostrar cantidad si está caliente",
        "en": "Show value if hot",
        "pt": "Mostrar valor se estiver quente",
        "fr": "Afficher la valeur si chaud",
        "ru": "Показывать значение, если горячо"
    })
    if display_mode == "warning": label_warning = f"{ICON_CHECK} {label_warning}"
    else: label_warning = f"  {label_warning}"
    
    label_c = "Celsius (°C)"
    if unit == "C": label_c = f"{ICON_CHECK} {label_c}"
    else: label_c = f"  {label_c}"
    
    label_f = "Fahrenheit (°F)"
    if unit == "F": label_f = f"{ICON_CHECK} {label_f}"
    else: label_f = f"  {label_f}"
    
    label_k = "Kelvin (K)"
    if unit == "K": label_k = f"{ICON_CHECK} {label_k}"
    else: label_k = f"  {label_k}"
    
    options = [
        label_always,
        label_never,
        label_warning,
        label_c,
        label_f,
        label_k
    ]
    
    input_str = "\n".join(options)
    prompt = L({"es": "Configuración de Temperatura", "en": "Temperature Config", "pt": "Configuração de Temperatura", "fr": "Configuration de Température", "ru": "Настройки температуры"})
    
    cmd = ["rofi", "-dmenu", "-i", "-theme-str", THEME_STR, "-p", prompt, "-format", "s"]
    res = subprocess.run(cmd, input=input_str, text=True, capture_output=True)
    
    if res.returncode != 0: return # Cancel
    
    choice = res.stdout.strip()
    
    # Using simple substring matches to determine the choice
    if "siempre" in choice or "Always" in choice or "Sempre" in choice or "Toujours" in choice or "Всегда" in choice:
        config["display_mode"] = "always"
        save_config(config)
    elif "solo icono" in choice or "icon only" in choice or "apenas" in choice or "uniquement" in choice or "только" in choice:
        config["display_mode"] = "never"
        save_config(config)
    elif "caliente" in choice or "hot" in choice or "quente" in choice or "chaud" in choice or "горячо" in choice:
        config["display_mode"] = "warning"
        save_config(config)
    elif "Celsius" in choice:
        config["unit"] = "C"
        save_config(config)
    elif "Fahrenheit" in choice:
        config["unit"] = "F"
        save_config(config)
    elif "Kelvin" in choice:
        config["unit"] = "K"
        save_config(config)

if __name__ == "__main__":
    main()
