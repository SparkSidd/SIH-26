"""
amr_node.py — ROS 2 Adapter Node for a single Autonomous Mobile Robot.

This module bridges the frozen SIH26123 coordination stack into ROS 2.
It runs on EACH robot independently (decentralized, no shared state server).

Architecture
------------
                    ┌──────────────────────────────────────────┐
                    │           AMRNode (this file)            │
                    │                                          │
  ROS Topics ──────►│  /robot_id/odom   (nav_msgs/Odometry)   │
  (Gazebo or       │  /robot_id/scan   (sensor_msgs/LaserScan)│
   SIL publisher)  │  /fleet/beliefs   (std_msgs/String JSON) │
                    │                                          │
                    │       ┌──────────────────────┐           │
                    │       │  FROZEN COORD STACK  │           │
                    │       │  ─────────────────── │           │
                    │       │  FleetCoordinator    │           │
                    │       │  (PIBT + STA*)       │           │
                    │       │  FleetAwareAllocator │           │
                    │       │  SafetyDecision      │           │
                    │       └──────────────────────┘           │
                    │                                          │
  ROS Topics ◄─────│  /robot_id/cmd_vel (geometry_msgs/Twist) │
                    │  /fleet/beliefs   (broadcast own state)  │
                    └──────────────────────────────────────────┘

DO NOT modify the coordination stack. All changes stay in this file and
coordinate_bridge.py.
"""

from __future__ import annotations

import json
import math
import time
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# ROS 2 / SIL import routing
# ──────────────────────────────────────────────────────────────────────────────
import os
_FORCE_MOCK = os.environ.get("USE_MOCK_ROS", "").lower() in ("1", "true")

if not _FORCE_MOCK:
    try:
        import rclpy
        from rclpy.node import Node
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan
        from std_msgs.msg import String
        _ROS2_REAL = True
    except ImportError:
        _FORCE_MOCK = True

if _FORCE_MOCK:
    # Fall back to mock stubs (SIL mode — Windows without WSL2)
    from ros2_integration.mock_ros import rclpy_stub as rclpy
    from ros2_integration.mock_ros.rclpy_stub import Node
    from ros2_integration.mock_ros.geometry_msgs import Twist, Vector3
    from ros2_integration.mock_ros.nav_msgs import Odometry
    from ros2_integration.mock_ros.sensor_msgs import LaserScan
    from ros2_integration.mock_ros.std_msgs import String
    _ROS2_REAL = False

# ──────────────────────────────────────────────────────────────────────────────
# Frozen coordination stack (DO NOT MODIFY THESE IMPORTS OR THEIR BEHAVIOUR)
# ──────────────────────────────────────────────────────────────────────────────
import sys
for _cand in [
    os.environ.get("SIH26_PROJECT_DIR", ""),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    "/home/siddharth/sih26",
]:
    if _cand and os.path.isdir(os.path.join(_cand, "coordination")) and _cand not in sys.path:
        sys.path.insert(0, _cand)
        break

