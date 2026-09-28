#!/usr/bin/env bash
# One-line install on Raspberry Pi OS:
#   curl -fsSL https://raw.githubusercontent.com/FuNK3Y/kvm-poc/main/install.sh | sudo bash -s -- \
#       --monitor 20:0x0f:0x11 --monitor 21:0x0f:0x11 --usb-pin 17
#
# Re-running without arguments updates the code and keeps the existing configuration.
# Add --with-tools to also install ddcutil and i2c-tools (handy to find bus/input values).
set -euo pipefail

# Installer-only options are stripped; everything else is passed to the app.
WITH_TOOLS=0
APP_ARGS=()
for a in "$@"; do
    case "$a" in
        --with-tools) WITH_TOOLS=1 ;;
        *) APP_ARGS+=("$a") ;;
    esac
done
set -- "${APP_ARGS[@]}"

REPO="${KVM_REPO:-FuNK3Y/kvm-poc}"
BRANCH="${KVM_BRANCH:-main}"
PREFIX=/opt/kvm
UNIT=/etc/systemd/system/kvm.service

[ "$(id -u)" -eq 0 ] || { echo "Please run as root (sudo)." >&2; exit 1; }

if [ $# -eq 0 ] && [ ! -f "$UNIT" ]; then
    cat >&2 <<EOF
Usage: install.sh --monitor BUS:INPUT_A:INPUT_B [--monitor ...] --usb-pin GPIO [options] [--with-tools]
Find buses with 'ddcutil detect' and input values with 'ddcutil --bus N capabilities'
(install them with: sudo apt install ddcutil i2c-tools).
EOF
    exit 1
fi

PKGS=(python3 python3-gpiozero python3-lgpio curl)
[ "$WITH_TOOLS" -eq 1 ] && PKGS+=(ddcutil i2c-tools)
[[ "$*" == *ddcutil* ]] && PKGS+=(ddcutil)   # --ddc-backend ddcutil needs it

MISSING=()
for p in "${PKGS[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "ok installed" || MISSING+=("$p")
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo "==> Installing packages: ${MISSING[*]}"
    apt-get update -qq
    apt-get install -y -qq "${MISSING[@]}" >/dev/null
else
    echo "==> All required packages already installed"
fi

echo "==> Enabling i2c-dev"
echo i2c-dev > /etc/modules-load.d/kvm.conf
modprobe i2c-dev || true

echo "==> Fetching code into $PREFIX"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || true)"
rm -rf "$PREFIX.new" && mkdir -p "$PREFIX.new"
if [ -n "$SRC" ] && [ -f "$SRC/kvm/core.py" ]; then
    cp -r "$SRC/kvm" "$PREFIX.new/"                      # running from a local clone
else
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
        | tar xz --strip-components=1 -C "$PREFIX.new"
fi
rm -rf "$PREFIX" && mv "$PREFIX.new" "$PREFIX"

echo "==> Creating service user"
id kvm >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin kvm
for g in i2c gpio; do getent group "$g" >/dev/null && usermod -aG "$g" kvm; done

if [ $# -gt 0 ]; then
    # Validate the arguments before installing the service.
    PYTHONPATH="$PREFIX" python3 - "$@" <<'EOF'
import sys
from kvm.__main__ import parse_args
parse_args(sys.argv[1:])
EOF
    # Quote each argument for systemd ExecStart ('%' must be doubled).
    ARGS=""
    for a in "$@"; do
        a="${a//\\/\\\\}"; a="${a//\"/\\\"}"; a="${a//%/%%}"
        ARGS+=" \"$a\""
    done
    echo "==> Installing systemd service"
    cat > "$UNIT" <<EOF
[Unit]
Description=DDC/CI + GPIO KVM switch
After=network-online.target
Wants=network-online.target

[Service]
User=kvm
Environment=PYTHONPATH=$PREFIX
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -m kvm$ARGS
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
fi

systemctl daemon-reload
systemctl enable kvm.service >/dev/null
systemctl restart kvm.service

echo "==> Done. Web UI: http://$(hostname -I | awk '{print $1}')/  (logs: journalctl -u kvm -f)"
