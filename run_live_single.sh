#!/usr/bin/env bash
# run_live_single.sh -- LIVE_TEST_SINGLE: 1 robot, 1 task loop
# Usage (in WSL2): bash run_live_single.sh
# Usage with telemetry: LIVE_TELEMETRY=1 bash run_live_single.sh

set -e

# Resolve clean path without single quotes for Gazebo/sh compatibility
if [ -d "/home/siddharth/sih26" ]; then
    PROJECT_DIR="/home/siddharth/sih26"
else
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

# Clean up any stale instances before starting fresh
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "ruby" 2>/dev/null || true
pkill -9 -f "parameter_bridge" 2>/dev/null || true
pkill -9 -f "amr_node" 2>/dev/null || true
pkill -9 -f "live_demo_task_generator" 2>/dev/null || true
pkill -9 -f "fleet_safety_hud" 2>/dev/null || true
sleep 0.5

# Source ROS 2 and workspace
if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
fi
if [ -f "$PROJECT_DIR/ros2_ws/install/setup.bash" ]; then
    source "$PROJECT_DIR/ros2_ws/install/setup.bash"
fi

# Display and audio for WSLg / Gazebo GUI
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export QT_QPA_PLATFORM="xcb"
export QSG_RENDER_LOOP="basic"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/mnt/wslg/PulseServer}"
export GALLIUM_DRIVER=d3d12

if command -v nvidia-smi &>/dev/null; then
    export MESA_D3D12_DEFAULT_ADAPTER_NAME="NVIDIA"
else
    export MESA_D3D12_DEFAULT_ADAPTER_NAME="Intel"
fi

export SIH26_PROFILE="recording"

# Ensure shared memory for WSLg Direct VAIL rendering (prevents [WARN:COPY MODE] blank windows)
if [ ! -d "/mnt/shared_memory" ] || ! mountpoint -q /mnt/shared_memory; then
    sudo mkdir -p /mnt/shared_memory 2>/dev/null
    sudo mount -t tmpfs -o rw,nosuid,nodev,relatime,mode=777 tmpfs /mnt/shared_memory 2>/dev/null
fi

# Project environment
export SIH26_PROJECT_DIR="$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}"
export LIVE_TELEMETRY="${LIVE_TELEMETRY:-0}"

# Auto-activate & raise Gazebo GUI window onto Windows 11 foreground
(
    for i in {1..25}; do
        sleep 1
        WID=$(xdotool search --name "Gazebo Sim" 2>/dev/null | head -n 1)
        if [ -n "$WID" ]; then
            xdotool windowactivate "$WID" 2>/dev/null || true
            xdotool windowraise "$WID" 2>/dev/null || true
            break
        fi
    done
) &

echo "=== SIH26123 LIVE SINGLE-ROBOT SMOKE TEST ==="
echo "Scenario: LIVE_TEST_SINGLE | LIVE_TELEMETRY=$LIVE_TELEMETRY"
echo "Project : $PROJECT_DIR"
cd "$PROJECT_DIR"
ros2 launch ros2_integration live_demo.launch.py scenario:=LIVE_TEST_SINGLE use_sim_time:=true inject_interval:=10.0 seed:=42 recording:=true