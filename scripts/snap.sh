#!/bin/bash
sleep 2
WID=$(DISPLAY=:0 xdotool search --class 'webots' | tail -1 || true)
if [ -n "$WID" ]; then
    DISPLAY=:0 import -window "$WID" /tmp/webots_live.png
    cp /tmp/webots_live.png "$(dirname "$0")/../simulation/webots/webots_live.png"
    echo "SUCCESS: Captured window $WID to simulation/webots/webots_live.png"
else
    echo "ERROR: Webots window not found."
fi
