"""
amr_fleet.launch.py — ROS 2 launch file for the full 6-AMR fleet.

Usage (ROS 2 Jazzy + Gazebo Harmonic, in WSL2):
  ros2 launch ros2_integration amr_fleet.launch.py scenario:=S1
  ros2 launch ros2_integration amr_fleet.launch.py scenario:=S4 num_robots:=6
  ros2 launch ros2_integration amr_fleet.launch.py scenario:=S5
  ros2 launch ros2_integration amr_fleet.launch.py scenario:=S8

Launches:
  - Gazebo Harmonic with the warehouse world SDF (world chosen by scenario)
  - 6 AMR nodes (amr_node.py), one per robot
  - ros_gz_bridge (cmd_vel, odom, scan, imu, clock) per robot
  - RViz2 for visualization (optional)

Scenario → World mapping:
  S1 → warehouse_s1.sdf  (open floor, high congestion tasks)
  S4 → warehouse_s4.sdf  (choke wall, blockage scenario)
  S5 → warehouse_s5.sdf  (open floor + runtime failure injection)
  S8 → warehouse_s8.sdf  (choke wall + runtime failure injection)

Topic convention (CONFIRMED by gz topic -l probe, Gazebo Harmonic 8.x):
  Each robot gets its own SDF generated at launch time with robot_id-scoped
  topic names embedded in DiffDrive and sensor plugins. This avoids topic
  collisions across the 6-robot fleet.

  Per robot R<XX>:
    gz subscribes: /R<XX>/cmd_vel        (geometry_msgs/Twist)
    gz publishes:  /R<XX>/odometry       (nav_msgs/Odometry)
    gz publishes:  /R<XX>/scan           (sensor_msgs/LaserScan)
    gz publishes:  /R<XX>/imu            (sensor_msgs/Imu)

Note: Requires ROS 2 Jazzy + Gazebo Harmonic installed in WSL2.
See docs/WSL2_SETUP_GUIDE.md for installation instructions.
"""

import os
import tempfile
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


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

_PKG_DIR = os.path.dirname(__file__)
AMR_SDF_TEMPLATE = os.path.join(_PKG_DIR, "..", "models", "amr", "model.sdf")
_WORLDS_DIR = os.path.join(_PKG_DIR, "..", "worlds")

# Scenario → world SDF mapping
SCENARIO_WORLDS = {
    "S1": os.path.join(_WORLDS_DIR, "warehouse_s1.sdf"),
    "S4": os.path.join(_WORLDS_DIR, "warehouse_s4.sdf"),
    "S5": os.path.join(_WORLDS_DIR, "warehouse_s5.sdf"),
    "S8": os.path.join(_WORLDS_DIR, "warehouse_s8.sdf"),
}

# Temporary directory for per-robot SDF files (created once per launch)
_TMP_SDF_DIR = tempfile.mkdtemp(prefix="sih26_amr_")


_ROBOT_COLORS = {
    "R01": "0.15 0.38 0.92 1",  # Precision Blue (#2563eb)
    "R02": "0.05 0.75 0.95 1",  # Electric Cyan (#06b6d4)
    "R03": "0.08 0.75 0.35 1",  # Emerald Green (#10b981)
    "R04": "0.95 0.80 0.05 1",  # Golden Yellow (#eab308)
    "R05": "0.98 0.45 0.08 1",  # Safety Orange (#f97316)
    "R06": "0.68 0.25 0.95 1",  # Vivid Purple (#a855f7)
}


