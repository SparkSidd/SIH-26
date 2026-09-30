#!/bin/bash
set -eo pipefail

# scripts/launch_gui_simulator.sh — Reusable Robust WSLg GUI Simulator Launcher
# Usage:
#   bash scripts/launch_gui_simulator.sh webots [world_file]
#   bash scripts/launch_gui_simulator.sh gazebo [single|two|fleet|custom_args...]
#   bash scripts/launch_gui_simulator.sh test

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================================"
echo "  SIH26123 — ROBUST WSLg GUI SIMULATOR LAUNCHER"
echo "  Repository : $REPO_DIR"
echo "======================================================================"

# 1. WSLg Environment Variables
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
if [ -d "/mnt/wslg/runtime-dir" ]; then
    export XDG_RUNTIME_DIR="/mnt/wslg/runtime-dir"
fi
export PULSE_SERVER="${PULSE_SERVER:-unix:/mnt/wslg/PulseServer}"

# Enable Direct3D 12 GPU Hardware Acceleration via WSLg (/dev/dxg)
export GALLIUM_DRIVER=d3d12
export MESA_D3D12_DEFAULT_ADAPTER_NAME="Intel"

# 2. Bounded GUI Initialization Wait (Max 10 seconds)
CHECK_SCRIPT="$SCRIPT_DIR/check_wslg.sh"
TIMEOUT_SECS=10
ELAPSED=0

echo "[1/4] Checking WSLg GUI infrastructure..."
while [ $ELAPSED -lt $TIMEOUT_SECS ]; do
    if bash "$CHECK_SCRIPT" >/dev/null 2>&1; then
        echo "      WSLg GUI is READY (checked in ${ELAPSED}s)."
        break
    fi
    # If /mnt/shared_memory is unmounted, attempt inline mount fallback
    if ! mount | grep -q "/mnt/shared_memory" 2>/dev/null; then
        sudo mkdir -p /mnt/shared_memory 2>/dev/null || true
        sudo mount -t tmpfs tmpfs /mnt/shared_memory 2>/dev/null || true
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done

if ! bash "$CHECK_SCRIPT"; then
    echo "ERROR: WSLg environment failed readiness checks after ${TIMEOUT_SECS}s."
    exit 1
fi

TARGET="${1:-test}"
shift || true

case "$TARGET" in
    test|xeyes)
        echo "[2/4] Testing basic GUI window with xeyes..."
        echo "      Starting xeyes on DISPLAY=$DISPLAY for 5 seconds..."
        xeyes &
        TEST_PID=$!
        sleep 5
        kill "$TEST_PID" 2>/dev/null || true
        echo "      xeyes test finished."
        exit 0
        ;;

    webots)
        WORLD="${1:-$REPO_DIR/simulation/webots/worlds/warehouse_fleet.wbt}"
        echo "[2/4] Preparing Webots GUI launch..."
        echo "      Target World: $WORLD"
        echo "      OpenGL Driver: D3D12 GPU-accelerated ($GALLIUM_DRIVER)"
        
        # Kill any existing hung webots processes
        pkill -9 -x webots-bin 2>/dev/null || true
        sleep 0.5

        # Ensure window is on-screen with calibrated geometry
        python3 "$REPO_DIR/scripts/reset_simulator_window_geometry.py" 2>/dev/null || true

        # Webots official launch:
        # NO --minimize (ensures window is visible)
        # NO --no-rendering (ensures 3D graphics render)
        # Use realtime GUI mode
        echo "[3/4] Launching Webots GUI..."
        exec /usr/local/bin/webots --mode=realtime "$WORLD"
        ;;

    gazebo)
        MODE="${1:-two}"
        echo "[2/4] Preparing Gazebo Simulation launch (Mode: $MODE)..."
        
        # Kill any hung gz processes
        pkill -9 -x gz-sim 2>/dev/null || pkill -9 -x ruby 2>/dev/null || true
        sleep 0.5

        # Source ROS 2 Jazzy and workspace
        if [ -f /opt/ros/jazzy/setup.bash ]; then
            source /opt/ros/jazzy/setup.bash
        fi
        if [ -f "$REPO_DIR/ros2_ws/install/setup.bash" ]; then
            source "$REPO_DIR/ros2_ws/install/setup.bash"
        fi

        export SIH26_PROJECT_DIR="$REPO_DIR"
        export PYTHONPATH="$REPO_DIR:${PYTHONPATH:-}"
        export SIH26_PROFILE="${SIH26_PROFILE:-recording}"

        echo "[3/4] Launching Gazebo GUI..."
        cd "$REPO_DIR"

        if [ "$MODE" = "two" ]; then
            exec bash "$REPO_DIR/run_live_two.sh"
        elif [ "$MODE" = "single" ]; then
            exec bash "$REPO_DIR/run_live_single.sh"
        elif [ "$MODE" = "fleet" ] || [ "$MODE" = "demo" ]; then
            exec bash "$REPO_DIR/run_live_fleet.sh" LIVE_DEMO proposed false recording
        else
            # Pass custom arguments
            exec ros2 launch ros2_integration "$MODE" "$@"
        fi
        ;;

    *)
        echo "Unknown target: $TARGET"
        echo "Usage: $0 {webots [world_file]|gazebo [single|two|fleet]|test}"
        exit 1
        ;;
esac
