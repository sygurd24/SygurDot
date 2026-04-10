#!/bin/bash

# 1. Matar y reiniciar Picom (limpia errores de renderizado)
pkill -x picom
picom --config "$HOME/.config/picom/picom.conf" -b &

# 2. Quitar el estado 'hidden' de todas las ventanas en todos los escritorios
for win in $(bspc query -N); do
    bspc node "$win" -g hidden=off
done

# 3. Eliminar opacidades personalizadas de X11 que puedan estar en 0
for win in $(xprop -root _NET_CLIENT_LIST | cut -d'#' -f2 | tr ',' '\n'); do
    xprop -id "$win" -remove _NET_WM_WINDOW_OPACITY 2>/dev/null
done

# 4. Refrescar bspwm
bspc wm -r

notify-send "Entorno arreglado" "Picom reiniciado y transparencias limpiadas."
