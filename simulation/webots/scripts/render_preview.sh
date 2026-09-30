#!/bin/bash
set -e
export WEBOTS_HOME=/usr/local/webots
export DISPLAY=:99

Xvfb :99 -screen 0 1600x1000x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 1

webots --stdout --stderr --batch --mode=realtime simulation/webots/worlds/warehouse_fleet.wbt > /tmp/preview.log 2>&1 &
WEBOTS_PID=$!

echo "Waiting for world initialization and supervisor..."
for i in {1..30}; do
  if grep -q "EXECUTING FLEET MISSION" /tmp/preview.log 2>/dev/null; then
    echo "Supervisor is active! Capturing render..."
    sleep 1
    break
  fi
  sleep 1
done

import -window root simulation/webots/warehouse_enhanced_render.png
echo "Snapshot saved."

kill -9 $WEBOTS_PID 2>/dev/null || true
kill -9 $XVFB_PID 2>/dev/null || true
