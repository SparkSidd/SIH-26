#!/usr/bin/env bash
# =============================================================================
# gazebo_smoke_test.sh
# SIH26123 — Gate 2-9 smoke test runner
# Run inside Ubuntu 24.04 WSL2 after install_ros_gazebo.sh completes.
#
# Tests:
#   GATE 2: ROS 2 Jazzy
#   GATE 3: Gazebo Harmonic
#   GATE 4: ros_gz_bridge
#   (Gates 5-9 require interactive Gazebo — see docs/GAZEBO_QUICKSTART.md)
# =============================================================================
set -eo pipefail

source /opt/ros/jazzy/setup.bash
PROJECT_PATH="/mnt/c/Users/thega/PROJECTS/SIH'26"
export PYTHONPATH="$PROJECT_PATH:${PYTHONPATH:-}"
WORKSPACE="$HOME/sih_ros_ws"
source "$WORKSPACE/install/setup.bash" 2>/dev/null || true

echo ""
echo "============================================================"
echo " SIH26123 Smoke Test — $(date)"
echo "============================================================"

PASS=0
FAIL=0

check() {
    local desc="$1"
    shift
    if "$@" &>/dev/null; then
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    else
        echo "[FAIL] $desc"
        FAIL=$((FAIL+1))
    fi
}

# ── GATE 2: ROS 2 ────────────────────────────────────────────────────────────
echo ""
echo "--- GATE 2: ROS 2 Jazzy ---"
check "ros2 binary exists" which ros2
check "ROS_DISTRO=jazzy" test "$ROS_DISTRO" = "jazzy"
check "geometry_msgs installed" ros2 pkg prefix geometry_msgs
check "nav_msgs installed" ros2 pkg prefix nav_msgs
check "sensor_msgs installed" ros2 pkg prefix sensor_msgs

# ── GATE 3: Gazebo Harmonic ──────────────────────────────────────────────────
echo ""
echo "--- GATE 3: Gazebo Harmonic ---"
check "gz binary exists" which gz
check "gz sim binary" which gz
GZ_VER=$(gz sim --version 2>&1 | head -1 || echo "unknown")
echo "      Gazebo version: $GZ_VER"

# ── GATE 4: ros_gz_bridge ────────────────────────────────────────────────────
echo ""
echo "--- GATE 4: ros_gz_bridge ---"
check "ros_gz_bridge pkg" ros2 pkg prefix ros_gz_bridge
check "ros_gz_sim pkg" ros2 pkg prefix ros_gz_sim
check "parameter_bridge executable" test -x /opt/ros/jazzy/lib/ros_gz_bridge/parameter_bridge

# ── Project imports ───────────────────────────────────────────────────────────
echo ""
echo "--- Project imports ---"
check "FleetCoordinator importable" python3 -c "from coordination.coordinator import FleetCoordinator"
check "AMRNode importable" python3 -c "from ros2_integration.amr_node import AMRNode"
check "coordinate_bridge importable" python3 -c "from ros2_integration.coordinate_bridge import grid_to_world"
check "fleet_launcher importable" python3 -c "from ros2_integration.fleet_launcher import ScenarioRunner"

# ── Original test suite ───────────────────────────────────────────────────────
echo ""
echo "--- Original 102-test regression suite ---"
cd "$PROJECT_PATH"
if python3 -m pytest tests/ -q --tb=no 2>&1 | tail -1 | grep -q "passed"; then
    RESULT=$(python3 -m pytest tests/ -q --tb=no 2>&1 | tail -1)
    echo "[PASS] $RESULT"
    PASS=$((PASS+1))
else
    echo "[FAIL] pytest returned non-zero or unexpected output"
    python3 -m pytest tests/ -q --tb=short 2>&1 | tail -20
    FAIL=$((FAIL+1))
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Smoke Test Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    echo " ALL GATES PASSED — ready for single-AMR Gazebo test"
    echo " Next: ros2 launch ros2_integration single_amr.launch.py"
else
    echo " SOME GATES FAILED — fix before proceeding"
fi
echo "============================================================"
echo ""

exit $FAIL
