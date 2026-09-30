#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
PROJECT_DIR="/home/siddharth/sih26"
cd "$PROJECT_DIR"

WORLD="$PROJECT_DIR/ros2_integration/worlds/warehouse_s1_recording.sdf"

echo "=== TEST: Gazebo WITH GUI, no nodes ==="
gz sim -r "$WORLD" &
GZ_PID=$!
sleep 6

for i in {1..5}; do
    timeout 2 gz topic -e -t /stats -n 1 | grep real_time_factor || echo "no stats"
    sleep 1
done

kill -9 $GZ_PID 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
