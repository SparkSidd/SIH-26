#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash
pkill -9 -f "gz sim" 2>/dev/null || true
sleep 1

PROJECT_DIR="/mnt/c/Users/thega/PROJECTS/SIH'26"
gz sim -s -r "$PROJECT_DIR/ros2_integration/worlds/warehouse_s1.sdf" &
GZ_PID=$!
sleep 4

ros2 run ros_gz_sim create \
    -name R01 \
    -file "$PROJECT_DIR/ros2_integration/models/amr/model.sdf" \
    -x 2.0 -y 17.0 -z 0.175 -Y 0.0

sleep 2
echo "=== ALL GAZEBO TOPICS ==="
gz topic -l
echo "========================="

kill -9 "$GZ_PID" 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
