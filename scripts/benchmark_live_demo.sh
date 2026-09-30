#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
source /home/siddharth/sih26/ros2_ws/install/setup.bash
PROJECT_DIR="/home/siddharth/sih26"
cd "$PROJECT_DIR"

echo "=== LAUNCHING LIVE DEMO FOR 15s ==="
bash run_live_fleet.sh LIVE_DEMO proposed false recording > /tmp/live_rtf.log 2>&1 &
LAUNCH_PID=$!

sleep 8
echo "=== CHECKING REAL TIME FACTOR WITH GUI + NODES ==="
for i in {1..8}; do
    timeout 2 gz topic -e -t /stats -n 1 | grep real_time_factor || echo "no stats"
    sleep 1
done

echo "=== CLEANING UP ==="
kill -9 $LAUNCH_PID 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "parameter_bridge" 2>/dev/null || true
pkill -9 -f "amr_node" 2>/dev/null || true
pkill -9 -f "live_demo_task_generator" 2>/dev/null || true
pkill -9 -f "fleet_safety_hud" 2>/dev/null || true
