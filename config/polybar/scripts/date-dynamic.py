#!/usr/bin/env python3
import time
import json
import os
import sys
import locale

CONFIG_FILE = os.path.expanduser("~/.config/polybar/date.json")

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

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"format": "%H:%M", "show_alt": False}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def main():
    set_lang_locale()

    if len(sys.argv) > 1 and sys.argv[1] == "toggle":
        config = load_config()
        current_fmt = config.get("format", "%H:%M")
        
        formats = [
            "%H:%M",
            "%H:%M:%S",
            "%I:%M %p",
            "%I:%M:%S %p",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%a, %d %b - %H:%M",
            "%a, %d %b - %H:%M:%S"
        ]
        
        try:
            idx = formats.index(current_fmt)
            next_idx = (idx + 1) % len(formats)
            config["format"] = formats[next_idx]
        except ValueError:
            config["format"] = formats[0]
            
        save_config(config)
        return

    config = load_config()
    fmt = config.get("format", "%H:%M")
    
    print(time.strftime(fmt))

if __name__ == "__main__":
    main()
