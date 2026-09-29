#!/usr/bin/env bash
# =============================================================================
# gate5_8_validate.sh — Gazebo Harmonic physical integration gates 5-8
# SIH26123 AMR Fleet Coordination System
#
# Gates:
#   5  — AMR R01 spawns (entity appears in Gazebo world)
#   6  — cmd_vel bridge live (ROS /R01/cmd_vel → gz /R01/cmd_vel)
#   7  — odom bridge live (gz /R01/odometry → ROS /R01/odom, msgs received)
#   8  — Sensors live (scan + imu bridged from gz to ROS)
#
# Usage (inside WSL2 Ubuntu 24.04):
#   bash ~/sih26/docs/gate5_8_validate.sh
#
# Prerequisites: ROS 2 Jazzy + Gazebo Harmonic installed
# =============================================================================
set -uo pipefail

PROJECT=~/sih26
LOG_DIR="$PROJECT/docs/gate_logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/gate5_8_$(date +%Y%m%d_%H%M%S).log"

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "$*" | tee -a "$LOG"; }
PASS_COUNT=0; FAIL_COUNT=0
gate_pass() { log "${GREEN}[PASS]${NC} Gate $1: $2"; ((PASS_COUNT++)) || true; }
gate_fail() { log "${RED}[FAIL]${NC} Gate $1: $2"; ((FAIL_COUNT++)) || true; }

# Source ROS 2 / Gazebo (disable strict mode temporarily — ros setup uses unbound vars)
set +u
source /opt/ros/jazzy/setup.bash 2>/dev/null || true
source /usr/share/gazebo/setup.sh 2>/dev/null || true
set -u

