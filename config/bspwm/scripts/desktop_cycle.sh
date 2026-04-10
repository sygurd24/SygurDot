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

if [ $DIFF -lt $TIMEOUT ]; then
    # Si la pulsación es rápida (dentro del ciclo), avanzar al siguiente ocupado
    # Si la pulsación es rápida (dentro del ciclo), avanzar al siguiente ocupado.
    # El usuario quiere ir "avanzando" (Next).
    bspc desktop -f next.occupied.local || bspc desktop -f next.occupied
else
    # Si es la primera pulsación (nuevo ciclo), ir al último usado
    bspc desktop -f last
fi

# Guardar timestamp actual
echo "$NOW" > "$STATE_FILE"
