#!/usr/bin/env python3
import subprocess
import sys
import os
import re
import time
import shutil
import html
try:
    import dbus
except Exception:
    dbus = None

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

# Bluetooth Rofi Manager
# A robust replacement for the bash script to provide a "Manager-like" experience.

ROFI_CMD = ["rofi", "-dmenu", "-i", "-p", "Bluetooth", "-format", "s", "-markup-rows"]
# Match the requested theme or similar
THEME_STR = 'window { width: 800px; } listview { lines: 12; } element-text { font: "JetBrainsMono Nerd Font Mono 11"; }'

# Icons (Nerd Fonts to ensure visibility)
ICON_CONNECTED = ""
ICON_PAIRED = " " 
ICON_NEW = " "
ICON_SCAN = "󰍉" # Search icon
ICON_POWER_ON = "  " + L({"es": "Activar Bluetooth", "en": "Power On Bluetooth", "pt": "Ativar Bluetooth", "fr": "Activer Bluetooth", "ru": "Включить Bluetooth"})
ICON_POWER_OFF = "󰂲  " + L({"es": "Desactivar Bluetooth", "en": "Power Off Bluetooth", "pt": "Desativar Bluetooth", "fr": "Désactiver Bluetooth", "ru": "Выключить Bluetooth"})

# Device Type Icons (Simple heuristic based on Icon name from info)
DEVICE_ICONS = {
    "audio-card": "",
    "audio-headset": "",
    "audio-headphones": "",
    "input-keyboard": "⌨",
    "input-mouse": "󰍽",
    "phone": "",
    "computer": "💻",
    "default": ""
}

def run_cmd(args):
    try:
        # Run command and wait for it
        return subprocess.check_output(args, text=True).strip()
    except subprocess.CalledProcessError:
        return ""

def str_has_yes(value):
    return bool(re.search(r"\b(yes|sí|si|true|1)\b", value, re.IGNORECASE))

def parse_info_flag(info, labels):
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*:\s*(\S+)", info, re.IGNORECASE)
        if match:
            return str_has_yes(match.group(1))
    return False

def map_icon_name(icon_name):
    if not icon_name:
        return DEVICE_ICONS["default"]
    for key, icon in DEVICE_ICONS.items():
        if key in icon_name:
            return icon
    return DEVICE_ICONS["default"]

def get_bluez_objects():
    if dbus is None:
        return {}
    try:
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        return manager.GetManagedObjects()
    except Exception:
        return {}

def get_adapter_powered(objects=None):
    objs = objects if objects is not None else get_bluez_objects()
    if not objs:
        return None
    for _, interfaces in objs.items():
        adapter = interfaces.get("org.bluez.Adapter1")
        if adapter and bool(adapter.get("Powered", False)):
            return True
    return False

def get_device_props(mac, objects=None):
    objs = objects if objects is not None else get_bluez_objects()
    if not objs:
        return None
    mac_up = mac.upper()
    for _, interfaces in objs.items():
        dev = interfaces.get("org.bluez.Device1")
        if not dev:
            continue
        addr = str(dev.get("Address", "")).upper()
        if addr == mac_up:
            name = str(dev.get("Alias", "")) or str(dev.get("Name", ""))
            return {
                "connected": bool(dev.get("Connected", False)),
                "paired": bool(dev.get("Paired", False)),
                "trusted": bool(dev.get("Trusted", False)),
                "icon": str(dev.get("Icon", "")),
                "name": name,
            }
    return None

def get_device_state_from_info(info):
    return {
        "connected": parse_info_flag(info, ["Connected", "Conectado"]),
        "paired": parse_info_flag(info, ["Paired", "Emparejado", "Vinculado"]),
        "trusted": parse_info_flag(info, ["Trusted", "Confiable", "Confiado", "De confianza"]),
    }

def is_connected(mac):
    props = get_device_props(mac)
    if props is not None:
        return props["connected"]
    info = run_cmd(["bluetoothctl", "info", mac])
    return parse_info_flag(info, ["Connected", "Conectado"])

def get_device_icon(device_info):
    # bluetoothctl info returns "Icon: audio-card" etc
    match = re.search(r"Icon:\s+(\S+)", device_info)
    if match:
        return map_icon_name(match.group(1))
    return DEVICE_ICONS["default"]

