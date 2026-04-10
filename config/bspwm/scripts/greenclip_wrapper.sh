#!/bin/bash
# Clipboard manager: greenclip history → rofi dmenu → paste
# Called directly by sxhkd on Super+V

GREENCLIP="$HOME/.local/bin/greenclip"

# 1. Get history (timeout prevents hangs)
HISTORY=$(timeout 1 "$GREENCLIP" print 2>/dev/null)
[ -z "$HISTORY" ] && exit 0

# 2. Format entries and pipe to rofi (icons for images, raw text otherwise)
#    printf writes \0 and \x1f bytes directly to rofi through the pipe
SELECTED=$(echo "$HISTORY" | while IFS= read -r line; do
    [ -z "$line" ] && continue
    if [[ "$line" == image/png* ]]; then
        img_id="${line##* }"
        img_path="/tmp/greenclip/${img_id}.png"
        if [ -f "$img_path" ]; then
            printf 'Image %s\0icon\x1f%s\n' "$img_id" "$img_path"
        else
            printf 'Image %s\n' "$img_id"
        fi
    else
        printf '%s\n' "$line"
    fi
done | rofi -dmenu -i -p " Clipboard" -theme "$HOME/.config/rofi/clipboard.rasi")

# 3. Nothing selected → exit
[ -z "$SELECTED" ] && exit 0

# 4. Copy selection to clipboard
if [[ "$SELECTED" == Image\ * ]]; then
    img_id="${SELECTED#Image }"
    img_path="/tmp/greenclip/${img_id}.png"
    [ -f "$img_path" ] && xclip -selection clipboard -t image/png -i "$img_path"
else
    printf '%s' "$SELECTED" | xclip -selection clipboard
fi

# 5. Auto-paste into the focused window
sleep 0.15
xdotool key --clearmodifiers ctrl+v
