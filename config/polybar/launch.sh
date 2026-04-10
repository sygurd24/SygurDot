#!/usr/bin/env bash

# Terminar las instancias de barra que ya se estén ejecutando
pkill -x polybar 2>/dev/null

# Esperar a que los procesos se hayan cerrado (con timeout)
timeout=5
while pgrep -u $UID -x polybar >/dev/null; do
  if [ "$timeout" -le 0 ]; then
    pkill -9 -x polybar 2>/dev/null
    break
  fi
  timeout=$((timeout - 1))
  sleep 1
done

# Cargar módulos habilitados desde archivo de configuración
POLY_CONF="$HOME/.config/dotfiles/polybar_modules_enabled"
DEFAULT_MODULES="date temperature cpu memory nvidia npu pulseaudio mic wlan bluetooth battery powermenu"

if [ -f "$POLY_CONF" ]; then
    ENABLED_MODULES=$(cat "$POLY_CONF")
else
    ENABLED_MODULES="$DEFAULT_MODULES"
fi

CENTER_MODULES=""
RIGHT_MODULES=""

for mod in $ENABLED_MODULES; do
    if [ "$mod" = "date" ]; then
        has_date=1
    elif [ "$mod" = "camera" ]; then
        has_camera=1
    else
        if [ -z "$RIGHT_MODULES" ]; then
            RIGHT_MODULES="$mod"
        else
            RIGHT_MODULES="$RIGHT_MODULES $mod"
        fi
    fi
done

if [ "${has_camera:-0}" -eq 1 ] && [ "${has_date:-0}" -eq 1 ]; then
    CENTER_MODULES="camera date"
elif [ "${has_camera:-0}" -eq 1 ]; then
    CENTER_MODULES="camera"
elif [ "${has_date:-0}" -eq 1 ]; then
    CENTER_MODULES="date"
fi

# Lanzar la barra llamada "example" (definida en el config.ini)
# Usamos export para que Polybar vea la variable de entorno
export POLYBAR_MODULES_CENTER="$CENTER_MODULES"
export POLYBAR_MODULES_RIGHT="$RIGHT_MODULES"
polybar example &


# Kill existing temperature daemon if running
pkill -f temperature-daemon.sh

# Start temperature daemon
~/.config/polybar/scripts/temperature-daemon.sh &

echo "Polybar lanzada..."
