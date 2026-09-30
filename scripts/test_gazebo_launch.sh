#!/bin/bash
set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

source /opt/ros/jazzy/setup.bash
if [ -f "$REPO_DIR/ros2_ws/install/setup.bash" ]; then
    source "$REPO_DIR/ros2_ws/install/setup.bash"
fi

export SIH26_PROJECT_DIR="$REPO_DIR"
export PYTHONPATH="$REPO_DIR:${PYTHONPATH:-}"
export SIH26_PROFILE="recording"

MODE="${1:-single}"

if [ "$MODE" = "single" ]; then
    ros2 launch ros2_integration live_demo.launch.py scenario:=LIVE_TEST_SINGLE use_sim_time:=true inject_interval:=10.0 seed:=42 recording:=true
elif [ "$MODE" = "two" ]; then
    ros2 launch ros2_integration live_demo.launch.py scenario:=LIVE_TEST_TWO use_sim_time:=true inject_interval:=10.0 seed:=42 recording:=true
else
    ros2 launch ros2_integration live_demo.launch.py scenario:=LIVE_DEMO use_sim_time:=true inject_interval:=8.0 seed:=42 recording:=true
fi