def get_devices(scan_cache_path="/tmp/bt_scan_cache"):
    devices = {}
    objects = get_bluez_objects()
    
    # 1. Get ALL Known Devices (Paired + Connected + Trusted + Others)
    # 'devices' command lists available/known devices
    raw_all = run_cmd(["bluetoothctl", "devices"])
    for line in raw_all.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2:
            mac = parts[1]
            name = parts[2] if len(parts) > 2 else "Unknown"
            
            # Initial assumption: Not connected/paired yet, will check in loop
            devices[mac] = {"name": name, "paired": False, "connected": False, "trusted": False, "info": ""}

    # 2. Get Scanned Devices
    if os.path.exists(scan_cache_path):
        with open(scan_cache_path, "r") as f:
            for line in f:
                # Format: Device MAC Name
                parts = line.strip().split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    mac = parts[1]
                    name = parts[2]
                    if mac not in devices:
                        devices[mac] = {"name": name, "paired": False, "connected": False, "info": ""}

    # 3. Check Details & Filter
    final_devices = {}
    
    for mac, data in devices.items():
        props = get_device_props(mac, objects)
        if props is not None:
            if props.get("name"):
                data["name"] = props["name"]
            data["connected"] = props["connected"]
            data["paired"] = props["paired"]
            data["trusted"] = props["trusted"]
            data["icon"] = map_icon_name(props.get("icon", ""))
        else:
            info = run_cmd(["bluetoothctl", "info", mac])
            data["info"] = info
            state = get_device_state_from_info(info)
            data["connected"] = state["connected"]
            data["paired"] = state["paired"]
            data["trusted"] = state["trusted"]
            data["icon"] = get_device_icon(info)
        
        # FILTER RULE: Show if Correlated (Paired/Connected/Trusted) OR in recent Scan Cache
        # How to check if in scan cache? logic above added it to 'devices'.
        # We can try to guess: if not paired/trusted/connected -> implies it came from scan cache OR bluetoothctl devices (ghost).
        # User wants "si desconecto... se siga mostrando".
        # This implies: If it is Known (bluetoothctl devices), show it?
        # But user also wants clean menu.
        # Compromise: Show if Paired OR Connected OR Trusted.
        # AND Show if explicitly presently in Scan Cache (Scan just ran).
        
        # To distinguish Scan Cache items vs Old Ghosts:
        # We don't track origin easily here.
        # But devices coming from 'bluetoothctl devices' might be old ghosts.
        # Devices from 'scan_cache' are fresh.
        # Let's assume if we are looking at it, and it's NOT connected/paired/trusted, we ONLY show it if it was in the scan cache file?
        # Re-read scan cache to be sure?
        # Actually, simpler: Show everything?
        # User complained about "old records".
        # Let's filter: Keep if (Paired or Trusted or Connected) OR (In Scan Cache).
        
        keep = False
        if data["connected"] or data["paired"] or data["trusted"]:
            keep = True
        else:
            # Check if likely from fresh scan logic?
            # We can check if mac was in scan cache text content?
            # This is expensive I/O again? No, we read it.
            pass

        # Since we added keys from scan cache, we want to keep them.
        # But we also added keys from 'bluetoothctl devices' (all known).
        # Sort out ghosts: If from 'devices' but NOT (P/C/T) -> Ghost?
        # Most "Ghosts" are unpaired devices seen long ago.
        # bluetoothctl devices keeps them? Yes.
        # So we should validly filter them out if not P/C/T.
        # But how to know if it's currently visible (scanned)?
        # Only if we scanned recently.
        
        # Simplified Logic:
        # We only added keys from 'devices' (history) and 'scan_cache' (fresh).
        # We want to keep ALL 'scan_cache' (fresh).
        # We want to keep 'devices' ONLY if P/C/T.
        # But 'devices' dict is merged.
        
        # Let's assume we keep it if:
        # 1. Connect/Paired/Trusted
        # 2. OR it is known to be in the scan results?
        
        # Re-reading scan cache content to check explicit presence
        in_scan = False
        if os.path.exists(scan_cache_path):
             with open(scan_cache_path) as sc:
                 if mac in sc.read():
                     in_scan = True
        
        if keep or in_scan:
             final_devices[mac] = data

    return final_devices

