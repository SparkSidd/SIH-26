#!/usr/bin/env bash
set -e
PROJECT_DIR="/home/siddharth/sih26"
cd "$PROJECT_DIR"

bash run_live_fleet.sh LIVE_DEMO proposed false recording > /tmp/fleet_test.log 2>&1 &
SIM_PID=$!

echo "Sim launched with PID $SIM_PID. Waiting 10s for full fleet to spawn..."
sleep 10

echo "=== TOP CPU CONSUMING PROCESSES ==="
ps -eo pid,ppid,%cpu,%mem,comm,args --sort=-%cpu | head -n 25

echo "=== CLEANING UP ==="
kill -9 $SIM_PID 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "ruby" 2>/dev/null || true
pkill -9 -f "parameter_bridge" 2>/dev/null || true
pkill -9 -f "amr_node" 2>/dev/null || true
pkill -9 -f "live_demo_task_generator" 2>/dev/null || true
pkill -9 -f "fleet_safety_hud" 2>/dev/null || true

echo "Done profiling."
