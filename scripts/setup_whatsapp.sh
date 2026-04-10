#!/bin/bash
set -e

DOTFILES_DIR="$HOME/dotfiles"
LOCAL_APPS_DIR="$DOTFILES_DIR/local_apps"

log() {
    echo "[INFO] $1"
}

log "Instalando Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    log "Descargando Google Chrome..."
    wget -qO /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    log "Instalando Google Chrome via apt..."
    sudo apt install -y /tmp/google-chrome-stable_current_amd64.deb
    rm -f /tmp/google-chrome-stable_current_amd64.deb
else
    log "Google Chrome ya está instalado."
fi

log "Creando acceso directo de WhatsApp Web para Rofi..."

mkdir -p "$LOCAL_APPS_DIR"
DESKTOP_FILE="$LOCAL_APPS_DIR/whatsapp-web-chrome.desktop"

# User Agent de Windows 10/11 con Chrome para engañar a WhatsApp y permitir llamadas
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+' | head -n 1)
WINDOWS_UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/$CHROME_VERSION.0.0.0 Safari/537.36"

# Crear el archivo .desktop dentro de los dotfiles para que sea persistente
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Name=WhatsApp Web - Chrome
Comment=WhatsApp Web App simulando Windows para Video Llamadas
Exec=google-chrome --app=https://web.whatsapp.com/ --password-store=basic --user-agent="$WINDOWS_UA"
Terminal=false
Type=Application
Icon=whatsapp
Categories=Network;InstantMessaging;
EOF

chmod +x "$DESKTOP_FILE"

# Enlazar al directorio de aplicaciones del usuario
mkdir -p "$HOME/.local/share/applications"
ln -sf "$DESKTOP_FILE" "$HOME/.local/share/applications/whatsapp-web-chrome.desktop"

# Actualizar base de datos de escritorio para que Rofi lo detecte al instante
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications/"
fi

log "¡Configuración de WhatsApp Web completada con éxito!"
log "Ya puedes buscar 'WhatsApp Web - Chrome' en tu menú Rofi."