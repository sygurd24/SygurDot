#!/bin/bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "Este script necesita permisos de root. Ejecuta:"
    echo "  sudo $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${SUDO_USER:-sygurd}"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
USER_SHARE="$TARGET_HOME/.local/share/face-auth"

OPT_DIR="/opt/face-auth"
DATA_DIR="/var/lib/face-auth"
PAM_OUT="/usr/lib/x86_64-linux-gnu/security/pam_face_auth.so"
MODELS_URL="https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip"

# Ensure minimal build/runtime dependencies exist on fresh Debian installs
MISSING_PKGS=()
command -v gcc >/dev/null 2>&1 || MISSING_PKGS+=(gcc)
command -v curl >/dev/null 2>&1 || MISSING_PKGS+=(curl)
[ -f /usr/include/security/pam_modules.h ] || MISSING_PKGS+=(libpam0g-dev)
python3 -c "import ensurepip, venv" >/dev/null 2>&1 || MISSING_PKGS+=(python3-venv)

if [ "${#MISSING_PKGS[@]}" -gt 0 ] && command -v apt-get >/dev/null 2>&1; then
    echo "0. Instalando dependencias faltantes (${MISSING_PKGS[*]}) ..."
    apt-get update -qq
    apt-get install -y "${MISSING_PKGS[@]}"
fi

echo "1. Instalando entorno aislado (root:root) en $OPT_DIR ..."
install -d -o root -g root -m 755 "$OPT_DIR" "$OPT_DIR/models"
install -o root -g root -m 644 "$SCRIPT_DIR/face_engine.py" "$OPT_DIR/face_engine.py"
install -o root -g root -m 644 "$SCRIPT_DIR/face_daemon.py" "$OPT_DIR/face_daemon.py"
install -o root -g root -m 755 "$SCRIPT_DIR/face-auth-cli.py" "$OPT_DIR/face-auth-cli.py"

if [ -d "$USER_SHARE/models" ] && [ -f "$USER_SHARE/models/det_500m.onnx" ] && [ -f "$USER_SHARE/models/w600k_mbf.onnx" ]; then
    cp -f "$USER_SHARE/models/"*.onnx "$OPT_DIR/models/"
fi

if [ ! -s "$OPT_DIR/models/det_500m.onnx" ] || [ ! -s "$OPT_DIR/models/w600k_mbf.onnx" ]; then
    echo "   Descargando modelos InsightFace buffalo_sc (~14 MB) ..."
    TMP_ZIP=$(mktemp /tmp/buffalo_sc.XXXXXX.zip)
    trap 'rm -f "$TMP_ZIP"' EXIT
    curl -fSL "$MODELS_URL" -o "$TMP_ZIP"
    python3 -c "import zipfile, sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$TMP_ZIP" "$OPT_DIR/models"
    rm -f "$TMP_ZIP"
fi
chown -R root:root "$OPT_DIR/models"
chmod 644 "$OPT_DIR/models/"*.onnx

if [ ! -x "$OPT_DIR/venv/bin/python" ]; then
    echo "   Creando virtualenv de sistema en $OPT_DIR/venv ..."
    python3 -m venv "$OPT_DIR/venv"
    "$OPT_DIR/venv/bin/pip" install --quiet --upgrade pip
    "$OPT_DIR/venv/bin/pip" install --quiet numpy opencv-python-headless onnxruntime
    chown -R root:root "$OPT_DIR/venv"
fi

# System-wide CLI wrapper so `sudo face-auth enroll` works cleanly
ln -sf "$OPT_DIR/face-auth-cli.py" /usr/local/bin/face-auth

echo "2. Protegiendo almacenamiento de embeddings en $DATA_DIR (0700 root:root) ..."
install -d -o root -g root -m 700 "$DATA_DIR"
if [ -f "$USER_SHARE/embeddings.npz" ] && [ ! -f "$DATA_DIR/embeddings.npz" ]; then
    install -o root -g root -m 600 "$USER_SHARE/embeddings.npz" "$DATA_DIR/embeddings.npz"
    rm -f "$USER_SHARE/embeddings.npz"
    echo "   Embeddings migrados a $DATA_DIR/embeddings.npz y copia de usuario eliminada."
fi

echo "3. Compilando e instalando módulo PAM nativo ($PAM_OUT) ..."
gcc -O2 -Wall -Wextra -Werror -fPIC -shared -o "$PAM_OUT" "$SCRIPT_DIR/pam_face_auth.c" -lpam
chown root:root "$PAM_OUT"
chmod 644 "$PAM_OUT"

if [ -f /etc/pam.d/i3lock ] && [ ! -f /etc/pam.d/i3lock.bak ]; then
    cp /etc/pam.d/i3lock /etc/pam.d/i3lock.bak
fi

cat <<'EOF' > /etc/pam.d/i3lock
# PAM configuration for i3lock with hardened local IR facial unlock
# - Pressing Enter with empty password triggers IR face scan (~0.6s).
# - Typing a password skips the camera (<0.05ms) and validates via pam_unix.
auth sufficient pam_face_auth.so
auth [success=1 default=ignore] pam_unix.so nullok try_first_pass nodelay
auth requisite pam_deny.so
auth required pam_permit.so
@include common-account
@include common-password
@include common-session
EOF
chmod 644 /etc/pam.d/i3lock

echo "4. Instalando servicio systemd del sistema (/etc/systemd/system/face-auth.service) ..."
sed "s/^Environment=FACE_AUTH_USER=.*/Environment=FACE_AUTH_USER=$TARGET_USER/" \
    "$SCRIPT_DIR/face-auth.service" > /etc/systemd/system/face-auth.service
chmod 644 /etc/systemd/system/face-auth.service

systemctl daemon-reload
systemctl enable --now face-auth.service
systemctl restart face-auth.service

echo "Instalación endurecida completada."
