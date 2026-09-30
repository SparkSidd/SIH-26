#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
PROJECT_DIR="/home/siddharth/sih26"
cd "$PROJECT_DIR"
WORLD="$PROJECT_DIR/ros2_integration/worlds/warehouse_s1_recording.sdf"

echo "=== TEST B1: Gazebo GUI + 6 robots spawned (NO ROS nodes) ==="
gz sim -r "$WORLD" &
GZ_PID=$!
sleep 3

for i in {1..6}; do
    rid=$(printf "R%02d" $i)
    ros2 run ros_gz_sim create -name "$rid" -file "$PROJECT_DIR/ros2_integration/models/amr/model_recording.sdf" -x "$((i*2))" -y 5 -z 0.28 >/dev/null 2>&1 &
done
sleep 5

echo "RTF with 6 robots in GUI:"
for i in {1..4}; do
    timeout 2 gz topic -e -t /stats -n 1 | grep real_time_factor || echo "no stats"
    sleep 1
done

kill -9 $GZ_PID 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "create" 2>/dev/null || true