def main_menu():
    # Check Power
    powered = get_adapter_powered()
    if powered is False:
        print(f"{ICON_POWER_ON}")
        return
    if powered is None:
        power_state = run_cmd(["bluetoothctl", "show"])
        if not parse_info_flag(power_state, ["Powered", "Encendido", "Activado"]):
            print(f"{ICON_POWER_ON}")
            return

    # Power is ON
    print(f"{ICON_POWER_OFF}")
    print(f"{ICON_SCAN}  " + L({"es": "Escanear (Descubrir nuevos)", "en": "Scan (Discover new)", "pt": "Escanear (Descobrir novos)", "fr": "Scanner (Découvrir de nouveaux)", "ru": "Сканировать (Найти новые)"}))
    
    # List Devices
    devices = get_devices()
    
    # Sort: Connected first, then Paired, then Scanned
    sorted_macs = sorted(devices.keys(), key=lambda x: (
        not devices[x]["connected"], 
        not devices[x]["paired"], 
        devices[x]["name"]
    ))

    for mac in sorted_macs:
        d = devices[mac]
        
        # Status Logic:
        # Connected = Check (Green)
        # Trusted (but not con) = Shield/Bolt (Blue/Yellow)
        # Paired (but not trusted) = Cloud
        # New = Star/Plus
        
        if d["connected"]:
            status_icon = ICON_CONNECTED
        elif d["trusted"]:
            status_icon = " " # Trusted Shield (or ⚡)
        elif d["paired"]:
            status_icon = ICON_PAIRED
        else:
            status_icon = ICON_NEW
            
        dev_icon = d.get("icon", "")
        name = html.escape(d["name"])
        
        # Pango formatting
        # Status Icon | Device Icon | Name (Bold) | MAC (Small/Transparent)
        display = f"{status_icon}   {dev_icon}  <b>{name}</b> <span size='x-small' alpha='50%'>{mac}</span>"
        print(display)

def ensure_agent():
    # Enable a simple agent for pairing (no prompt needed for most devices)
    run_cmd(["bluetoothctl", "agent", "on"])
    run_cmd(["bluetoothctl", "default-agent"])
    run_cmd(["bluetoothctl", "pairable", "on"])
    run_cmd(["bluetoothctl", "pairable-timeout", "180"])

CONNECT_TIMEOUT = 15
PAIR_TIMEOUT = 20

def run_bt(args, timeout=None):
    try:
        res = subprocess.run(["bluetoothctl"] + args, capture_output=True, text=True, timeout=timeout)
        out = (res.stdout or "") + (res.stderr or "")
        out = out.strip()
        return res.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, L({"es": "Tiempo de espera agotado", "en": "Timeout reached", "pt": "Tempo limite atingido", "fr": "Délai d'attente dépassé", "ru": "Время ожидания истекло"})

def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", text or "")

def output_indicates_connected(text):
    clean = strip_ansi(text)
    if parse_info_flag(clean, ["Connected", "Conectado"]):
        return True
    if re.search(r"\balready connected\b|\bya est[aá] conectado\b", clean, re.IGNORECASE):
        return True
    return False

def scan_and_cache(duration=3, notify=True):
    cache_file = "/tmp/bt_scan_cache"

    if notify:
        msg = L({
            "es": f"Escaneando ({duration}s)...",
            "en": f"Scanning ({duration}s)...",
            "pt": f"Escaneando ({duration}s)...",
            "fr": f"Analyse ({duration}s)...",
            "ru": f"Сканирование ({duration}с)..."
        })
        subprocess.Popen(["notify-send", "Bluetooth", msg, "-i", "bluetooth"])

    expect_script_path = "/tmp/bt_scan.exp"
    expect_script_content = f"""#!/usr/bin/expect -f
set timeout {duration + 4}
spawn bluetoothctl
expect "#"
send "scan on\\r"
expect -re "Discovery started|SetDiscoveryFilter success"
sleep {duration}
send "scan off\\r"
expect -re "Discovery stopped|Failed to stop discovery"
send "exit\\r"
"""
    with open(expect_script_path, "w") as f:
        f.write(expect_script_content)

    os.chmod(expect_script_path, 0o755)

    subprocess.call(expect_script_path, shell=True)

    output = run_cmd(["bluetoothctl", "devices"])
    with open(cache_file, "w") as f:
        f.write(output)

    if notify:
        msg2 = L({
            "es": "Escaneo finalizado",
            "en": "Scan finished",
            "pt": "Escaneamento finalizado",
            "fr": "Analyse terminée",
            "ru": "Сканирование завершено"
        })
        subprocess.Popen(["notify-send", "Bluetooth", msg2, "-i", "bluetooth"])

