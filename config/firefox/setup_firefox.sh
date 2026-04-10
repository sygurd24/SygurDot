#!/bin/bash
# setup_youtube_fullscreen.sh - Configures Firefox to stay in bspwm tiles during fullscreen.

set -e

# Get the password from the first argument or prompt
PASSWORD="$1"

run_sudo() {
    if [ -n "$PASSWORD" ]; then
        echo "$PASSWORD" | sudo -S "$@"
    else
        sudo "$@"
    fi
}

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLICIES_SRC="$DOTFILES_DIR/config/firefox/policies.json"

echo "Configuring Firefox global policies..."

# Update the dotfiles policy to true before applying (Robust regex)
sed -i 's/"full-screen-api.ignore-widgets":\s*{\s*"Value":\s*false/"full-screen-api.ignore-widgets": { "Value": true/g' "$POLICIES_SRC"


if [ -f "$POLICIES_SRC" ]; then
    run_sudo mkdir -p /etc/firefox/policies
    run_sudo cp "$POLICIES_SRC" /etc/firefox/policies/policies.json
    
    for ff_install in "/usr/lib/firefox" "/usr/lib/firefox-esr"; do
        if [ -d "$ff_install" ]; then
            run_sudo mkdir -p "$ff_install/distribution"
            run_sudo cp "$POLICIES_SRC" "$ff_install/distribution/policies.json"
        fi
    done
fi

echo "Configuring Firefox user profiles..."
# Firefox might not have been opened yet, so these directories might be missing.
# We only apply to existing profiles; the system policy handles new ones.
for ff_dir in "$HOME/.mozilla/firefox" "$HOME/.config/mozilla/firefox"; do
    if [ -d "$ff_dir" ]; then
        find "$ff_dir" -maxdepth 1 -type d -name "*.*" | while read -r profile; do
            # Skip non-profile directories
            [ "$(basename "$profile")" == "firefox" ] && continue
            [ ! -f "$profile/prefs.js" ] && [ ! -f "$profile/user.js" ] && continue
            
            echo "Applying settings to profile: $(basename "$profile")"
            cat > "$profile/user.js" << 'EOF'
user_pref("full-screen-api.ignore-widgets", true);
user_pref("full-screen-api.transition-duration.enter", "0 0");
user_pref("full-screen-api.transition-duration.leave", "0 0");
user_pref("full-screen-api.warning.timeout", 0);
EOF
        done
    fi
done


echo "Ensuring bspwm rules are active..."
# Re-add state=tiled if missing (simple grep/append)
if ! grep -q "bspc rule -a 'Firefox' state=tiled" "$DOTFILES_DIR/config/bspwm/bspwmrc"; then
    sed -i "/# Reglas de Firefox/a bspc rule -a 'firefox' state=tiled focus=on follow=on\nbspc rule -a 'Firefox' state=tiled focus=on follow=on" "$DOTFILES_DIR/config/bspwm/bspwmrc"
fi

bspc wm -r

echo "SUCCESS: YouTube fullscreen should now stay within the bspwm mosaic."
echo "Please restart Firefox to apply changes."