def _make_robot_sdf(robot_id: str) -> str:
    """
    Generate a per-robot SDF string from the template, substituting robot_id
    into the DiffDrive and sensor topic names so each robot has unique gz topics
    and distinct high-visibility fleet color for presentation.

    Returns the path to the generated SDF file.
    """
    with open(AMR_SDF_TEMPLATE, "r") as f:
        template = f.read()

    # Replace the model name so Gazebo identifies each robot correctly
    sdf = template.replace('<model name="amr">', f'<model name="{robot_id}">')

    # Apply distinctive, vibrant per-AMR chassis color matching Python Digital Twin
    color = _ROBOT_COLORS.get(robot_id, "0.15 0.38 0.92 1")
    sdf = sdf.replace("<ambient>0.1 0.5 0.9 1</ambient>", f"<ambient>{color}</ambient>")
    sdf = sdf.replace("<diffuse>0.1 0.5 0.9 1</diffuse>", f"<diffuse>{color}</diffuse>")

    # Insert robot-specific elevated 3D ID faceplates and payload cargo box
    payload_xml = f"""
      <visual name="id_face_front">
        <pose>0.024 0 0.39 0 0 0</pose>
        <geometry><box><size>0.005 0.30 0.11</size></box></geometry>
        <material><ambient>{color}</ambient><diffuse>{color}</diffuse><specular>0.6 0.6 0.6 1</specular></material>
      </visual>
      <visual name="id_face_back">
        <pose>-0.024 0 0.39 0 0 0</pose>
        <geometry><box><size>0.005 0.30 0.11</size></box></geometry>
        <material><ambient>{color}</ambient><diffuse>{color}</diffuse><specular>0.6 0.6 0.6 1</specular></material>
      </visual>
      <!-- Realistic 3D Warehouse Cargo Container with Lid & Barcode -->
      <visual name="cargo_payload_body">
        <pose>-0.18 0 0.27 0 0 0</pose>
        <geometry><box><size>0.34 0.38 0.18</size></box></geometry>
        <material><ambient>0.82 0.52 0.12 1</ambient><diffuse>0.92 0.60 0.15 1</diffuse><specular>0.3 0.3 0.3 1</specular></material>
      </visual>
      <visual name="cargo_payload_lid">
        <pose>-0.18 0 0.365 0 0 0</pose>
        <geometry><box><size>0.36 0.40 0.02</size></box></geometry>
        <material><ambient>0.20 0.24 0.32 1</ambient><diffuse>0.25 0.30 0.40 1</diffuse><specular>0.4 0.4 0.4 1</specular></material>
      </visual>
      <visual name="cargo_payload_latch">
        <pose>-0.18 0 0.37 0 0 0</pose>
        <geometry><box><size>0.10 0.41 0.015</size></box></geometry>
        <material><ambient>0.95 0.75 0.05 1</ambient><diffuse>0.98 0.80 0.08 1</diffuse></material>
      </visual>
      <visual name="cargo_barcode_plate">
        <pose>-0.008 0 0.27 0 0 0</pose>
        <geometry><box><size>0.004 0.22 0.10</size></box></geometry>
        <material><ambient>0.95 0.95 0.95 1</ambient><diffuse>0.98 0.98 0.98 1</diffuse></material>
      </visual>
    """
    sdf = sdf.replace("<!-- ROBOT_PAYLOAD_VISUAL -->", payload_xml)

    # Replace DiffDrive topic placeholders:
    # <topic>cmd_vel</topic>   → <topic>/R01/cmd_vel</topic>
    # <odom_topic>odometry</odom_topic> → <odom_topic>/R01/odometry</odom_topic>
    # <tf_topic>tf</tf_topic>  → <tf_topic>/R01/tf</tf_topic>
    sdf = sdf.replace("<topic>cmd_vel</topic>", f"<topic>/{robot_id}/cmd_vel</topic>")
    sdf = sdf.replace("<odom_topic>odometry</odom_topic>", f"<odom_topic>/{robot_id}/odometry</odom_topic>")
    sdf = sdf.replace("<tf_topic>tf</tf_topic>", f"<tf_topic>/{robot_id}/tf</tf_topic>")

    # Replace sensor topic names:
    # <topic>scan</topic> → <topic>/R01/scan</topic>
    # <topic>imu</topic>  → <topic>/R01/imu</topic>
    sdf = sdf.replace("<topic>scan</topic>", f"<topic>/{robot_id}/scan</topic>")
    sdf = sdf.replace("<topic>imu</topic>", f"<topic>/{robot_id}/imu</topic>")

    out_path = os.path.join(_TMP_SDF_DIR, f"{robot_id}.sdf")
    with open(out_path, "w") as f:
        f.write(sdf)
    return out_path


