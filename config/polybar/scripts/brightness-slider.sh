#!/bin/bash
# brightness-slider.sh

if ! command -v yad >/dev/null 2>&1; then
    exit 1
fi

get_brightness() {
    brightnessctl i | grep -oP '\(\d+%\)' | tr -d '()%' | head -n 1
}

set_brightness() {
    brightnessctl set "${1}%"
}

current_val=$(get_brightness)
if [[ ! "$current_val" =~ ^[0-9]+$ ]]; then
    current_val=0
fi

# Close any existing slider to avoid duplicates
pkill -x yad 2>/dev/null

# Geometry: top-right, horizontal slider (align with tiling area)
SLIDER_WIDTH=220
SLIDER_HEIGHT=38
MARGIN_X=10
MARGIN_Y=45
NUDGE_X=2

get_bspc_anchor() {
    if ! command -v bspc >/dev/null 2>&1; then
        return 1
    fi

    python3 - <<'PY' 2>/dev/null
import json
import subprocess
import sys

try:
    mon = json.loads(subprocess.check_output(["bspc", "query", "-T", "-m", "focused"], text=True))
    desk = json.loads(subprocess.check_output(["bspc", "query", "-T", "-d", "focused"], text=True))
except Exception:
    sys.exit(1)

root = (desk or {}).get("root") or {}
root_rect = root.get("rectangle") or {}
if root_rect:
    rx = root_rect.get("x")
    ry = root_rect.get("y")
    rw = root_rect.get("width")
    gap = (desk or {}).get("windowGap", 0) or 0
    border = (desk or {}).get("borderWidth")
    if border is None:
        border = (mon or {}).get("borderWidth", 0) or 0
    if None not in (rx, ry, rw):
        print(f"{rx + rw - gap - border} {ry}")
        sys.exit(0)

rect = (mon or {}).get("rectangle") or {}
pad = (mon or {}).get("padding") or {}

x = rect.get("x")
y = rect.get("y")
w = rect.get("width")
if None in (x, y, w):
    sys.exit(1)

pt = pad.get("top", 0) or 0
pr = pad.get("right", 0) or 0
gap = (desk or {}).get("windowGap", 0) or 0
border = (desk or {}).get("borderWidth")
if border is None:
    border = (mon or {}).get("borderWidth", 0) or 0

corner_x = x + w - pr
corner_y = y + pt + gap
corner_x = corner_x - border

print(f"{corner_x} {corner_y}")
PY
}

get_primary_geometry() {
    if command -v xrandr >/dev/null 2>&1; then
        xrandr --query | awk '/ primary/{print $4; exit}'
    fi
}

geom="$(get_primary_geometry)"
if [[ "$geom" =~ ^([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+)$ ]]; then
    screen_w="${BASH_REMATCH[1]}"
    screen_h="${BASH_REMATCH[2]}"
    offset_x="${BASH_REMATCH[3]}"
    offset_y="${BASH_REMATCH[4]}"
elif command -v xdotool >/dev/null 2>&1; then
    read -r screen_w screen_h < <(xdotool getdisplaygeometry)
    offset_x=0
    offset_y=0
fi

geometry_arg=()
if command -v bspc >/dev/null 2>&1; then
    if read -r corner_x corner_y < <(get_bspc_anchor); then
        if [[ "$corner_x" =~ ^-?[0-9]+$ ]] && [[ "$corner_y" =~ ^-?[0-9]+$ ]]; then
            x_pos=$((corner_x - SLIDER_WIDTH - NUDGE_X))
            y_pos=$((corner_y))
            bspc rule -a -o BrightnessSlider state=floating rectangle=${SLIDER_WIDTH}x${SLIDER_HEIGHT}+${x_pos}+${y_pos} 2>/dev/null
            geometry_arg=(--geometry="${SLIDER_WIDTH}x${SLIDER_HEIGHT}+${x_pos}+${y_pos}")
        fi
    fi
fi

if [[ -n "$screen_w" ]]; then
    if [[ ${#geometry_arg[@]} -eq 0 ]]; then
        x_pos=$((offset_x + screen_w - SLIDER_WIDTH - MARGIN_X - NUDGE_X))
        y_pos=$((offset_y + MARGIN_Y))
        geometry_arg=(--geometry="${SLIDER_WIDTH}x${SLIDER_HEIGHT}+${x_pos}+${y_pos}")
    fi
fi

yad --class="BrightnessSlider" --name="BrightnessSlider" \
    --scale --min-value=1 --max-value=100 --value="$current_val" --title="Brightness" \
    --width="$SLIDER_WIDTH" --height="$SLIDER_HEIGHT" --undecorated --no-buttons \
    --print-partial --close-on-unfocus --on-top --sticky \
    --window-icon="display-brightness" "${geometry_arg[@]}" | while read -r val; do
        if [[ "$val" =~ ^[0-9]+$ ]]; then
            set_brightness "$val"
        fi
    done
