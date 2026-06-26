#!/bin/bash

# Archivo temporal para el estado de Alt+Tab
STATE_FILE="/tmp/bspwm_alt_tab_state"

# Función para obtener los escritorios ocupados que no sean "ocultos" (F1-F12)
get_occupied_visible() {
    bspc query -D -d .occupied --names | grep -v '^F'
}

cycle_occupied() {
    local current=$(bspc query -D -d focused --names)
    local desktops=($(get_occupied_visible))
    local count=${#desktops[@]}

    if [ $count -eq 0 ]; then
        return
    fi

    # Si estamos en un escritorio oculto, saltar al primero visible ocupado
    if [[ $current =~ ^F ]]; then
        bspc desktop -f "${desktops[0]}"
        return
    fi

    # Buscar la posición actual y saltar al siguiente
    for i in "${!desktops[@]}"; do
        if [[ "${desktops[$i]}" == "$current" ]]; then
            local next_idx=$(( (i + 1) % count ))
            bspc desktop -f "${desktops[$next_idx]}"
            return
        fi
    done
    
    # Si por alguna razón no se encontró, ir al primero
    bspc desktop -f "${desktops[0]}"
}

if [ -f "$STATE_FILE" ]; then
    # Si el archivo existe, significa que Alt se mantiene presionado 
    # y esta es una pulsación adicional de Tab (ciclar hacia adelante)
    cycle_occupied
else
    # Primera pulsación: crear estado e ir al último escritorio (alternar)
    touch "$STATE_FILE"
    
    LAST_DESK=$(bspc query -D -d last --names)
    if [[ ! $LAST_DESK =~ ^F ]] && [ -n "$LAST_DESK" ]; then
        bspc desktop -f last
    else
        cycle_occupied
    fi
fi
