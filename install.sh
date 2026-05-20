#!/bin/bash
set -e

if [ "$EUID" -eq 0 ]; then
    echo "[ERROR] Please do not run this script as root."
    echo "[ERROR] Run it as your normal user, it will prompt for sudo when needed."
    exit 1
fi

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/dotfiles_backup_$(date +%Y%m%d_%H%M%S)"

log() {
    echo "[INFO] $1"
}

warn() {
    echo "[WARN] $1"
}

install_packages() {
    log "Installing packages: $@"
    
    # Check if dpkg is already in a broken state
    if dpkg -l | grep -q "^iU"; then
        warn "System has unconfigured packages. Attempting to fix before proceeding..."
        sudo dpkg --configure -a || true
    fi

    if sudo apt install -y "$@"; then
        log "All packages installed successfully."
    else
        # If the main installation fails, check if it's a systemic error (e.g., DKMS failure)
        # We search for common fatal apt/dpkg error patterns in a temporary log or pipe
        warn "Direct installation failed."
        
        # Avoid the individual retry loop if dpkg is fundamentally broken (e.g. DKMS build failing)
        if dpkg -l | grep -q "^iU"; then
            warn "Systemic configuration error detected (broken dependencies or DKMS). Skipping individual retries to avoid infinite loops."
            return 1
        fi

        warn "Attempting to install packages individually..."
        for pkg in "$@"; do
            if sudo apt install -y "$pkg"; then
                log "Successfully installed $pkg"
            else
                warn "Failed to install $pkg. Skipping."
            fi
        done
    fi
}

nmcli_c() {
    LC_ALL=C LANG=C nmcli "$@"
}

confirm_network_migration() {
    if [ "${DOTFILES_SKIP_NETWORK:-0}" -eq 1 ]; then
        warn "Skipping network migration (DOTFILES_SKIP_NETWORK=1)."
        return 1
    fi

    if [ "${DOTFILES_ASSUME_YES:-0}" -eq 1 ]; then
        return 0
    fi

    if [ -t 0 ] && [ -t 1 ]; then
        printf "Detected ifupdown Wi-Fi config. Migrate to NetworkManager now? This may disconnect Wi-Fi. [y/N] "
        read -r reply
        case "$reply" in
            [yY]|[yY][eE][sS]) return 0 ;;
            *) return 1 ;;
        esac
    fi

    warn "Non-interactive shell; skipping network migration. Set DOTFILES_ASSUME_YES=1 to force."
    return 1
}

