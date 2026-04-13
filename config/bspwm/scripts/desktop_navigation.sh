#!/bin/bash

# Navegación entre escritorios visibles (I a X) ignorando los ocultos (F1 a F12)
DIRECTION=$1 # "next" o "prev"
CURRENT=$(bspc query -D -d focused --names)

# Obtenemos la lista de escritorios que NO empiezan con 'F'
DESKTOPS=($(bspc query -D --names | grep -v '^F'))
COUNT=${#DESKTOPS[@]}

for i in "${!DESKTOPS[@]}"; do
    if [[ "${DESKTOPS[$i]}" == "$CURRENT" ]]; then
        if [[ "$DIRECTION" == "next" ]]; then
            NEXT_IDX=$(( (i + 1) % COUNT ))
        else
            NEXT_IDX=$(( (i - 1 + COUNT) % COUNT ))
        fi
        bspc desktop -f "${DESKTOPS[$NEXT_IDX]}"
        exit 0
    fi
done

# Si estamos en un escritorio oculto, volver al primero visible
bspc desktop -f "${DESKTOPS[0]}"