def handle_scan():
    # Clean old cache before scan
    try:
        if os.path.exists("/tmp/bt_scan_cache"):
            os.remove("/tmp/bt_scan_cache")
    except Exception:
        pass
    scan_and_cache(duration=3, notify=True)

def clear_scan_cache():
    try:
        if os.path.exists("/tmp/bt_scan_cache"):
            os.remove("/tmp/bt_scan_cache")
            return True
    except Exception:
        return False
    return False

def forget_unpaired_devices():
    removed = 0
    raw = run_cmd(["bluetoothctl", "devices"])
    for line in raw.splitlines():
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        mac = parts[1]
        props = get_device_props(mac)
        if props is not None:
            if props["connected"] or props["paired"] or props["trusted"]:
                continue
        else:
            info = run_cmd(["bluetoothctl", "info", mac])
            state = get_device_state_from_info(info)
            if state["connected"] or state["paired"] or state["trusted"]:
                continue
        run_cmd(["bluetoothctl", "remove", mac])
        removed += 1
    return removed

def connect_device(mac):
    ensure_agent()
    # Trust the device before connecting (helps with some controllers/headphones)
    run_cmd(["bluetoothctl", "trust", mac])
    
    ok, out = run_bt(["connect", mac], timeout=CONNECT_TIMEOUT)
    connected_now = is_connected(mac) or output_indicates_connected(out)
    if connected_now:
        time.sleep(1.0)
        if is_connected(mac):
            return True, ""
        return False, L({"es": "Se conectó y luego se desconectó", "en": "Connected and then disconnected", "pt": "Conectou e depois desconectou", "fr": "Connecté puis déconnecté", "ru": "Подключился и затем отключился"})

    clean = strip_ansi(out)
    if (not ok) or ("Failed to connect" in clean) or ("Falló conexión" in clean):
        run_cmd(["bluetoothctl", "disconnect", mac])
        return False, clean or L({"es": "Error al conectar", "en": "Error connecting", "pt": "Erro ao conectar", "fr": "Erreur de connexion", "ru": "Ошибка подключения"})

    run_cmd(["bluetoothctl", "disconnect", mac])
    return False, clean or L({"es": "No se pudo establecer la conexión", "en": "Failed to establish connection", "pt": "Falha ao estabelecer conexão", "fr": "Échec de l'établissement de la connexion", "ru": "Не удалось установить соединение"})

def pair_device(mac):
    ensure_agent()
    ok, out = run_bt(["pair", mac], timeout=PAIR_TIMEOUT)
    if (not ok) or ("Failed" in out):
        return False, out or L({"es": "Error al vincular", "en": "Error pairing", "pt": "Erro ao parear", "fr": "Erreur de couplage", "ru": "Ошибка сопряжения"})
    return True, ""

