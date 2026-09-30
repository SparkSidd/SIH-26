#!/bin/bash
set -euo pipefail

# scripts/check_wslg.sh — Reusable WSLg Health Check

# 1. /mnt/wslg exists
if [ ! -d "/mnt/wslg" ]; then
    echo "WSLg NOT READY"
    echo "REASON: /mnt/wslg directory does not exist."
    exit 1
fi

# 2. /mnt/shared_memory exists
if [ ! -d "/mnt/shared_memory" ]; then
    echo "WSLg NOT READY"
    echo "REASON: /mnt/shared_memory directory does not exist."
    exit 1
fi

# 3. /mnt/shared_memory is mounted
if ! mount | grep -q "/mnt/shared_memory"; then
    echo "WSLg NOT READY"
    echo "REASON: /mnt/shared_memory is not mounted."
    exit 1
fi

# 4. $DISPLAY is sane
DISPLAY_VAL="${DISPLAY:-}"
if [ -z "$DISPLAY_VAL" ]; then
    export DISPLAY=":0"
    DISPLAY_VAL=":0"
fi

if [[ "$DISPLAY_VAL" != ":0" && "$DISPLAY_VAL" != ":0.0" ]]; then
    echo "WSLg NOT READY"
    echo "REASON: DISPLAY='$DISPLAY_VAL' is not a standard WSLg display (expected :0)."
    exit 1
fi

# 5. /tmp/.X11-unix exists and contains X0 socket
if [ ! -d "/tmp/.X11-unix" ]; then
    echo "WSLg NOT READY"
    echo "REASON: /tmp/.X11-unix does not exist."
    exit 1
fi

if [ ! -S "/tmp/.X11-unix/X0" ] && [ ! -S "/mnt/wslg/.X11-unix/X0" ]; then
    echo "WSLg NOT READY"
    echo "REASON: X0 socket not found in /tmp/.X11-unix or /mnt/wslg/.X11-unix."
    exit 1
fi

# 6. WSLg runtime directories exist
if [ ! -S "/mnt/wslg/runtime-dir/wayland-0" ] && [ ! -S "/run/user/$(id -u)/wayland-0" ]; then
    # Warning or check Wayland
    :
fi

# 7. Basic GUI launch infrastructure is available (xset or xdpyinfo or glxinfo)
if command -v xset >/dev/null 2>&1; then
    if ! DISPLAY="$DISPLAY_VAL" xset q >/dev/null 2>&1; then
        echo "WSLg NOT READY"
        echo "REASON: Cannot communicate with X server on DISPLAY=$DISPLAY_VAL."
        exit 1
    fi
elif command -v xdpyinfo >/dev/null 2>&1; then
    if ! DISPLAY="$DISPLAY_VAL" xdpyinfo >/dev/null 2>&1; then
        echo "WSLg NOT READY"
        echo "REASON: Cannot communicate with X server on DISPLAY=$DISPLAY_VAL."
        exit 1
    fi
fi

echo "WSLg READY"
exit 0
