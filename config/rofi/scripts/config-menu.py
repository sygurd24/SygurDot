#!/usr/bin/env python3
import subprocess
import os
import sys

# Dotfiles Configuration Menu
# Handles system-wide settings like Language

LANG_FILE = os.path.expanduser("~/.config/dotfiles/language")
POLY_ENABLED_FILE = os.path.expanduser("~/.config/dotfiles/polybar_modules_enabled")
THEME_STR = 'window { width: 600px; } listview { columns: 1; lines: 10; } element-text { font: "JetBrainsMono Nerd Font Mono 11"; }'

# Icons
ICON_LANG = "󰗊 "
ICON_KB = "󰌌 "
ICON_CHECK = " "
ICON_BACK = " "
ICON_ES = "󰗊 ES "
ICON_EN = "󰗊 EN "
ICON_PT = "󰗊 PT "
ICON_FR = "󰗊 FR "
ICON_RU = "󰗊 RU "
ICON_POLYBAR = "󱓡 "
ICON_TEMP = " "
ICON_CURSOR = "󰆿 "
ICON_WALLPAPER = "󰸉 "


def get_current_lang():
    if os.path.exists(LANG_FILE):
        with open(LANG_FILE, "r") as f:
            return f.read().strip()
    # Fallback to system locale
    sys_lang = os.environ.get("LANG", "en").split("_")[0].split(".")[0]
    return sys_lang

