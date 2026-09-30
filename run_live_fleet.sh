#!/usr/bin/env bash
# run_live_fleet.sh -- SIH26123 Gazebo Live Fleet Launcher with Real-Time Safety HUD
# Usage (in WSL2):
#   bash run_live_fleet.sh [SCENARIO] [POLICY] [RECORDING] [PROFILE]
#
# Examples:
#   bash run_live_fleet.sh                                    # 6 robots, LIVE_DEMO, normal profile
#   bash run_live_fleet.sh SCENARIO_C proposed false normal   # Blockage recovery, normal profile
#   bash run_live_fleet.sh SCENARIO_C proposed false recording # Blockage recovery, RECORDING profile
#   bash run_live_fleet.sh LIVE_DEMO proposed true recording  # Presentation Recording mode
#
# Profiles:
#   normal    Balanced simulation (full sensors, moderate rendering, INFO logs)
#   debug     Maximum observability (180 LiDAR rays, visualize, DEBUG logs)
#   recording SIH video optimized (36 rays, no shadows, ERROR-only logs)

SCENARIO="${1:-LIVE_DEMO}"
POLICY="${2:-proposed}"
RECORDING="${3:-false}"
PROFILE="${4:-recording}"

if [ -d "/home/siddharth/sih26" ]; then
    PROJECT_DIR="/home/siddharth/sih26"
else
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
fi
if [ -f "$PROJECT_DIR/ros2_ws/install/setup.bash" ]; then
    source "$PROJECT_DIR/ros2_ws/install/setup.bash"
fi

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export QT_QPA_PLATFORM="xcb"
export QSG_RENDER_LOOP="basic"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/mnt/wslg/PulseServer}"
export GALLIUM_DRIVER=d3d12
export MESA_D3D12_DEFAULT_ADAPTER_NAME="Intel"

# Ensure shared memory for WSLg Direct VAIL rendering
if [ ! -d "/mnt/shared_memory" ] || ! mountpoint -q /mnt/shared_memory; then
    sudo mkdir -p /mnt/shared_memory 2>/dev/null
    sudo mount -t tmpfs -o rw,nosuid,nodev,relatime,mode=777 tmpfs /mnt/shared_memory 2>/dev/null
fi

export SIH26_PROJECT_DIR="$PROJECT_DIR"
export SIH26_PROFILE="$PROFILE"
# CRITICAL: Re-prepend project source AFTER any ROS2 overlay sourcing.
# The ament install/setup.bash may re-inject the colcon-built egg at the front
# of PYTHONPATH via local_setup.bash. We override it here to ensure the live
# source tree always takes precedence over any stale installed package.
export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}"
export LIVE_TELEMETRY="${LIVE_TELEMETRY:-0}"

# GPU selection: prefer NVIDIA if present, otherwise use Intel/D3D12
# (Gazebo Harmonic picks up MESA_D3D12_DEFAULT_ADAPTER_NAME for GPU routing)
if command -v nvidia-smi &>/dev/null; then
    export MESA_D3D12_DEFAULT_ADAPTER_NAME="NVIDIA"
else
    export MESA_D3D12_DEFAULT_ADAPTER_NAME="Intel"
fi

# Clean up any stale instances before starting fresh
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "ruby" 2>/dev/null || true
pkill -9 -f "parameter_bridge" 2>/dev/null || true
pkill -9 -f "amr_node" 2>/dev/null || true
pkill -9 -f "live_demo_task_generator" 2>/dev/null || true
pkill -9 -f "fleet_safety_hud" 2>/dev/null || true
sleep 0.5

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

echo "======================================================================"
echo "  SIH26123 — DECENTRALIZED AMR FLEET COORDINATION (GAZEBO/ROS 2)"
echo "  Scenario:  $SCENARIO"
echo "  Policy:    $POLICY (PIBT + Space-Time A* + Hungarian Allocation)"
echo "  Profile:   $PROFILE  (world: warehouse_*_${PROFILE}.sdf)"
echo "  Recording: $RECORDING"
echo "  Project:   $PROJECT_DIR"
echo "=================================================================="

cd "$PROJECT_DIR"

# Re-assert project source precedence immediately before launch.
# This is the final defence against any overlay that injected itself into PYTHONPATH.
export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH}"

ros2 launch ros2_integration live_demo.launch.py \
    scenario:="$SCENARIO" \
    policy:="$POLICY" \
    use_sim_time:=true \
    inject_interval:=8.0 \
    seed:=42 \
    hud:=true \
    recording:="$RECORDING"