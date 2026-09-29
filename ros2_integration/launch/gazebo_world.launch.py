"""
gazebo_world.launch.py — Launches just the Gazebo world (no robots).
Used for world validation and debugging.

Usage:
  ros2 launch ros2_integration gazebo_world.launch.py
  ros2 launch ros2_integration gazebo_world.launch.py world:=warehouse_s4
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

_WORLDS_DIR = os.path.join(os.path.dirname(__file__), "..", "worlds")


def generate_launch_description() -> LaunchDescription:
    world_arg = DeclareLaunchArgument(
        "world",
        default_value="warehouse_s1",
        description="World file name (without .sdf)",
    )
    gui_arg = DeclareLaunchArgument(
        "gui",
        default_value="true",
        description="Show Gazebo GUI",
    )

    world_file = [_WORLDS_DIR, "/", LaunchConfiguration("world"), ".sdf"]

    gz_args = ["-r ", *world_file]

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join("/opt/ros/jazzy/share/ros_gz_sim/launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": gz_args,
            "on_exit_shutdown": "true",
        }.items(),
    )

    # Clock bridge (always needed for use_sim_time)
    from launch_ros.actions import Node
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
    )

    return LaunchDescription([world_arg, gui_arg, gz_sim, clock_bridge])