def get_current_layout():
    kb_file = os.path.expanduser("~/.config/dotfiles/keyboard")
    if os.path.exists(kb_file):
        with open(kb_file, "r") as f:
            saved = f.read().strip()
            if saved: return saved

    layout = "us"
    variant = ""
    try:
        res = subprocess.run(["setxkbmap", "-query"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if "layout:" in line:
                layout = line.split(":")[1].strip().split(",")[0]
            elif "variant:" in line:
                variant = line.split(":")[1].strip().split(",")[0]
    except:
        pass
    
    if variant:
        return f"{layout}({variant})"
    return layout

def L(translations):
    """
    translations is a dict like {'es': 'Hola', 'en': 'Hello', ...}
    """
    lang = get_current_lang()
    # Fallback order: lang -> en -> first available
    if lang in translations:
        return translations[lang]
    if 'en' in translations:
        return translations['en']
    return list(translations.values())[0]

def set_lang(lang):
    os.makedirs(os.path.dirname(LANG_FILE), exist_ok=True)
    with open(LANG_FILE, "w") as f:
        f.write(lang)
    
    # Update system locales for shell environment
    locale_map = {
        "es": "es_ES.UTF-8",
        "en": "en_US.UTF-8",
        "pt": "pt_BR.UTF-8",
        "fr": "fr_FR.UTF-8",
        "ru": "ru_RU.UTF-8"
    }
    
    val = locale_map.get(lang, "en_US.UTF-8")
    locale_file = os.path.expanduser("~/.config/dotfiles/locale.sh")

    with open(locale_file, "w") as f:
        f.write(f'export LANG="{val}"\n')
        f.write(f'export LC_ALL="{val}"\n')
        f.write(f'export LANGUAGE="{lang}"\n')

    msg_map = {
        "es": "Idioma cambiado a Español",
        "en": "Language changed to English",
        "pt": "Idioma alterado para Português",
        "fr": "Langue changée en Français",
        "ru": "Язык изменен на Русский"
    }
    
    msg = msg_map.get(lang, "Language changed")
    subprocess.Popen(["notify-send", L({"es": "Sistema", "en": "System", "pt": "Sistema", "fr": "Système", "ru": "Система"}), msg, "-i", "preferences-desktop-locale"])

def set_layout(layout_str):
    # Handle layout(variant) format
    if "(" in layout_str and layout_str.endswith(")"):
        layout = layout_str.split("(")[0]
        variant = layout_str.split("(")[1][:-1]
        subprocess.run(["setxkbmap", "-layout", layout, "-variant", variant])
    else:
        subprocess.run(["setxkbmap", layout_str])

    # Persist the setting
    kb_file = os.path.expanduser("~/.config/dotfiles/keyboard")
    os.makedirs(os.path.dirname(kb_file), exist_ok=True)
    with open(kb_file, "w") as f:
        f.write(layout_str)
    
    # Update keyboard.sh for startup persistence
    kb_script = os.path.expanduser("~/.config/dotfiles/keyboard.sh")
    with open(kb_script, "w") as f:
        f.write(f'#!/bin/sh\n')
        if "(" in layout_str and layout_str.endswith(")"):
            layout = layout_str.split("(")[0]
            variant = layout_str.split("(")[1][:-1]
            f.write(f'setxkbmap -layout {layout} -variant {variant}\n')
        else:
            f.write(f'setxkbmap {layout_str}\n')
            
    os.chmod(kb_script, 0o755)
    
    msg = L({
        "es": f"Teclado cambiado a {layout_str.upper()}",
        "en": f"Keyboard changed to {layout_str.upper()}",
        "pt": f"Teclado alterado para {layout_str.upper()}",
        "fr": f"Clavier changé en {layout_str.upper()}",
        "ru": f"Клавиатура изменена на {layout_str.upper()}"
    })
    subprocess.Popen(["notify-send", L({"es": "Sistema", "en": "System", "pt": "Sistema", "fr": "Système", "ru": "Система"}), msg, "-i", "input-keyboard"])

def show_rofi(prompt, options, markup=True, theme_str=None):
    if theme_str is None:
        theme_str = THEME_STR
    input_str = "\n".join(options)
    cmd = ["rofi", "-dmenu", "-i", "-theme-str", theme_str, "-p", prompt, "-format", "i"]
    if markup:
        cmd.append("-markup-rows")
    
    res = subprocess.run(cmd, input=input_str, text=True, capture_output=True)
    if res.returncode != 0:
        return -1
    try:
        return int(res.stdout.strip())
    except:
        return -1

def keyboard_menu():
    while True:
        current = get_current_layout()
        options = []
        
        layouts = [
            ("us", "English (US)"),
            ("us(intl)", "English (US, intl. dead keys)"),
            ("us(altgr-intl)", "English (US, altgr-intl.)"),
            ("es", "Español (ES)"),
            ("latam", "Latinoamericano (LATAM)"),
            ("gb", "English (UK)"),
            ("br", "Portuguese (Brazil)"),
            ("fr", "French (FR)"),
            ("ru", "Russian (RU)")
        ]
        
        # Add current layout first
        for code, name in layouts:
            if current == code:
                options.append(f"{ICON_CHECK} {ICON_KB} {name}")
                break
        
        # Add others
        for code, name in layouts:
            if current != code:
                options.append(f"{ICON_KB} {name}")
        
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        idx = show_rofi(L({"es": "Teclado", "en": "Keyboard", "pt": "Teclado", "fr": "Clavier", "ru": "Клавиатура"}), options)
        
        if idx == -1 or idx == len(options) - 1: # Cancel or Back
            break
        
        # Determine selected layout
        # The list has: 1 current + (N-1) others + Volver
        # To be safe, we rebuild a list of codes in the same order as options
        ordered_codes = []
        # Find current
        for code, name in layouts:
            if current == code:
                ordered_codes.append(code)
                break
        # Find others
        for code, name in layouts:
            if current != code:
                ordered_codes.append(code)
        
        if idx < len(ordered_codes):
            set_layout(ordered_codes[idx])

def language_menu():
    while True:
        current = get_current_lang()
        options = []
        
        langs = [
            ("es", ICON_ES, "Español"),
            ("en", ICON_EN, "English"),
            ("pt", ICON_PT, "Português"),
            ("fr", ICON_FR, "Français"),
            ("ru", ICON_RU, "Русский")
        ]
        
        for code, icon, name in langs:
            label = f"{icon} {name}"
            if current == code:
                label = f"{ICON_CHECK} {label}"
            options.append(label)
        
        # Unsupported System Language info
        supported_codes = [l[0] for l in langs]
        if current not in supported_codes:
            sys_label = f"󰗊 {current.upper()} (auto english - no support)"
            options.append(f"{ICON_CHECK} {sys_label}")
        
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        idx = show_rofi(L({"es": "Idioma", "en": "Language", "pt": "Idioma", "fr": "Langue", "ru": "Язык"}), options)
        
        if idx == -1 or idx == len(options) - 1:
            break
        
        # Map back to code
        if idx < len(langs):
            set_lang(langs[idx][0])


def get_enabled_polybar_modules():
    default_modules = ["temperature", "cpu", "memory", "nvidia", "npu", "pulseaudio", "mic", "wlan", "bluetooth", "battery", "powermenu"]
    if not os.path.exists(POLY_ENABLED_FILE):
        return default_modules
    try:
        with open(POLY_ENABLED_FILE, "r") as f:
            content = f.read().strip()
            # return empty list if content is empty, instead of returning default_modules
            return content.split()
    except:
        return default_modules

def set_enabled_polybar_modules(modules):
    os.makedirs(os.path.dirname(POLY_ENABLED_FILE), exist_ok=True)
    with open(POLY_ENABLED_FILE, "w") as f:
        f.write(" ".join(modules))
    
    # Restart polybar to apply changes
    # Use launch.sh to ensure everything is reloaded correctly
    launch_script = os.path.expanduser("~/dotfiles/config/polybar/launch.sh")
    if os.path.exists(launch_script):
        subprocess.Popen([launch_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["pkill", "-USR1", "polybar"]) # Fallback

def border_submenu():
    import json
    CONFIG_FILE = os.path.expanduser("~/.config/bspwm/border_config.json")
    
    def load_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"enabled": True, "profile": "blue_teal", "speed": "medium"}

    def save_config(config):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def profile_submenu(config):
        profiles = [
            ("blue_teal", L({"es": "Azul-Turquesa", "en": "Blue-Teal", "pt": "Azul-Turquesa", "fr": "Bleu-Turquoise", "ru": "Сине-Бирюзовый"})),
            ("cyberpunk", L({"es": "Cyberpunk", "en": "Cyberpunk", "pt": "Cyberpunk", "fr": "Cyberpunk", "ru": "Киберпанк"})),
            ("sunset", L({"es": "Atardecer", "en": "Sunset", "pt": "Pôr do sol", "fr": "Coucher de soleil", "ru": "Закат"})),
            ("ocean", L({"es": "Océano", "en": "Ocean", "pt": "Oceano", "fr": "Océan", "ru": "Океан"}))
        ]
        while True:
            current = config.get("profile", "blue_teal")
            options = [f"{ICON_CHECK if current == p[0] else '   '} {p[1]}" for p in profiles]
            options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
            idx = show_rofi(L({"es": "Perfil", "en": "Profile", "pt": "Perfil", "fr": "Profil", "ru": "Профиль"}), options)
            if idx == -1 or idx == len(options) - 1: break
            config["profile"] = profiles[idx][0]
            save_config(config)

    def intensity_submenu(config):
        intensities = [
            ("high", L({"es": "Alta", "en": "High", "pt": "Alta", "fr": "Haute", "ru": "Высокая"})),
            ("medium", L({"es": "Media", "en": "Medium", "pt": "Média", "fr": "Moyenne", "ru": "Средняя"})),
            ("low", L({"es": "Baja", "en": "Low", "pt": "Baixa", "fr": "Basse", "ru": "Низкая"}))
        ]
        while True:
            current = config.get("intensity", "medium")
            options = [f"{ICON_CHECK if current == i[0] else '   '} {i[1]}" for i in intensities]
            options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
            idx = show_rofi(L({"es": "Intensidad", "en": "Intensity", "pt": "Intensidade", "fr": "Intensité", "ru": "Интенсивность"}), options)
            if idx == -1 or idx == len(options) - 1: break
            config["intensity"] = intensities[idx][0]
            save_config(config)

    def speed_submenu(config):
        speeds = [
            ("fast", L({"es": "Rápida", "en": "Fast", "pt": "Rápida", "fr": "Rapide", "ru": "Быстро"})),
            ("medium", L({"es": "Media", "en": "Medium", "pt": "Média", "fr": "Moyenne", "ru": "Средняя"})),
            ("slow", L({"es": "Lenta", "en": "Slow", "pt": "Lenta", "fr": "Lente", "ru": "Медленно"}))
        ]
        while True:
            current = config.get("speed", "medium")
            options = [f"{ICON_CHECK if current == s[0] else '   '} {s[1]}" for s in speeds]
            options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
            idx = show_rofi(L({"es": "Velocidad", "en": "Speed", "pt": "Velocidade", "fr": "Vitesse", "ru": "Скорость"}), options)
            if idx == -1 or idx == len(options) - 1: break
            config["speed"] = speeds[idx][0]
            save_config(config)

    while True:
        config = load_config()
        enabled = config.get("enabled", True)
        show_border = config.get("show_border", True)
        
        options = [
            f"{ICON_CHECK if show_border else '   '} " + L({"es": "Mostrar marco de color", "en": "Show colored border", "pt": "Mostrar borda colorida", "fr": "Afficher bordure colorée", "ru": "Показывать цветную рамку"}),
            f"{ICON_CHECK if enabled else '   '} " + L({"es": "Animación activada", "en": "Animation enabled", "pt": "Animação ativada", "fr": "Animation activée", "ru": "Анимация включена"}),
            L({"es": "Seleccionar perfil de color", "en": "Select color profile", "pt": "Selecionar perfil de cor", "fr": "Sélectionner profil couleur", "ru": "Выбрать профиль цвета"}),
            L({"es": "Seleccionar intensidad", "en": "Select intensity", "pt": "Selecionar intensidade", "fr": "Sélectionner intensité", "ru": "Выбрать интенсивность"}),
            L({"es": "Seleccionar velocidad", "en": "Select speed", "pt": "Selecionar velocidade", "fr": "Sélectionner vitesse", "ru": "Выбрать скорость"}),
            f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"})
        ]
        
        idx = show_rofi(L({"es": "Configuración Borde", "en": "Border Config", "pt": "Configuração Borda", "fr": "Config. Bordure", "ru": "Настройка рамки"}), options)
        
        if idx == -1 or idx == 5: break
        elif idx == 0:
            config["show_border"] = not show_border
            save_config(config)
        elif idx == 1:
            config["enabled"] = not enabled
            save_config(config)
        elif idx == 2: profile_submenu(config)
        elif idx == 3: intensity_submenu(config)
        elif idx == 4: speed_submenu(config)

def bspwm_heatmap_submenu(config, save_config):
    variants = [
        ("heatmap_red_cyan", L({"es": "Blanco->Rojo (Foco Cyan)", "en": "White->Red (Focus Cyan)", "pt": "Branco->Vermelho (Foco Ciano)", "fr": "Blanc->Rouge (Focus Cyan)", "ru": "Белый->Красный (Фокус Голубой)"})),
        ("heatmap_red_teal", L({"es": "Blanco->Rojo (Foco Turquesa)", "en": "White->Red (Focus Teal)", "pt": "Branco->Vermelho (Foco Turquesa)", "fr": "Blanc->Rouge (Focus Sarcelle)", "ru": "Белый->Красный (Фокус Бирюзовый)"})),
        ("heatmap_cyan_teal", L({"es": "Blanco->Cyan (Foco Turquesa)", "en": "White->Cyan (Focus Teal)", "pt": "Branco->Ciano (Foco Turquesa)", "fr": "Blanc->Cyan (Focus Sarcelle)", "ru": "Белый->Голубой (Фокус Бирюзовый)"})),
        ("heatmap_neon", L({"es": "Blanco->Magenta (Foco Turquesa)", "en": "White->Magenta (Focus Teal)", "pt": "Branco->Magenta (Foco Turquesa)", "fr": "Blanc->Magenta (Focus Sarcelle)", "ru": "Белый->Пурпурный (Фокус Бирюзовый)"}))
    ]
    
    while True:
        current = config.get("color_mode", "heatmap_red_cyan")
        if not current.startswith("heatmap"):
            current = "heatmap_red_cyan"
            
        options = []
        for v_val, v_lbl in variants:
            options.append(f"{ICON_CHECK if current == v_val else '   '} {v_lbl}")
        
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        title = L({"es": "Variantes Heatmap", "en": "Heatmap Variants", "pt": "Variantes Heatmap", "fr": "Variantes Heatmap", "ru": "Варианты Heatmap"})
        idx = show_rofi(title, options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        if 0 <= idx < len(variants):
            config["color_mode"] = variants[idx][0]
            save_config(config)

def bspwm_submenu():
    import json
    CONFIG_FILE = os.path.expanduser("~/.config/polybar/bspwm.json")
    
    def load_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {
            "style": "circles",
            "color_mode": "heatmap_red_cyan",
            "hide_empty": False
        }

    def save_config(config):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        launch_script = os.path.expanduser("~/dotfiles/config/polybar/launch.sh")
        if os.path.exists(launch_script):
            subprocess.Popen([launch_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    styles = [
        ("circles", L({"es": "Estilo: Círculos (  )", "en": "Style: Circles (  )", "pt": "Estilo: Círculos (  )", "fr": "Style: Cercles (  )", "ru": "Стиль: Круги (  )"})),
        ("numbers", L({"es": "Estilo: Números Normales (1 2 3)", "en": "Style: Normal Numbers (1 2 3)", "pt": "Estilo: Números Normais (1 2 3)", "fr": "Style: Nombres Normaux (1 2 3)", "ru": "Стиль: Обычные Числа (1 2 3)"})),
        ("roman", L({"es": "Estilo: Números Romanos (I II III)", "en": "Style: Roman Numerals (I II III)", "pt": "Estilo: Numerais Romanos (I II III)", "fr": "Style: Chiffres Romains (I II III)", "ru": "Стиль: Римские Цифры (I II III)"})),
        ("icons_numbers", L({"es": "Estilo: Números + Iconos", "en": "Style: Numbers + Icons", "pt": "Estilo: Números + Ícones", "fr": "Style: Nombres + Icônes", "ru": "Стиль: Числа + Значки"})),
        ("squares", L({"es": "Estilo: Cuadrados (■ ◩ □)", "en": "Style: Squares (■ ◩ □)", "pt": "Estilo: Quadrados (■ ◩ □)", "fr": "Style: Carrés (■ ◩ □)", "ru": "Стиль: Квадраты (■ ◩ □)"}))
    ]
    
    color_modes = [
        ("heatmap", L({"es": "Color: Mapa de Calor 󰁕", "en": "Color: Heatmap 󰁕", "pt": "Cor: Mapa de Calor 󰁕", "fr": "Couleur: Carte Thermique 󰁕", "ru": "Цвет: Тепловая карта 󰁕"})),
        ("static", L({"es": "Color: Estático (Blanco)", "en": "Color: Static (White)", "pt": "Cor: Estático (Branco)", "fr": "Couleur: Statique (Blanc)", "ru": "Цвет: Статический (Белый)"}))
    ]

    while True:
        config = load_config()
        current_style = config.get("style", "circles")
        current_color = config.get("color_mode", "heatmap_red_cyan")
        if current_color == "heatmap": current_color = "heatmap_red_cyan"
        is_heatmap = current_color.startswith("heatmap")
        
        hide_empty = config.get("hide_empty", False)
        
        options = []
        
        for s_val, s_lbl in styles:
            options.append(f"{ICON_CHECK if current_style == s_val else '   '} {s_lbl}")
            
        for c_val, c_lbl in color_modes:
            checked = '   '
            if c_val == "heatmap" and is_heatmap:
                checked = ICON_CHECK
            elif c_val == current_color:
                checked = ICON_CHECK
            options.append(f"{checked} {c_lbl}")
            
        # Add a new option for border settings
        options.append(f"󰈈 " + L({"es": "Configuración de borde", "en": "Border Config", "pt": "Configuração da borda", "fr": "Configuration de bordure", "ru": "Настройка рамки"}))

        options.append(f"{ICON_CHECK if hide_empty else '   '} " + L({"es": "Ocultar espacios vacíos", "en": "Hide empty spaces", "pt": "Ocultar espaços vazios", "fr": "Masquer les espaces vides", "ru": "Скрывать пустые рабочие места"}))
        
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        title = L({"es": "Configuración BSPWM", "en": "BSPWM Config", "pt": "Configuração BSPWM", "fr": "Configuration BSPWM", "ru": "Настройка BSPWM"})
        idx = show_rofi(title, options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        # Map idx to actions
        if 0 <= idx < len(styles):
            config["style"] = styles[idx][0]
            save_config(config)
        elif len(styles) <= idx < len(styles) + len(color_modes):
            c_val = color_modes[idx - len(styles)][0]
            if c_val == "heatmap":
                bspwm_heatmap_submenu(config, save_config)
            else:
                config["color_mode"] = c_val
                save_config(config)
        elif idx == len(styles) + len(color_modes):
            border_submenu()
        elif idx == len(styles) + len(color_modes) + 1:
            config["hide_empty"] = not hide_empty
            save_config(config)

def polybar_menu():
    while True:
        enabled = get_enabled_polybar_modules()
        all_modules = ["date", "temperature", "cpu", "memory", "nvidia", "npu", "pulseaudio", "mic", "brightness", "wlan", "bluetooth", "battery", "camera", "powermenu"]
        
        # Mapping of module names to their Polybar icons
        module_icons = {
            "date": "󰃰",
            "temperature": "",
            "cpu": "",
            "memory": "",
            "nvidia": "󰢮",
            "npu": "󱚟",
            "pulseaudio": "",
            "mic": "󰍬",
            "brightness": "󰃠",
            "wlan": "󰖩",
            "bluetooth": "",
            "battery": "󰁹",
            "camera": "",
            "powermenu": ""
        }
        
        module_names = {
            "date": L({"es": "Fecha", "en": "Date &amp; Time", "pt": "Data", "fr": "Date", "ru": "Дата"}),
            "temperature": L({"es": "Temperatura", "en": "Temperature", "pt": "Temperatura", "fr": "Température", "ru": "Температура"}),
            "cpu": L({"es": "CPU", "en": "CPU", "pt": "CPU", "fr": "CPU", "ru": "ЦП"}),
            "memory": L({"es": "RAM", "en": "RAM", "pt": "RAM", "fr": "RAM", "ru": "ОЗУ"}),
            "nvidia": L({"es": "NVIDIA", "en": "NVIDIA", "pt": "NVIDIA", "fr": "NVIDIA", "ru": "NVIDIA"}),
            "npu": L({"es": "NPU", "en": "NPU", "pt": "NPU", "fr": "NPU", "ru": "NPU"}),
            "pulseaudio": L({"es": "Volumen", "en": "Volume", "pt": "Volume", "fr": "Volume", "ru": "Громкость"}),
            "mic": L({"es": "Micrófono", "en": "Microphone", "pt": "Microfone", "fr": "Microphone", "ru": "Микрофон"}),
            "brightness": L({"es": "Brillo", "en": "Brightness", "pt": "Brilho", "fr": "Luminosité", "ru": "Яркость"}),
            "wlan": L({"es": "Wi-Fi", "en": "Wi-Fi", "pt": "Wi-Fi", "fr": "Wi-Fi", "ru": "Wi-Fi"}),
            "bluetooth": L({"es": "Bluetooth", "en": "Bluetooth", "pt": "Bluetooth", "fr": "Bluetooth", "ru": "Bluetooth"}),
            "battery": L({"es": "Batería", "en": "Battery", "pt": "Bateria", "fr": "Batterie", "ru": "Батарея"}),
            "camera": L({"es": "Cámara", "en": "Camera", "pt": "Câmera", "fr": "Caméra", "ru": "Камера"}),
            "powermenu": L({"es": "Apagado", "en": "Power Menu", "pt": "Energia", "fr": "Alimentation", "ru": "Питание"})
        }
        
        options = []
        
        # Removed bspwm from here
        
        for mod in all_modules:
            icon = module_icons.get(mod, "󰅪") # Fallback to a generic icon
            mod_name = module_names.get(mod, mod)
            label = f"{icon} {mod_name}"
            if mod in enabled:
                label = f"{ICON_CHECK} {label}"
            else:
                label = f"   {label}" # Alignment
            options.append(label)
        
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        prompt = L({
            "es": "Módulos Polybar",
            "en": "Polybar Modules",
            "pt": "Módulos Polybar",
            "fr": "Modules Polybar",
            "ru": "Модули Polybar"
        })
        
        custom_theme = 'window { width: 500px; } listview { columns: 2; lines: 8; } element-text { font: "JetBrainsMono Nerd Font Mono 11"; }'
        idx = show_rofi(prompt, options, theme_str=custom_theme)
        
        if idx == -1 or idx == len(options) - 1: # Cancel or Back
            break
            
        # The offset for togglable modules is 0 because BSPWM is no longer here
        selected_mod = all_modules[idx]

        if selected_mod == "temperature":
            temperature_submenu(enabled, all_modules)
        elif selected_mod == "date":
            date_submenu(enabled, all_modules)
        elif selected_mod == "pulseaudio":
            display_submenu("pulseaudio", enabled, all_modules, module_names["pulseaudio"], "~/.config/polybar/volume.json")
        elif selected_mod == "mic":
            display_submenu("mic", enabled, all_modules, module_names["mic"], "~/.config/polybar/mic.json")
        elif selected_mod == "brightness":
            display_submenu("brightness", enabled, all_modules, module_names["brightness"], "~/.config/polybar/brightness.json")
        elif selected_mod == "camera":
            camera_submenu(enabled, all_modules)
        else:
            if selected_mod in enabled:
                enabled.remove(selected_mod)
            else:
                enabled.append(selected_mod)
            
            # Sort enabled modules based on their original order in all_modules
            ordered_enabled = [mod for mod in all_modules if mod in enabled]
            set_enabled_polybar_modules(ordered_enabled)

def display_submenu(module_name, enabled, all_modules, title_str, config_path):
    import json
    CONFIG_FILE = os.path.expanduser(config_path)
    
    def load_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"display_mode": "icon_only"}

    def save_config(config):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)

    while True:
        config = load_config()
        display_mode = config.get("display_mode", "icon_only")
        
        is_module_enabled = module_name in enabled
        
        toggle_lbl_text = L({
            "es": "Módulo Polybar: ACTIVADO",
            "en": "Polybar Module: ENABLED",
            "pt": "Módulo Polybar: ATIVADO",
            "fr": "Module Polybar: ACTIVÉ",
            "ru": "Модуль Polybar: ВКЛЮЧЕН"
        }) if is_module_enabled else L({
            "es": "Módulo Polybar: DESACTIVADO",
            "en": "Polybar Module: DISABLED",
            "pt": "Módulo Polybar: DESATIVADO",
            "fr": "Module Polybar: DÉSACTIVÉ",
            "ru": "Модуль Polybar: ОТКЛЮЧЕН"
        })
        toggle_lbl = f"{ICON_CHECK if is_module_enabled else '   '} {toggle_lbl_text}"
        
        label_always = f"{ICON_CHECK if display_mode == 'always' else '   '} " + L({"es": "Mostrar siempre icono y números", "en": "Always show icon and numbers", "pt": "Sempre mostrar ícone e números", "fr": "Toujours afficher l'icône et les nombres", "ru": "Всегда показывать значок и числа"})
        label_icon_only = f"{ICON_CHECK if display_mode == 'icon_only' else '   '} " + L({"es": "Mostrar solo icono (ocultar números)", "en": "Show icon only (hide numbers)", "pt": "Mostrar apenas ícone (ocultar números)", "fr": "Afficher uniquement l'icône", "ru": "Показывать только значок"})
        
        options = [toggle_lbl, label_always, label_icon_only]
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        idx = show_rofi(title_str, options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        if idx == 0:
            if module_name in enabled:
                enabled.remove(module_name)
            else:
                enabled.append(module_name)
            ordered_enabled = [mod for mod in all_modules if mod in enabled]
            set_enabled_polybar_modules(ordered_enabled)
        elif idx == 1:
            config["display_mode"] = "always"
            save_config(config)
        elif idx == 2:
            config["display_mode"] = "icon_only"
            save_config(config)

def temperature_submenu(enabled, all_modules):
    import json
    CONFIG_FILE = os.path.expanduser("~/.config/polybar/temperature.json")
    
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
        old_state = os.path.exists("/tmp/polybar_temp_state")
        return {"display_mode": "always" if old_state else "never", "unit": "C"}

    def save_config(config):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        subprocess.run(["polybar-msg", "action", "temperature", "hook", "0"], capture_output=True)

    while True:
        config = load_config()
        display_mode = config.get("display_mode", "never")
        unit = config.get("unit", "C")
        
        is_module_enabled = "temperature" in enabled
        
        toggle_lbl_text = L({
            "es": "Módulo Polybar: ACTIVADO",
            "en": "Polybar Module: ENABLED",
            "pt": "Módulo Polybar: ATIVADO",
            "fr": "Module Polybar: ACTIVÉ",
            "ru": "Модуль Polybar: ВКЛЮЧЕН"
        }) if is_module_enabled else L({
            "es": "Módulo Polybar: DESACTIVADO",
            "en": "Polybar Module: DISABLED",
            "pt": "Módulo Polybar: DESATIVADO",
            "fr": "Module Polybar: DÉSACTIVÉ",
            "ru": "Модуль Polybar: ОТКЛЮЧЕН"
        })
        toggle_lbl = f"{ICON_CHECK if is_module_enabled else '   '} {toggle_lbl_text}"
        
        label_always = f"{ICON_CHECK if display_mode == 'always' else '   '} " + L({"es": "Mostrar icono y cantidad siempre", "en": "Always show icon and value", "pt": "Sempre mostrar ícone e valor", "fr": "Toujours afficher l'icône et la valeur", "ru": "Всегда показывать значок и значение"})
        label_never = f"{ICON_CHECK if display_mode == 'never' else '   '} " + L({"es": "Mostrar solo icono", "en": "Show icon only", "pt": "Mostrar apenas ícone", "fr": "Afficher uniquement l'icône", "ru": "Показывать только значок"})
        label_warning = f"{ICON_CHECK if display_mode == 'warning' else '   '} " + L({"es": "Mostrar cantidad si está caliente", "en": "Show value if hot", "pt": "Mostrar valor se estiver quente", "fr": "Afficher la valeur si chaud", "ru": "Показывать значение, если горячо"})
        
        label_c = f"{ICON_CHECK if unit == 'C' else '   '} Celsius (°C)"
        label_f = f"{ICON_CHECK if unit == 'F' else '   '} Fahrenheit (°F)"
        label_k = f"{ICON_CHECK if unit == 'K' else '   '} Kelvin (K)"
        
        options = [
            toggle_lbl,
            label_always,
            label_never,
            label_warning,
            label_c,
            label_f,
            label_k,
            f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"})
        ]
        
        idx = show_rofi(L({"es": "Temperatura", "en": "Temperature", "pt": "Temperatura", "fr": "Température", "ru": "Температура"}), options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        if idx == 0:
            if "temperature" in enabled:
                enabled.remove("temperature")
            else:
                enabled.append("temperature")
            ordered_enabled = [mod for mod in all_modules if mod in enabled]
            set_enabled_polybar_modules(ordered_enabled)
        elif idx == 1:
            config["display_mode"] = "always"
            save_config(config)
        elif idx == 2:
            config["display_mode"] = "never"
            save_config(config)
        elif idx == 3:
            config["display_mode"] = "warning"
            save_config(config)
        elif idx == 4:
            config["unit"] = "C"
            save_config(config)
        elif idx == 5:
            config["unit"] = "F"
            save_config(config)
        elif idx == 6:
            config["unit"] = "K"
            save_config(config)

def date_submenu(enabled, all_modules):
    import json
    import time
    import locale
    CONFIG_FILE = os.path.expanduser("~/.config/polybar/date.json")
    
    lang = get_current_lang()
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

    formats = [
        ("%H:%M", L({"es": "14:30 (24h)", "en": "14:30 (24h)", "pt": "14:30 (24h)", "fr": "14:30 (24h)", "ru": "14:30 (24h)"})),
        ("%H:%M:%S", L({"es": "14:30:05 (24h+seg)", "en": "14:30:05 (24h+sec)", "pt": "14:30:05 (24h+seg)", "fr": "14:30:05 (24h+sec)", "ru": "14:30:05 (24h+сек)"})),
        ("%I:%M %p", L({"es": "02:30 PM (12h)", "en": "02:30 PM (12h)", "pt": "02:30 PM (12h)", "fr": "02:30 PM (12h)", "ru": "02:30 PM (12h)"})),
        ("%I:%M:%S %p", L({"es": "02:30:05 PM (12h+seg)", "en": "02:30:05 PM (12h+sec)", "pt": "02:30:05 PM (12h+seg)", "fr": "02:30:05 PM (12h+sec)", "ru": "02:30:05 PM (12h+сек)"})),
        ("%Y-%m-%d %H:%M", L({"es": "2023-10-25 14:30 (Fecha)", "en": "2023-10-25 14:30 (Date)", "pt": "2023-10-25 14:30 (Data)", "fr": "2023-10-25 14:30 (Date)", "ru": "2023-10-25 14:30 (Дата)"})),
        ("%Y-%m-%d %H:%M:%S", L({"es": "2023-10-25 14:30:05 (Fecha+s)", "en": "2023-10-25 14:30:05 (Date+s)", "pt": "2023-10-25 14:30:05 (Data+s)", "fr": "2023-10-25 14:30:05 (Date+s)", "ru": "2023-10-25 14:30:05 (Дата+с)"})),
        ("%a, %d %b - %H:%M", L({"es": "Wed, 25 Oct - 14:30 (Día)", "en": "Wed, 25 Oct - 14:30 (Day)", "pt": "Wed, 25 Oct - 14:30 (Dia)", "fr": "Wed, 25 Oct - 14:30 (Jour)", "ru": "Wed, 25 Oct - 14:30 (День)"})),
        ("%a, %d %b - %H:%M:%S", L({"es": "Wed, 25 Oct - 14:30:05 (Día+s)", "en": "Wed, 25 Oct - 14:30:05 (Day+s)", "pt": "Wed, 25 Oct - 14:30:05 (Dia+s)", "fr": "Wed, 25 Oct - 14:30:05 (Jour+s)", "ru": "Wed, 25 Oct - 14:30:05 (День+с)"}))
    ]

    while True:
        config = load_config()
        current_fmt = config.get("format", "%H:%M")
        
        is_module_enabled = "date" in enabled
        
        toggle_lbl_text = L({
            "es": "Módulo Polybar: ACTIVADO",
            "en": "Polybar Module: ENABLED",
            "pt": "Módulo Polybar: ATIVADO",
            "fr": "Module Polybar: ACTIVÉ",
            "ru": "Модуль Polybar: ВКЛЮЧЕН"
        }) if is_module_enabled else L({
            "es": "Módulo Polybar: DESACTIVADO",
            "en": "Polybar Module: DISABLED",
            "pt": "Módulo Polybar: DESATIVADO",
            "fr": "Module Polybar: DÉSACTIVÉ",
            "ru": "Модуль Polybar: ОТКЛЮЧЕН"
        })
        toggle_lbl = f"{ICON_CHECK if is_module_enabled else '   '} {toggle_lbl_text}"
        
        options = [toggle_lbl]
        
        for fmt, desc in formats:
            example = time.strftime(fmt)
            label = f"{desc} -> {example}"
            options.append(f"{ICON_CHECK if current_fmt == fmt else '   '} {label}")
            
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        idx = show_rofi(L({"es": "Fecha y Hora", "en": "Date & Time", "pt": "Data e Hora", "fr": "Date et Heure", "ru": "Дата и время"}), options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        if idx == 0:
            if "date" in enabled:
                enabled.remove("date")
            else:
                enabled.append("date")
            ordered_enabled = [mod for mod in all_modules if mod in enabled]
            set_enabled_polybar_modules(ordered_enabled)
        elif 1 <= idx <= len(formats):
            config["format"] = formats[idx-1][0]
            save_config(config)

def get_current_cursor():
    cursor_file = os.path.expanduser("~/.config/dotfiles/cursor")
    if os.path.exists(cursor_file):
        with open(cursor_file, "r") as f:
            return f.read().strip()
    return "Bibata-Modern-Ice"

def set_cursor(cursor_theme):
    # Save to dotfiles state
    cursor_file = os.path.expanduser("~/.config/dotfiles/cursor")
    os.makedirs(os.path.dirname(cursor_file), exist_ok=True)
    with open(cursor_file, "w") as f:
        f.write(cursor_theme)

    # Update ~/.icons/default/index.theme
    index_theme_dir = os.path.expanduser("~/.icons/default")
    os.makedirs(index_theme_dir, exist_ok=True)
    with open(os.path.join(index_theme_dir, "index.theme"), "w") as f:
        f.write(f"[Icon Theme]\nInherits={cursor_theme}\n")

    # Update ~/.config/gtk-3.0/settings.ini
    gtk_settings = os.path.expanduser("~/.config/gtk-3.0/settings.ini")
    if os.path.exists(gtk_settings):
        with open(gtk_settings, "r") as f:
            lines = f.readlines()
        with open(gtk_settings, "w") as f:
            for line in lines:
                if line.startswith("gtk-cursor-theme-name"):
                    f.write(f"gtk-cursor-theme-name={cursor_theme}\n")
                else:
                    f.write(line)
    else:
        os.makedirs(os.path.dirname(gtk_settings), exist_ok=True)
        with open(gtk_settings, "w") as f:
            f.write(f"[Settings]\ngtk-cursor-theme-name={cursor_theme}\n")

    # Update ~/.Xresources
    xresources = os.path.expanduser("~/.Xresources")
    if os.path.exists(xresources):
        with open(xresources, "r") as f:
            lines = f.readlines()
        with open(xresources, "w") as f:
            found = False
            for line in lines:
                if line.startswith("Xcursor.theme:"):
                    f.write(f"Xcursor.theme: {cursor_theme}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"Xcursor.theme: {cursor_theme}\n")
    else:
        with open(xresources, "w") as f:
            f.write(f"Xcursor.theme: {cursor_theme}\n")

    # Apply
    subprocess.run(["xrdb", "-merge", xresources])
    subprocess.run(["xsetroot", "-cursor_name", "left_ptr"])

    msg = L({
        "es": f"Cursor cambiado a {cursor_theme}",
        "en": f"Cursor changed to {cursor_theme}",
        "pt": f"Cursor alterado para {cursor_theme}",
        "fr": f"Curseur changé en {cursor_theme}",
        "ru": f"Курсор изменен на {cursor_theme}"
    })
    subprocess.Popen(["notify-send", L({"es": "Sistema", "en": "System", "pt": "Sistema", "fr": "Système", "ru": "Система"}), msg, "-i", "input-mouse"])

def cursor_submenu():
    cursors = [
        ("Bibata-Modern-Ice", "Bibata Modern Ice"),
        ("Bibata-Modern-Classic", "Bibata Modern Classic"),
        ("macOS-Monterey", "macOS Monterey"),
        ("Nordzy-cursors", "Nordzy Cursors"),
        ("breeze_cursors", "Breeze Snow"),
        ("LyraB-cursors", "LyraB Cursors"),
        ("WinSur-dark-cursors", "WinSur Dark Cursors")
    ]
    
    while True:
        current = get_current_cursor()
        options = []
        
        # Add "Base/Default" option (Adwaita)
        if current == "Adwaita":
            options.append(f"{ICON_CHECK} Base (Adwaita)")
        else:
            options.append(f"   Base (Adwaita)")
        
        for code, name in cursors:
            if current == code:
                options.append(f"{ICON_CHECK} {name}")
            else:
                options.append(f"   {name}")
        
        options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
        
        idx = show_rofi(L({"es": "Cursor", "en": "Cursor", "pt": "Cursor", "fr": "Curseur", "ru": "Курсор"}), options)
        
        if idx == -1 or idx == len(options) - 1:
            break
        
        if idx == 0:
            set_cursor("Adwaita")
        elif 0 < idx <= len(cursors):
            set_cursor(cursors[idx-1][0])

def wallpaper_menu():
    mode_file = os.path.expanduser("~/.config/dotfiles/wallpaper_mode")
    custom_file = os.path.expanduser("~/.config/dotfiles/custom_wallpaper_path")
    
    while True:
        current_mode = "dynamic"
        if os.path.exists(mode_file):
            with open(mode_file, "r") as f:
                current_mode = f.read().strip()
                
        dynamic_lbl = L({"es": "Modo Dinámico (Por hora)", "en": "Dynamic Mode (Time of day)", "pt": "Modo Dinâmico (Por hora)", "fr": "Mode Dynamique (Par heure)", "ru": "Динамический режим (По времени)"})
        custom_lbl = L({"es": "Elegir Wallpaper...", "en": "Choose Wallpaper...", "pt": "Escolher Wallpaper...", "fr": "Choisir Fond d'écran...", "ru": "Выбрать обои..."})
        
        options = [
            f"{ICON_CHECK if current_mode == 'dynamic' else '   '} {dynamic_lbl}",
            f"{ICON_CHECK if current_mode == 'custom' else '   '} {custom_lbl}",
            f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"})
        ]
        
        title = L({"es": "Fondo de Pantalla", "en": "Wallpaper", "pt": "Papel de Parede", "fr": "Fond d'écran", "ru": "Обои"})
        idx = show_rofi(title, options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        os.makedirs(os.path.dirname(mode_file), exist_ok=True)
        if idx == 0:
            with open(mode_file, "w") as f: f.write("dynamic")
            subprocess.run(["pkill", "-USR1", "-f", "dynamic_wallpaper.sh"])
        elif idx == 1:
            wp_dir = os.path.expanduser("~/Pictures/Wallpapers")
            if os.path.exists(wp_dir):
                images = sorted([f for f in os.listdir(wp_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                while True:
                    current_custom = ""
                    if os.path.exists(custom_file):
                        with open(custom_file, "r") as f:
                            current_custom = f.read().strip()
                    
                    img_options = []
                    for img in images:
                        is_active = current_custom == os.path.join(wp_dir, img)
                        img_options.append(f"{ICON_CHECK if is_active else '   '} {img}")
                    
                    img_options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
                    
                    img_idx = show_rofi("Select Image", img_options)
                    if img_idx == -1 or img_idx == len(images):
                        break
                    
                    selected_path = os.path.join(wp_dir, images[img_idx])
                    with open(custom_file, "w") as f: f.write(selected_path)
                    with open(mode_file, "w") as f: f.write("custom")
                    subprocess.run(["pkill", "-USR1", "-f", "dynamic_wallpaper.sh"])

def picom_submenu():
    import re
    picom_conf_path = os.path.expanduser("~/dotfiles/config/picom/picom.conf")
    
    def read_picom_conf():
        try:
            with open(picom_conf_path, "r") as f:
                return f.read()
        except:
            return ""

    def write_picom_conf(content):
        with open(picom_conf_path, "w") as f:
            f.write(content)
        # Wait for picom to fully exit before restarting to avoid losing the compositor
        restart_cmd = "killall -q picom; while pgrep -x picom >/dev/null; do sleep 0.1; done; picom -b --config ~/dotfiles/config/picom/picom.conf"
        subprocess.Popen(restart_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    while True:
        conf = read_picom_conf()
        
        has_animations = re.search(r'^animations\s*=\s*\(', conf, re.MULTILINE) is not None
        has_shadow = re.search(r'^shadow\s*=\s*true;', conf, re.MULTILINE) is not None
        has_vsync = re.search(r'^vsync\s*=\s*true;', conf, re.MULTILINE) is not None
        
        lbl_anim = f"{ICON_CHECK if has_animations else '   '} " + L({"es": "Animaciones de ventanas", "en": "Window Animations", "pt": "Animações de janelas", "fr": "Animations de fenêtres", "ru": "Анимации окон"})
        lbl_shadow = f"{ICON_CHECK if has_shadow else '   '} " + L({"es": "Sombras", "en": "Shadows", "pt": "Sombras", "fr": "Ombres", "ru": "Тени"})
        lbl_vsync = f"{ICON_CHECK if has_vsync else '   '} " + L({"es": "VSync (Anti-tearing)", "en": "VSync (Anti-tearing)", "pt": "VSync (Anti-tearing)", "fr": "VSync (Anti-déchirure)", "ru": "VSync (Анти-разрыв)"})
        
        options = [
            lbl_anim,
            lbl_shadow,
            lbl_vsync,
            f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"})
        ]
        
        idx = show_rofi(L({"es": "Efectos Visuales (Picom)", "en": "Visual Effects (Picom)", "pt": "Efeitos Visuais (Picom)", "fr": "Effets Visuels (Picom)", "ru": "Визуальные эффекты (Picom)"}), options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        if idx == 0:
            if has_animations:
                new_conf = re.sub(r'^animations\s*=\s*\([\s\S]*?^\);', lambda m: "\n".join(["# " + line for line in m.group(0).split("\n")]), conf, flags=re.MULTILINE)
            else:
                new_conf = re.sub(r'^# animations\s*=\s*\([\s\S]*?^# \);', lambda m: "\n".join([line.replace("# ", "", 1) if line.startswith("# ") else line.replace("#", "", 1) if line.startswith("#") else line for line in m.group(0).split("\n")]), conf, flags=re.MULTILINE)
            write_picom_conf(new_conf)
        elif idx == 1:
            if has_shadow:
                new_conf = re.sub(r'^shadow\s*=\s*true;', 'shadow = false;', conf, flags=re.MULTILINE)
            else:
                new_conf = re.sub(r'^shadow\s*=\s*false;', 'shadow = true;', conf, flags=re.MULTILINE)
            write_picom_conf(new_conf)
        elif idx == 2:
            if has_vsync:
                new_conf = re.sub(r'^vsync\s*=\s*true;', 'vsync = false;', conf, flags=re.MULTILINE)
            else:
                new_conf = re.sub(r'^vsync\s*=\s*false;', 'vsync = true;', conf, flags=re.MULTILINE)
            write_picom_conf(new_conf)

def desktop_menu():
    while True:
        bspwm_text = L({"es": "Gestor de ventanas (BSPWM)", "en": "Window Manager (BSPWM)", "pt": "Gerenciador de Janelas (BSPWM)", "fr": "Gestionnaire de fenêtres (BSPWM)", "ru": "Оконный менеджер (BSPWM)"})
        polybar_text = L({"es": "Barra de estado (Polybar)", "en": "Status Bar (Polybar)", "pt": "Barra de status (Polybar)", "fr": "Barre d'état (Polybar)", "ru": "Строка состояния (Polybar)"})
        picom_text = L({"es": "Efectos Visuales (Picom)", "en": "Visual Effects (Picom)", "pt": "Efeitos Visuais (Picom)", "fr": "Effets Visuels (Picom)", "ru": "Визуальные эффекты (Picom)"})
        
        options = [
            f"󰕮 {bspwm_text}",
            f"{ICON_POLYBAR} {polybar_text}",
            f"󰗈 {picom_text}",
            f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"})
        ]
        
        title = L({"es": "Entorno", "en": "Desktop", "pt": "Ambiente", "fr": "Environnement", "ru": "Окружение"})
        idx = show_rofi(title, options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        if idx == 0:
            bspwm_submenu()
        elif idx == 1:
            polybar_menu()
        elif idx == 2:
            picom_submenu()

def main_menu():
    while True:
        lang_text = L({"es": "Idioma", "en": "Language", "pt": "Idioma", "fr": "Langue", "ru": "Язык"})
        kb_text = L({"es": "Teclado", "en": "Keyboard", "pt": "Teclado", "fr": "Clavier", "ru": "Клавиатура"})
        env_text = L({"es": "Entorno", "en": "Desktop", "pt": "Ambiente", "fr": "Environnement", "ru": "Окружение"})
        cursor_text = L({"es": "Cursor", "en": "Cursor", "pt": "Cursor", "fr": "Curseur", "ru": "Курсор"})
        wallpaper_text = L({"es": "Fondo", "en": "Wallpaper", "pt": "Papel de Parede", "fr": "Fond d'écran", "ru": "Обои"})
        config_text = L({"es": "Configuración", "en": "Configuration", "pt": "Configuração", "fr": "Configuration", "ru": "Настройка"})
        
        options = [
            f"{ICON_LANG} {lang_text}",
            f"{ICON_KB} {kb_text}",
            f"󰕮 {env_text}",
            f"{ICON_CURSOR} {cursor_text}",
            f"{ICON_WALLPAPER} {wallpaper_text}"
        ]
        
        idx = show_rofi(config_text, options)
        
        if idx == -1:
            break
            
        if idx == 0:
            language_menu()
        elif idx == 1:
            keyboard_menu()
        elif idx == 2:
            desktop_menu()
        elif idx == 3:
            cursor_submenu()
        elif idx == 4:
            wallpaper_menu()
        else:
            break

def camera_submenu(enabled, all_modules):
    import json
    CONFIG_FILE = os.path.expanduser("~/.config/polybar/camera.json")
    
    def load_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"color": "#00FF00", "blink": True, "speed": "medium"}

    def save_config(config):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def camera_color_submenu(config):
        colors = [
            ("#00FF00", L({"es": "Verde (Batería)", "en": "Green (Battery)", "pt": "Verde (Bateria)", "fr": "Vert (Batterie)", "ru": "Зеленый (Батарея)"})),
            ("#FF0000", L({"es": "Rojo Oscuro", "en": "Dark Red", "pt": "Vermelho Escuro", "fr": "Rouge Foncé", "ru": "Темно-красный"})),
            ("#00BCD4", L({"es": "Cian", "en": "Cyan", "pt": "Ciano", "fr": "Cyan", "ru": "Голубой"})),
            ("#FFFFFF", L({"es": "Blanco", "en": "White", "pt": "Branco", "fr": "Blanc", "ru": "Белый"})),
            ("#00FFB3", L({"es": "Turquesa", "en": "Teal", "pt": "Turquesa", "fr": "Sarcelle", "ru": "Бирюзовый"}))
        ]
        while True:
            current_color = config.get("color", "#00FF00")
            options = [f"{ICON_CHECK if current_color == hex_val else '   '} {name}" for hex_val, name in colors]
            options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
            
            idx = show_rofi(L({"es": "Color", "en": "Color", "pt": "Cor", "fr": "Couleur", "ru": "Цвет"}), options)
            if idx == -1 or idx == len(options) - 1:
                break
            if 0 <= idx < len(colors):
                config["color"] = colors[idx][0]
                save_config(config)

    def camera_speed_submenu(config):
        speeds = [
            ("fast", L({"es": "Rápida (0.3s)", "en": "Fast (0.3s)", "pt": "Rápida (0.3s)", "fr": "Rapide (0.3s)", "ru": "Быстро (0.3s)"})),
            ("medium", L({"es": "Media (0.6s)", "en": "Medium (0.6s)", "pt": "Média (0.6s)", "fr": "Moyenne (0.6s)", "ru": "Средняя (0.6s)"})),
            ("slow", L({"es": "Lenta (1.2s)", "en": "Slow (1.2s)", "pt": "Lenta (1.2s)", "fr": "Lente (1.2s)", "ru": "Медленно (1.2s)"}))
        ]
        while True:
            current_speed = config.get("speed", "medium")
            options = [f"{ICON_CHECK if current_speed == s_val else '   '} {name}" for s_val, name in speeds]
            options.append(f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
            
            idx = show_rofi(L({"es": "Velocidad", "en": "Speed", "pt": "Velocidade", "fr": "Vitesse", "ru": "Скорость"}), options)
            if idx == -1 or idx == len(options) - 1:
                break
            if 0 <= idx < len(speeds):
                config["speed"] = speeds[idx][0]
                save_config(config)

    while True:
        config = load_config()
        is_module_enabled = "camera" in enabled
        is_blinking = config.get("blink", True)
        
        toggle_lbl = f"{ICON_CHECK if is_module_enabled else '   '} " + (L({"es": "Módulo: ACTIVADO", "en": "Module: ENABLED", "pt": "Módulo: ATIVADO", "fr": "Module: ACTIVÉ", "ru": "Модуль: ВКЛЮЧЕН"}) if is_module_enabled else L({"es": "Módulo: DESACTIVADO", "en": "Module: DISABLED", "pt": "Módulo: DESATIVADO", "fr": "Module: DÉSACTIVÉ", "ru": "Модуль: ОТКЛЮЧЕН"}))
        color_lbl = f"  " + L({"es": "Cambiar Color...", "en": "Change Color...", "pt": "Alterar Cor...", "fr": "Changer Couleur...", "ru": "Изменить цвет..."})
        blink_lbl = f"{ICON_CHECK if is_blinking else '   '} " + (L({"es": "Parpadeo: ACTIVADO", "en": "Blink: ON", "pt": "Piscar: LIGADO", "fr": "Clignotement: ACTIVÉ", "ru": "Мерцание: ВКЛЮЧЕНО"}) if is_blinking else L({"es": "Parpadeo: DESACTIVADO", "en": "Blink: OFF", "pt": "Piscar: DESLIGADO", "fr": "Clignotement: DÉSACTIVÉ", "ru": "Мерцание: ВЫКЛЮЧЕНО"}))
        speed_lbl = f"󰥔  " + L({"es": "Velocidad...", "en": "Speed...", "pt": "Velocidade...", "fr": "Vitesse...", "ru": "Скорость..."})
        
        options = [
            toggle_lbl,
            color_lbl,
            blink_lbl,
            speed_lbl,
            f"{ICON_BACK} " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"})
        ]
        
        idx = show_rofi(L({"es": "Configuración Cámara", "en": "Camera Config", "pt": "Config. Câmera", "fr": "Config. Caméra", "ru": "Настройки Камеры"}), options)
        
        if idx == -1 or idx == len(options) - 1:
            break
            
        if idx == 0:
            if "camera" in enabled:
                enabled.remove("camera")
            else:
                enabled.append("camera")
            ordered_enabled = [mod for mod in all_modules if mod in enabled]
            set_enabled_polybar_modules(ordered_enabled)
        elif idx == 1:
            camera_color_submenu(config)
        elif idx == 2:
            config["blink"] = not is_blinking
            save_config(config)
        elif idx == 3:
            camera_speed_submenu(config)

def main():
    if len(sys.argv) > 1:
        enabled = get_enabled_polybar_modules()
        all_modules = ["date", "temperature", "cpu", "memory", "nvidia", "npu", "pulseaudio", "mic", "brightness", "wlan", "bluetooth", "battery", "camera", "powermenu"]
        if sys.argv[1] == "date":
            date_submenu(enabled, all_modules)
        elif sys.argv[1] == "temperature":
            temperature_submenu(enabled, all_modules)
        elif sys.argv[1] == "pulseaudio":
            display_submenu("pulseaudio", enabled, all_modules, L({"es": "Volumen", "en": "Volume", "pt": "Volume", "fr": "Volume", "ru": "Громкость"}), "~/.config/polybar/volume.json")
        elif sys.argv[1] == "mic":
            display_submenu("mic", enabled, all_modules, L({"es": "Micrófono", "en": "Microphone", "pt": "Microfone", "fr": "Microphone", "ru": "Микрофон"}), "~/.config/polybar/mic.json")
        elif sys.argv[1] == "brightness":
            display_submenu("brightness", enabled, all_modules, L({"es": "Brillo", "en": "Brightness", "pt": "Brilho", "fr": "Luminosité", "ru": "Яркость"}), "~/.config/polybar/brightness.json")
        elif sys.argv[1] == "camera":
            camera_submenu(enabled, all_modules)
        return
    main_menu()

if __name__ == "__main__":
    main()
