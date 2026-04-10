#!/bin/bash
set -e

echo ">>> Setting up Hibernation (Suspend-to-Disk)..."

# Require root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: run this script with sudo (root)."
    exit 1
fi

# Detect RAM
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
RECOMMENDED_SWAP=$((TOTAL_RAM_GB + 1))

echo "Detected RAM: ${TOTAL_RAM_GB}GB"
echo "For hibernation, swap size should be at least equal to RAM size."
echo "Recommended: ${RECOMMENDED_SWAP}GB"

read -p "Enter desired swap size in GB (default: ${RECOMMENDED_SWAP}): " USER_SWAP
SWAP_SIZE=${USER_SWAP:-$RECOMMENDED_SWAP}

echo ">>> Selected Swap Size: ${SWAP_SIZE}GB"

# 1. Create Swapfile
CREATE_SWAP=true
if [ -f /swapfile ]; then
    SWAP_SIZE_HUMAN=$(du -h /swapfile | awk '{print $1}')
    echo "Existing /swapfile found (Size: ${SWAP_SIZE_HUMAN})."
    echo "If you choose 'No', the script will skip creation and use this existing file for hibernation configuration."
    read -p "Do you want to delete and recreate it? [y/N]: " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "Skipping swapfile recreation. Using existing /swapfile."
        CREATE_SWAP=false
    else
        echo "Turning it off and deleting /swapfile..."
        swapoff /swapfile || true
        rm /swapfile
    fi
fi

if [ "$CREATE_SWAP" = true ]; then
    echo ">>> Creating ${SWAP_SIZE}GB Swapfile (this may take a moment)..."
    dd if=/dev/zero of=/swapfile bs=1G count="$SWAP_SIZE" status=progress
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
fi

echo ">>> Updating /etc/fstab..."
# Verify fstab doesn't already have it
if ! grep -q "/swapfile" /etc/fstab; then
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# 2. Configure GRUB
echo ">>> Configuring GRUB..."
# Get UUID of root partition
ROOT_UUID=$(findmnt -no UUID -T /swapfile)
# Get Offset of swapfile
RESUME_OFFSET=$(filefrag -v /swapfile | awk 'NR==4{print $4}' | tr -d .)

if [ -z "$ROOT_UUID" ] || [ -z "$RESUME_OFFSET" ]; then
    echo "Error: Could not determine UUID or Offset."
    exit 1
fi

echo "UUID: $ROOT_UUID"
echo "Offset: $RESUME_OFFSET"

# Add resume params to GRUB_CMDLINE_LINUX_DEFAULT
# We use sed to append if not present
if grep -q "^GRUB_CMDLINE_LINUX_DEFAULT=" /etc/default/grub; then
    if grep -q "resume=" /etc/default/grub; then
        echo "GRUB already has resume parameters. Updating them..."
        sed -i "s/resume=UUID=[^ ]\\+ resume_offset=[^ ]\\+/resume=UUID=$ROOT_UUID resume_offset=$RESUME_OFFSET/" /etc/default/grub
    else
        sed -i "s/GRUB_CMDLINE_LINUX_DEFAULT=\"/GRUB_CMDLINE_LINUX_DEFAULT=\"resume=UUID=$ROOT_UUID resume_offset=$RESUME_OFFSET /" /etc/default/grub
    fi
else
    echo "GRUB_CMDLINE_LINUX_DEFAULT=\"resume=UUID=$ROOT_UUID resume_offset=$RESUME_OFFSET\"" >> /etc/default/grub
fi
echo ">>> Updating GRUB config..."
update-grub

# 3. Update Initramfs
echo ">>> Updating initramfs (to include resume capability)..."
# Ensure initramfs-tools has correct resume config (overwrite to avoid stale values)
echo "RESUME=UUID=$ROOT_UUID" > /etc/initramfs-tools/conf.d/resume
echo "resume_offset=$RESUME_OFFSET" >> /etc/initramfs-tools/conf.d/resume
update-initramfs -u

# 4. Configure Logind
echo ">>> Configuring logind to Hibernate on lid close..."
if grep -q "^#HandleLidSwitch=" /etc/systemd/logind.conf; then
    sed -i 's/^#HandleLidSwitch=.*/HandleLidSwitch=hibernate/' /etc/systemd/logind.conf
elif grep -q "^HandleLidSwitch=" /etc/systemd/logind.conf; then
    sed -i 's/^HandleLidSwitch=.*/HandleLidSwitch=hibernate/' /etc/systemd/logind.conf
else
    echo "HandleLidSwitch=hibernate" >> /etc/systemd/logind.conf
fi

echo ">>> DONE! Please restart your computer to apply changes."