def device_submenu(mac, name):
    # Check current status
    props = get_device_props(mac)
    if props is not None:
        connected = props["connected"]
        paired = props["paired"]
        trusted = props["trusted"]
    else:
        info = run_cmd(["bluetoothctl", "info", mac])
        state = get_device_state_from_info(info)
        connected = state["connected"]
        paired = state["paired"]
        trusted = state["trusted"]
    
    options = []
    
    if connected:
        options.append(f"󰅖 " + L({"es": "Desconectar", "en": "Disconnect", "pt": "Desconectar", "fr": "Déconnecter", "ru": "Отключить"}))
    else:
        options.append(f"󰂱 " + L({"es": "Conectar", "en": "Connect", "pt": "Conectar", "fr": "Connecter", "ru": "Подключиться"}))
        
    if paired or trusted:
        options.append(f" " + L({"es": "Desvincular (Unpair)", "en": "Unpair", "pt": "Desemparelhar", "fr": "Dissocier", "ru": "Отвязать"}))
    else:
        options.append(f" " + L({"es": "Vincular (Pair)", "en": "Pair", "pt": "Emparelhar", "fr": "Associer", "ru": "Связать"}))
        
    if trusted:
        options.append(f" " + L({"es": "Quitar Confianza (Untrust)", "en": "Untrust", "pt": "Remover Confiança", "fr": "Ne plus faire confiance", "ru": "Убрать доверие"}))
    else:
        options.append(f" " + L({"es": "Confiar (Trust)", "en": "Trust", "pt": "Confiar", "fr": "Faire confiance", "ru": "Доверять"}))
        
    options.append(f" " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))

    
    # Print options for Rofi
    for opt in options:
        print(opt)

