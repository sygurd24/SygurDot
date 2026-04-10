#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import time
import locale

CONFIG_FILE = os.path.expanduser("~/.config/polybar/date.json")
THEME_STR = 'window { width: 500px; } listview { lines: 8; } element-text { font: "JetBrainsMono Nerd Font Mono 12"; }'

ICON_CHECK = ""

def set_lang_locale():
    lang_file = os.path.expanduser("~/.config/dotfiles/language")
    lang = "en"
    if os.path.exists(lang_file):
        try:
            with open(lang_file, "r") as f:
                lang = f.read().strip()
        except:
            pass
    else:
        lang = os.environ.get("LANG", "en").split("_")[0].split(".")[0]

    locale_map = {
        "es": "es_ES.UTF-8",
        "en": "en_US.UTF-8",
        "pt": "pt_BR.UTF-8",
        "fr": "fr_FR.UTF-8",
        "ru": "ru_RU.UTF-8"
    }
    loc = locale_map.get(lang, "en_US.UTF-8")
    try:
        locale.setlocale(locale.LC_TIME, loc)
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, "C")
        except:
            pass
    return lang

def L(lang, translations):
    if lang in translations:
        return translations[lang]
    if 'en' in translations:
        return translations['en']
    return list(translations.values())[0]

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"format": "%H:%M"}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def main():
    lang = set_lang_locale()
    config = load_config()
    current_fmt = config.get("format", "%H:%M")
    
    formats = [
        ("%H:%M", L(lang, {"es": "14:30 (24h)", "en": "14:30 (24h)", "pt": "14:30 (24h)", "fr": "14:30 (24h)", "ru": "14:30 (24h)"})),
        ("%H:%M:%S", L(lang, {"es": "14:30:05 (24h + seg)", "en": "14:30:05 (24h + sec)", "pt": "14:30:05 (24h + seg)", "fr": "14:30:05 (24h + sec)", "ru": "14:30:05 (24h + сек)"})),
        ("%I:%M %p", L(lang, {"es": "02:30 PM (12h)", "en": "02:30 PM (12h)", "pt": "02:30 PM (12h)", "fr": "02:30 PM (12h)", "ru": "02:30 PM (12h)"})),
        ("%I:%M:%S %p", L(lang, {"es": "02:30:05 PM (12h + seg)", "en": "02:30:05 PM (12h + sec)", "pt": "02:30:05 PM (12h + seg)", "fr": "02:30:05 PM (12h + sec)", "ru": "02:30:05 PM (12h + сек)"})),
        ("%Y-%m-%d %H:%M", L(lang, {"es": "2023-10-25 14:30 (Fecha + Hora)", "en": "2023-10-25 14:30 (Date + Time)", "pt": "2023-10-25 14:30 (Data + Hora)", "fr": "2023-10-25 14:30 (Date + Heure)", "ru": "2023-10-25 14:30 (Дата + Время)"})),
        ("%Y-%m-%d %H:%M:%S", L(lang, {"es": "2023-10-25 14:30:05 (Fecha + Hora + seg)", "en": "2023-10-25 14:30:05 (Date + Time + sec)", "pt": "2023-10-25 14:30:05 (Data + Hora + seg)", "fr": "2023-10-25 14:30:05 (Date + Heure + sec)", "ru": "2023-10-25 14:30:05 (Дата + Время + сек)"})),
        ("%a, %d %b - %H:%M", L(lang, {"es": "Wed, 25 Oct - 14:30 (Día + Hora)", "en": "Wed, 25 Oct - 14:30 (Day + Time)", "pt": "Wed, 25 Oct - 14:30 (Dia + Hora)", "fr": "Wed, 25 Oct - 14:30 (Jour + Heure)", "ru": "Wed, 25 Oct - 14:30 (День + Время)"})),
        ("%a, %d %b - %H:%M:%S", L(lang, {"es": "Wed, 25 Oct - 14:30:05 (Día + Hora + seg)", "en": "Wed, 25 Oct - 14:30:05 (Day + Time + sec)", "pt": "Wed, 25 Oct - 14:30:05 (Dia + Hora + seg)", "fr": "Wed, 25 Oct - 14:30:05 (Jour + Heure + sec)", "ru": "Wed, 25 Oct - 14:30:05 (День + Время + сек)"}))
    ]
    
    options = []
    for fmt, desc in formats:
        example = time.strftime(fmt)
        label = f"{desc} -> {example}"
        if current_fmt == fmt:
            options.append(f"{ICON_CHECK} {label}")
        else:
            options.append(f"  {label}")
            
    input_str = "\n".join(options)
    prompt = L(lang, {"es": "Formato de Fecha y Hora", "en": "Date & Time Format", "pt": "Formato de Data e Hora", "fr": "Format de Date et Heure", "ru": "Формат даты и времени"})
    
    cmd = ["rofi", "-dmenu", "-i", "-theme-str", THEME_STR, "-p", prompt, "-format", "i"]
    res = subprocess.run(cmd, input=input_str, text=True, capture_output=True)
    
    if res.returncode != 0: return # Cancel
    
    try:
        idx = int(res.stdout.strip())
        if 0 <= idx < len(formats):
            config["format"] = formats[idx][0]
            save_config(config)
    except:
        pass

if __name__ == "__main__":
    main()
