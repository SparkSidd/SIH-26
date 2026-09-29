"""
live_demo.launch.py -- SIH26123 Gazebo Live Functional Demo Launch File.

This is the FUNCTIONALITY-FIRST demo launcher. It drives the full physical
loop:
  TASK ARRIVAL -> TASK ASSIGNMENT -> COORDINATOR -> ACTION -> cmd_vel
  -> Gazebo DiffDrive -> PHYSICAL MOVEMENT -> odom -> coordinator -> next tick
  -> PICKUP -> DELIVERY -> NEXT TASK

Usage:
  # Single robot, one task loop (first functional verification)
  ros2 launch ros2_integration live_demo.launch.py scenario:=LIVE_TEST_SINGLE

  # Two robots, head-on conflict test
  ros2 launch ros2_integration live_demo.launch.py scenario:=LIVE_TEST_TWO

  # Full 6-robot continuous demo
  ros2 launch ros2_integration live_demo.launch.py scenario:=LIVE_DEMO

Environment Variables:
  LIVE_TELEMETRY=1    Enable full A-K data chain trace at 2 Hz (very verbose)
  LIVE_TELEMETRY=0    Normal operation logs (default)

Topic convention (Gazebo Harmonic / gz-sim-diff-drive-system):
  Robot R01:
    gz subscribes: /R01/cmd_vel   (ROS -> Gazebo, geometry_msgs/Twist)
    gz publishes:  /R01/odom      (Gazebo -> ROS, nav_msgs/Odometry)
    gz publishes:  /R01/scan      (Gazebo -> ROS, sensor_msgs/LaserScan)

The odom topic is injected directly into the SDF as <odom_topic>/R01/odom</odom_topic>
so no bridge remap is needed.

IMPORTANT: Each AMRNode gets its own FleetCoordinator in this configuration.
The coordinator is NOT shared across robots -- each runs decentralized
coordination via belief broadcasting on /fleet/beliefs.
"""

import os
import tempfile
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    TimerAction,
    LogInfo,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# -- Package paths ------------------------------------------------------------
_PKG_DIR     = os.path.dirname(__file__)
_WORLDS_DIR  = os.path.join(_PKG_DIR, "..", "worlds")
_MODELS_DIR  = os.path.join(_PKG_DIR, "..", "models", "amr")
AMR_SDF_TPL  = os.path.join(_MODELS_DIR, "model.sdf")
_TMP_DIR     = tempfile.mkdtemp(prefix="sih26_livedemo_")

# -- Robot counts per scenario ------------------------------------------------
_SCENARIO_ROBOTS = {
    # Live Demo modes
    "LIVE_TEST_SINGLE": 1,
    "LIVE_TEST_TWO":    2,
    "LIVE_DEMO":        6,
    # Official SIH Presentation Scenarios (A–F)
    "SCENARIO_A":       6,
    "SCENARIO_B":       6,
    "SCENARIO_C":       6,
    "SCENARIO_D":       6,
    "SCENARIO_E":       6,
    "SCENARIO_F":       6,
    # Legacy numerical aliases
    "S1":               6,
    "S4":               6,
    "S5":               6,
    "S8":               6,
}

# -- World SDF: choke scenarios use warehouse_s4.sdf (dividing wall + choke) --
_WORLD_SDF_DEFAULT = os.path.join(_WORLDS_DIR, "warehouse_s1.sdf")
_WORLD_SDF_CHOKE   = os.path.join(_WORLDS_DIR, "warehouse_s4.sdf")
_CHOKE_SCENARIOS   = {"SCENARIO_B", "SCENARIO_D", "S4", "S8"}

# -- Per-robot colors (same as amr_fleet.launch.py) ---------------------------
_ROBOT_COLORS = {
    "R01": "0.15 0.38 0.92 1",
    "R02": "0.05 0.75 0.95 1",
    "R03": "0.08 0.75 0.35 1",
    "R04": "0.95 0.80 0.05 1",
    "R05": "0.98 0.45 0.08 1",
    "R06": "0.68 0.25 0.95 1",
}


