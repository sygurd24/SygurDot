#!/bin/bash
set -e

echo "Configuring LightDM and Slick Greeter..."

# Ensure sudo exists (script runs as user but writes system files)
if ! command -v sudo &> /dev/null; then
    echo "Error: sudo not found. Install sudo or run as root."
    exit 1
fi

# Ensure packages are installed
if ! command -v lightdm &> /dev/null; then
    echo "Installing LightDM and Slick Greeter..."
    sudo apt update
    sudo apt install -y lightdm slick-greeter
fi

# Determine Wallpaper
# User mentioned 'pantallabloque_debian.png', let's prioritize that if it exists
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WALLPAPER_SRC=""

if [ -f "$REPO_DIR/wallpapers/pantallabloqueo_debian.png" ]; then
    WALLPAPER_SRC="$REPO_DIR/wallpapers/pantallabloqueo_debian.png"
elif [ -f "$REPO_DIR/wallpapers/firewatch_noche.png" ]; then
    WALLPAPER_SRC="$REPO_DIR/wallpapers/firewatch_noche.png"
else
    echo "Warning: No suitable wallpaper found in $REPO_DIR/wallpapers."
fi

# Copy wallpaper to system directory to avoid permission issues
if [ -n "$WALLPAPER_SRC" ]; then
    sudo mkdir -p /usr/share/backgrounds/my_setup
    sudo cp "$WALLPAPER_SRC" /usr/share/backgrounds/my_setup/login_wallpaper.png
    WALLPAPER_PATH="/usr/share/backgrounds/my_setup/login_wallpaper.png"
    echo "Wallpaper copied to $WALLPAPER_PATH"
else
    WALLPAPER_PATH="/usr/share/backgrounds/default.png" # Fallback
fi

echo "Writing /etc/lightdm/lightdm.conf..."
cat <<EOF | sudo tee /etc/lightdm/lightdm.conf
[Seat:*]
greeter-session=slick-greeter
user-session=bspwm
minimum-vt=1
EOF

echo "Writing /etc/lightdm/slick-greeter.conf..."
cat <<EOF | sudo tee /etc/lightdm/slick-greeter.conf
[Greeter]
background=$WALLPAPER_PATH
draw-user-backgrounds=false
draw-grid=false
theme-name=Arc-Dark
icon-theme-name=Papirus-Dark
font-name=JetBrainsMono Nerd Font 11
xft-antialias=true
xft-hinting=true
show-clock=true
clock-format=%H:%M
show-keyboard=false
show-a11y=false
show-power=true
show-hostname=false
EOF

# Warn if another display manager is enabled
for dm in gdm3 sddm lxdm; do
    if systemctl is-enabled "$dm" &> /dev/null; then
        echo "Warning: $dm is enabled. Consider disabling it to use LightDM."
    fi
done

echo "Enabling LightDM Service..."
sudo systemctl enable lightdm

# Detect if we are on a Hybrid Graphics system (NVIDIA + Integrated)
# Plymouth (splash) and TTY masking often cause black screens on these setups.
is_hybrid=0
if lspci | grep -qi "NVIDIA" && lspci | grep -qiE "Intel|AMD"; then
    echo "Hybrid Graphics detected. Disabling 'splash' and TTY masking for safety."
    is_hybrid=1
fi

# Mask TTY1 by default to prevent login prompt flicker
echo "Masking TTY1 to prevent login prompt flicker..."
sudo systemctl mask getty@tty1.service

