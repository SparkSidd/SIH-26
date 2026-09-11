"""
amr_fleet.launch.py — ROS 2 launch file for the full 6-AMR fleet.

Usage (ROS 2 Jazzy + Gazebo Harmonic, in WSL2):
  ros2 launch ros2_integration amr_fleet.launch.py scenario:=S1
  ros2 launch ros2_integration amr_fleet.launch.py scenario:=S4 num_robots:=6

Launches:
  - Gazebo Harmonic with the warehouse world SDF
  - 6 AMR nodes (amr_node.py), one per robot
  - ros2_control (diff drive controller per robot)
  - RViz2 for visualization (optional)

Note: Requires ROS 2 Jazzy + Gazebo Harmonic installed in WSL2.
See docs/WSL2_SETUP_GUIDE.md for installation instructions.
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    GroupAction,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# Robot ID list (R01 … R06)
ROBOT_IDS = [f"R{i:02d}" for i in range(1, 7)]

# Default spawn positions matching S1 benchmark layout (col, row → x, y with y-flip)
# 1 grid cell = 1.0 m, grid_rows = 20 → y = (19 - row)
DEFAULT_SPAWNS = {
    "R01": (2.0, 17.0, 0.0),   # (2, 2) → (2, 17)
    "R02": (2.0, 9.0, 0.0),    # (2, 10) → (2, 9)
    "R03": (2.0, 2.0, 0.0),    # (2, 17) → (2, 2)
    "R04": (10.0, 9.0, 0.0),   # (10, 10) → (10, 9)
    "R05": (5.0, 14.0, 0.0),   # (5, 5) → (5, 14)
    "R06": (5.0, 5.0, 0.0),    # (5, 14) → (5, 5)
}

AMR_SDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "amr", "model.sdf"
)
WORLD_SDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "worlds", "warehouse_s1.sdf"
)


def generate_launch_description() -> LaunchDescription:
    scenario_arg = DeclareLaunchArgument(
        "scenario",
        default_value="S1",
        description="Scenario to run (S1, S4, S5, S8)",
    )
    num_robots_arg = DeclareLaunchArgument(
        "num_robots",
        default_value="6",
        description="Number of AMR robots to spawn (1-6)",
    )
    use_rviz_arg = DeclareLaunchArgument(
        "use_rviz",
        default_value="false",
        description="Launch RViz2 for visualization",
    )
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use simulation time from Gazebo",
    )

    # ── Gazebo Harmonic world ─────────────────────────────────────────────────
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join("/opt/ros/jazzy/share/ros_gz_sim/launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": f"-r {WORLD_SDF_PATH}",
            "on_exit_shutdown": "true",
        }.items(),
    )

    # ── AMR Nodes (one per robot) ─────────────────────────────────────────────
    amr_nodes = []
    for robot_id in ROBOT_IDS:
        x, y, yaw = DEFAULT_SPAWNS.get(robot_id, (1.0, 1.0, 0.0))

        # Spawn entity in Gazebo
        spawn = Node(
            package="ros_gz_sim",
            executable="create",
            arguments=[
                "-name", robot_id,
                "-file", AMR_SDF_PATH,
                "-x", str(x),
                "-y", str(y),
                "-z", "0.0",
                "-Y", str(yaw),
            ],
            output="screen",
        )

        # AMR coordination node
        amr = Node(
            package="ros2_integration",
            executable="amr_node",
            name=f"amr_{robot_id}",
            namespace=robot_id,
            output="screen",
            parameters=[{
                "robot_id": robot_id,
                "use_sim_time": LaunchConfiguration("use_sim_time"),
                "scenario": LaunchConfiguration("scenario"),
                "map_width": 25,
                "map_height": 20,
            }],
        )

        # ROS 2 ↔ Gazebo bridge (odom, scan, cmd_vel)
        bridge = Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name=f"bridge_{robot_id}",
            arguments=[
                f"/{robot_id}/cmd_vel@geometry_msgs/msg/Twist[gz.msgs.Twist",
                f"/{robot_id}/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
                f"/{robot_id}/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
            ],
            output="screen",
        )

        amr_nodes.extend([spawn, amr, bridge])

    # ── RViz2 (optional) ─────────────────────────────────────────────────────
    rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        condition=IfCondition(LaunchConfiguration("use_rviz")),
        output="screen",
    )

    return LaunchDescription([
        scenario_arg,
        num_robots_arg,
        use_rviz_arg,
        use_sim_time_arg,
        LogInfo(msg="Launching SIH26123 AMR Fleet with Gazebo Harmonic"),
        gazebo,
        *amr_nodes,
        rviz,
    ])
