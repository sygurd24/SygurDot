#!/bin/bash

# Language detection
if [ -f "$HOME/.config/dotfiles/language" ]; then
    LANGUAGE=$(cat "$HOME/.config/dotfiles/language")
else
    LANGUAGE=$(echo "$LANG" | cut -c1-2)
fi

# Get current volume for toggle logic
VOL=$(pactl get-source-volume @DEFAULT_SOURCE@ | grep -Po '\d+(?=%)' | head -n 1)
if [ -z "$VOL" ]; then VOL=0; fi

case "$LANGUAGE" in
    es)
        prompt="Micrófono"
        apps_option="  Aplicaciones en uso"
        no_apps="Ninguna aplicación activa"
        header="Programas usando el micrófono:"
        if [ "$VOL" -gt 0 ]; then
            mute_option="  Silenciar (0%)"
        else
            mute_option="  Activar (100%)"
        fi
        ;;
    pt)
        prompt="Microfone"
        apps_option="  Aplicativos em uso"
        no_apps="Nenhum aplicativo ativo"
        header="Programas usando o microfone:"
        if [ "$VOL" -gt 0 ]; then
            mute_option="  Mudo (0%)"
        else
            mute_option="  Desmutar (100%)"
        fi
        ;;
    fr)
        prompt="Microphone"
        apps_option="  Applications en cours d'utilisation"
        no_apps="Aucune application active"
        header="Programmes utilisant le microphone:"
        if [ "$VOL" -gt 0 ]; then
            mute_option="  Muet (0%)"
        else
            mute_option="  Activer le son (100%)"
        fi
        ;;
    ru)
        prompt="Микрофон"
        apps_option="  Используемые приложения"
        no_apps="Нет активных приложений"
        header="Программы, использующие микрофон:"
        if [ "$VOL" -gt 0 ]; then
            mute_option="  Отключить звук (0%)"
        else
            mute_option="  Включить звук (100%)"
        fi
        ;;
    *)
        # Default to English
        prompt="Microphone"
        apps_option="  Applications in use"
        no_apps="No active applications"
        header="Programs using the microphone:"
        if [ "$VOL" -gt 0 ]; then
            mute_option="  Mute (0%)"
        else
            mute_option="  Unmute (100%)"
        fi
        ;;
esac

# Main Menu
selected=$(echo -e "$mute_option\n$apps_option" | rofi -dmenu -p "$prompt" -i -config ~/.config/rofi/config.rasi)

if [ "$selected" == "$mute_option" ]; then
    if [ "$VOL" -gt 0 ]; then
        pactl set-source-volume @DEFAULT_SOURCE@ 0%
    else
        pactl set-source-volume @DEFAULT_SOURCE@ 100%
    fi
elif [ "$selected" == "$apps_option" ]; then
    # Sub-menu: Get list of applications
    # We grep -v "cava" to ignore it, as it uses source monitor just for visualization
    APPS=$(pactl list source-outputs | grep "application.name =" | grep -v -i "cava" | cut -d'"' -f2 | sort -u)
    if [ -z "$APPS" ]; then
        echo "$no_apps" | rofi -dmenu -p "$prompt" -i -config ~/.config/rofi/config.rasi
    else
        echo -e "$header\n$APPS" | rofi -dmenu -p "$prompt" -i -config ~/.config/rofi/config.rasi
    fi
fi
