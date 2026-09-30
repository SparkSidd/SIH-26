#!/bin/bash
set -e

WORLD="${1:-simulation/webots/worlds/warehouse_poc01.wbt}"
ROBOT_NAME="${2:-R01}"
PORT=1234

echo "=========================================================="
echo "  SIH26123 — WEBOTS HARDWARE TEST A (1 AMR: $ROBOT_NAME)"
echo "  World: $WORLD"
echo "=========================================================="

export WEBOTS_HOME=/usr/local/webots
export PYTHONPATH=/usr/local/webots/lib/controller/python:$PYTHONPATH

# Kill any lingering webots or Xvfb
pkill -f webots-bin || true
pkill -f Xvfb || true
sleep 1

# Start Webots with xvfb-run in background
xvfb-run -a webots --batch --no-rendering --mode=fast --stdout --stderr --port=$PORT "$WORLD" > /tmp/webots_test_a.log 2>&1 &
XVFB_PID=$!
echo "Started Webots with xvfb-run (PID $XVFB_PID), waiting for server to initialize..."

# Wait up to 10 seconds for Webots port to open
READY=0
for i in {1..20}; do
  if grep -q "Waiting for local or remote connection" /tmp/webots_test_a.log 2>/dev/null; then
    READY=1
    break
  fi
  sleep 0.5
done

if [ $READY -eq 1 ]; then
  echo "Webots ready for extern controllers. Running hardware test..."
else
  echo "Current log:"
  cat /tmp/webots_test_a.log
fi

export WEBOTS_CONTROLLER_URL="ipc://1234/$ROBOT_NAME"
export PYTHONUNBUFFERED=1
python3 simulation/webots/scripts/test_webots_hardware.py "$ROBOT_NAME"
TEST_STATUS=$?

echo "Stopping Webots..."
pkill -9 -f webots-bin || true
pkill -9 -f Xvfb || true

exit $TEST_STATUS

exit $TEST_STATUS
