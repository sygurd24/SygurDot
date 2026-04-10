#!/bin/bash
if [ -f "$HOME/.config/dotfiles/language" ]; then
    LANGUAGE=$(cat "$HOME/.config/dotfiles/language")
else
    LANGUAGE=$(echo "$LANG" | cut -c1-2)
fi

case "$LANGUAGE" in
    es)
        shutdown=" Apagar"
        reboot=" Reiniciar"
        lock=" Bloquear"
        suspend=" Suspender"
        hibernate=" Hibernar"
        logout=" Cerrar Sesión"
        prompt="Energía"
        ;;
    pt)
        shutdown=" Desligar"
        reboot=" Reiniciar"
        lock=" Bloquear"
        suspend=" Suspender"
        hibernate=" Hibernar"
        logout=" Sair"
        prompt="Energia"
        ;;
    fr)
        shutdown=" Éteindre"
        reboot=" Redémarrer"
        lock=" Verrouiller"
        suspend=" Suspendre"
        hibernate=" Mettre en veille prolongée"
        logout=" Se déconnecter"
        prompt="Énergie"
        ;;
    ru)
        shutdown=" Выключить"
        reboot=" Перезагрузить"
        lock=" Заблокировать"
        suspend=" Спящий режим"
        hibernate=" Гибернация"
        logout=" Выйти"
        prompt="Питание"
        ;;
    *)
        # Default to English
        shutdown=" Shutdown"
        reboot=" Reboot"
        lock=" Lock"
        suspend=" Suspend"
        hibernate=" Hibernate"
        logout=" Logout"
        prompt="Power"
        ;;
esac

# Build options list dynamically
options_array=("$lock" "$shutdown" "$reboot" "$suspend")

# Check if hibernation is supported via logind
if busctl call org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager CanHibernate --expect-reply=true | grep -q "\"yes\""; then
    options_array+=("$hibernate")
fi

options_array+=("$logout")

# Show menu
selected_option=$(printf "%s\n" "${options_array[@]}" | rofi -dmenu -i -p "$prompt" -config ~/.config/rofi/config.rasi)

# Actions
if [ "$selected_option" == "$shutdown" ]; then
    systemctl poweroff
elif [ "$selected_option" == "$reboot" ]; then
    systemctl reboot
elif [ "$selected_option" == "$lock" ]; then
    "$HOME/.config/bspwm/scripts/lock.sh"
elif [ "$selected_option" == "$logout" ]; then
    bspc quit
elif [ "$selected_option" == "$suspend" ]; then
    systemctl suspend
elif [ "$selected_option" == "$hibernate" ]; then
    systemctl hibernate
fi
