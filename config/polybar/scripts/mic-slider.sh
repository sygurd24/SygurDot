#!/bin/bash
if ! command -v yad >/dev/null 2>&1; then exit 1; fi

get_mic_volume() {
    pactl get-source-volume "$(pactl get-default-source)" | grep -Po '\d+(?=%)' | head -n 1
}

# Anchor logic
SLIDER_WIDTH=220
SLIDER_HEIGHT=38
MARGIN_X=10
MARGIN_Y=45
NUDGE_X=2

# We need to get the anchor using python since bash command sub is tricky with security filters
get_bspc_anchor() {
    python3 - <<'PY'
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
except: print("0 0")
PY
}

coords=$(get_bspc_anchor)
corner_x=$(echo $coords | cut -d' ' -f1)
corner_y=$(echo $coords | cut -d' ' -f2)

x_pos=$((corner_x - SLIDER_WIDTH - NUDGE_X))
y_pos=$corner_y

yad --class="MicSlider" --name="MicSlider" \
    --scale --min-value=0 --max-value=200 --value="$(get_mic_volume)" --title="Microphone" \
    --width="$SLIDER_WIDTH" --height="$SLIDER_HEIGHT" --undecorated --no-buttons \
    --print-partial --close-on-unfocus --on-top --sticky \
    --window-icon="audio-input-microphone" --geometry="${SLIDER_WIDTH}x${SLIDER_HEIGHT}+${x_pos}+${y_pos}" | while read -r vol; do
        if [[ "$vol" =~ ^[0-9]+$ ]]; then
            python3 -c "import subprocess; 
sources = subprocess.check_output(['pactl', 'list', 'short', 'sources'], text=True).splitlines()
for s in sources:
    if 'monitor' not in s:
        subprocess.run(['pactl', 'set-source-volume', s.split('\t')[1], '$vol%'])"
        fi
    done