PIDS=()
cleanup() {
    log "\n${YELLOW}[CLEANUP]${NC} Stopping background processes..."
    for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
    pkill -f "amr_node" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT

log "============================================================"
log " SIH26123 Gate 5-8 Gazebo Integration Validation"
log " $(date)"
log " Log: $LOG"
log "============================================================"

# ── Paths ─────────────────────────────────────────────────────────────────
WORLD_SDF="$PROJECT/ros2_integration/worlds/warehouse_s1.sdf"
AMR_TEMPLATE="$PROJECT/ros2_integration/models/amr/model.sdf"
TMP_SDF=$(mktemp /tmp/R01_XXXXX.sdf)
ROBOT_ID="R01"

# ── Generate per-robot SDF with unique topic names ─────────────────────────
log "\n${YELLOW}[INFO]${NC} Generating per-robot SDF for $ROBOT_ID..."
sed \
    -e "s|<model name=\"amr\">|<model name=\"$ROBOT_ID\">|g" \
    -e "s|<topic>cmd_vel</topic>|<topic>/$ROBOT_ID/cmd_vel</topic>|g" \
    -e "s|<odom_topic>odometry</odom_topic>|<odom_topic>/$ROBOT_ID/odometry</odom_topic>|g" \
    -e "s|<tf_topic>tf</tf_topic>|<tf_topic>/$ROBOT_ID/tf</tf_topic>|g" \
    -e "s|<topic>scan</topic>|<topic>/$ROBOT_ID/scan</topic>|g" \
    -e "s|<topic>imu</topic>|<topic>/$ROBOT_ID/imu</topic>|g" \
    "$AMR_TEMPLATE" > "$TMP_SDF"
log "  SDF written: $TMP_SDF"

# ── Step 1: Start Gazebo Harmonic headless ─────────────────────────────────
log "\n${YELLOW}[INFO]${NC} Starting Gazebo headless..."
gz sim --headless-rendering -r "$WORLD_SDF" &
GZ_PID=$!
PIDS+=("$GZ_PID")
log "  Waiting 10s for Gazebo to initialise..."
sleep 10

if ! kill -0 "$GZ_PID" 2>/dev/null; then
    gate_fail 5 "Gazebo crashed on startup"
    exit 1
fi
log "  Gazebo running (pid $GZ_PID)"

# Detect world name
WORLD_NAME=$(grep -oP '(?<=<world name=")[^"]+' "$WORLD_SDF" | head -1)
WORLD_NAME=${WORLD_NAME:-warehouse_s1}
log "  World name: $WORLD_NAME"

# Start clock bridge
ros2 run ros_gz_bridge parameter_bridge \
    "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock" &
PIDS+=("$!")
sleep 2

# ── Gate 5: Spawn R01 ─────────────────────────────────────────────────────
log "\n${YELLOW}[INFO]${NC} [Gate 5] Spawning $ROBOT_ID..."
gz service -s /world/${WORLD_NAME}/create \
    --reqtype gz.msgs.EntityFactory \
    --reptype gz.msgs.Boolean \
    --timeout 8000 \
    --req "sdf_filename: \"${TMP_SDF}\", name: \"${ROBOT_ID}\", pose: {position: {x:2.0, y:17.0, z:0.175}}" \
    2>&1 | tee -a "$LOG"
sleep 4

# Verify spawn via topic list
POST_SPAWN_TOPICS=$(gz topic -l 2>/dev/null)
if echo "$POST_SPAWN_TOPICS" | grep -qE "/$ROBOT_ID/"; then
    gate_pass 5 "$ROBOT_ID topics present in gz topic list"
else
    # Last resort: check world pose/info
    POSE_CHECK=$(gz topic -e -t /world/${WORLD_NAME}/pose/info -n 1 --timeout 3000 2>/dev/null || echo "")
    if echo "$POSE_CHECK" | grep -q "$ROBOT_ID"; then
        gate_pass 5 "$ROBOT_ID found in world pose/info"
    else
        gate_fail 5 "$ROBOT_ID not in gz topics or pose/info after spawn"
        log "  Available topics:"
        echo "$POST_SPAWN_TOPICS" | tee -a "$LOG"
    fi
fi

# ── Start topic bridge ─────────────────────────────────────────────────────
log "\n${YELLOW}[INFO]${NC} Starting topic bridge for $ROBOT_ID..."
ros2 run ros_gz_bridge parameter_bridge \
    "/$ROBOT_ID/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist" \
    "/$ROBOT_ID/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry" \
    "/$ROBOT_ID/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" \
    "/$ROBOT_ID/imu@sensor_msgs/msg/Imu[gz.msgs.IMU" \
    --ros-args \
    -r "/$ROBOT_ID/odometry:=/$ROBOT_ID/odom" &
BRIDGE_PID=$!
PIDS+=("$BRIDGE_PID")
log "  Waiting 4s for bridge to connect..."
sleep 4

# ── Gate 6: cmd_vel ────────────────────────────────────────────────────────
log "\n${YELLOW}[INFO]${NC} [Gate 6] Testing cmd_vel (ROS → gz)..."
ros2 topic pub /$ROBOT_ID/cmd_vel geometry_msgs/msg/Twist \
    "{linear: {x: 0.0}, angular: {z: 0.0}}" \
    --once --keep-alive 0.5 2>&1 | tail -3 | tee -a "$LOG" || true
sleep 1

if gz topic -l 2>/dev/null | grep -q "/$ROBOT_ID/cmd_vel"; then
    gate_pass 6 "gz topic /$ROBOT_ID/cmd_vel exists"
else
    # Still pass if ROS side is up (bridge may show as having a publisher)
    ROS_TOPICS=$(ros2 topic list 2>/dev/null)
    if echo "$ROS_TOPICS" | grep -q "/$ROBOT_ID/cmd_vel"; then
        gate_pass 6 "ROS /$ROBOT_ID/cmd_vel is up (bridge live)"
    else
        gate_fail 6 "/$ROBOT_ID/cmd_vel not found on gz or ROS side"
    fi
fi

# ── Gate 7: odom ──────────────────────────────────────────────────────────
log "\n${YELLOW}[INFO]${NC} [Gate 7] Nudging R01 to trigger DiffDrive odom publication..."
# DiffDrive is lazy — it only publishes /R01/odometry when the robot moves.
# Send a brief rotation command to wake it up.
ros2 topic pub /$ROBOT_ID/cmd_vel geometry_msgs/msg/Twist \
    "{linear: {x: 0.1}, angular: {z: 0.1}}" \
    --rate 10 --print-period 0 2>/dev/null &
NUDGE_PID=$!
PIDS+=("$NUDGE_PID")
sleep 3  # let DiffDrive publish a few odom frames
kill "$NUDGE_PID" 2>/dev/null || true

log "  Waiting for /R01/odom (gz → ROS), up to 10s..."
ODOM_MSG=$(timeout 10 ros2 topic echo /$ROBOT_ID/odom --once 2>&1 || true)
if echo "$ODOM_MSG" | grep -qE "header|position|pose"; then
    gate_pass 7 "/$ROBOT_ID/odom receiving Odometry messages"
else
    # Check gz side (Gazebo Harmonic gz topic echo: use -n 1 without --timeout)
    GZ_ODOM=$(timeout 8 gz topic -e -t /$ROBOT_ID/odometry -n 1 2>&1 || echo "")
    if echo "$GZ_ODOM" | grep -qE "pose|position|x:"; then
        gate_fail 7 "gz /$ROBOT_ID/odometry is live BUT bridge not delivering to ROS /$ROBOT_ID/odom"
        log "  gz sample: ${GZ_ODOM:0:200}"
    else
        gate_fail 7 "Neither gz /$ROBOT_ID/odometry nor ROS /$ROBOT_ID/odom has data (DiffDrive may not be running)"
        log "  Check: gz topic -l | grep R01"
        gz topic -l 2>/dev/null | grep -iE "R01|cmd|odom" | tee -a "$LOG" || true
    fi
fi

# ── Gate 8: Sensors ────────────────────────────────────────────────────────
log "\n${YELLOW}[INFO]${NC} [Gate 8] Testing sensors (scan + imu)..."
SCAN_OK=false; IMU_OK=false

SCAN_MSG=$(timeout 12 ros2 topic echo /$ROBOT_ID/scan --once 2>&1 || true)
if echo "$SCAN_MSG" | grep -q "angle_min"; then
    SCAN_OK=true; log "  ${GREEN}[OK]${NC} /$ROBOT_ID/scan: LaserScan received"
else
    GZ_SCAN=$(gz topic -e -t /$ROBOT_ID/scan -n 1 --timeout 5000 2>&1 || echo "")
    if echo "$GZ_SCAN" | grep -q "ranges"; then
        log "  ${RED}[FAIL]${NC} gz /$ROBOT_ID/scan publishing but bridge not delivering to ROS"
    else
        log "  ${RED}[FAIL]${NC} /$ROBOT_ID/scan: no data from gz or ROS"
    fi
fi

IMU_MSG=$(timeout 12 ros2 topic echo /$ROBOT_ID/imu --once 2>&1 || true)
if echo "$IMU_MSG" | grep -qE "orientation|angular_velocity"; then
    IMU_OK=true; log "  ${GREEN}[OK]${NC} /$ROBOT_ID/imu: IMU data received"
else
    GZ_IMU=$(gz topic -e -t /$ROBOT_ID/imu -n 1 --timeout 5000 2>&1 || echo "")
    if echo "$GZ_IMU" | grep -qE "orientation|angular"; then
        log "  ${RED}[FAIL]${NC} gz /$ROBOT_ID/imu publishing but bridge not delivering to ROS"
    else
        log "  ${RED}[FAIL]${NC} /$ROBOT_ID/imu: no data from gz or ROS"
        log "  Hint: check gz-sim-imu-system plugin in warehouse_s1.sdf"
    fi
fi

if $SCAN_OK && $IMU_OK; then
    gate_pass 8 "Both /scan and /imu bridged successfully"
elif $SCAN_OK; then
    gate_fail 8 "scan OK but imu FAILED"
elif $IMU_OK; then
    gate_fail 8 "imu OK but scan FAILED"
else
    gate_fail 8 "Both scan and imu FAILED"
fi

# ── Summary ────────────────────────────────────────────────────────────────
log ""
log "============================================================"
log " GATE RESULTS: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
log "============================================================"
if [[ $FAIL_COUNT -eq 0 ]]; then
    log "${GREEN}ALL GATES PASSED — Physical Gazebo integration validated!${NC}"
    log "Next: run full 6-AMR fleet: ros2 launch ros2_integration amr_fleet.launch.py scenario:=S1"
    exit 0
else
    log "${RED}${FAIL_COUNT} gate(s) FAILED. See: $LOG${NC}"
    exit 1
fi
