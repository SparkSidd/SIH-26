#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
PROJECT_DIR="/home/siddharth/sih26"
cd "$PROJECT_DIR"
WORLD="$PROJECT_DIR/ros2_integration/worlds/warehouse_s1_recording.sdf"

echo "=== TEST C1: Gazebo GUI + 6 robots + fleet_parameter_bridge (NO amr_node) ==="
gz sim -r "$WORLD" &
GZ_PID=$!
sleep 2

# Bridge arguments for 6 robots
bridge_args=("/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock")
for i in {1..6}; do
    rid=$(printf "R%02d" $i)
    bridge_args+=("/${rid}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist")
    bridge_args+=("/${rid}/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry")
    bridge_args+=("/${rid}/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan")
done

ros2 run ros_gz_bridge parameter_bridge "${bridge_args[@]}" &
BRIDGE_PID=$!
sleep 1

# Spawn 6 robots
for i in {1..6}; do
    rid=$(printf "R%02d" $i)
    ros2 run ros_gz_sim create -name "$rid" -file "$PROJECT_DIR/ros2_integration/models/amr/model_recording.sdf" -x "$((i*2))" -y 5 -z 0.28 >/dev/null 2>&1 &
done
sleep 5

echo "RTF with Bridge + 6 robots:"
for i in {1..5}; do
    timeout 2 gz topic -e -t /stats -n 1 | grep real_time_factor || echo "no stats"
    sleep 1
done

kill -9 $GZ_PID $BRIDGE_PID 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "parameter_bridge" 2>/dev/null || true
pkill -9 -f "create" 2>/dev/null || true