setup_network_manager() {
    if ! command -v systemctl &> /dev/null; then
        return 0
    fi

    sudo systemctl enable --now NetworkManager || true
    sudo mkdir -p /etc/NetworkManager/conf.d || true
    if ! cat <<'EOF' | sudo tee /etc/NetworkManager/conf.d/99-dotfiles-managed.conf > /dev/null; then
[ifupdown]
managed=true
EOF
        warn "Failed to write /etc/NetworkManager/conf.d/99-dotfiles-managed.conf"
    fi

    # Fix: MediaTek MT7921/MT7922 crashes when NM randomizes MAC addresses on scans
    if ! cat <<'EOF' | sudo tee /etc/NetworkManager/conf.d/disable-random-mac.conf > /dev/null; then
[device]
wifi.scan-rand-mac-address=no
EOF
        warn "Failed to write /etc/NetworkManager/conf.d/disable-random-mac.conf"
    fi
    sudo systemctl restart NetworkManager || true

    if ! command -v nmcli &> /dev/null; then
        return 0
    fi

    nmcli_c -t -f DEVICE,TYPE dev status | awk -F: '$2=="wifi"{print $1}' | while read -r dev; do
        [ -n "$dev" ] && sudo env LC_ALL=C LANG=C nmcli dev set "$dev" managed yes || true
    done

    WIFI_UNMANAGED=0
    if nmcli_c -t -f DEVICE,TYPE,STATE dev status | awk -F: '$2=="wifi" && $3=="unmanaged"{exit 0} END{exit 1}'; then
        WIFI_UNMANAGED=1
    fi

    WIFI_IFUPDOWN=0
    if [ -f /etc/network/interfaces ]; then
        if grep -qE '^[[:space:]]*[^#].*wpa-(ssid|psk)' /etc/network/interfaces || \
           grep -qE '^[[:space:]]*[^#].*(allow-hotplug|auto)[[:space:]]+(en|eth|wlan|wlo|wl)' /etc/network/interfaces || \
           grep -qE '^[[:space:]]*[^#].*iface[[:space:]]+(en|eth|wlan|wlo|wl)' /etc/network/interfaces; then
            WIFI_IFUPDOWN=1
        fi
    fi

    IFD_WIFI_FILES=()
    if [ -d /etc/network/interfaces.d ]; then
        while IFS= read -r -d '' f; do
            if grep -qE '^[[:space:]]*[^#].*wpa-(ssid|psk)' "$f" || \
               grep -qE '^[[:space:]]*[^#].*(allow-hotplug|auto)[[:space:]]+(en|eth|wlan|wlo|wl)' "$f" || \
               grep -qE '^[[:space:]]*[^#].*iface[[:space:]]+(en|eth|wlan|wlo|wl)' "$f"; then
                WIFI_IFUPDOWN=1
                IFD_WIFI_FILES+=("$f")
            fi
        done < <(find /etc/network/interfaces.d -maxdepth 1 -type f -print0)
    fi

    if [ "$WIFI_UNMANAGED" -eq 1 ] || [ "$WIFI_IFUPDOWN" -eq 1 ]; then
        if ! confirm_network_migration; then
            warn "Skipping ifupdown migration."
            return 0
        fi

        log "Detected ifupdown Network config. Migrating control to NetworkManager..."
        if [ -f /etc/network/interfaces ]; then
            IF_BACKUP="/etc/network/interfaces.dotfiles.bak.$(date +%Y%m%d_%H%M%S)"
            sudo cp /etc/network/interfaces "$IF_BACKUP" || true
        fi
        if ! cat <<'EOF' | sudo tee /etc/network/interfaces > /dev/null; then
# Managed by dotfiles to allow NetworkManager to control Wi-Fi and Ethernet.
source /etc/network/interfaces.d/*
auto lo
iface lo inet loopback
EOF
            warn "Failed to write /etc/network/interfaces; skipping migration."
            return 0
        fi

        if [ "${#IFD_WIFI_FILES[@]}" -gt 0 ]; then
            IFD_BACKUP="/etc/network/interfaces.d.dotfiles.bak.$(date +%Y%m%d_%H%M%S)"
            sudo mkdir -p "$IFD_BACKUP" || true
            for f in "${IFD_WIFI_FILES[@]}"; do
                sudo mv "$f" "$IFD_BACKUP/" || true
            done
        fi

        sudo systemctl disable --now networking || true
        sudo systemctl restart NetworkManager || true
    fi
}

setup_locales() {
    log "Ensuring necessary locales (en_US, es_ES, pt_BR, fr_FR, ru_RU) are generated..."
    local needs_gen=0
    if ! locale -a | grep -q "en_US.utf8"; then needs_gen=1; fi
    if ! locale -a | grep -q "es_ES.utf8"; then needs_gen=1; fi
    if ! locale -a | grep -q "pt_BR.utf8"; then needs_gen=1; fi
    if ! locale -a | grep -q "fr_FR.utf8"; then needs_gen=1; fi
    if ! locale -a | grep -q "ru_RU.utf8"; then needs_gen=1; fi

    if [ "$needs_gen" -eq 1 ]; then
        log "Generating locales... this may take a moment."
        sudo sed -i '/^#.*en_US.UTF-8 UTF-8/s/^#//' /etc/locale.gen 2>/dev/null || true
        sudo sed -i '/^#.*es_ES.UTF-8 UTF-8/s/^#//' /etc/locale.gen 2>/dev/null || true
        sudo sed -i '/^#.*pt_BR.UTF-8 UTF-8/s/^#//' /etc/locale.gen 2>/dev/null || true
        sudo sed -i '/^#.*fr_FR.UTF-8 UTF-8/s/^#//' /etc/locale.gen 2>/dev/null || true
        sudo sed -i '/^#.*ru_RU.UTF-8 UTF-8/s/^#//' /etc/locale.gen 2>/dev/null || true
        sudo locale-gen || true
    else
        log "Locales already generated."
    fi
}

setup_battery_threshold() {
    # Check if the system supports battery charge thresholds
    if [ -d /sys/class/power_supply/BAT0 ] && [ -f /sys/class/power_supply/BAT0/charge_control_end_threshold ]; then
        log "Battery charge threshold support detected. Setting up sudoers rule for passwordless control..."
        sudo mkdir -p /etc/sudoers.d
        # We use $USER instead of hardcoding to make it generic for fresh installs
        echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/power_supply/BAT0/charge_control_end_threshold" | sudo tee /etc/sudoers.d/battery_threshold > /dev/null
        sudo chmod 440 /etc/sudoers.d/battery_threshold
        log "Battery threshold sudoers rule created."
    else
        log "Battery charge threshold support not detected or not found at BAT0. Skipping sudoers rule."
    fi
}



# 1. Install dependencies
PACKAGES="bspwm sxhkd polybar picom rofi kitty zsh thunar gvfs gvfs-backends gtk2-engines-murrine gtk2-engines-pixbuf lsd bat xinput xss-lock feh scrot maim slop imagemagick libinput-tools libnotify-bin dunst arc-theme papirus-icon-theme firefox xclip xdotool python3 python3-dbus python3-gi python3-psutil python3-pip python3-setuptools gir1.2-glib-2.0 cava pavucontrol btop flameshot expect network-manager nm-connection-editor bc playerctl brightnessctl bluez blueman pipewire pipewire-pulse pipewire-alsa wireplumber libspa-0.2-bluetooth pulseaudio-utils psmisc lsof upower git wget fontconfig yad xorg xinit x11-xserver-utils dbus-x11 linux-headers-amd64 build-essential libegl1-mesa-dev libgl1-mesa-dev"

setup_graphics() {
    log "Configuring Graphics (Hybrid or Integrated)..."

    local vendor=""
    # Identify vendor using PCI IDs for 100% accuracy
    # 8086 = Intel, 1002 = AMD, 10de = NVIDIA
    if lspci -n | grep -iE "0300|0302|0380" | grep -iq "1002"; then
        vendor="amd"
    elif lspci -n | grep -iE "0300|0302|0380" | grep -iq "8086"; then
        vendor="intel"
    fi

    local has_nvidia=0
    local is_rtx5000=0
    if lspci | grep -iE 'vga|3d|display' | grep -iq 'nvidia'; then
        has_nvidia=1
        if lspci -n | grep -iE "0300|0302|0380" | grep -iq "10de:2d"; then
            is_rtx5000=1
        fi
    fi

    local gpu_pkgs="xinit xserver-xorg firmware-linux firmware-misc-nonfree dkms build-essential linux-headers-$(uname -r)"
    if [ "$has_nvidia" -eq 1 ]; then
        if [ "$is_rtx5000" -eq 1 ]; then
            log "NVIDIA RTX 5000 Series (Blackwell) GPU detected!"
            log "Blacklisting nouveau driver to prepare for official NVIDIA driver..."
            sudo mkdir -p /etc/modprobe.d
            echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nouveau.conf > /dev/null
            echo "options nouveau modeset=0" | sudo tee -a /etc/modprobe.d/blacklist-nouveau.conf > /dev/null
            
            log "Enabling 32-bit architecture for Steam compatibility..."
            sudo dpkg --add-architecture i386
            sudo apt-get update
            
            log "Installing build dependencies for official NVIDIA driver..."
            install_packages build-essential pkg-config libglvnd-dev dkms linux-headers-$(uname -r) pkg-config:i386 libc6:i386

            DRIVER_VER="595.58.03"
            log "Downloading NVIDIA Official Driver v${DRIVER_VER} (Blackwell support)..."
            # Retry loop for wget to ensure download completes
            local retry=0
            while [ $retry -lt 3 ]; do
                if wget -c -O /tmp/nvidia.run "https://us.download.nvidia.com/XFree86/Linux-x86_64/${DRIVER_VER}/NVIDIA-Linux-x86_64-${DRIVER_VER}.run"; then
                    break
                fi
                retry=$((retry + 1))
                log "Download failed. Retrying ($retry/3)..."
                sleep 5
            done
            chmod +x /tmp/nvidia.run

            log "Executing NVIDIA Official Installer (Open Kernel Modules + 32-bit Compat)..."
            # Compile with open modules; vital for GSP firmware on Blackwell
            sudo /tmp/nvidia.run --silent --dkms --no-nouveau-check --accept-license --kernel-module-type=open --no-questions || warn "NVIDIA Installer might have failed or needs TTY. Run 'sudo /tmp/nvidia.run' manually if GPU fails."
            
            # CRITICAL FIX: Do NOT install firmware-nvidia-gsp via apt here, as it conflicts with the version provided by the Nvidia Runfile.
            if [ "$vendor" = "amd" ]; then
                log "AMD + Blackwell topology detected. Injecting amd_iommu=off to gracefully initialize GSP firmware..."
                if [ -f /etc/default/grub ]; then
                    if ! grep -q "amd_iommu=off" /etc/default/grub; then
                        sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="amd_iommu=off /' /etc/default/grub
                        sudo update-grub || warn "Failed to update grub."
                    fi
                fi
            fi
        else
            # Universal fallback for older NVIDIA cards (e.g. GTX 10xx, MX350, RTX 30xx)
            gpu_pkgs="$gpu_pkgs nvidia-driver firmware-nvidia-gsp"
        fi
    fi

    if [ "$vendor" = "amd" ]; then
        log "AMD CPU/iGPU detected. Ensuring NPU firmware is included."
        gpu_pkgs="$gpu_pkgs firmware-amd-graphics xserver-xorg-video-amdgpu"
    elif [ "$vendor" = "intel" ]; then
        log "Intel CPU/iGPU detected."
        gpu_pkgs="$gpu_pkgs xserver-xorg-video-intel"
    fi

    log "Installing graphics dependencies: $gpu_pkgs"
    install_packages $gpu_pkgs

    if [ "$has_nvidia" -eq 1 ]; then
        log "NVIDIA Dedicated GPU detected. Setting up DRM and PRIME Render Offload..."
        
        local is_tigerlake=0
        local pci_igpu_chk=$(lspci | grep -iE 'vga|3d|display' | grep -iE 'intel' | awk '{print $1}' | head -n 1)
        if [ -n "$pci_igpu_chk" ]; then
            local igpu_id_chk=$(lspci -n -s "$pci_igpu_chk" | awk '{print $3}')
            if echo "$igpu_id_chk" | grep -iq '9a49\|9a40\|9a78\|9ac0\|9ac9\|9ad9'; then
                is_tigerlake=1
            fi
        fi

        if [ "$is_tigerlake" -eq 1 ]; then
            log "Tiger Lake detected. Skipping 'nvidia-drm modeset=1' to avoid Xorg/bspwm KMS deadlock."
            log "Applying pure Intel deadlock fix: Blacklisting the conflicting 'xe' kernel module."
            sudo mkdir -p /etc/modprobe.d
            echo "blacklist xe" | sudo tee /etc/modprobe.d/blacklist-xe.conf > /dev/null
            log "Updating initramfs..."
            sudo update-initramfs -u
        else
            # Early KMS: force drivers into initramfs only for detected hardware
            sudo mkdir -p /etc/initramfs-tools
            local mods=""
            [ "$vendor" = "amd" ] && mods="$mods amdgpu"
            [ "$vendor" = "intel" ] && mods="$mods i915 xe"
            if [ "$has_nvidia" -eq 1 ]; then
                mods="$mods nvidia nvidia_modeset nvidia_uvm nvidia_drm"
                log "Blacklisting 'nouveau' to prevent XOrg crashes on NVIDIA hardware..."
                sudo mkdir -p /etc/modprobe.d
                printf 'blacklist nouveau\noptions nouveau modeset=0\n' | sudo tee /etc/modprobe.d/blacklist-nouveau.conf > /dev/null
            fi

            for m in $mods; do
                if ! grep -q "^$m" /etc/initramfs-tools/modules 2>/dev/null; then
                    log "Adding $m to initramfs-tools/modules..."
                    echo "$m" | sudo tee -a /etc/initramfs-tools/modules > /dev/null
                fi
            done

            log "Updating initramfs..."
            sudo update-initramfs -u

            local params="quiet splash"
            
            # BLACKWELL FIX: NVIDIA Blackwell (RTX 50xx) deadlocks with nvidia-drm.modeset=1 on many laptop topologies.
            # We also need pcie_port_pm=off to stabilize GSP firmware on HP Victus.
            if [ "$is_rtx5000" -eq 1 ]; then
                log "Blackwell detected: Optimizing for stability (No KMS modeset + PCIe PM off)."
                params="$params pcie_port_pm=off nvidia_drm.fbdev=1"
            else
                [ "$has_nvidia" -eq 1 ] && params="$params nvidia-drm.modeset=1 nvidia_drm.fbdev=1"
            fi

            [ "$vendor" = "amd" ] && params="$params amdgpu.backlight=0"
            # amd_iommu=off is specific to AMD+NVIDIA GSP firmware stabilization
            if [ "$vendor" = "amd" ] && [ "$has_nvidia" -eq 1 ]; then
                params="$params amd_iommu=off"
            fi

            # FIX: Prevenir Deadlock del Kernel (Congelamiento de Pantalla/Ventanas) en AMD Krackan (HP Victus)
            # Desactiva Scatter/Gather y Panel Self Refresh (PSR) en la iGPU de AMD
            if [ "$vendor" = "amd" ]; then
                log "Inyectando mitigaciones de PSR y Scatter/Gather para estabilidad de pantalla en AMD..."
                params="$params amdgpu.sg_display=0 amdgpu.dcdebugmask=0x10"
            fi

            for param in $params; do
                if ! grep -q "$param" /etc/default/grub; then
                    log "Inyectando $param en GRUB..."
                    sudo sed -i "s/GRUB_CMDLINE_LINUX_DEFAULT=\"/GRUB_CMDLINE_LINUX_DEFAULT=\"$param /" /etc/default/grub
                fi
            done
            sudo update-grub || warn "Failed to update grub."
        fi

        log "Generating dynamic Xorg configuration for Hybrid topology..."
        sudo mkdir -p /etc/X11/xorg.conf.d

        calc_busid() {
            local hex_addr="$1"
            # Robust parsing reading from right to left to avoid domain (0000:) issues if present
            local func="${hex_addr##*.}"
            local addr_no_func="${hex_addr%.*}"
            local dev="${addr_no_func##*:}"
            local addr_no_dev="${addr_no_func%:*}"
            local bus="${addr_no_dev##*:}"
            
            printf "PCI:%d:%d:%d\n" "0x$bus" "0x$dev" "0x$func"
        }

        local pci_igpu=""
        local pci_nvidia=""

        # To prevent pipeline set -e issues, '|| true' validates edge cases silently
        while read -r pci_line; do
            local pci_addr=$(echo "$pci_line" | awk '{print $1}')
            if echo "$pci_line" | grep -iq 'nvidia'; then
                pci_nvidia="$pci_addr"
            elif echo "$pci_line" | grep -iq 'intel\|amd\|radeon\|ati'; then
                pci_igpu="$pci_addr"
            fi
        done < <(lspci | grep -iE 'vga|3d|display' || true)

        if [ -n "$pci_igpu" ] && [ -n "$pci_nvidia" ]; then
            # We no longer strictly check for the nvidia module here, because on a fresh
            # installation it might not be loaded yet until the first reboot. 
            # We proceed with the configuration and warn the user.
            local nvidia_present=0
            if lsmod | grep -q "^nvidia" || sudo modprobe nvidia 2>/dev/null; then
                nvidia_present=1
            fi

            local busid_igpu=$(calc_busid "$pci_igpu")
            local busid_nvidia=$(calc_busid "$pci_nvidia")
            local igpu_driver="modesetting"
            local igpu_id=""
            
            if [ -n "$pci_igpu" ]; then
                igpu_id=$(lspci -n -s "$pci_igpu" | awk '{print $3}')
            fi
                
            if [ "$vendor" = "amd" ]; then
                igpu_driver="amdgpu"
            elif [ "$vendor" = "intel" ]; then
                igpu_driver="modesetting"
            fi

            if echo "$igpu_id" | grep -iq '9a49\|9a40\|9a78\|9ac0\|9ac9\|9ad9'; then
                log "Tiger Lake / Iris Xe detected."
                log "Skipping /etc/X11/xorg.conf.d/10-hibrido.conf creation to prevent ServerLayout freezes."
                log "PRIME Offload is handled automatically by the NVIDIA driver on modern Debian."
            else
                cat <<EOF | sudo tee /etc/X11/xorg.conf.d/10-hibrido.conf > /dev/null
# Generated by SygurDot Install Script
# Documentation: https://download.nvidia.com/XFree86/Linux-x86_64/535.104.05/README/primerenderoffload.html

Section "ServerLayout"
    Identifier "layout"
    Screen 0 "iGPU"
    Inactive "nvidia"
    Option "AllowNVIDIAGPUScreens"
EndSection

Section "Device"
    Identifier "iGPU"
    Driver "$igpu_driver"
    BusID "$busid_igpu"
    Option "TearFree" "true"
EndSection

Section "Screen"
    Identifier "iGPU"
    Device "iGPU"
EndSection

Section "Device"
    Identifier "nvidia"
    Driver "nvidia"
    BusID "$busid_nvidia"
    Option "AllowEmptyInitialConfiguration"
EndSection

# OutputClass sections force proper GPU routing on modern NVIDIA (Blackwell/Ada/Turing)
# Prevents the "Failed to create pixmap" error when modesetting auto-detects NVIDIA
Section "OutputClass"
    Identifier "nvidia"
    MatchDriver "nvidia-drm"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration"
    Option "PrimaryGPU" "no"
EndSection

Section "OutputClass"
    Identifier "${igpu_driver}"
    MatchDriver "${igpu_driver}"
    Driver "${igpu_driver}"
    Option "PrimaryGPU" "yes"
EndSection
EOF
                log "Hybrid graphics Xorg configuration created successfully with dynamic BusIDs."
                log "iGPU: BusID $busid_igpu, Driver $igpu_driver"
                log "NVIDIA: BusID $busid_nvidia"
            fi
                
            if [ "$nvidia_present" -eq 0 ]; then
                warn "NVIDIA module is not loaded yet. REBOOT is required for hybrid graphics to work."
            fi
        else
            warn "Could not identify both iGPU and NVIDIA GPU perfectly. Skipping dynamic Xorg configuration."
        fi
    else
        log "No NVIDIA Dedicated GPU detected. Proceeding without Hybrid setup."
    fi
}

log "Detected Debian/Ubuntu system. Configuring repositories..."
if command -v apt &> /dev/null; then
    # Ensure contrib and non-free are enabled for firmware and drivers
    sudo sed -i 's/main/main contrib non-free non-free-firmware/g' /etc/apt/sources.list
    
    # 1.0 Setup Mozilla Repository for Firefox Stable
    if [ ! -f /etc/apt/sources.list.d/mozilla.list ]; then
        log "Setting up Mozilla repository for Firefox Stable..."
        sudo mkdir -p /etc/apt/keyrings
        wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | sudo tee /etc/apt/keyrings/packages.mozilla.org.gpg > /dev/null
        echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.gpg] https://packages.mozilla.org/apt mozilla main" | sudo tee /etc/apt/sources.list.d/mozilla.list > /dev/null
        echo '
Package: *
Pin: origin packages.mozilla.org
Pin-Priority: 1000
' | sudo tee /etc/apt/preferences.d/mozilla > /dev/null
    fi

    sudo apt update
    setup_locales
    setup_graphics
    install_packages $PACKAGES

    # Try to install fastfetch if available, otherwise warn
    if apt-cache search fastfetch | grep -q fastfetch; then
        sudo apt install -y fastfetch
    else
        warn "Fastfetch not found in default repos. You might need to install it manually from GitHub releases."
    fi
else
    warn "Package manager 'apt' not found. Please install these manually: $PACKAGES"
fi





# 1.3 Install i3lock-color (replaces standard i3lock)
if ! i3lock --version 2>&1 | grep -q "i3lock-color"; then
    # Prefer distro package if available
    if apt-cache search i3lock-color | grep -q "^i3lock-color"; then
        log "Installing i3lock-color from apt..."
        sudo apt install -y i3lock-color
    else
        log "Installing i3lock-color from source..."
        I3LOCK_BUILD_DEPS="autoconf gcc make pkg-config libpam0g-dev libcairo2-dev libfontconfig1-dev libxcb-composite0-dev libev-dev libx11-xcb-dev libxcb-xkb-dev libxcb-xinerama0-dev libxcb-randr0-dev libxcb-image0-dev libxcb-util-dev libxcb-xrm-dev libxkbcommon-dev libxkbcommon-x11-dev libjpeg-dev libgif-dev"
        sudo apt install -y $I3LOCK_BUILD_DEPS
        I3LOCK_TMP=$(mktemp -d)

        if getent hosts github.com > /dev/null 2>&1; then
            if git clone --depth=1 https://github.com/Raymo111/i3lock-color.git "$I3LOCK_TMP"; then
                if (cd "$I3LOCK_TMP" && ./build.sh); then
                    sudo install -m 755 "$I3LOCK_TMP/build/i3lock" /usr/local/bin/i3lock
                    log "i3lock-color installed to /usr/local/bin/i3lock"
                else
                    warn "i3lock-color build failed. You can retry later when the network is stable."
                fi
            else
                warn "Failed to clone i3lock-color from GitHub. You can retry later when the network is stable."
            fi
        else
            warn "DNS/network unavailable for github.com. Skipping i3lock-color build."
        fi

        rm -rf "$I3LOCK_TMP"
        cd "$DOTFILES_DIR"
    fi
else
    log "i3lock-color already installed."
fi

# 1.2 Install Powerlevel10k
P10K_DIR="$HOME/.zsh/powerlevel10k"
if [ -d "$P10K_DIR/.git" ]; then
    log "Powerlevel10k already installed."
elif [ -d "$P10K_DIR" ]; then
    warn "Powerlevel10k directory exists but is not a git repo. Skipping."
else
    log "Installing Powerlevel10k..."
    if getent hosts github.com > /dev/null 2>&1; then
        if git clone --depth=1 https://github.com/romkatv/powerlevel10k.git "$P10K_DIR"; then
            log "Powerlevel10k installed to ~/.zsh/powerlevel10k"
        else
            warn "Failed to clone Powerlevel10k. You can retry later when the network is stable."
        fi
    else
        warn "DNS/network unavailable for github.com. Skipping Powerlevel10k."
    fi
fi



# 1.2 Install Zsh Plugins
mkdir -p "$HOME/.zsh"
if [ ! -d "$HOME/.zsh/zsh-autosuggestions/.git" ]; then
    if [ -d "$HOME/.zsh/zsh-autosuggestions" ]; then
        warn "zsh-autosuggestions exists but is not a git repo. Skipping."
    else
        log "Installing zsh-autosuggestions..."
        if getent hosts github.com > /dev/null 2>&1; then
            if ! git clone https://github.com/zsh-users/zsh-autosuggestions "$HOME/.zsh/zsh-autosuggestions"; then
                warn "Failed to clone zsh-autosuggestions. You can retry later when the network is stable."
            fi
        else
            warn "DNS/network unavailable for github.com. Skipping zsh-autosuggestions."
        fi
    fi
fi
if [ ! -d "$HOME/.zsh/zsh-syntax-highlighting/.git" ]; then
    if [ -d "$HOME/.zsh/zsh-syntax-highlighting" ]; then
        warn "zsh-syntax-highlighting exists but is not a git repo. Skipping."
    else
        log "Installing zsh-syntax-highlighting..."
        if getent hosts github.com > /dev/null 2>&1; then
            if ! git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "$HOME/.zsh/zsh-syntax-highlighting"; then
                warn "Failed to clone zsh-syntax-highlighting. You can retry later when the network is stable."
            fi
        else
            warn "DNS/network unavailable for github.com. Skipping zsh-syntax-highlighting."
        fi
    fi
fi

# i3lock-color and other dependencies were processed above.

# 2. Link Dotfiles
create_link() {
    local src="$1"
    local dest="$2"

    if [ -L "$dest" ]; then
        if [ "$(readlink -f "$dest")" == "$(readlink -f "$src")" ]; then
            log "$dest is already correctly linked."
            return
        fi
    fi 

    if [ -e "$dest" ]; then
        log "Backing up existing $dest to $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
        # Only move if destination exists and isn't the link we want
        mv "$dest" "$BACKUP_DIR/"
    fi
    
    mkdir -p "$(dirname "$dest")"
    ln -sf "$src" "$dest"
    log "Linked $src -> $dest"
}

# Link Home files (recursively link directories to maintain structure)
if [ -d "$DOTFILES_DIR/home" ]; then
    log "Linking home files and directories..."
    find "$DOTFILES_DIR/home" -maxdepth 1 -mindepth 1 | while read file; do
        filename=$(basename "$file")
        if [[ "$filename" == ".git" ]]; then continue; fi
        create_link "$file" "$HOME/$filename"
    done
fi

# Link Wallpapers
if [ -d "$DOTFILES_DIR/wallpapers" ]; then
    log "Linking Wallpapers..."
    mkdir -p "$HOME/Pictures"
    create_link "$DOTFILES_DIR/wallpapers" "$HOME/Pictures/Wallpapers"
fi

# Link Local Apps (Replaces the broken home/.local direct link)
if [ -d "$DOTFILES_DIR/local_apps" ]; then
    log "Linking local applications..."
    mkdir -p "$HOME/.local/share/applications"
    find "$DOTFILES_DIR/local_apps" -maxdepth 1 -mindepth 1 | while read file; do
        filename=$(basename "$file")
        # EXCLUSION: Do not link WhatsApp Web desktop file during initial install.
        # It should only be linked after running scripts/setup_whatsapp.sh.
        if [[ "$filename" == "whatsapp-web-chrome.desktop" ]]; then
            log "Skipping $filename (will be linked by setup_whatsapp.sh)"
            continue
        fi
        create_link "$file" "$HOME/.local/share/applications/$filename"
    done
fi

# Link Config directories
if [ -d "$DOTFILES_DIR/config" ]; then
    find "$DOTFILES_DIR/config" -maxdepth 1 -mindepth 1 | while read file; do
        filename=$(basename "$file")
        if [[ "$filename" == "config" || "$filename" == "home" || "$filename" == ".git" ]]; then continue; fi
        create_link "$file" "$HOME/.config/$filename"
    done
fi

# Install Binaries
if [ -d "$DOTFILES_DIR/bin" ]; then
    log "Installing Binaries..."
    rm -rf "$HOME/.local/bin" 2>/dev/null || true
    mkdir -p "$HOME/.local"
    ln -snf "$DOTFILES_DIR/bin" "$HOME/.local/bin"
fi

# Ensure Executable Permissions for all scripts (Polybar, bspwm, bin, etc.)
log "Ensuring executable permissions and Linux encodings for all scripts..."
# 1. Strip Windows UTF-8 BOM which completely breaks the Linux shebang `#!/`
find "$DOTFILES_DIR/config" "$DOTFILES_DIR/bin" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.conf" -o -name "bspwmrc" -o -name "sxhkdrc" \) -exec perl -pi -e 's/^\xef\xbb\xbf//' {} + 2>/dev/null || true
# 2. Strip Windows CRLF line endings which break shebang execution paths
find "$DOTFILES_DIR/config" "$DOTFILES_DIR/bin" -type f \( -name "*.sh" -o -name "*.py" -o -name "bspwmrc" -o -name "sxhkdrc" \) -exec sed -i 's/\r$//' {} + 2>/dev/null || true
# 3. Give execution rights
find "$DOTFILES_DIR/config" -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true
find "$DOTFILES_DIR/config" -type f -name "*.py" -exec chmod +x {} + 2>/dev/null || true
find "$DOTFILES_DIR/bin" -type f -exec chmod +x {} + 2>/dev/null || true
chmod +x "$DOTFILES_DIR/config/bspwm/bspwmrc" 2>/dev/null || true
chmod +x "$DOTFILES_DIR/config/sxhkd/sxhkdrc" 2>/dev/null || true

# Enable Bluetooth Service
if command -v systemctl &> /dev/null; then
    log "Enabling Bluetooth Service..."
    
    # Fix for modern Bluetooth headphones (force Classic Audio profile over LE)
    # This prevents headphones from pairing as useless generic BLE devices.
    # Note: 'bredr' disables pure BLE devices (some modern mice/smartwatches).
    if [ -f /etc/bluetooth/main.conf ]; then
        if grep -qE "^#?ControllerMode" /etc/bluetooth/main.conf; then
            # If the line exists (commented or not), replace it
            sudo sed -i 's/^#*ControllerMode.*/ControllerMode = bredr/' /etc/bluetooth/main.conf
        elif grep -q "^\[General\]" /etc/bluetooth/main.conf; then
            # If the line doesn't exist but [General] does, append right after it
            sudo sed -i '/^\[General\]/a ControllerMode = bredr' /etc/bluetooth/main.conf
        else
            # If even [General] is missing, append both to the end of the file
            echo -e "\n[General]\nControllerMode = bredr" | sudo tee -a /etc/bluetooth/main.conf >/dev/null
        fi
    fi
    
    sudo systemctl enable --now bluetooth || warn "Failed to enable bluetooth service."
fi

# Restart PipeWire to ensure bluetooth module is loaded
if command -v wpctl &> /dev/null; then
    log "Configuring PipeWire as default audio server..."
    # Reload user systemd daemon to pick up newly installed services
    systemctl --user daemon-reload || true
    
    # Disable and mask PulseAudio just in case they survived the apt package swap
    systemctl --user disable --now pulseaudio.service pulseaudio.socket 2>/dev/null || true
    systemctl --user mask pulseaudio.service pulseaudio.socket 2>/dev/null || true
    
    # Enable and start PipeWire services
    systemctl --user enable --now pipewire pipewire-pulse wireplumber || true
    systemctl --user restart pipewire pipewire-pulse wireplumber || true
    
    # Wait for PipeWire to restart
    sleep 2
    log "Unmuting microphone and setting volume to 100%..."
    pactl set-source-mute @DEFAULT_SOURCE@ 0 >/dev/null 2>&1 || true
    pactl set-source-volume @DEFAULT_SOURCE@ 100% >/dev/null 2>&1 || true
fi

log "Configuring NetworkManager..."
setup_network_manager || warn "NetworkManager setup encountered issues; continuing."

# Configure Firefox Global Policies (Stay in Mosaic fix)
log "Configuring Firefox for YouTube fullscreen (Stay in Mosaic)..."
if [ -f "$DOTFILES_DIR/config/firefox/setup_firefox.sh" ]; then
    # We pass the sudo capability if possible, but the script handles its own sudo.
    # On a fresh install, the user would provide the password when prompted by the script.
    bash "$DOTFILES_DIR/config/firefox/setup_firefox.sh" || warn "Firefox fullscreen setup failed."
else
    warn "Firefox setup script not found at $DOTFILES_DIR/config/firefox/setup_firefox.sh"
fi

# Configure Root User Zsh/Powerlevel10k
log "Configuring root user Zsh/Powerlevel10k..."
if [ -f "$DOTFILES_DIR/install.d/setup_root_zsh.sh" ]; then
    bash "$DOTFILES_DIR/install.d/setup_root_zsh.sh" || warn "Root Zsh setup failed."
else
    warn "Root Zsh setup script not found at $DOTFILES_DIR/install.d/setup_root_zsh.sh"
fi

# Refresh desktop database to ensure Rofi/Launchers see new .desktop files

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
fi

# 1.1 Install Fonts (Moved down to ensure it happens after symlink creation)
if [ -d "$DOTFILES_DIR/fonts" ]; then
    log "Installing Fonts..."
    rm -rf "$HOME/.local/share/fonts" 2>/dev/null || true
    mkdir -p "$HOME/.local/share"
    ln -snf "$DOTFILES_DIR/fonts" "$HOME/.local/share/fonts"
    if command -v fc-cache &> /dev/null; then
        log "Updating font cache..."
        fc-cache -fv || warn "fc-cache failed."
    fi
fi

fi

if [ ! -d "$HOME/.icons/Nordzy-cursors" ]; then
    log "Downloading Nordzy cursors..."
    if getent hosts github.com > /dev/null 2>&1; then
        wget -qO- https://github.com/guillaumeboehm/Nordzy-cursors/releases/download/v2.4.0/Nordzy-cursors.tar.gz | tar -xz -C "$HOME/.icons/" || warn "Failed to extract Nordzy-cursors"
    else
        warn "DNS/network unavailable for github.com. Skipping Nordzy-cursors."
    fi
fi

log "Installation complete!"
warn "A REBOOT IS STRONGLY RECOMMENDED to apply kernel modules, drivers, and system-wide changes."
log "To start the graphical session after reboot: startx"

# Configure Greenclip Static History File (Optional but recommended)
if [ ! -f "$HOME/.config/greenclip.toml" ]; then
    cat > "$HOME/.config/greenclip.toml" << TOML
[greenclip]
  blacklisted_applications = []
  enable_image_support = true
  history_file = "$HOME/.cache/greenclip.history"
  image_cache_directory = "/tmp/greenclip"
  max_history_length = 24
  max_selection_size_bytes = 0
  static_history = []
  trim_space_from_selection = true
  use_primary_selection_as_input = false
TOML
fi

# Initialize Language Preference
if [ ! -f "$HOME/.config/dotfiles/language" ]; then
    SYS_LANG=$(echo "$LANG" | cut -c1-2)
    if [[ "$SYS_LANG" == "es" ]]; then
        LANG_VAL="es"
        LOCALE_VAL="es_ES.UTF-8"
    else
        LANG_VAL="en"
        LOCALE_VAL="en_US.UTF-8"
    fi
    log "Initializing default language ($LANG_VAL) from system locale ($SYS_LANG)..."
    mkdir -p "$HOME/.config/dotfiles"
    echo "$LANG_VAL" > "$HOME/.config/dotfiles/language"
    
    # Also initialize locale.sh for immediate shell use
    echo "export LANG=\"$LOCALE_VAL\"" > "$HOME/.config/dotfiles/locale.sh"
    echo "export LC_ALL=\"$LOCALE_VAL\"" >> "$HOME/.config/dotfiles/locale.sh"
    echo "export LANGUAGE=\"$LANG_VAL\"" >> "$HOME/.config/dotfiles/locale.sh"
fi

# Initialize Keyboard Preference
if [ ! -f "$HOME/.config/dotfiles/keyboard" ]; then
    # Try to detect current layout and variant
    QUERY=$(setxkbmap -query)
    L=$(echo "$QUERY" | grep layout | awk '{print $2}')
    V=$(echo "$QUERY" | grep variant | awk '{print $2}')
    
    if [ -n "$V" ]; then
        CURR_LAYOUT="$L($V)"
    else
        CURR_LAYOUT="$L"
    fi
    
    [ -z "$L" ] && CURR_LAYOUT="us"
    
    log "Initializing default keyboard layout ($CURR_LAYOUT)..."
    mkdir -p "$HOME/.config/dotfiles"
    echo "$CURR_LAYOUT" > "$HOME/.config/dotfiles/keyboard"
    echo "#!/bin/sh" > "$HOME/.config/dotfiles/keyboard.sh"
    if [ -n "$V" ]; then
        echo "setxkbmap -layout $L -variant $V" >> "$HOME/.config/dotfiles/keyboard.sh"
    else
        echo "setxkbmap $L" >> "$HOME/.config/dotfiles/keyboard.sh"
    fi
    chmod +x "$HOME/.config/dotfiles/keyboard.sh"
fi

setup_battery_threshold || true

log "Installation complete!"