if __name__ == "__main__":
    # Clean cache on startup (Session start)
    if len(sys.argv) == 1:
        # First launch - Clear cache
        if os.path.exists("/tmp/bt_scan_cache"):
            os.remove("/tmp/bt_scan_cache")
    
    # State tracking
    MAC = None 
    
    while True:
        # Generate items
        items = []
        
        # Redirect stdout
        from io import StringIO
        capture = StringIO()
        sys.stdout = capture
        
        PROMPT = "Bluetooth"
        
        if MAC:
            # Submenu
            device_submenu(MAC, "Device")
            PROMPT = L({"es": "Acción", "en": "Action", "pt": "Ação", "fr": "Action", "ru": "Действие"}) + f" ({MAC})"
        else:
            # Main Menu
            main_menu()
            PROMPT = "Bluetooth"
            
        sys.stdout = sys.__stdout__ # Restore
        menu_str = capture.getvalue()
        
        # Run Rofi
        try:
            cmd = ROFI_CMD + ["-theme-str", THEME_STR, "-p", PROMPT]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            chosen, _ = proc.communicate(input=menu_str)
            
            if proc.returncode != 0:
                # Cancel / Escape
                if MAC:
                    MAC = None # Go back to main
                    continue
                else:
                    break # Exit app
            
            chosen = chosen.strip()
            if not chosen: break
            
            # Extract Value: JUST USE CHOSEN STRING
            value = chosen
                
            # Actions
            if value.startswith(ICON_POWER_ON):
                run_cmd(["bluetoothctl", "power", "on"])
                time.sleep(0.2) 
            elif value.startswith(ICON_POWER_OFF):
                run_cmd(["bluetoothctl", "power", "off"])
                time.sleep(0.2)
            elif value.startswith(ICON_SCAN):
                handle_scan()
            elif any(x in value for x in ["Volver", "Back", "Voltar", "Retour", "Назад"]):
                MAC = None
            elif any(x in value for x in ["Disconnect", "Desconectar", "Déconnecter", "Отключить"]):
                run_cmd(["bluetoothctl", "disconnect", MAC])
                msg = L({
                    "es": f"Desconectado: {MAC}", "en": f"Disconnected: {MAC}", "pt": f"Desconectado: {MAC}",
                    "fr": f"Déconnecté: {MAC}", "ru": f"Отключено: {MAC}"
                })
                subprocess.Popen(["notify-send", "Bluetooth", msg, "-i", "bluetooth"])
                # Close menu as requested by user
                break
            elif any(x in value for x in ["Connect", "Conectar", "Connecter", "Подключиться"]):
                msg_conn = L({
                    "es": f"Conectando a {MAC}...", "en": f"Connecting to {MAC}...", "pt": f"Conectando a {MAC}...",
                    "fr": f"Connexion à {MAC}...", "ru": f"Подключение к {MAC}..."
                })
                subprocess.Popen(["notify-send", "Bluetooth", msg_conn, "-i", "bluetooth"])
                ok, err = connect_device(MAC)
                if ok:
                    msg_ok = L({
                        "es": f"Conectado: {MAC}", "en": f"Connected: {MAC}", "pt": f"Conectado: {MAC}",
                        "fr": f"Connecté: {MAC}", "ru": f"Подключено: {MAC}"
                    })
                    subprocess.Popen(["notify-send", "Bluetooth", msg_ok, "-i", "bluetooth", "-u", "normal"])
                    # Close menu as requested by user
                    break
                else:
                    msg_err = L({
                        "es": f"Falló conexión: {err}", "en": f"Connection failed: {err}", "pt": f"Falha na conexão: {err}",
                        "fr": f"Échec de la connexion: {err}", "ru": f"Сбой подключения: {err}"
                    })
                    subprocess.Popen(["notify-send", "Bluetooth", msg_err, "-i", "dialog-error", "-u", "critical"])
                    MAC = None 
            elif any(x in value for x in ["Unpair", "Desvincular", "Desemparelhar", "Dissocier", "Отвязать"]):
                run_cmd(["bluetoothctl", "remove", MAC])
                msg_unp = L({
                    "es": f"Desvinculado: {MAC}", "en": f"Unpaired: {MAC}", "pt": f"Desemparelhado: {MAC}",
                    "fr": f"Dissocié: {MAC}", "ru": f"Отвязано: {MAC}"
                })
                subprocess.Popen(["notify-send", "Bluetooth", msg_unp, "-i", "bluetooth"])
                MAC = None # Device gone, return to main
            elif any(x in value for x in ["Pair", "Vincular", "Emparelhar", "Associer", "Связать"]):
                msg_pair = L({
                    "es": f"Vinculando {MAC}...", "en": f"Pairing {MAC}...", "pt": f"Emparelhando {MAC}...",
                    "fr": f"Association de {MAC}...", "ru": f"Сопряжение {MAC}..."
                })
                subprocess.Popen(["notify-send", "Bluetooth", msg_pair, "-i", "bluetooth"])
                ok, err = pair_device(MAC)
                if ok:
                    msg_ok = L({
                        "es": f"Vinculado: {MAC}", "en": f"Paired: {MAC}", "pt": f"Emparelhado: {MAC}",
                        "fr": f"Associé: {MAC}", "ru": f"Сопряжено: {MAC}"
                    })
                    subprocess.Popen(["notify-send", "Bluetooth", msg_ok, "-i", "bluetooth", "-u", "normal"])
                else:
                    msg_err = L({
                        "es": f"Falló vinculación: {err}", "en": f"Pairing failed: {err}", "pt": f"Falha no emparelhamento: {err}",
                        "fr": f"Échec de l'association: {err}", "ru": f"Сбой сопряжения: {err}"
                    })
                    subprocess.Popen(["notify-send", "Bluetooth", msg_err, "-i", "dialog-error", "-u", "critical"])
                    MAC = None # Go back on error
                time.sleep(0.5)
            elif any(x in value for x in ["Untrust", "Quitar Confianza", "Remover Confiança", "Ne plus faire confiance", "Убрать доверие"]):
                run_cmd(["bluetoothctl", "untrust", MAC])
                msg_untr = L({
                    "es": f"Confianza retirada: {MAC}", "en": f"Trust removed: {MAC}", "pt": f"Confiança removida: {MAC}",
                    "fr": f"Confiance retirée: {MAC}", "ru": f"Доверие снято: {MAC}"
                })
                subprocess.Popen(["notify-send", "Bluetooth", msg_untr, "-i", "bluetooth"])
                time.sleep(0.5)
            elif any(x in value for x in ["Trust", "Confiar", "Faire confiance", "Доверять"]):
                run_cmd(["bluetoothctl", "trust", MAC])
                msg_tr = L({
                    "es": f"Dispositivo de Confianza: {MAC}", "en": f"Trusted Device: {MAC}", "pt": f"Dispositivo Confiável: {MAC}",
                    "fr": f"Appareil de confiance: {MAC}", "ru": f"Доверенное устройство: {MAC}"
                })
                subprocess.Popen(["notify-send", "Bluetooth", msg_tr, "-i", "bluetooth"])
                time.sleep(0.5)
            else:
                # Device Selection
                # Extract MAC using regex
                match = re.search(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", value)
                if match:
                    MAC = match.group(0)
                    
        except KeyboardInterrupt:
            break
            
        time.sleep(0.1)
