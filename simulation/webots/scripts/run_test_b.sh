#!/bin/bash
set -e

WORLD="simulation/webots/worlds/warehouse_poc01.wbt"
PORT=1234

echo "=========================================================="
echo "  SIH26123 — WEBOTS HARDWARE TEST B (2 AMRs: R01 & R02)"
echo "  World: $WORLD"
echo "=========================================================="

export WEBOTS_HOME=/usr/local/webots
export PYTHONPATH=/usr/local/webots/lib/controller/python:.

pkill -9 -f webots-bin || true
pkill -9 -f Xvfb || true
sleep 1

xvfb-run -a webots --batch --no-rendering --mode=fast --stdout --stderr --port=$PORT "$WORLD" > /tmp/webots_test_b.log 2>&1 &
XVFB_PID=$!

READY=0
for i in {1..20}; do
  if grep -q "Waiting for local or remote connection" /tmp/webots_test_b.log 2>/dev/null; then
    READY=1
    break
  fi
  sleep 0.5
done

if [ $READY -eq 1 ]; then
  echo "Webots ready for extern controllers. Running 2-AMR hardware test..."
else
  echo "Current log:"
  cat /tmp/webots_test_b.log
fi

export PYTHONUNBUFFERED=1
python3 simulation/webots/scripts/test_two_robots_hardware.py
TEST_STATUS=$?

echo "Stopping Webots..."
pkill -9 -f webots-bin || true
pkill -9 -f Xvfb || true

exit $TEST_STATUS
