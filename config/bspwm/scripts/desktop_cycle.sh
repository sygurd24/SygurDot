#!/bin/bash

# Archivo temporal para guardar el timestamp de la última ejecución
STATE_FILE="/tmp/bspwm_desktop_cycle_state"
TIMEOUT=1500 # Tiempo en milisegundos para considerar "ciclo continuo"

# Obtener tiempo actual en milisegundos
NOW=$(date +%s%3N)
LAST_RUN=0

if [ -f "$STATE_FILE" ]; then
    LAST_RUN=$(cat "$STATE_FILE")
fi

DIFF=$((NOW - LAST_RUN))

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
    
    # Si por alguna razón no se encontró (ej. el actual no está ocupado), ir al primero
    bspc desktop -f "${desktops[0]}"
}

if [ $DIFF -lt $TIMEOUT ]; then
    # Ciclo continuo: ir al siguiente visible ocupado
    cycle_occupied
else
    # Primera pulsación: intentar ir al último (siempre que no sea oculto)
    LAST_DESK=$(bspc query -D -d last --names)
    if [[ ! $LAST_DESK =~ ^F ]] && [ -n "$LAST_DESK" ]; then
        bspc desktop -f last
    else
        cycle_occupied
    fi
fi

# Guardar timestamp actual
echo "$NOW" > "$STATE_FILE"
