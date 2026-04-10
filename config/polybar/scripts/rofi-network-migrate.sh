#!/bin/bash
set -e

echo "========================================="
echo "   Migrando Red (Wi-Fi/Ethernet)...      "
echo "========================================="
echo "Se requieren permisos de administrador (sudo)."

sudo -v || { echo "No se pudo obtener sudo."; sleep 3; exit 1; }

echo "[+] Habilitando gestión de interfaces en NetworkManager..."
sudo mkdir -p /etc/NetworkManager/conf.d
cat <<'EOF' | sudo tee /etc/NetworkManager/conf.d/99-dotfiles-managed.conf > /dev/null
[ifupdown]
managed=true
EOF

echo "[+] Limpiando configuración de ifupdown..."
if [ -f /etc/network/interfaces ]; then
    IF_BACKUP="/etc/network/interfaces.dotfiles.bak.$(date +%Y%m%d_%H%M%S)"
    sudo cp /etc/network/interfaces "$IF_BACKUP" || true
fi

cat <<'EOF' | sudo tee /etc/network/interfaces > /dev/null
# Managed by dotfiles to allow NetworkManager to control Wi-Fi and Ethernet.
source /etc/network/interfaces.d/*
auto lo
iface lo inet loopback
EOF

if [ -d /etc/network/interfaces.d ]; then
    IFD_BACKUP="/etc/network/interfaces.d.dotfiles.bak.$(date +%Y%m%d_%H%M%S)"
    sudo mkdir -p "$IFD_BACKUP" || true
    sudo find /etc/network/interfaces.d -maxdepth 1 -type f -exec mv {} "$IFD_BACKUP/" \; || true
fi

echo "[+] Deshabilitando demonio anterior (networking) si existe..."
sudo systemctl disable --now networking 2>/dev/null || true
sudo systemctl stop wpa_supplicant 2>/dev/null || true
sudo killall -9 wpa_supplicant 2>/dev/null || true

echo "[+] Limpiando estados de red anteriores..."
# Get any wifi/ethernet interfaces
W_INT=$(ip -o link show | awk -F': ' '$2 ~ /^(en|eth|wlan|wlo|wl)/ {print $2}')
for i in $W_INT; do
    echo "[*] Limpiando $i..."
    sudo ip addr flush dev "$i" 2>/dev/null || true
    sudo ip link set "$i" down 2>/dev/null || true
done

echo "[+] Reiniciando NetworkManager..."
sudo systemctl enable --now NetworkManager || true
sudo systemctl restart NetworkManager

echo "========================================="
echo " Migración completada exitosamente.      "
echo " Puedes abrir tu menú de Red de nuevo.   "
echo "========================================="
echo "Presiona ENTER para salir..."
read
