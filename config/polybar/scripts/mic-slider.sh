#!/bin/bash
# mic-slider.sh - Matched exactly with volume-slider.sh logic

if ! command -v yad >/dev/null 2>&1; then
    exit 1
fi

get_mic_volume() {
    pactl get-source-volume @DEFAULT_SOURCE@ | grep -Po '\d+(?=%)' | head -n 1
}

set_mic_volume() {
    pactl set-source-volume @DEFAULT_SOURCE@ "${1}%"
}

current_vol=$(get_mic_volume)
pkill -x yad 2>/dev/null

# Exactly the same parameters as volume-slider.sh
SLIDER_WIDTH=220
SLIDER_HEIGHT=38
MARGIN_X=10
MARGIN_Y=45
NUDGE_X=2

get_bspc_anchor() {
    python3 - <<'PY' 2>/dev/null
import json, subprocess, sys
try:
    mon = json.loads(subprocess.check_output(["bspc", "query", "-T", "-m", "focused"], text=True))
    desk = json.loads(subprocess.check_output(["bspc", "query", "-T", "-d", "focused"], text=True))
    root_rect = desk.get("root", {}).get("rectangle", {})
    if root_rect:
        print(f"{root_rect['x'] + root_rect['width'] - desk.get('windowGap', 0) - mon.get('borderWidth', 0)} {root_rect['y']}")
    else:
        rect = mon['rectangle']; pad = mon['padding']; gap = desk.get('windowGap', 0); border = mon.get('borderWidth', 0)
        print(f"{rect['x'] + rect['width'] - pad['right'] - border} {rect['y'] + pad['top'] + gap}")
except: sys.exit(1)
PY
}

if read -r corner_x corner_y < <(get_bspc_anchor); then
    x_pos=$((corner_x - SLIDER_WIDTH - NUDGE_X))
    y_pos=$((corner_y))
    geometry_arg=(--geometry="${SLIDER_WIDTH}x${SLIDER_HEIGHT}+${x_pos}+${y_pos}")
else
    # Fallback to absolute screen position if bspc fails
    read -r screen_w screen_h < <(xdotool getdisplaygeometry)
    x_pos=$((screen_w - SLIDER_WIDTH - MARGIN_X - NUDGE_X))
    y_pos=$MARGIN_Y
    geometry_arg=(--geometry="${SLIDER_WIDTH}x${SLIDER_HEIGHT}+${x_pos}+${y_pos}")
fi

yad --class="MicSlider" --name="MicSlider" \
    --scale --min-value=0 --max-value=200 --value="$current_vol" --title="Microphone" \
    --width="$SLIDER_WIDTH" --height="$SLIDER_HEIGHT" --undecorated --no-buttons \
    --print-partial --close-on-unfocus --on-top --sticky \
    --window-icon="audio-input-microphone" "${geometry_arg[@]}" | while read -r vol; do
        if [[ "$vol" =~ ^[0-9]+$ ]]; then
            set_mic_volume "$vol"
        fi
    done
