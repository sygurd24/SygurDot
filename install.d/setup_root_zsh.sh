#!/bin/bash
# setup_root_zsh.sh - Configure Powerlevel10k for root user.

set -e

PASSWORD="$1"

run_sudo() {
    if [ -n "$PASSWORD" ]; then
        echo "$PASSWORD" | sudo -S "$@"
    else
        sudo "$@"
    fi
}

echo "[INFO] Changing root shell to zsh..."
run_sudo chsh -s /usr/bin/zsh root

echo "[INFO] Copying Zsh configuration and plugins to /root..."
run_sudo mkdir -p /root/.zsh
# Use sync to be safe
run_sudo cp -r "$HOME/.zsh/"* /root/.zsh/ 2>/dev/null || true
run_sudo cp "$HOME/.zshrc" /root/.zshrc
run_sudo cp "$HOME/.p10k.zsh" /root/.p10k.zsh

echo "[INFO] Personalizing root prompt..."
run_sudo bash -c "cat << 'EOF' >> /root/.p10k.zsh

# Root user customizations (Added by setup_root_zsh.sh)
typeset -g POWERLEVEL9K_CONTEXT_ROOT_TEMPLATE='ROOT'
typeset -g POWERLEVEL9K_CONTEXT_ROOT_VISUAL_IDENTIFIER_EXPANSION=''
typeset -g POWERLEVEL9K_CONTEXT_ROOT_FOREGROUND=1
typeset -g POWERLEVEL9K_CONTEXT_{DEFAULT,SUDO}_{CONTENT,VISUAL_IDENTIFIER}_EXPANSION=
EOF"

run_sudo chown -R root:root /root/.zsh /root/.zshrc /root/.p10k.zsh

echo "[SUCCESS] root user is now configured with Powerlevel10k."