def _make_robot_sdf(robot_id: str) -> str:
    """Generate per-robot SDF with /R<XX>/odom directly in DiffDrive plugin."""
    with open(AMR_SDF_TPL, "r") as f:
        sdf = f.read()

    # Model name
    sdf = sdf.replace('<model name="amr">', f'<model name="{robot_id}">')

    # Color
    color = _ROBOT_COLORS.get(robot_id, "0.15 0.38 0.92 1")
    sdf = sdf.replace("<ambient>0.1 0.5 0.9 1</ambient>", f"<ambient>{color}</ambient>")
    sdf = sdf.replace("<diffuse>0.1 0.5 0.9 1</diffuse>", f"<diffuse>{color}</diffuse>")

    # DiffDrive topics -- inject robot-specific names directly into SDF
    # This avoids any bridge remapping ambiguity.
    sdf = sdf.replace("<topic>cmd_vel</topic>",       f"<topic>/{robot_id}/cmd_vel</topic>")
    sdf = sdf.replace("<odom_topic>odometry</odom_topic>", f"<odom_topic>/{robot_id}/odom</odom_topic>")
    sdf = sdf.replace("<tf_topic>tf</tf_topic>",      f"<tf_topic>/{robot_id}/tf</tf_topic>")

    # Sensor topics
    sdf = sdf.replace("<topic>scan</topic>", f"<topic>/{robot_id}/scan</topic>")
    sdf = sdf.replace("<topic>imu</topic>",  f"<topic>/{robot_id}/imu</topic>")

    out = os.path.join(_TMP_DIR, f"{robot_id}.sdf")
    with open(out, "w") as f:
        f.write(sdf)
    return out


