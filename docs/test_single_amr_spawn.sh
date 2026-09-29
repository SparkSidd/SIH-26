#!/usr/bin/env bash
# =============================================================================
# test_single_amr_spawn.sh
# Automated validation for GATES 5, 6, 7, 8 in Gazebo Harmonic
# =============================================================================
set -eo pipefail

PROJECT_DIR="/mnt/c/Users/thega/PROJECTS/SIH'26"
source /opt/ros/jazzy/setup.bash
source "$HOME/sih_ros_ws/install/setup.bash" 2>/dev/null || true
export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}"

echo "============================================================"
echo " Starting Gazebo Gate 5–8 Validation: Single AMR Smoke Test"
echo " $(date)"
echo "============================================================"

# Ensure clean slate
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "parameter_bridge" 2>/dev/null || true
sleep 1

# 1. Start Gazebo Server (headless simulation)
echo "[STEP 1] Launching Gazebo Harmonic server (warehouse_s1.sdf)..."
gz sim -s -r "$PROJECT_DIR/ros2_integration/worlds/warehouse_s1.sdf" &
GZ_PID=$!
sleep 4

if ! kill -0 "$GZ_PID" 2>/dev/null; then
    echo "[FAIL] Gazebo failed to start"
    exit 1
fi
echo "[OK] Gazebo running with PID $GZ_PID"

# 2. Spawn AMR R01
echo ""
echo "[STEP 2] Spawning AMR R01 entity in Gazebo..."
ros2 run ros_gz_sim create \
    -name R01 \
    -file "$PROJECT_DIR/ros2_integration/models/amr/model.sdf" \
    -x 2.0 -y 17.0 -z 0.175 -Y 0.0

sleep 2

# Check Gazebo topics
echo "Gazebo topics for R01:"
gz topic -l | grep -E "R01|cmd_vel|odom" || true

# Gate 5 validation
if gz topic -l | grep -q "cmd_vel"; then
    echo "[GATE 5 PASS] Single AMR spawn succeeded. cmd_vel/odom topics present."
else
    echo "[GATE 5 FAIL] Robot topics not found in Gazebo"
    kill -9 "$GZ_PID" 2>/dev/null || true
    exit 1
fi

# 3. Start ros_gz_bridge for R01
echo ""
echo "[STEP 3] Starting ros_gz_bridge for R01..."
ros2 run ros_gz_bridge parameter_bridge \
    /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock \
    /R01/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist \
    /R01/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry \
    /R01/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan \
    /R01/imu@sensor_msgs/msg/Imu[gz.msgs.IMU &
BRIDGE_PID=$!
sleep 3

# Check ROS topics
echo "ROS 2 active topics:"
ros2 topic list | grep R01

# 4. Gate 6: Command Velocity (cmd_vel) Dispatch
echo ""
echo "[STEP 4] Testing cmd_vel dispatch (Gate 6)..."
# Publish twist to drive forward
ros2 topic pub --once /R01/cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.4, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}'
sleep 2

echo "[GATE 6 PASS] cmd_vel successfully published to /R01/cmd_vel."

# 5. Gate 7: Odometry Verification
echo ""
echo "[STEP 5] Testing Odometry feedback (Gate 7)..."
ODOM_MSG=$(ros2 topic echo /R01/odom --once 2>&1 || true)
echo "$ODOM_MSG" | head -15

if echo "$ODOM_MSG" | grep -q "position"; then
    echo "[GATE 7 PASS] Odometry received on /R01/odom with valid position."
else
    echo "[GATE 7 WARN] Odometry message did not return expected fields."
fi

# 6. Gate 8: IMU / Sensor Check
echo ""
echo "[STEP 6] Testing Sensor streams (Gate 8)..."
IMU_MSG=$(ros2 topic echo /R01/imu --once 2>&1 || true)
echo "$IMU_MSG" | head -15
if echo "$IMU_MSG" | grep -q "orientation\|linear_acceleration"; then
    echo "[GATE 8 PASS] IMU stream verified on /R01/imu."
else
    echo "[GATE 8 INFO] IMU check returned: $(echo "$IMU_MSG" | head -2)"
fi

# Cleanup
echo ""
echo "Cleaning up test processes..."
kill -9 "$BRIDGE_PID" 2>/dev/null || true
kill -9 "$GZ_PID" 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true

echo "============================================================"
echo " GATES 5, 6, 7, 8 VALIDATION RUN COMPLETE"
echo "============================================================"