def generate_launch_description() -> LaunchDescription:
    scenario_arg = DeclareLaunchArgument(
        "scenario",
        default_value="S1",
        description="Scenario to run (S1, S4, S5, S8)",
    )
    policy_arg = DeclareLaunchArgument(
        "policy",
        default_value="proposed",
        description="Coordination policy (proposed, baseline)",
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
    record_arg = DeclareLaunchArgument(
        "record",
        default_value="true",
        description="Launch GazeboDataLogger to record run metrics",
    )
    run_id_arg = DeclareLaunchArgument(
        "run_id",
        default_value="S1_run_001",
        description="Unique run ID for results directory",
    )
    continuous_arg = DeclareLaunchArgument(
        "continuous",
        default_value="false",
        description="Run continuous tasks indefinitely in interactive demo mode",
    )
    start_gazebo_arg = DeclareLaunchArgument(
        "start_gazebo",
        default_value="false",
        description="Whether to launch Gazebo simulator",
    )

    # ── Gazebo Harmonic world ─────────────────────────────────────────────────
    # Use OpaqueFunction to resolve the correct world SDF path at launch time.
    # The scenario arg (e.g. 'S1') maps to warehouse_s1.sdf via SCENARIO_WORLDS.
    def launch_gazebo(context, *args, **kwargs):
        start_gz = LaunchConfiguration("start_gazebo").perform(context).lower() in ("true", "1")
        if not start_gz:
            return []
        scenario = LaunchConfiguration("scenario").perform(context)
        world_path = SCENARIO_WORLDS.get(scenario.upper())
        if world_path is None:
            world_path = SCENARIO_WORLDS["S1"]  # fallback
        import shutil
        clean_world = os.path.join(_TMP_SDF_DIR, os.path.basename(world_path))
        shutil.copyfile(world_path, clean_world)
        return [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join("/opt/ros/jazzy/share/ros_gz_sim/launch", "gz_sim.launch.py")
                ),
                launch_arguments={
                    "gz_args": f"-r --render-engine-gui ogre2 --gui-config /home/siddharth/.gz/sim/8/gui.config {clean_world}",
                    "on_exit_shutdown": "true",
                }.items(),
            )
        ]

    gazebo = OpaqueFunction(function=launch_gazebo)

    # ── Clock bridge (global, shared) ──────────────────────────────────────────
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    # ── AMR Fleet Spawning & Nodes ────────────────────────────────────────────
    def launch_fleet(context, *args, **kwargs):
        scenario = LaunchConfiguration("scenario").perform(context).upper()
        policy = LaunchConfiguration("policy").perform(context).lower()
        use_sim_time = LaunchConfiguration("use_sim_time")
        num_robots_val = int(LaunchConfiguration("num_robots").perform(context))

        from ros2_integration.fleet_launcher import SCENARIOS
        from ros2_integration.coordinate_bridge import grid_to_world

        sc_info = SCENARIOS.get(scenario, SCENARIOS["S1"])
        robot_starts = sc_info["robot_starts"]

        active_robots = ROBOT_IDS[:num_robots_val]

        fleet_actions = []
        for i, robot_id in enumerate(active_robots):
            if i < len(robot_starts):
                col, row = robot_starts[i]
                x, y, _ = grid_to_world(col, row, 20)
            else:
                x, y = 1.0, 1.0
            yaw = 0.0

            robot_sdf_path = _make_robot_sdf(robot_id)

            spawn = Node(
                package="ros_gz_sim",
                executable="create",
                arguments=[
                    "-world", "warehouse_s1",
                    "-name", robot_id,
                    "-file", robot_sdf_path,
                    "-x", str(x),
                    "-y", str(y),
                    "-z", "0.28",
                    "-Y", str(yaw),
                ],
                output="screen",
            )

            amr = Node(
                package="ros2_integration",
                executable="amr_node",
                name=f"amr_{robot_id}",
                namespace=robot_id,
                output="screen",
                parameters=[{
                    "robot_id": robot_id,
                    "use_sim_time": use_sim_time,
                    "scenario": scenario,
                    "policy": policy,
                    "map_width": 25,
                    "map_height": 20,
                    "continuous": LaunchConfiguration("continuous"),
                }],
            )

            bridge = Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name=f"bridge_{robot_id}",
                arguments=[
                    f"/{robot_id}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
                    f"/{robot_id}/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry",
                    f"/{robot_id}/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
                    f"/{robot_id}/imu@sensor_msgs/msg/Imu[gz.msgs.IMU",
                ],
                remappings=[
                    (f"/{robot_id}/odometry", f"/{robot_id}/odom"),
                ],
                parameters=[{"use_sim_time": use_sim_time}],
            )

            spawn_delay = i * 1.0 + 1.0
            fleet_actions.extend([
                TimerAction(period=spawn_delay, actions=[spawn]),
                TimerAction(period=spawn_delay + 1.5, actions=[bridge, amr]),
            ])
        return fleet_actions

    fleet = OpaqueFunction(function=launch_fleet)

    # ── GazeboDataLogger (metrics recorder) ──────────────────────────────────
    data_logger = Node(
        package="ros2_integration",
        executable="gazebo_data_logger",
        name="gazebo_data_logger",
        parameters=[{
            "run_id": LaunchConfiguration("run_id"),
            "scenario": LaunchConfiguration("scenario"),
            "policy": LaunchConfiguration("policy"),
            "num_robots": LaunchConfiguration("num_robots"),
            "use_sim_time": LaunchConfiguration("use_sim_time"),
        }],
        condition=IfCondition(LaunchConfiguration("record")),
        output="screen",
    )

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
        policy_arg,
        num_robots_arg,
        use_rviz_arg,
        use_sim_time_arg,
        record_arg,
        run_id_arg,
        continuous_arg,
        start_gazebo_arg,
        LogInfo(msg=f"[SIH26123] Temp SDF dir: {_TMP_SDF_DIR}"),
        LogInfo(msg="Launching SIH26123 AMR Fleet with Gazebo Harmonic"),
        gazebo,
        clock_bridge,
        fleet,
        data_logger,
        rviz,
    ])