def generate_launch_description() -> LaunchDescription:
    # -- Arguments -----------------------------------------------------------
    scenario_arg = DeclareLaunchArgument(
        "scenario",
        default_value="LIVE_TEST_SINGLE",
        description="Live demo scenario: LIVE_TEST_SINGLE | LIVE_TEST_TWO | LIVE_DEMO",
    )
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time", default_value="true",
        description="Use Gazebo simulation time",
    )
    inject_interval_arg = DeclareLaunchArgument(
        "inject_interval", default_value="8.0",
        description="Task injection interval in seconds",
    )
    seed_arg = DeclareLaunchArgument(
        "seed", default_value="42",
        description="Deterministic seed for task generation",
    )
    policy_arg = DeclareLaunchArgument(
        "policy", default_value="proposed",
        description="Coordination policy: proposed | baseline",
    )
    hud_arg = DeclareLaunchArgument(
        "hud", default_value="true",
        description="Enable real-time Safety Supervisor HUD and invariant assertion",
    )
    recording_arg = DeclareLaunchArgument(
        "recording", default_value="false",
        description="Enable clean presentation recording mode",
    )

    # -- Gazebo world (resolved at launch time via OpaqueFunction) -------------
    # World selection is done inside launch_fleet() so SCENARIO determines SDF.
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join("/opt/ros/jazzy/share/ros_gz_sim/launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": f"-r {_WORLD_SDF_DEFAULT}",
            "on_exit_shutdown": "true",
        }.items(),
    )

    # -- Clock bridge (shared) ------------------------------------------------
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    # -- Fleet spawn + AMR nodes + bridges (resolved at launch time) ----------
    def launch_fleet(context, *args, **kwargs):
        scenario = LaunchConfiguration("scenario").perform(context).upper()
        policy = LaunchConfiguration("policy").perform(context).lower()
        use_sim_time = LaunchConfiguration("use_sim_time")
        inject_interval = float(LaunchConfiguration("inject_interval").perform(context))
        seed = int(LaunchConfiguration("seed").perform(context))

        num_robots = _SCENARIO_ROBOTS.get(scenario, 6)
        robot_ids  = [f"R{i:02d}" for i in range(1, num_robots + 1)]

        # Choose world based on scenario type
        world_sdf = _WORLD_SDF_CHOKE if scenario in _CHOKE_SCENARIOS else _WORLD_SDF_DEFAULT

        # CRITICAL: Propagate live-source PYTHONPATH into all spawned nodes.
        # The ament overlay may have prepended a stale colcon-built egg. By
        # re-inserting the project dir here, all ROS2 nodes use the live source.
        import sys, os as _os
        _proj = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
        _sih26_env = {
            "PYTHONPATH": f"{_proj}:{_os.environ.get('PYTHONPATH', '')}",
            "SIH26_PROJECT_DIR": _proj,
            "LIVE_TELEMETRY": _os.environ.get("LIVE_TELEMETRY", "0"),
        }
        if _proj not in sys.path:
            sys.path.insert(0, _proj)

        from ros2_integration.live_demo_task_generator import (
            SCENARIO_ROBOT_STARTS,
            make_initial_tasks,
        )
        from ros2_integration.coordinate_bridge import grid_to_world

        robot_starts = SCENARIO_ROBOT_STARTS.get(scenario, [(2, 2)])
        actions = []

        for i, robot_id in enumerate(robot_ids):
            col, row = robot_starts[i] if i < len(robot_starts) else (2, 2)
            wx, wy, _ = grid_to_world(col, row, 20)

            sdf_path = _make_robot_sdf(robot_id)

            spawn = Node(
                package="ros_gz_sim",
                executable="create",
                arguments=[
                    "-name", robot_id,
                    "-file", sdf_path,
                    "-x", str(wx),
                    "-y", str(wy),
                    "-z", "0.28",
                    "-Y", "0.0",
                ],
                output="screen",
            )

            # Bridge: /R<XX>/cmd_vel (ROS->gz), /R<XX>/odom (gz->ROS),
            #         /R<XX>/scan (gz->ROS)
            # NOTE: odom_topic is already /R<XX>/odom in the SDF so bridge
            #       name matches directly -- NO remapping required.
            bridge = Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name=f"bridge_{robot_id}",
                arguments=[
                    f"/{robot_id}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
                    f"/{robot_id}/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
                    f"/{robot_id}/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
                ],
                output="screen",
                parameters=[{"use_sim_time": use_sim_time}],
            )

            amr = Node(
                package="ros2_integration",
                executable="amr_node",
                name=f"amr_{robot_id}",
                namespace=robot_id,
                output="screen",
                parameters=[{
                    "robot_id":    robot_id,
                    "use_sim_time": use_sim_time,
                    "scenario":    scenario,
                    "policy":      policy,
                    "map_width":   25,
                    "map_height":  20,
                    "continuous":  True,   # always continuous in live demo
                }],
                additional_env=_sih26_env,
            )

            spawn_delay = i * 1.5 + 3.0
            actions.extend([
                TimerAction(period=spawn_delay, actions=[spawn]),
                TimerAction(period=spawn_delay + 2.5, actions=[bridge, amr]),
            ])

        # Task generator node (starts after all robots are up)
        task_gen_delay = num_robots * 1.5 + 8.0
        task_gen = Node(
            package="ros2_integration",
            executable="live_demo_task_generator",
            name="live_demo_task_generator",
            output="screen",
            parameters=[{
                "scenario":    scenario,
                "seed":        seed,
                "interval":    inject_interval,
                "max_queued":  num_robots,
                "use_sim_time": use_sim_time,
            }],
            additional_env=_sih26_env,
        )
        actions.append(TimerAction(period=task_gen_delay, actions=[task_gen]))

        # Safety HUD node (renders real-time mathematical assertions & status banner)
        enable_hud = LaunchConfiguration("hud").perform(context).lower() in ("true", "1")
        recording_val = LaunchConfiguration("recording").perform(context).lower() in ("true", "1")
        if enable_hud:
            hud_node = Node(
                package="ros2_integration",
                executable="fleet_safety_hud",
                name="fleet_safety_hud",
                output="screen",
                parameters=[{
                    "scenario":    scenario,
                    "robots":      num_robots,
                    "use_sim_time": use_sim_time,
                    "recording":   recording_val,
                }],
                additional_env=_sih26_env,
            )
            actions.append(TimerAction(period=task_gen_delay + 1.0, actions=[hud_node]))

        return actions

    fleet = OpaqueFunction(function=launch_fleet)

    return LaunchDescription([
        scenario_arg,
        policy_arg,
        use_sim_time_arg,
        inject_interval_arg,
        seed_arg,
        hud_arg,
        recording_arg,
        LogInfo(msg="[SIH26123] Live Demo launching — FUNCTION FIRST"),
        LogInfo(msg=f"[SIH26123] Temp SDF dir: {_TMP_DIR}"),
        gz_sim,
        clock_bridge,
        fleet,
    ])