from coordination.coordinator import FleetCoordinator
from execution.action import RobotAction, ActionType
from execution.motion_model import MotionModel
from simulator.robot import Robot, RobotGeometry, RobotBattery, RobotState
from simulator.task import Task, TaskState
from world_model.local_world import LocalWorldModel
from simulator.sensors import SensorObservation
from ros2_integration.coordinate_bridge import (
    grid_to_world,
    world_to_grid,
    heading_to_yaw,
    GRID_ROWS,
    CELL_SIZE_M,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
CONTROL_LOOP_HZ = 10.0              # coordination step rate
BELIEF_BROADCAST_HZ = 5.0          # P2P state broadcast rate
ODOM_POSITION_TOLERANCE = 0.3      # metres — snap to grid cell when within this
LIDAR_OBSTACLE_THRESHOLD = 0.8     # metres — range reading below this = obstacle
FLEET_BELIEF_TOPIC = "/fleet/beliefs"
SIL_STEP_DT = 1.0 / CONTROL_LOOP_HZ

# ── Runtime telemetry (toggled by LIVE_TELEMETRY env var) ────────────────────
# Set LIVE_TELEMETRY=1 for human-readable 2 Hz trace of the full A-K data chain.
_LIVE_TELEMETRY = os.environ.get("LIVE_TELEMETRY", "").lower() in ("1", "true")
_TELEM_HZ = 2.0       # max log rate for telemetry messages
_TELEM_PERIOD = 1.0 / _TELEM_HZ


class AMRNode(Node):
    """
    Single-robot ROS 2 node that:
      1. Receives odometry + LiDAR from Gazebo (or SIL publisher)
      2. Feeds sensor data into the local world model
      3. Calls the frozen FleetCoordinator to get the next action
      4. Translates the action to cmd_vel and publishes it
      5. Broadcasts own belief state over P2P topic
      6. Receives peer beliefs and updates local world model

    One AMRNode instance per physical/simulated robot.
    """

    def __init__(
        self,
        robot_id: str,
        initial_position: Tuple[int, int],
        static_grid: np.ndarray,
        fleet_coordinator: FleetCoordinator,
        tasks: Dict[str, Task],
        map_width: int = 25,
        map_height: int = GRID_ROWS,
        initial_task_id: Optional[str] = None,
        continuous: bool = False,
        **node_kwargs,
    ):
        super().__init__(f"amr_{robot_id}", **node_kwargs)
        self.robot_id = robot_id
        self._map_width = map_width
        self._map_height = map_height
        self._static_grid = static_grid
        self._tasks = tasks  # shared task registry (updated by fleet_launcher)
        self._continuous_demo = continuous
        self._demo_task_seq = 0
        self._scenario_task_defs: list = []

        # ── Robot model (mirrors internal sim representation) ─────────────────
        self.robot = Robot(
            id=robot_id,
            initial_position=initial_position,
            geometry=RobotGeometry(),
            battery=RobotBattery(),
        )
        if initial_task_id and initial_task_id in self._tasks:
            self.robot.current_task_id = initial_task_id
            self.robot.set_state(RobotState.TASK_ASSIGNED)
            self._tasks[initial_task_id].state = TaskState.ASSIGNED
            self._tasks[initial_task_id].assigned_robot_id = robot_id
            self.robot.target_position = self._tasks[initial_task_id].pickup

        self.robot.local_world_model = LocalWorldModel(
            self_id=robot_id,
            map_width=map_width,
            map_height=map_height,
            static_grid=static_grid,
        )
        self._motion_model = MotionModel(geometry=self.robot.geometry)

        # ── Frozen coordination stack (shared instance across fleet) ──────────
        self._coordinator = fleet_coordinator

        # ── World-frame tracking ──────────────────────────────────────────────
        self._world_x: float = 0.0
        self._world_y: float = 0.0
        self._world_yaw: float = 0.0
        wx, wy, _ = grid_to_world(initial_position[0], initial_position[1], map_height)
        self._world_x, self._world_y = wx, wy
        self._init_world_x = wx
        self._init_world_y = wy
        self._odom_received: bool = False   # True once first real odom arrives

        # ── Metrics ───────────────────────────────────────────────────────────
        self._tasks_completed: int = 0
        self._collision_events: int = 0
        self._step_count: int = 0
        self._cmd_vel_latencies: List[float] = []
        self._blocked_cells: Set[Tuple[int, int]] = set()
        self._min_forward_dist: float = 999.0

        # ── ROS 2 publishers ──────────────────────────────────────────────────
        self._pub_cmd_vel = self.create_publisher(
            Twist, f"/{robot_id}/cmd_vel", 10
        )
        self._pub_belief = self.create_publisher(
            String, FLEET_BELIEF_TOPIC, 10
        )

        # ── ROS 2 subscriptions ───────────────────────────────────────────────
        self._sub_odom = self.create_subscription(
            Odometry, f"/{robot_id}/odom", self._on_odom, 10
        )
        self._sub_scan = self.create_subscription(
            LaserScan, f"/{robot_id}/scan", self._on_scan, 10
        )
        self._sub_peer_beliefs = self.create_subscription(
            String, FLEET_BELIEF_TOPIC, self._on_peer_belief, 10
        )

        # ── Timers ────────────────────────────────────────────────────────────
        self._coord_timer = self.create_timer(
            1.0 / CONTROL_LOOP_HZ, self._coordination_step
        )
        self._belief_timer = self.create_timer(
            1.0 / BELIEF_BROADCAST_HZ, self._broadcast_belief
        )
        # Heartbeat: confirm coordinator is ticking (printed at 0.5 Hz)
        self._heartbeat_timer = self.create_timer(2.0, self._heartbeat)
        self._last_telem_time: float = 0.0
        self._coord_ticks: int = 0

        self.get_logger().info(
            f"[AMRNode/{robot_id}] Initialized at grid {initial_position} "
            f"world=({wx:.2f},{wy:.2f}) "
            f"({'ROS2' if _ROS2_REAL else 'SIL'} mode) "
            f"LIVE_TELEMETRY={'ON' if _LIVE_TELEMETRY else 'OFF'}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Subscription callbacks
    # ──────────────────────────────────────────────────────────────────────────

    def _on_odom(self, msg: Odometry) -> None:
        """
        Receive odometry from Gazebo / SIL publisher.
        Updates robot world-frame position and snaps to grid cell.

        IMPORTANT: Gazebo DiffDrive publishes in the 'odom' frame.
        The pose in this frame is ABSOLUTE from spawn point, NOT relative.
        We use it directly as world position (spawn = world origin).
        """
        px = msg.pose.pose.position.x
        py = msg.pose.pose.position.y
        qx = msg.pose.pose.orientation.x
        qy = msg.pose.pose.orientation.y
        qz = msg.pose.pose.orientation.z
        qw = msg.pose.pose.orientation.w
        self._world_yaw = math.atan2(
            2.0 * (qw * qz + qx * qy),
            1.0 - 2.0 * (qy * qy + qz * qz),
        )

        # In Gazebo, odom frame pose is absolute from the spawn position.
        # Spawn position = initial world coords from grid_to_world().
        # So: world_pos = spawn_offset + odom_relative_pos
        # But since we spawn the robot at its world grid position,
        # odom starts at (0,0) and accumulates. Add spawn offset.
        if not _ROS2_REAL:
            # SIL mode: mock odom is already in world frame
            self._world_x = px
            self._world_y = py
        else:
            # Real Gazebo: odom frame starts at spawn. Add spawn world offset.
            self._world_x = self._init_world_x + px
            self._world_y = self._init_world_y + py

        self._odom_received = True

        # Snap to grid cell
        grid_col, grid_row = world_to_grid(self._world_x, self._world_y, self._map_height)
        grid_col = max(0, min(self._map_width - 1, grid_col))
        grid_row = max(0, min(self._map_height - 1, grid_row))

        old_pos = self.robot.position
        if (grid_col, grid_row) != old_pos:
            self._motion_model.step_discrete_motion(
                self.robot, (grid_col, grid_row), SIL_STEP_DT
            )
            if _LIVE_TELEMETRY:
                t_now = time.monotonic()
                if t_now - self._last_telem_time >= _TELEM_PERIOD:
                    logger.info(
                        "[ODOM] %s world=(%.2f,%.2f) yaw=%.2f "
                        "grid=%s->%s",
                        self.robot_id, self._world_x, self._world_y,
                        math.degrees(self._world_yaw),
                        old_pos, (grid_col, grid_row)
                    )

        # Velocity from twist
        self.robot.velocity = math.hypot(
            msg.twist.twist.linear.x,
            msg.twist.twist.linear.y,
        )

    def _on_scan(self, msg: LaserScan) -> None:
        """
        Receive LiDAR scan. Detect obstacles and nearby robot silhouettes.
        Updates local world model blocked cells and tracks forward clearance.
        """
        current_obstacles: Set[Tuple[int, int]] = set()
        detected_robots: List[Tuple[str, Tuple[int, int]]] = []
        min_fwd = 999.0

        # Robot chassis half-length is 0.40m — ignore rays inside vehicle footprint
        min_body_radius = 0.42

        angle = msg.angle_min
        for r in msg.ranges:
            if math.isfinite(r) and r >= min_body_radius and r <= msg.range_max:
                # Forward cone: +/- 25 degrees (0.436 rad)
                if abs(angle) < 0.436 and r < min_fwd:
                    min_fwd = r

                if r < 0.55:
                    # Convert to world frame relative to robot
                    bx = self._world_x + r * math.cos(self._world_yaw + angle)
                    by = self._world_y + r * math.sin(self._world_yaw + angle)
                    gc, gr = world_to_grid(bx, by, self._map_height)
                    if (gc, gr) != self.robot.position and (gc, gr) != self.robot.target_position:
                        current_obstacles.add((gc, gr))
            angle += msg.angle_increment

        self._blocked_cells = current_obstacles
        self._min_forward_dist = min_fwd
        obstacles = list(current_obstacles)

        obs = SensorObservation(
            robot_id=self.robot_id,
            timestamp=time.monotonic(),
            detected_obstacles=obstacles,
            detected_robots=detected_robots,
            self_localized_pos=self.robot.position,
            confidence=0.95,
        )
        if self.robot.local_world_model:
            self.robot.local_world_model.update_from_sensor_observation(obs)

    def _on_peer_belief(self, msg: String) -> None:
        """
        Receive P2P belief broadcast from a fleet peer.
        Deserializes JSON and updates local world model.
        """
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        sender_id = payload.get("robot_id")
        if not sender_id or sender_id == self.robot_id:
            return  # ignore own broadcasts

        if self.robot.local_world_model:
            self.robot.local_world_model.update_from_peer_message(
                sender_id=sender_id,
                position=tuple(payload.get("position", [0, 0])),
                velocity=payload.get("velocity", 0.0),
                heading=payload.get("heading", 0.0),
                intended_action=payload.get("intended_action", "WAIT"),
                planned_path=[tuple(p) for p in payload.get("planned_path", [])],
                current_task_id=payload.get("current_task_id"),
                priority=payload.get("priority", 1.0),
                timestamp=payload.get("timestamp", 0.0),
                sequence_number=payload.get("seq", 0),
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Coordination timer — main control loop
    # ──────────────────────────────────────────────────────────────────────────

    def _heartbeat(self) -> None:
        """Confirm the coordinator timer is alive. Printed at 0.5 Hz."""
        self.get_logger().info(
            f"[COORD_TICK] {self.robot_id} tick={self._coord_ticks} "
            f"state={self.robot.state.name} "
            f"pos={self.robot.position} "
            f"target={self.robot.target_position} "
            f"task={self.robot.current_task_id} "
            f"odom_rcvd={self._odom_received} "
            f"world=({self._world_x:.2f},{self._world_y:.2f})"
        )

    def _coordination_step(self) -> None:
        """
        Main per-robot control loop, called at CONTROL_LOOP_HZ.

        Implements the complete A-K data chain:
          A. Task exists?       -> log task_id, pickup, dropoff, state
          B. Task assigned?     -> log task_id, robot_id
          C. Coordinator runs?  -> log tick, pos, goal, action
          D. RobotAction?       -> log action type
          E. cmd_vel published? -> log vx, wz
          F-K handled via odom callback and heartbeat.
        """
        self._coord_ticks += 1

        if not self.robot.is_healthy:
            self._publish_estop()
            return

        t0 = time.monotonic()
        t_now = t0
        sim_time = t0
        do_telem = _LIVE_TELEMETRY and (t_now - self._last_telem_time >= _TELEM_PERIOD)
        if do_telem:
            self._last_telem_time = t_now

        # ── Auto-assign task from queue if robot is idle ─────────────────────
        # This covers QUEUED tasks injected by LiveDemoTaskGenerator
        if (self.robot.state == RobotState.IDLE
                and not self.robot.current_task_id):
            queued_task = next(
                (t for t in self._tasks.values()
                 if t.state == TaskState.QUEUED
                 and not t.assigned_robot_id),
                None
            )
            if queued_task is not None:
                queued_task.state = TaskState.ASSIGNED
                queued_task.assigned_robot_id = self.robot_id
                queued_task.assigned_time = t_now
                self.robot.current_task_id = queued_task.id
                self.robot.target_position = queued_task.pickup
                self.robot.set_state(RobotState.TASK_ASSIGNED, "QUEUED task self-assigned")
                if self.robot.local_world_model:
                    self.robot.local_world_model.known_task_ids.add(queued_task.id)
                self.get_logger().info(
                    f"[{t_now:.2f}] TASK_ASSIGNED {queued_task.id} -> {self.robot_id} "
                    f"pickup={queued_task.pickup} dropoff={queued_task.dropoff}"
                )

        # Continuous demo mode: auto-replenish from scenario pool if idle
        if getattr(self, "_continuous_demo", False) and self.robot.state == RobotState.IDLE:
            if not self.robot.current_task_id or (
                self.robot.current_task_id in self._tasks
                and self._tasks[self.robot.current_task_id].state == TaskState.DELIVERED
            ):
                self._replenish_continuous_task()

        # ── [A] Log current task state ────────────────────────────────────────
        if do_telem and self.robot.current_task_id:
            task = self._tasks.get(self.robot.current_task_id)
            if task:
                logger.info(
                    "[A] TASK %s state=%s pickup=%s dropoff=%s robot=%s",
                    task.id, task.state.name, task.pickup, task.dropoff,
                    task.assigned_robot_id
                )

        # ── Pickup and delivery arrival detection ─────────────────────────────
        if self.robot.current_task_id and self.robot.current_task_id in self._tasks:
            task = self._tasks[self.robot.current_task_id]
            px, py, _ = grid_to_world(task.pickup[0], task.pickup[1], self._map_height)
            dx, dy, _ = grid_to_world(task.dropoff[0], task.dropoff[1], self._map_height)
            dist_to_pickup  = math.hypot(px - self._world_x, py - self._world_y)
            dist_to_dropoff = math.hypot(dx - self._world_x, dy - self._world_y)

            at_pickup  = (self.robot.position == task.pickup  or dist_to_pickup  < 0.75)
            at_dropoff = (self.robot.position == task.dropoff or dist_to_dropoff < 0.75)

            if task.state == TaskState.ASSIGNED:
                if at_pickup:
                    # Normal: picked up from pickup bay
                    task.state = TaskState.PICKED_UP
                    task.pickup_time = sim_time
                    self.robot.has_payload = True
                    self.robot.target_position = task.dropoff
                    self.robot.set_state(RobotState.DELIVERING, "Arrived at pickup bay")
                    self.get_logger().info(
                        f"[{t_now:.2f}] PICKUP {task.id} {self.robot_id} "
                        f"at={task.pickup} dist={dist_to_pickup:.2f}m "
                        f"-> DROPOFF={task.dropoff}"
                    )
                elif at_dropoff and self.robot.state == RobotState.DELIVERING:
                    # Coordinator routed to dropoff directly (ASSIGNED->DELIVERING via action).
                    # Synthesize: PICKUP + DELIVERY in one step.
                    task.state = TaskState.DELIVERED
                    task.pickup_time = sim_time
                    task.completion_time = sim_time
                    self.robot.has_payload = False
                    self.robot.tasks_completed += 1
                    self._tasks_completed += 1
                    self.robot.current_task_id = None
                    self.robot.target_position = None
                    self.robot.reset_wait()
                    self.robot.set_state(RobotState.IDLE, "Express delivery (no pickup stop)")
                    self.get_logger().info(
                        f"[{t_now:.2f}] EXPRESS_DELIVERY {task.id} {self.robot_id} "
                        f"at_dropoff={task.dropoff} (pickup was bypassed) "
                        f"TOTAL_DONE={self._tasks_completed}"
                    )
                    if getattr(self, "_continuous_demo", False):
                        self._replenish_continuous_task()

            elif task.state == TaskState.PICKED_UP or self.robot.has_payload:
                if at_dropoff:
                    task.state = TaskState.DELIVERED
                    task.completion_time = sim_time
                    self.robot.has_payload = False
                    self.robot.tasks_completed += 1
                    self._tasks_completed += 1
                    self.robot.current_task_id = None
                    self.robot.target_position = None
                    self.robot.reset_wait()
                    self.robot.set_state(RobotState.IDLE, "Delivered payload at bay")
                    self.get_logger().info(
                        f"[{t_now:.2f}] DELIVERY {task.id} {self.robot_id} "
                        f"at={task.dropoff} dist={dist_to_dropoff:.2f}m "
                        f"TOTAL_DONE={self._tasks_completed}"
                    )
                    if getattr(self, "_continuous_demo", False):
                        self._replenish_continuous_task()


        # ── [C] Coordinator tick log ──────────────────────────────────────────
        if do_telem:
            logger.info(
                "[C] COORD_TICK %s tick=%d pos=%s goal=%s world=(%.2f,%.2f)",
                self.robot_id, self._coord_ticks,
                self.robot.position, self.robot.target_position,
                self._world_x, self._world_y
            )

        # Build fleet snapshot for coordinator
        fleet_snapshot = self._build_fleet_snapshot()

        def is_walkable(pos: Tuple[int, int]) -> bool:
            x, y = pos
            if not (0 <= x < self._map_width and 0 <= y < self._map_height):
                return False
            if self._static_grid[x, y] in (1, 2):
                return False
            return True

        try:
            actions = self._coordinator.step_coordinate(
                robots=fleet_snapshot,
                tasks=self._tasks,
                is_walkable_fn=is_walkable,
                blocked_cells=self._blocked_cells,
                sim_time=sim_time,
                step=self._step_count,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[AMRNode/%s] Coordinator error: %s", self.robot_id, exc)
            self._publish_estop()
            return

        my_action = actions.get(self.robot_id)
        if my_action is None:
            if do_telem:
                logger.info("[D] NO_ACTION %s from coordinator", self.robot_id)
            return

        # ── [D] RobotAction produced ──────────────────────────────────────────
        if do_telem:
            logger.info(
                "[D] ACTION %s type=%s target=%s vel=%.2f",
                self.robot_id, my_action.action_type.name,
                getattr(my_action, 'target_cell', None),
                getattr(my_action, 'target_velocity', 0.0)
            )

        # Translate action -> cmd_vel
        twist = self._action_to_cmd_vel(my_action)

        # ── [E] cmd_vel log ───────────────────────────────────────────────────
        if do_telem:
            logger.info(
                "[E] CMD_VEL %s vx=%.3f wz=%.3f",
                self.robot_id,
                twist.linear.x, twist.angular.z
            )

        self._pub_cmd_vel.publish(twist)
        latency_ms = (time.monotonic() - t0) * 1000.0
        self._cmd_vel_latencies.append(latency_ms)

        # ── SIL self-odom: advance world position when no Gazebo odom ────────
        # In real Gazebo, the robot physically moves and publishes odom.
        # In SIL/mock mode, we must drive the odom ourselves so the position
        # feedback loop closes. This is NOT teleportation — it mirrors the
        # continuous physics model at grid-cell granularity.
        if not _ROS2_REAL and my_action.action_type == ActionType.MOVE:
            target_cell = my_action.target_cell
            tx, ty, _ = grid_to_world(target_cell[0], target_cell[1], self._map_height)
            # Compute distance to target cell center
            dist = math.hypot(tx - self._world_x, ty - self._world_y)
            # Advance along velocity vector (simple integrator, one step)
            speed = abs(twist.linear.x)
            step_dist = speed * SIL_STEP_DT  # distance covered in one tick
            if dist > 0.01:
                frac = min(1.0, step_dist / dist)
                new_x = self._world_x + frac * (tx - self._world_x)
                new_y = self._world_y + frac * (ty - self._world_y)
                # Build synthetic odom and feed back
                from ros2_integration.mock_ros.nav_msgs import Odometry
                from ros2_integration.mock_ros.geometry_msgs import Point, Quaternion
                odom = Odometry()
                odom.header.frame_id = "world"
                odom.pose.pose.position.x = new_x
                odom.pose.pose.position.y = new_y
                odom.pose.pose.position.z = 0.0
                target_yaw = heading_to_yaw(self.robot.position, target_cell)
                odom.pose.pose.orientation.z = math.sin(target_yaw / 2.0)
                odom.pose.pose.orientation.w = math.cos(target_yaw / 2.0)
                odom.twist.twist.linear.x = speed
                self._on_odom(odom)

        # Periodic status at 1/30 ticks (not tied to do_telem rate)
        if self._step_count % 30 == 0:
            self.get_logger().info(
                f"[AMRNode/{self.robot_id}] "
                f"state={self.robot.state.name} "
                f"action={my_action.action_type.name} "
                f"pos={self.robot.position} "
                f"target={self.robot.target_position} "
                f"vx={twist.linear.x:.2f} wz={twist.angular.z:.2f}"
            )
        self._step_count += 1

        # Update robot state machine
        self._apply_action_to_robot_model(my_action)

    def _build_fleet_snapshot(self) -> Dict[str, Robot]:
        """
        Build the robot dict that FleetCoordinator.step_coordinate() expects.
        In decentralized mode each robot only knows about itself + peers via
        belief messages. The snapshot uses peer_beliefs to reconstruct peer
        Robot stubs (position only — other fields are defaults).
        """
        snapshot: Dict[str, Robot] = {self.robot_id: self.robot}

        if self.robot.local_world_model:
            for peer_id, belief in self.robot.local_world_model.peer_beliefs.items():
                peer_stub = Robot(
                    id=peer_id,
                    initial_position=belief.position,
                )
                peer_stub.heading = belief.heading
                peer_stub.velocity = belief.velocity
                peer_stub.planned_path = list(belief.planned_path)
                peer_stub.current_task_id = belief.current_task_id
                peer_stub.base_priority = belief.priority
                if belief.intended_action and hasattr(RobotState, belief.intended_action):
                    peer_stub.set_state(RobotState[belief.intended_action])
                snapshot[peer_id] = peer_stub

                # Conflict resolution: if peer and self claim the same task, tie-break by ID
                if belief.current_task_id and belief.current_task_id == self.robot.current_task_id:
                    if peer_id < self.robot_id:
                        self.robot.current_task_id = None
                        self.robot.target_position = None
                        self.robot.set_state(RobotState.IDLE, "Yielded duplicate task to peer")

                # Sync peer task assignment into local task dict to prevent duplicate assignment
                if belief.current_task_id and belief.current_task_id in self._tasks:
                    ptask = self._tasks[belief.current_task_id]
                    ptask.state = TaskState.ASSIGNED
                    ptask.assigned_robot_id = peer_id

        return snapshot

    # ──────────────────────────────────────────────────────────────────────────
    # Action → cmd_vel translation
    # ──────────────────────────────────────────────────────────────────────────

    def _action_to_cmd_vel(self, action: RobotAction) -> "Twist":
        """
        Translate a RobotAction from the coordination stack into a ROS 2
        geometry_msgs/Twist velocity command.

        Mapping:
          MOVE    → linear.x = max_velocity, angular.z = required heading change
          WAIT    → all zeros
          ROTATE  → linear.x = 0, angular.z = angular velocity to reach target
          PICK    → all zeros (arm/gripper handled separately)
          DROP    → all zeros
          CHARGE  → all zeros
          ESTOP   → all zeros (safety-critical)
        """
        twist = Twist()

        if action.action_type == ActionType.MOVE:
            target = action.target_cell
            target_yaw = heading_to_yaw(self.robot.position, target)
            yaw_error = _normalize_angle(target_yaw - self._world_yaw)

            tx, ty, _ = grid_to_world(target[0], target[1], self._map_height)
            dist_to_target = math.hypot(tx - self._world_x, ty - self._world_y)
            base_speed = action.target_velocity * self.robot.geometry.max_velocity

            # Proximity safety buffer: halt linear motion only if immediate bumper obstruction < 0.40m
            if self._min_forward_dist < 0.40:
                twist.linear.x = 0.0
                twist.angular.z = float(1.5 * yaw_error) if abs(yaw_error) > 0.05 else 0.5
            elif abs(yaw_error) > math.radians(45.0):
                # Rotate first if facing more than 45 degrees away
                twist.linear.x = 0.0
                twist.angular.z = float(2.0 * math.copysign(1.0, yaw_error))
            else:
                # Smooth unicycle control: blend speed with cosine of yaw error
                cos_err = max(0.0, math.cos(yaw_error))
                if dist_to_target < 0.35:
                    speed = max(0.2, min(base_speed, dist_to_target * 2.0)) * cos_err
                else:
                    speed = base_speed * cos_err

                twist.linear.x = float(speed)
                twist.angular.z = float(2.0 * yaw_error)

        elif action.action_type == ActionType.ROTATE:
            if action.target_heading is not None:
                yaw_error = _normalize_angle(action.target_heading - self._world_yaw)
                twist.angular.z = float(2.0 * math.copysign(1.0, yaw_error))

        # WAIT, PICK, DROP, CHARGE, ESTOP → zero twist (robot stops)
        return twist

    def _publish_estop(self) -> None:
        """Publish zero-velocity emergency stop."""
        self._pub_cmd_vel.publish(Twist())

    # ──────────────────────────────────────────────────────────────────────────
    # Robot model update
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_action_to_robot_model(self, action: RobotAction) -> None:
        """Reflect action outcome into the internal robot state machine."""
        if action.action_type == ActionType.MOVE:
            if self.robot.has_payload or self.robot.state == RobotState.DELIVERING:
                self.robot.set_state(RobotState.DELIVERING)
            else:
                self.robot.set_state(RobotState.MOVING_TO_PICKUP)
        elif action.action_type == ActionType.WAIT:
            self.robot.increment_wait(reason="Coordination wait")
        elif action.action_type == ActionType.PICK:
            self.robot.has_payload = True
            self.robot.set_state(RobotState.MOVING_TO_DROPOFF)
        elif action.action_type == ActionType.DROP:
            self.robot.has_payload = False
            self._tasks_completed += 1
            self.robot.tasks_completed += 1
            self.robot.set_state(RobotState.IDLE)
            if getattr(self, "_continuous_demo", False):
                self._replenish_continuous_task()
        elif action.action_type == ActionType.CHARGE:
            self.robot.set_state(RobotState.CHARGING)
        elif action.action_type == ActionType.ESTOP:
            self.robot.set_state(RobotState.FAILED, reason="E-stop")

    def _replenish_continuous_task(self) -> None:
        """Assign a new continuous material handling mission in interactive demo mode."""
        if not self._scenario_task_defs:
            # Fallback pickup/dropoff points matching warehouse_s4 layout
            pickups = [(2, 2), (2, 7), (2, 12), (2, 17), (5, 5), (5, 14)]
            dropoffs = [(20, 3), (20, 8), (20, 13), (20, 16), (21, 5), (21, 14)]
            self._scenario_task_defs = list(zip(pickups, dropoffs))
        self._demo_task_seq += 1
        rid_num = int("".join(filter(str.isdigit, self.robot_id)) or "1")
        idx = (rid_num + self._demo_task_seq) % len(self._scenario_task_defs)
        p, d = self._scenario_task_defs[idx]
        tid = f"T_DEMO_{self.robot_id}_{self._demo_task_seq}"
        new_task = Task(id=tid, pickup=p, dropoff=d, state=TaskState.ASSIGNED)
        new_task.assigned_robot_id = self.robot_id
        new_task.assigned_time = time.monotonic()
        self._tasks[tid] = new_task
        self.robot.current_task_id = tid
        self.robot.target_position = p
        self.robot.set_state(RobotState.TASK_ASSIGNED, "Continuous demo mission assigned")
        if self.robot.local_world_model:
            self.robot.local_world_model.known_task_ids.add(tid)

    # ──────────────────────────────────────────────────────────────────────────
    # P2P belief broadcast
    # ──────────────────────────────────────────────────────────────────────────

    def _broadcast_belief(self) -> None:
        """Serialize own state and broadcast to fleet P2P topic."""
        payload = {
            "robot_id": self.robot_id,
            "position": list(self.robot.position),
            "velocity": self.robot.velocity,
            "heading": self.robot.heading,
            "intended_action": self.robot.state.name,
            "planned_path": [list(p) for p in self.robot.planned_path[:10]],
            "current_task_id": self.robot.current_task_id,
            "priority": self.robot.dynamic_priority,
            "timestamp": time.monotonic(),
            "seq": self._step_count,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._pub_belief.publish(msg)

    # ──────────────────────────────────────────────────────────────────────────
    # Metrics API (used by fleet_launcher)
    # ──────────────────────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Return per-robot performance metrics."""
        lats = self._cmd_vel_latencies
        return {
            "robot_id": self.robot_id,
            "tasks_completed": self._tasks_completed,
            "collision_events": self._collision_events,
            "steps": self._step_count,
            "battery": round(self.robot.battery.current_charge, 2),
            "is_healthy": self.robot.is_healthy,
            "cmd_vel_latency_mean_ms": round(sum(lats) / len(lats), 3) if lats else 0.0,
            "cmd_vel_latency_p95_ms": round(sorted(lats)[int(len(lats) * 0.95)], 3) if lats else 0.0,
            "total_distance": round(self.robot.total_distance_traveled, 2),
            "wait_steps": self.robot.wait_steps,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_angle(angle: float) -> float:
    """Normalize angle to [-π, π]."""
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def main(args=None):
    """Console script entry point for amr_node ROS 2 executable."""
    if not _ROS2_REAL:
        print("[ERROR] Real rclpy is required to run amr_node as a ROS 2 node.")
        return

    rclpy.init(args=args)

    from rcl_interfaces.msg import ParameterDescriptor
    dyn_desc = ParameterDescriptor(dynamic_typing=True)

    temp_node = Node("amr_init_helper")
    temp_node.declare_parameter("robot_id", "R01", dyn_desc)
    temp_node.declare_parameter("scenario", "S1", dyn_desc)
    temp_node.declare_parameter("policy", "proposed", dyn_desc)
    temp_node.declare_parameter("map_width", 25, dyn_desc)
    temp_node.declare_parameter("map_height", 20, dyn_desc)
    temp_node.declare_parameter("continuous", False, dyn_desc)

    robot_id = str(temp_node.get_parameter("robot_id").value)
    scenario_name = str(temp_node.get_parameter("scenario").value)
    policy = str(temp_node.get_parameter("policy").value).lower()
    map_width = int(temp_node.get_parameter("map_width").value)
    map_height = int(temp_node.get_parameter("map_height").value)
    cont_raw = temp_node.get_parameter("continuous").value
    continuous = cont_raw if isinstance(cont_raw, bool) else (str(cont_raw).lower() in ("true", "1", "yes"))

    # Fallback: if robot_id defaulted to R01 but node was launched in namespace like /R04
    ns = temp_node.get_namespace().strip("/")
    if ns and (robot_id == "R01" or not robot_id) and ns.startswith("R"):
        robot_id = ns

    temp_node.destroy_node()

    from ros2_integration.fleet_launcher import SCENARIOS
    sc_info = SCENARIOS.get(scenario_name, SCENARIOS["S1"])
    static_grid = sc_info["grid_fn"]()

    rid_digits = "".join(filter(str.isdigit, robot_id))
    rid_num = int(rid_digits) if rid_digits else 1
    idx = (rid_num - 1) % len(sc_info["robot_starts"])
    init_pos = sc_info["robot_starts"][idx]

    tasks = {}
    for tid, p, d in sc_info["tasks"]:
        tasks[tid] = Task(id=tid, pickup=p, dropoff=d, state=TaskState.CREATED)

    initial_task_id = None
    if 0 <= (rid_num - 1) < len(sc_info["tasks"]):
        initial_task_id = sc_info["tasks"][rid_num - 1][0]

    planner_algo = "stop_and_wait" if policy == "baseline" else "pibt"
    alloc_type = "nearest" if policy == "baseline" else "fleet_aware"

    coordinator = FleetCoordinator(
        map_width=map_width,
        map_height=map_height,
        planner_algorithm=planner_algo,
        allocator_type=alloc_type,
    )

    node = AMRNode(
        robot_id=robot_id,
        initial_position=init_pos,
        static_grid=static_grid,
        fleet_coordinator=coordinator,
        tasks=tasks,
        map_width=map_width,
        map_height=map_height,
        initial_task_id=initial_task_id,
        continuous=continuous,
    )
    if "tasks" in sc_info:
        node._scenario_task_defs = [(p, d) for _, p, d in sc_info["tasks"]]

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        import traceback
        traceback.print_exc()
        logger.error(f"[AMRNode/{robot_id}] Spin exception: {exc}")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

