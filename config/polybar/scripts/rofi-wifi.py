#!/usr/bin/env python3
import subprocess
import sys
import os
import shutil
import re

# Rofi Wifi Manager for Polybar
# Advanced logic for Submenus and Actions

# Theme (Same as Bluetooth for consistency)
THEME_STR = 'window { width: 800px; } listview { lines: 12; } element-text { font: "JetBrainsMono Nerd Font Mono 11"; }'

# Icons
ICON_CONNECTED = ""
ICON_SAVED = " " # Saved but not connected
ICON_LOCK = ""
ICON_OPEN = ""

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

def run_cmd(args: list) -> str:
    try:
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        return subprocess.check_output(args, text=True, env=env).strip()
    except subprocess.CalledProcessError:
        return ""

def get_signal_icon(strength):
    try:
        s = int(strength)
        if s >= 80: return "󰤨"
        elif s >= 60: return "󰤥"
        elif s >= 40: return "󰤢"
        elif s >= 20: return "󰤟"
        else: return "󰤯"
    except:
        return "󰤯"

def get_saved_connections():
    # Returns list of saved connection names
    raw = run_cmd(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    saved = set()
    for line in raw.splitlines():
        if ":802-11-wireless" in line:
            name = line.split(":")[0]
            saved.add(name)
    return saved

def get_networks():
    networks = {}
    
    # Get Active SSID
    active_ssid = run_cmd(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    active_ssid_name = ""
    for line in active_ssid.splitlines():
        if line.startswith("yes:"):
            active_ssid_name = line.split(":")[1]
            break

    # Get Saved List
    saved_connections = get_saved_connections()

    # Scan List
    # SSID, SECURITY, SIGNAL, BARS
    raw = run_cmd(["nmcli", "-t", "-f", "SSID,SECURITY,SIGNAL", "device", "wifi", "list"])
    
    # Process
    for line in raw.splitlines():
        # Clean colons
        # nmcli -t escapes colons with \, but here we split simply.
        # This layout is consistent mostly.
        parts = line.split(":")
        if len(parts) < 3: continue
        
        ssid = parts[0]
        if not ssid: continue # Skip hidden
        
        # Determine security
        security = "OPEN"
        if len(parts) >= 2 and parts[1]:
            security = parts[1]
        
        signal = "0"
        if len(parts) >= 3:
            signal = parts[2]
            
        # Is Active?
        is_active = (ssid == active_ssid_name)
        
        # Is Saved?
        is_saved = (ssid in saved_connections)
        
        # Prioritize Active, then Saved, then Strongest
        # We store just one entry per SSID (strongest usually comes first in nmcli list)
        if ssid not in networks:
            networks[ssid] = {
                "ssid": ssid,
                "security": security,
                "signal": signal,
                "active": is_active,
                "saved": is_saved
            }
            
    return networks

def submenu(net):
    ssid = net["ssid"]
    options = []
    
    if net["active"]:
        options.append(f"󰅖 " + L({"es": "Desconectar", "en": "Disconnect", "pt": "Desconectar", "fr": "Déconnecter", "ru": "Отключить"}))
        options.append(f" " + L({"es": "Olvidar (Borrar perfil)", "en": "Forget (Delete profile)", "pt": "Esquecer (Excluir perfil)", "fr": "Oublier (Supprimer le profil)", "ru": "Забыть (Удалить профиль)"}))
    elif net["saved"]:
        options.append(f"󰂱 " + L({"es": "Conectar", "en": "Connect", "pt": "Conectar", "fr": "Connecter", "ru": "Подключиться"}))
        options.append(f" " + L({"es": "Olvidar (Borrar perfil)", "en": "Forget (Delete profile)", "pt": "Esquecer (Excluir perfil)", "fr": "Oublier (Supprimer le profil)", "ru": "Забыть (Удалить профиль)"}))
    else:
        # New Network
        options.append(f"󰂱 " + L({"es": "Conectar", "en": "Connect", "pt": "Conectar", "fr": "Connecter", "ru": "Подключиться"}))
        
    options.append(f" " + L({"es": "Volver", "en": "Back", "pt": "Voltar", "fr": "Retour", "ru": "Назад"}))
    
    # Run Rofi Submenu
    menu_str = "\n".join(options)
    prompt = L({"es": "Acción", "en": "Action", "pt": "Ação", "fr": "Action", "ru": "Действие"}) + f" ({ssid})"
    
    cmd = ["rofi", "-dmenu", "-i", "-theme-str", THEME_STR, "-p", prompt, "-format", "s"]
    res = subprocess.run(cmd, input=menu_str, text=True, capture_output=True)
    
    if res.returncode != 0: return # Cancel
    
    choice = res.stdout.strip()
    
    # Selection check (check against multiple languages)
    if any(x in choice for x in ["Disconnect", "Desconectar", "Déconnecter", "Отключить", "Desconectar"]):
        # Use connection down instead of device disconnect to avoid needing interface name (wlan0)
        run_cmd(["nmcli", "connection", "down", "id", ssid]) 
        msg = L({
            "es": f"Desconectado de {ssid}",
            "en": f"Disconnected from {ssid}",
            "pt": f"Desconectado de {ssid}",
            "fr": f"Déconnecté de {ssid}",
            "ru": f"Отключено от {ssid}"
        })
        subprocess.Popen(["notify-send", "WiFi", msg, "-i", "network-wireless-disconnected"])
        
    elif any(x in choice for x in ["Connect", "Conectar", "Connecter", "Подключиться"]):
        if net["saved"]:
            # Known network, just up
            msg_conn = L({
                "es": f"Conectando a {ssid}...",
                "en": f"Connecting to {ssid}...",
                "pt": f"Conectando a {ssid}...",
                "fr": f"Connexion à {ssid}...",
                "ru": f"Подключение к {ssid}..."
            })
            subprocess.Popen(["notify-send", "WiFi", msg_conn, "-i", "network-wireless-acquiring"])
            res = subprocess.run(["nmcli", "connection", "up", "id", ssid], capture_output=True, text=True)
            if res.returncode == 0:
                msg_ok = L({
                    "es": f"Conectado: {ssid}",
                    "en": f"Connected: {ssid}",
                    "pt": f"Conectado: {ssid}",
                    "fr": f"Connecté: {ssid}",
                    "ru": f"Подключено: {ssid}"
                })
                subprocess.Popen(["notify-send", "WiFi", msg_ok, "-i", "network-wireless-connected"])
            else:
                 subprocess.Popen(["notify-send", "WiFi", f"Error: {res.stderr}", "-i", "dialog-error"])
        else:
            # New Network -> Password?
            # Check security
            if "WPA" in net["security"] or "WEP" in net["security"]:
                # Ask Password
                pass_prompt = L({
                    "es": f"Contraseña para {ssid}",
                    "en": f"Password for {ssid}",
                    "pt": f"Senha para {ssid}",
                    "fr": f"Mot de passe pour {ssid}",
                    "ru": f"Пароль для {ssid}"
                })
                pass_cmd = ["rofi", "-dmenu", "-theme-str", THEME_STR, "-p", pass_prompt, "-password"]
                pass_res = subprocess.run(pass_cmd, input="", text=True, capture_output=True)
                password = pass_res.stdout.strip()
                
                if not password: return
                
                msg_conn = L({
                    "es": f"Conectando a {ssid}...",
                    "en": f"Connecting to {ssid}...",
                    "pt": f"Conectando a {ssid}...",
                    "fr": f"Connexion à {ssid}...",
                    "ru": f"Подключение к {ssid}..."
                })
                subprocess.Popen(["notify-send", "WiFi", msg_conn, "-i", "network-wireless-acquiring"])
                res = subprocess.run(["nmcli", "device", "wifi", "connect", ssid, "password", password], capture_output=True, text=True)
                
                if res.returncode == 0:
                    msg_ok = L({
                        "es": f"Conectado: {ssid}",
                        "en": f"Connected: {ssid}",
                        "pt": f"Conectado: {ssid}",
                        "fr": f"Connecté: {ssid}",
                        "ru": f"Подключено: {ssid}"
                    })
                    subprocess.Popen(["notify-send", "WiFi", msg_ok, "-i", "network-wireless-connected"])
                else:
                    subprocess.Popen(["notify-send", "WiFi", f"Error: {res.stderr}", "-i", "dialog-error"])
            else:
                # Open Network
                msg_open = L({
                    "es": f"Conectando a {ssid} (Abierta)...",
                    "en": f"Connecting to {ssid} (Open)...",
                    "pt": f"Conectando a {ssid} (Aberta)...",
                    "fr": f"Connexion à {ssid} (Ouverte)...",
                    "ru": f"Подключение к {ssid} (Открытая)..."
                })
                subprocess.Popen(["notify-send", "WiFi", msg_open, "-i", "network-wireless-acquiring"])
                res = subprocess.run(["nmcli", "device", "wifi", "connect", ssid], capture_output=True, text=True)
                if res.returncode == 0:
                    msg_ok = L({
                        "es": f"Conectado: {ssid}",
                        "en": f"Connected: {ssid}",
                        "pt": f"Conectado: {ssid}",
                        "fr": f"Connecté: {ssid}",
                        "ru": f"Подключено: {ssid}"
                    })
                    subprocess.Popen(["notify-send", "WiFi", msg_ok, "-i", "network-wireless-connected"])

    elif any(x in choice for x in ["Forget", "Olvidar", "Oublier", "Esquecer", "Забыть"]):
        run_cmd(["nmcli", "connection", "delete", "id", ssid])
        msg_forg = L({
            "es": f"Olvidada: {ssid}",
            "en": f"Forgotten: {ssid}",
            "pt": f"Esquecida: {ssid}",
            "fr": f"Oubliée: {ssid}",
            "ru": f"Забыта: {ssid}"
        })
        subprocess.Popen(["notify-send", "WiFi", msg_forg, "-i", "network-wireless-disconnected"])

def is_wifi_unmanaged():
    # If nmcli fails (NM not running), it needs migration/activation
    try:
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        subprocess.check_output(["nmcli", "general", "status"], env=env, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return True

    # Check NM device status
    raw_status = run_cmd(["nmcli", "-t", "-f", "TYPE,STATE", "dev", "status"])
    is_any_wifi_managed_connected = False
    has_explicit_unmanaged = False
    
    for line in raw_status.splitlines():
        if "unmanaged" in line and ("802-11-wireless" in line or "wifi" in line):
            has_explicit_unmanaged = True
        if ("connected" in line or "connecting" in line) and ("802-11-wireless" in line or "wifi" in line):
            is_any_wifi_managed_connected = True
            
    if has_explicit_unmanaged:
        return True
    
    # Heuristic: If NM doesn't have a connected wifi, but the system has a wifi default route
    if not is_any_wifi_managed_connected:
        route_out = run_cmd(["sh", "-c", "ip -o -4 route show default 2>/dev/null"])
        if re.search(r"\b(wlan|wlo|wl)\d*", route_out):
            return True

    return False

def get_ethernet_status():
    raw_status = run_cmd(["nmcli", "-t", "-f", "TYPE,STATE", "dev", "status"])
    for line in raw_status.splitlines():
        if ("ethernet" in line or "802-3-ethernet" in line) and "connected" in line:
            return True
    return False

def main():
    if is_wifi_unmanaged():
        rofi_rows = [
            "󰖩  " + L({"es": "Wi-Fi no gestionado (ifupdown)", "en": "Wi-Fi is Unmanaged (ifupdown)", "pt": "Wi-Fi não gerenciado (ifupdown)", "fr": "Wi-Fi non géré (ifupdown)", "ru": "Wi-Fi не управляется (ifupdown)"}),
            "󰦖  " + L({"es": "Migrar a NetworkManager (Recomendado)", "en": "Migrate to NetworkManager (Recommended)", "pt": "Migrar para NetworkManager (Recomendado)", "fr": "Migrer vers NetworkManager (Recommandé)", "ru": "Перейти на NetworkManager (Рекомендуется)"})
        ]
        input_str = "\n".join(rofi_rows)
        cmd = ["rofi", "-dmenu", "-i", "-theme-str", THEME_STR, "-p", "Network", "-format", "s"]
        res = subprocess.run(cmd, input=input_str, text=True, capture_output=True)
        if res.returncode != 0: return
        chosen = res.stdout.strip()
        if any(x in chosen for x in ["Migrate", "Migrar", "Migrer", "Перейти"]):
            script_path = os.path.expanduser("~/.config/polybar/scripts/rofi-network-migrate.sh")
            subprocess.Popen(["kitty", "-e", "bash", "-c", script_path])
        return

    networks = get_networks()
    
    # Sort
    # Active First, then Saved, then Signal Strength
    # Signal is string "80", convert to int
    sorted_ssids = sorted(networks.keys(), key=lambda x: (
        not networks[x]["active"],
        not networks[x]["saved"],
        -int(networks[x]["signal"])
    ))
    
    rofi_rows = []
    
    if get_ethernet_status():
        eth_line = "󰈀  " + L({"es": "Ethernet (Conectado)", "en": "Ethernet (Connected)", "pt": "Ethernet (Conectado)", "fr": "Ethernet (Connecté)", "ru": "Ethernet (Подключено)"})
        rofi_rows.append(eth_line)
    
    toggle_line = "󰖩  " + L({"es": "Activar/Desactivar Wi-Fi", "en": "Enable/Disable Wi-Fi", "pt": "Ativar/Desativar Wi-Fi", "fr": "Activer/Désactiver Wi-Fi", "ru": "Включить/Выключить Wi-Fi"})
    rofi_rows.append(toggle_line)
    
    repair_line = "  " + L({"es": "Reparar/Restablecer Wi-Fi (Fix Hardware)", "en": "Repair/Reset Wi-Fi (Fix Hardware)", "pt": "Reparar/Redefinir Wi-Fi (Fix Hardware)", "fr": "Réparer/Réinitialiser Wi-Fi (Fix Hardware)", "ru": "Восстановить Wi-Fi (Fix Hardware)"})
    rofi_rows.append(repair_line)
    
    for ssid in sorted_ssids:
        net: dict = networks.get(ssid, {})
        
        # Icon Logic
        signal_val = str(net.get("signal", "0"))
        sig_icon = get_signal_icon(signal_val)
        
        status = ""
        is_active = net.get("active", False)
        is_saved = net.get("saved", False)
        
        if is_active:
            status = ICON_CONNECTED
        elif is_saved:
            status = ICON_SAVED
        else:
            status = "  "
            
        security = str(net.get("security", ""))
        sec_icon = ICON_LOCK if ("WPA" in security or "WEP" in security) else ICON_OPEN
        
        # Format
        # Status | Signal | SSID | Security
        display = f"{status}  {sig_icon}   <b>{ssid}</b> <span size='small' alpha='50%'>{sec_icon} {signal_val}%</span>"
        rofi_rows.append(display)
        
    input_str = "\n".join(rofi_rows)
    
    cmd = ["rofi", "-dmenu", "-i", "-theme-str", THEME_STR, "-p", "Network", "-format", "s", "-markup-rows"]
    res = subprocess.run(cmd, input=input_str, text=True, capture_output=True)
    
    if res.returncode != 0: return
    
    chosen = res.stdout.strip()
    
    if not chosen: return
    
    if any(x in chosen for x in ["Enable/Disable", "Activar/Desactivar", "Ativar/Desativar", "Activer/Désactiver", "Включить/Выключить"]):
        # Simple Toggle
        status = run_cmd(["nmcli", "radio", "wifi"])
        if "enabled" in status:
            run_cmd(["nmcli", "radio", "wifi", "off"])
            msg_off = L({"es": "Desactivado", "en": "Disabled", "pt": "Desativado", "fr": "Désactivé", "ru": "Выключено"})
            subprocess.Popen(["notify-send", "WiFi", msg_off, "-i", "network-wireless-disconnected"])
        else:
            run_cmd(["nmcli", "radio", "wifi", "on"])
            msg_on = L({"es": "Activado", "en": "Enabled", "pt": "Ativado", "fr": "Activé", "ru": "Включено"})
            subprocess.Popen(["notify-send", "WiFi", msg_on, "-i", "network-wireless-connected"])
        return
        
    if any(x in chosen for x in ["Repair/Reset", "Reparar/Restablecer", "Reparar/Redefinir", "Réparer/Réinitialiser", "Восстановить"]):
        msg_reset = L({
            "es": "Reiniciando hardware de red...",
            "en": "Resetting network hardware...",
            "pt": "Redefinindo hardware de rede...",
            "fr": "Réinitialisation du matériel réseau...",
            "ru": "Перезагрузка сетевого оборудования..."
        })
        subprocess.Popen(["notify-send", "WiFi", msg_reset, "-i", "view-refresh"])
        import time
        run_cmd(["nmcli", "networking", "off"])
        time.sleep(2)
        run_cmd(["nmcli", "networking", "on"])
        msg_done = L({
            "es": "Hardware reiniciado. Escaneando...",
            "en": "Hardware reset. Scanning...",
            "pt": "Hardware redefinido. Escaneando...",
            "fr": "Matériel réinitialisé. Analyse en cours...",
            "ru": "Оборудование перезагружено. Сканирование..."
        })
        subprocess.Popen(["notify-send", "WiFi", msg_done, "-i", "network-wireless-connected"])
        return

    # Extract SSID
    # We used Pango markup, so chosen string contains it.
    # Regex to extract <b>SSID</b>
    # Format: ... <b>{ssid}</b> ...
    match = re.search(r"<b>(.*?)</b>", chosen)
    if match:
        ssid = match.group(1)
        if ssid in networks:
            submenu(networks[ssid])

if __name__ == "__main__":
    main()
