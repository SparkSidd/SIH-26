"""
single_amr.launch.py — Launch one AMR in Gazebo for smoke testing.

Gate 5/6/7/8/9 validation target.

Usage:
  ros2 launch ros2_integration single_amr.launch.py
  ros2 launch ros2_integration single_amr.launch.py x:=5.0 y:=5.0

Topic convention (CONFIRMED by gz topic -l probe, Gazebo Harmonic 8.x):
  Per-robot SDF is generated with robot_id-scoped topic names:
    gz subscribes: /R01/cmd_vel
    gz publishes:  /R01/odometry, /R01/scan, /R01/imu
  Bridge maps gz /R01/... ↔ ROS /R01/...
"""

import os
import tempfile
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# Paths relative to the installed package share directory
_SHARE = os.path.join(os.path.dirname(__file__), "..")
AMR_SDF_TEMPLATE = os.path.join(_SHARE, "models", "amr", "model.sdf")
WORLD_SDF = os.path.join(_SHARE, "worlds", "warehouse_s1.sdf")
_TMP_SDF_DIR = tempfile.mkdtemp(prefix="sih26_single_")

ROBOT_ID = "R01"  # default for smoke test


def _make_robot_sdf(robot_id: str) -> str:
    """Generate per-robot SDF with robot_id-scoped topic names."""
    with open(AMR_SDF_TEMPLATE, "r") as f:
        sdf = f.read()
    sdf = sdf.replace('<model name="amr">', f'<model name="{robot_id}">')
    sdf = sdf.replace("<topic>cmd_vel</topic>", f"<topic>/{robot_id}/cmd_vel</topic>")
    sdf = sdf.replace("<odom_topic>odometry</odom_topic>", f"<odom_topic>/{robot_id}/odometry</odom_topic>")
    sdf = sdf.replace("<tf_topic>tf</tf_topic>", f"<tf_topic>/{robot_id}/tf</tf_topic>")
    sdf = sdf.replace("<topic>scan</topic>", f"<topic>/{robot_id}/scan</topic>")
    sdf = sdf.replace("<topic>imu</topic>", f"<topic>/{robot_id}/imu</topic>")
    out = os.path.join(_TMP_SDF_DIR, f"{robot_id}.sdf")
    with open(out, "w") as f:
        f.write(sdf)
    return out


AMR_SDF = _make_robot_sdf(ROBOT_ID)


def generate_launch_description() -> LaunchDescription:
    robot_id_arg = DeclareLaunchArgument(
        "robot_id", default_value="R01", description="Robot ID"
    )
    x_arg = DeclareLaunchArgument("x", default_value="2.0", description="X spawn position (m)")
    y_arg = DeclareLaunchArgument("y", default_value="17.0", description="Y spawn position (m)")
    scenario_arg = DeclareLaunchArgument(
        "scenario", default_value="S1", description="Scenario (S1/S4/S5/S8)"
    )
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time", default_value="true", description="Use Gazebo sim time"
    )
    start_gazebo_arg = DeclareLaunchArgument(
        "start_gazebo", default_value="false", description="Whether to launch Gazebo (set false if already running)"
    )
    start_amr_node_arg = DeclareLaunchArgument(
        "start_amr_node", default_value="false", description="Whether to start amr_node (set false for manual cmd_vel test)"
    )

    x = LaunchConfiguration("x")
    y = LaunchConfiguration("y")

    # ── 1. Gazebo world (conditional) ─────────────────────────────────────────
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join("/opt/ros/jazzy/share/ros_gz_sim/launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": f"-r {WORLD_SDF}",
            "on_exit_shutdown": "true",
        }.items(),
        condition=IfCondition(LaunchConfiguration("start_gazebo")),
    )

    # ── 2. Spawn AMR entity (per-robot SDF with unique topic names) ───────────
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-world", "warehouse_s1",
            "-name", ROBOT_ID,
            "-file", AMR_SDF,
            "-x", x,
            "-y", y,
            "-z", "0.28",
            "-Y", "0.0",
        ],
        output="screen",
    )

    # ── 3. ros_gz_bridge for this robot ──────────────────────────────────────
    # gz topic names (confirmed by 'gz topic -l' probe, Gazebo Harmonic 8.x):
    #   /{ROBOT_ID}/cmd_vel   — DiffDrive subscribes (ros→gz)
    #   /{ROBOT_ID}/odometry  — DiffDrive publishes  (gz→ros)
    #   /{ROBOT_ID}/scan      — GPU LiDAR publishes  (gz→ros)
    #   /{ROBOT_ID}/imu       — IMU sensor publishes (gz→ros)
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    topic_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name=f"bridge_{ROBOT_ID}",
        arguments=[
            f"/{ROBOT_ID}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            # gz publishes /{ROBOT_ID}/odometry (DiffDrive <odom_topic>)
            # Argument must match gz topic name; remap renames on ROS side
            f"/{ROBOT_ID}/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            f"/{ROBOT_ID}/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
            f"/{ROBOT_ID}/imu@sensor_msgs/msg/Imu[gz.msgs.IMU",
        ],
        remappings=[
            # gz /{ROBOT_ID}/odometry → ROS /{ROBOT_ID}/odom (AMRNode API)
            (f"/{ROBOT_ID}/odometry", f"/{ROBOT_ID}/odom"),
        ],
        output="screen",
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    # ── 4. AMR coordination node (conditional) ────────────────────────────────
    amr_node = Node(
        package="ros2_integration",
        executable="amr_node",
        name="amr_node",
        namespace=ROBOT_ID,
        output="screen",
        parameters=[{
            "robot_id": ROBOT_ID,
            "use_sim_time": LaunchConfiguration("use_sim_time"),
            "scenario": LaunchConfiguration("scenario"),
            "map_width": 25,
            "map_height": 20,
        }],
        condition=IfCondition(LaunchConfiguration("start_amr_node")),
    )

    return LaunchDescription([
        robot_id_arg,
        x_arg,
        y_arg,
        scenario_arg,
        use_sim_time_arg,
        start_gazebo_arg,
        start_amr_node_arg,
        gz_sim,
        bridge,  # clock bridge starts immediately
        TimerAction(period=1.0, actions=[spawn_robot]),
        TimerAction(period=2.0, actions=[topic_bridge]),
        TimerAction(period=3.0, actions=[amr_node]),
    ])
