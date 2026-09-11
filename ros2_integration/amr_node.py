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
try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String
    _ROS2_REAL = True
except ImportError:
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
        **node_kwargs,
    ):
        super().__init__(f"amr_{robot_id}", **node_kwargs)
        self.robot_id = robot_id
        self._map_width = map_width
        self._map_height = map_height
        self._static_grid = static_grid
        self._tasks = tasks  # shared task registry (updated by fleet_launcher)

        # ── Robot model (mirrors internal sim representation) ─────────────────
        self.robot = Robot(
            id=robot_id,
            initial_position=initial_position,
            geometry=RobotGeometry(),
            battery=RobotBattery(),
        )
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

        # ── Metrics ───────────────────────────────────────────────────────────
        self._tasks_completed: int = 0
        self._collision_events: int = 0
        self._step_count: int = 0
        self._cmd_vel_latencies: List[float] = []
        self._blocked_cells: Set[Tuple[int, int]] = set()

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

        self.get_logger().info(
            f"[AMRNode/{robot_id}] Initialized at grid {initial_position} "
            f"({'ROS2' if _ROS2_REAL else 'SIL'} mode)"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Subscription callbacks
    # ──────────────────────────────────────────────────────────────────────────

    def _on_odom(self, msg: Odometry) -> None:
        """
        Receive odometry from Gazebo / SIL publisher.
        Updates robot world-frame position and snaps to grid cell.
        """
        # Extract pose
        px = msg.pose.pose.position.x
        py = msg.pose.pose.position.y
        # Yaw from quaternion
        qx = msg.pose.pose.orientation.x
        qy = msg.pose.pose.orientation.y
        qz = msg.pose.pose.orientation.z
        qw = msg.pose.pose.orientation.w
        self._world_yaw = math.atan2(
            2.0 * (qw * qz + qx * qy),
            1.0 - 2.0 * (qy * qy + qz * qz),
        )
        self._world_x = px
        self._world_y = py

        # Snap to grid cell
        grid_col, grid_row = world_to_grid(px, py, self._map_height)
        grid_col = max(0, min(self._map_width - 1, grid_col))
        grid_row = max(0, min(self._map_height - 1, grid_row))

        old_pos = self.robot.position
        if (grid_col, grid_row) != old_pos:
            self._motion_model.step_discrete_motion(
                self.robot, (grid_col, grid_row), SIL_STEP_DT
            )

        # Velocity from twist
        self.robot.velocity = math.hypot(
            msg.twist.twist.linear.x,
            msg.twist.twist.linear.y,
        )

    def _on_scan(self, msg: LaserScan) -> None:
        """
        Receive LiDAR scan. Detect obstacles and nearby robot silhouettes.
        Updates local world model blocked cells.
        """
        obstacles: List[Tuple[int, int]] = []
        detected_robots: List[Tuple[str, Tuple[int, int]]] = []

        angle = msg.angle_min
        for r in msg.ranges:
            if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
                if r < LIDAR_OBSTACLE_THRESHOLD:
                    # Convert to world frame relative to robot
                    bx = self._world_x + r * math.cos(self._world_yaw + angle)
                    by = self._world_y + r * math.sin(self._world_yaw + angle)
                    gc, gr = world_to_grid(bx, by, self._map_height)
                    if (gc, gr) != self.robot.position:
                        obstacles.append((gc, gr))
                        self._blocked_cells.add((gc, gr))
            angle += msg.angle_increment

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

    def _coordination_step(self) -> None:
        """
        Main per-robot control loop, called at CONTROL_LOOP_HZ.

        Calls the frozen FleetCoordinator.step_coordinate() for this robot,
        translates the returned RobotAction → cmd_vel Twist, publishes it.
        """
        if not self.robot.is_healthy:
            self._publish_estop()
            return

        t0 = time.monotonic()

        # Build fleet snapshot for coordinator (only this robot's entry + peer beliefs)
        fleet_snapshot = self._build_fleet_snapshot()
        sim_time = time.monotonic()

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
            return

        # Translate action → cmd_vel
        t1 = time.monotonic()
        twist = self._action_to_cmd_vel(my_action)
        self._pub_cmd_vel.publish(twist)
        latency_ms = (time.monotonic() - t0) * 1000.0
        self._cmd_vel_latencies.append(latency_ms)
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
                snapshot[peer_id] = peer_stub

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

            # Proportional angular control — slow down if large heading error
            if abs(yaw_error) > math.radians(15.0):
                # Rotate first before moving
                twist.linear.x = 0.0
                twist.angular.z = float(2.0 * math.copysign(1.0, yaw_error))
            else:
                # Heading is aligned — drive forward
                speed = action.target_velocity * self.robot.geometry.max_velocity
                twist.linear.x = float(speed)
                twist.angular.z = float(1.5 * yaw_error)  # correction

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
            self.robot.set_state(RobotState.MOVING_TO_PICKUP
                                  if self.robot.state in (RobotState.IDLE, RobotState.TASK_ASSIGNED)
                                  else RobotState.MOVING_TO_DROPOFF)
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
        elif action.action_type == ActionType.CHARGE:
            self.robot.set_state(RobotState.CHARGING)
        elif action.action_type == ActionType.ESTOP:
            self.robot.set_state(RobotState.FAILED, reason="E-stop")

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