# Optional Clean Boot Configuration (GRUB + Plymouth)
echo ""
read -p "¿Deseas configurar un inicio limpio (Plymouth + GRUB oculto)? (s/n, o 'r' para REVERTIR cambios): " confirm_clean_boot
if [[ "$confirm_clean_boot" =~ ^[Ss]$ ]]; then
    echo "Configurando Clean Boot (Plymouth + GRUB)..."
    
    # 1. Install Plymouth and update microcode
    sudo apt update && sudo apt install -y plymouth plymouth-themes amd64-microcode intel-microcode
    
    # 2. Configure GRUB
    echo "Configuring GRUB..."
    [ ! -f /etc/default/grub.bak ] && sudo cp /etc/default/grub /etc/default/grub.bak
    
    # Set timeout and style
    sudo sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub
    if grep -q "^GRUB_TIMEOUT_STYLE=" /etc/default/grub; then
        sudo sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=hidden/' /etc/default/grub
    else
        echo 'GRUB_TIMEOUT_STYLE=hidden' | sudo tee -a /etc/default/grub
    fi
    
    # Ensure Recordfail doesn't trigger a 30s timeout
    if grep -q "^GRUB_RECORDFAIL_TIMEOUT=" /etc/default/grub; then
        sudo sed -i 's/^GRUB_RECORDFAIL_TIMEOUT=.*/GRUB_RECORDFAIL_TIMEOUT=0/' /etc/default/grub
    else
        echo 'GRUB_RECORDFAIL_TIMEOUT=0' | sudo tee -a /etc/default/grub
    fi
    
    # Ensure we don't have duplicate CMDLINE definitions from previous failed runs
    if [ $(grep -c "^GRUB_CMDLINE_LINUX_DEFAULT=" /etc/default/grub) -gt 1 ]; then
        echo "Detected duplicate GRUB entries. Cleaning up..."
        sudo sed -i '/^GRUB_CMDLINE_LINUX_DEFAULT=/d' /etc/default/grub
        echo 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"' | sudo tee -a /etc/default/grub
    fi

    # Update CMDLINE (surgical append to avoid overwriting modeset/iommu)
    # loglevel=0 console=tty1 (default) 
    # clearcpuid=rdseed did not work to fix the AMD message, so it was removed. console=tty3 breaks plymouth in hybrid graphics.
    # Para esconder absolutamente TODO texto (ej: "RDSEED is broken" que salta la seguridad de loglevel=0), usaremos
    # el truco más seguro: volver todos los caracteres de texto de la consola físicamente color negro (vt.default_...).
    # Con esto la pantalla se mantiene negra (o con el logo de BGRT que trae UEFI) sin interrumpir los TTYs.
    params="quiet splash loglevel=0 udev.log_priority=3 rd.udev.log_priority=3 vt.global_cursor_default=0 systemd.show_status=false log_buf_len=1M logo.nologo fbcon=nodefer vga=current vt.default_red=0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 vt.default_grn=0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 vt.default_blu=0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
    
    for param in $params; do
        if ! grep -q "$param" /etc/default/grub; then
            sudo sed -i "s/GRUB_CMDLINE_LINUX_DEFAULT=\"/GRUB_CMDLINE_LINUX_DEFAULT=\"$param /" /etc/default/grub
        fi
    done
    
    # 3. Set Plymouth theme
    echo "Setting Plymouth theme to 'bgrt'..."
    sudo plymouth-set-default-theme -R bgrt || echo "Warning: Could not set bgrt theme."
    
    # 4. Patching GRUB to hide "Loading Linux..." messages and make it instant/black
    echo "Patching GRUB for absolute silence and speed..."
    if [ -f /etc/grub.d/10_linux ]; then
        sudo sed -i 's/quiet_boot="0"/quiet_boot="1"/' /etc/grub.d/10_linux
    fi

    # NOTE: GRUB_TERMINAL=console intentionally NOT set here.
    # On hybrid GPU laptops (AMD+NVIDIA), setting GRUB_TERMINAL=console prevents
    # the amdgpu driver from initializing the framebuffer in graphical mode.
    # This causes the VT switch to VT7 (where LightDM runs) to appear as a black
    # screen even though the X server is running correctly.
    ! grep -q "GRUB_BACKGROUND=\"\"" /etc/default/grub && echo 'GRUB_BACKGROUND=""' | sudo tee -a /etc/default/grub
    ! grep -q "GRUB_DISABLE_OS_PROBER=true" /etc/default/grub && echo 'GRUB_DISABLE_OS_PROBER=true' | sudo tee -a /etc/default/grub

    # 5. Update GRUB and Initramfs
    echo "Updating GRUB and Initramfs..."
    sudo update-grub
    sudo update-initramfs -u
    
    echo "¡Configuración de arranque limpio completada!"

elif [[ "$confirm_clean_boot" =~ ^[Rr]$ ]]; then
    echo "Revirtiendo cambios de arranque limpio..."
    
    # 1. Restore GRUB
    if [ -f /etc/default/grub.bak ]; then
        sudo cp /etc/default/grub.bak /etc/default/grub
        echo "Restaurado /etc/default/grub desde el respaldo."
    else
        # Manual revert if no backup
        sudo sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' /etc/default/grub
        sudo sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=menu/' /etc/default/grub
    # Ensure GRUB_TERMINAL=console is not set (breaks hybrid GPU VT switching)
    sudo sed -i 's/^GRUB_TERMINAL=console/#GRUB_TERMINAL=console/' /etc/default/grub
        sudo sed -i '/GRUB_DISABLE_OS_PROBER=true/d' /etc/default/grub
        sudo sed -i '/GRUB_BACKGROUND=""/d' /etc/default/grub
    fi
    
    # 2. Unpatch GRUB scripts
    if [ -f /etc/grub.d/10_linux ]; then
        sudo sed -i 's/quiet_boot="1"/quiet_boot="0"/' /etc/grub.d/10_linux
    fi
    
    # 3. Unmask TTY1
    sudo systemctl unmask getty@tty1.service
    
    # 4. Update
    sudo update-grub
    sudo update-initramfs -u
    echo "¡Cambios revertidos! El menú de GRUB y la terminal volverán a ser visibles."
fi

echo "Done! Reboot to see changes."
