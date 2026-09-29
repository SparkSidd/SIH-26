"""
fleet_bridge.launch.py — Bridges ROS 2 and Gazebo Harmonic topics for the 6-AMR fleet.
"""

from launch import LaunchDescription
from launch_ros.actions import Node

ROBOT_IDS = [f"R{i:02d}" for i in range(1, 7)]

def generate_launch_description():
    nodes = []

    # 1. Clock bridge
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
        parameters=[{"use_sim_time": True}],
    )
    nodes.append(clock_bridge)

    # 2. Per-AMR bridges (cmd_vel and odom only, no heavy lidar serialization)
    for rid in ROBOT_IDS:
        bridge = Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name=f"bridge_{rid}",
            arguments=[
                f"/{rid}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
                f"/{rid}/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            ],
            remappings=[
                (f"/{rid}/odometry", f"/{rid}/odom"),
            ],
            parameters=[{"use_sim_time": True}],
            output="screen",
        )
        nodes.append(bridge)

    return LaunchDescription(nodes)
