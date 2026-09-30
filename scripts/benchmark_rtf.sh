#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
PROJECT_DIR="/home/siddharth/sih26"
cd "$PROJECT_DIR"

WORLD="/tmp/test_world.sdf"
cp "$PROJECT_DIR/ros2_integration/worlds/warehouse_s1_recording.sdf" "$WORLD"

echo "=== TEST 1: World alone (no robots) ==="
gz sim -r -s "$WORLD" &
GZ_PID=$!
sleep 4
timeout 3 gz topic -e -t /stats -n 2 | grep real_time_factor
kill -9 $GZ_PID 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
sleep 1

echo "=== TEST 2: World with 6 AMRs spawned (headless) ==="
gz sim -r -s "$WORLD" &
GZ_PID=$!
sleep 2

# Spawn 6 robots
for i in {1..6}; do
    rid=$(printf "R%02d" $i)
    ros2 run ros_gz_sim create -name "$rid" -file "$PROJECT_DIR/ros2_integration/models/amr/model_recording.sdf" -x "$((i*2))" -y 5 -z 0.28 >/dev/null 2>&1 &
done
sleep 4

echo "Stats with 6 robots:"
timeout 4 gz topic -e -t /stats -n 5 | grep real_time_factor

kill -9 $GZ_PID 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "create" 2>/dev/null || true
