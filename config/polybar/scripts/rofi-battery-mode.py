#!/usr/bin/env python3
import subprocess
import os
import sys

# Battery Mode Selector for Polybar / Rofi
# Allows setting charge threshold to 60%, 80%, or 100%

THRESHOLD_FILE = "/sys/class/power_supply/BAT0/charge_control_end_threshold"
THEME_STR = 'window { width: 500px; } listview { lines: 6; } element-text { font: "JetBrainsMono Nerd Font Mono 12"; }'

# Icons
ICON_FULL = "󰁹"
ICON_BALANCED = "󰂄"
ICON_SAVER = "󱊢"
ICON_CHECK = ""

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

def get_current_threshold():
    if not os.path.exists(THRESHOLD_FILE):
        return None
    try:
        with open(THRESHOLD_FILE, "r") as f:
            return f.read().strip()
    except:
        return None

def set_threshold(value):
    # Adjust value by +1 for 60/80 modes to reach the target Linux percentage
    # (Hardware often stops at value-1)
    actual_value = value
    if value in [60, 80]:
        actual_value = value + 1
        
    cmd = f'echo {actual_value} | sudo /usr/bin/tee {THRESHOLD_FILE}'
    try:
        subprocess.run(["sh", "-c", cmd], check=True, capture_output=True)
        
        # Save to config for persistence across reboots
        conf_file = os.path.expanduser("~/.config/battery-charge-threshold")
        with open(conf_file, "w") as f:
            f.write(str(actual_value))
            
        msg = L({
            "es": f"Modo de batería cambiado a {value}%",
            "en": f"Battery mode changed to {value}%",
            "pt": f"Modo de bateria alterado para {value}%",
            "fr": f"Mode de batterie changé à {value}%",
            "ru": f"Режим батареи изменен на {value}%"
        })
        title = L({"es": "Batería", "en": "Battery", "pt": "Bateria", "fr": "Batterie", "ru": "Батарея"})
        subprocess.Popen(["notify-send", title, msg, "-i", "battery-good"])
    except subprocess.CalledProcessError as e:
        title = L({"es": "Error", "en": "Error", "pt": "Erro", "fr": "Erreur", "ru": "Ошибка"})
        subprocess.Popen(["notify-send", title, f"Failed to set threshold: {e.stderr.decode()}", "-i", "dialog-error"])

def main():
    if not os.path.exists(THRESHOLD_FILE):
        # Specific theme for error dialog that matches the main system theme
        THEME_ERROR = 'window { border: 3px; border-color: #7aa2f7; border-radius: 12px; background-color: #2b2e37; width: 600px; } ' \
                      'mainbox { background-color: #2b2e37; padding: 20px; } ' \
                      'textbox { text-color: #c0caf5; background-color: #2b2e37; font: "JetBrainsMono Nerd Font Bold 12"; }'
        
        msg = L({
            "es": "Tu computadora no soporta límites de batería (no se encontró el archivo de control)",
            "en": "Your computer does NOT support battery limits (control file not found)",
            "pt": "Seu computador não suporta limites de bateria (arquivo de controle não encontrado)",
            "fr": "Votre ordinateur ne prend PAS en charge les limites de batterie (fichier de contrôle introuvable)",
            "ru": "Ваш компьютер не поддерживает ограничения заряда батареи (файл управления не найден)"
        })
        cmd = ["rofi", "-e", msg, "-theme-str", THEME_ERROR]
        subprocess.run(cmd)
        return

    current_raw = get_current_threshold() or "100"
    
    # Compensate for display: if hardware says 81, we show 80.
    current = current_raw
    if current_raw == "81": current = "80"
    elif current_raw == "61": current = "60"
    
    options = []
    
    # Mode 100%
    label_100 = f"{ICON_FULL} " + L({
        "es": "Carga Completa (100%)",
        "en": "Full Capacity (100%)",
        "pt": "Carga Completa (100%)",
        "fr": "Capacité Complète (100%)",
        "ru": "Полный заряд (100%)"
    })
    if current == "100": label_100 = f"{ICON_CHECK} {label_100}"
    options.append(label_100)
    
    # Mode 80%
    label_80 = f"{ICON_BALANCED} " + L({
        "es": "Modo Balanceado (80%)",
        "en": "Balanced Mode (80%)",
        "pt": "Modo Balanceado (80%)",
        "fr": "Mode Équilibré (80%)",
        "ru": "Сбалансированный режим (80%)"
    })
    if current == "80": label_80 = f"{ICON_CHECK} {label_80}"
    options.append(label_80)
    
    # Mode 60%
    label_60 = f"{ICON_SAVER} " + L({
        "es": "Máxima Vida Útil (60%)",
        "en": "Maximum Lifespan (60%)",
        "pt": "Vida Útil Máxima (60%)",
        "fr": "Durée de vie maximale (60%)",
        "ru": "Максимальный срок службы (60%)"
    })
    if current == "60": label_60 = f"{ICON_CHECK} {label_60}"
    options.append(label_60)
    
    input_str = "\n".join(options)
    prompt = L({"es": "Modo de Batería", "en": "Battery Mode", "pt": "Modo de Bateria", "fr": "Mode Batterie", "ru": "Режим батареи"})
    
    cmd = ["rofi", "-dmenu", "-i", "-theme-str", THEME_STR, "-p", prompt, "-format", "s"]
    res = subprocess.run(cmd, input=input_str, text=True, capture_output=True)
    
    if res.returncode != 0: return # Cancel
    
    choice = res.stdout.strip()
    
    if "100%" in choice:
        set_threshold(100)
    elif "80%" in choice:
        set_threshold(80)
    elif "60%" in choice:
        set_threshold(60)

if __name__ == "__main__":
    main()
