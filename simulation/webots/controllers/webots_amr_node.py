#!/usr/bin/env python3
"""
webots_amr_node.py — Webots ROS 2 AMR Controller & Decentralized Coordinator Adapter.

SIH26123: Completely isolated Webots simulation adapter.
Reuses the FROZEN project coordination and planning algorithms:
  - Hungarian Allocation
  - Space-Time A*
  - Priority Inheritance with Backtracking (PIBT)
  - Time-Space Reservation Table
  - Wait-For Graph (WFG) Deadlock Detection
  - Safety Invariant Supervisor

Interfaces directly with Webots differential-drive motors and sensors via the
standard Webots controller Python API, while bridging to ROS 2 topics.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

# ── Ensure Project Root is on PYTHONPATH ─────────────────────────────────────
for _cand in [
    os.environ.get("SIH26_PROJECT_DIR", ""),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
    "/home/siddharth/sih26",
]:
    if _cand and os.path.isdir(os.path.join(_cand, "coordination")) and _cand not in sys.path:
        sys.path.insert(0, _cand)
        break

# ── Ensure Webots Python Controller API is on PYTHONPATH ─────────────────────
webots_home = os.environ.get("WEBOTS_HOME", "/usr/local/webots")
py_controller = os.path.join(webots_home, "lib", "controller", "python")
if os.path.isdir(py_controller) and py_controller not in sys.path:
    sys.path.append(py_controller)

try:
    from controller import Robot as WebotsRobot
except ImportError:
    WebotsRobot = None

# ── ROS 2 Imports ────────────────────────────────────────────────────────────
try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from std_msgs.msg import String
    from rosgraph_msgs.msg import Clock
    _REAL_ROS = True
except ImportError:
    from ros2_integration.mock_ros import rclpy_stub as rclpy
    from ros2_integration.mock_ros.rclpy_stub import Node
    from ros2_integration.mock_ros.geometry_msgs import Twist
    from ros2_integration.mock_ros.nav_msgs import Odometry
    from ros2_integration.mock_ros.std_msgs import String
    _REAL_ROS = False

# ── Project Core Imports (FROZEN ALGORITHMS — DO NOT MODIFY) ──────────────────
from coordination.coordinator import FleetCoordinator
from coordination.congestion import CongestionModel
from execution.action import RobotAction, ActionType
from simulator.robot import Robot as SimRobot, RobotGeometry, RobotState
from simulator.task import Task, TaskState
from ros2_integration.coordinate_bridge import grid_to_world, world_to_grid, GRID_ROWS, heading_to_yaw

# Constants
WHEEL_RADIUS_M = 0.10
WHEEL_BASE_M = 0.60
MAX_MOTOR_RAD_S = 15.0
CONTROL_HZ = 20.0
BELIEF_HZ = 5.0
FLEET_BELIEF_TOPIC = "/fleet/beliefs"


def _normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


class WebotsAMRNode(Node):
    """Webots AMR Controller wrapping the real SIH FleetCoordinator."""

    def __init__(
        self,
        robot_id: str = "R01",
        initial_position: Tuple[int, int] = (6, 9),
        map_width: int = 25,
        map_height: int = 20,
        policy: str = "proposed",
        shared_coordinator: Optional[FleetCoordinator] = None,
        tasks_dict: Optional[Dict[str, Task]] = None,
    ):
        super().__init__(f"amr_{robot_id}")
        self.robot_id = robot_id
        self._map_width = map_width
        self._map_height = map_height
        self._policy = policy

        # Instantiate or bind coordinator
        if shared_coordinator is not None:
            self._coordinator = shared_coordinator
        else:
            self._coordinator = FleetCoordinator(
                map_width=map_width,
                map_height=map_height,
                planner_algorithm="pibt",
                allocator_type="fleet_aware",
            )

        # Core Robot State Model
        self.sim_robot = SimRobot(
            id=robot_id,
            initial_position=initial_position,
            geometry=RobotGeometry(radius=0.45, max_velocity=1.5),
        )

        # World tracking
        wx, wy, _ = grid_to_world(initial_position[0], initial_position[1], map_height)
        self._world_x = wx
        self._world_y = wy
        self._world_yaw = 0.0
        self._step_count = 0
        self._tasks: Dict[str, Task] = tasks_dict if tasks_dict is not None else {}
        self._blocked_cells: Set[Tuple[int, int]] = set()

        # Connect to Webots Hardware API
        self.wb_robot = None
        self.left_motor = None
        self.right_motor = None
        self.left_sensor = None
        self.right_sensor = None
        self.timestep = 32

        if WebotsRobot is not None:
            try:
                # If WEBOTS_ROBOT_NAME is not set, set it to robot_id
                if not os.environ.get("WEBOTS_ROBOT_NAME"):
                    os.environ["WEBOTS_ROBOT_NAME"] = robot_id
                self.wb_robot = WebotsRobot()
                self.timestep = int(self.wb_robot.getBasicTimeStep())
                self.left_motor = self.wb_robot.getDevice("left wheel motor")
                self.right_motor = self.wb_robot.getDevice("right wheel motor")
                if self.left_motor and self.right_motor:
                    self.left_motor.setPosition(float("inf"))
                    self.right_motor.setPosition(float("inf"))
                    self.left_motor.setVelocity(0.0)
                    self.right_motor.setVelocity(0.0)

                self.left_sensor = self.wb_robot.getDevice("left wheel sensor")
                self.right_sensor = self.wb_robot.getDevice("right wheel sensor")
                if self.left_sensor and self.right_sensor:
                    self.left_sensor.enable(self.timestep)
                    self.right_sensor.enable(self.timestep)
                self.get_logger().info(f"[{robot_id}] Connected to Webots physical motors & sensors (dt={self.timestep}ms)")
            except Exception as e:
                self.get_logger().warn(f"[{robot_id}] Webots hardware initialization deferred: {e}")

        self._last_left_pos = 0.0
        self._last_right_pos = 0.0

        # ROS 2 Pub/Sub
        self._pub_cmd_vel = self.create_publisher(Twist, f"/{robot_id}/cmd_vel", 10)
        self._pub_odom = self.create_publisher(Odometry, f"/{robot_id}/odom", 10)
        self._pub_belief = self.create_publisher(String, FLEET_BELIEF_TOPIC, 10)
        self._sub_cmd_vel = self.create_subscription(Twist, f"/{robot_id}/cmd_vel", self._on_cmd_vel, 10)
        self._sub_beliefs = self.create_subscription(String, FLEET_BELIEF_TOPIC, self._on_peer_belief, 10)

        # Timers
        self._coord_timer = self.create_timer(1.0 / CONTROL_HZ, self._coordination_step)
        self._belief_timer = self.create_timer(1.0 / BELIEF_HZ, self._broadcast_belief)

        self.get_logger().info(
            f"[WebotsAMRNode/{robot_id}] Initialized at grid {initial_position} "
            f"world=({wx:.2f}, {wy:.2f}) policy={policy}"
        )

    def _on_cmd_vel(self, msg: Twist) -> None:
        """Drive physical differential wheels from cmd_vel."""
        vx = msg.linear.x
        wz = msg.angular.z

        # Differential kinematics
        v_left = (vx - wz * (WHEEL_BASE_M / 2.0)) / WHEEL_RADIUS_M
        v_right = (vx + wz * (WHEEL_BASE_M / 2.0)) / WHEEL_RADIUS_M

        v_left = max(-MAX_MOTOR_RAD_S, min(MAX_MOTOR_RAD_S, v_left))
        v_right = max(-MAX_MOTOR_RAD_S, min(MAX_MOTOR_RAD_S, v_right))

        if self.left_motor and self.right_motor:
            self.left_motor.setVelocity(float(v_left))
            self.right_motor.setVelocity(float(v_right))

    def _on_peer_belief(self, msg: String) -> None:
        """Receive peer beliefs for decentralized local world model."""
        try:
            data = json.loads(msg.data)
            sender_id = data.get("robot_id")
            if sender_id and sender_id != self.robot_id and self.sim_robot.local_world_model:
                pos = tuple(data.get("position", (0, 0)))
                vel = float(data.get("velocity", 0.0))
                head = float(data.get("heading", 0.0))
                path = [tuple(p) for p in data.get("planned_path", [])]
                self.sim_robot.local_world_model.update_peer_belief(
                    peer_id=sender_id,
                    position=pos,
                    velocity=vel,
                    heading=head,
                    intended_action=data.get("intended_action", "WAIT"),
                    planned_path=path,
                    current_task_id=data.get("current_task_id"),
                )
        except Exception:
            pass

    def _coordination_step(self) -> None:
        """Execute one cycle of real Hungarian allocation + PIBT + Space-Time A*."""
        sim_time = self._step_count * (1.0 / CONTROL_HZ)
        self._step_count += 1

        # Check pickup / dropoff arrivals
        cur_task_id = self.sim_robot.current_task_id
        if cur_task_id and cur_task_id in self._tasks:
            task = self._tasks[cur_task_id]
            px, py, _ = grid_to_world(task.pickup[0], task.pickup[1], self._map_height)
            dx, dy, _ = grid_to_world(task.dropoff[0], task.dropoff[1], self._map_height)
            dist_to_pickup = math.hypot(px - self._world_x, py - self._world_y)
            dist_to_dropoff = math.hypot(dx - self._world_x, dy - self._world_y)
            at_pickup = (self.sim_robot.position == task.pickup or dist_to_pickup < 0.50)
            at_dropoff = (self.sim_robot.position == task.dropoff or dist_to_dropoff < 0.50)

            if task.state == TaskState.ASSIGNED:
                if at_pickup:
                    task.state = TaskState.PICKED_UP
                    self.sim_robot.has_payload = True
                    self.sim_robot.target_position = task.dropoff
                    self.sim_robot.set_state(RobotState.DELIVERING)
                    self.get_logger().info(f"[{self.robot_id}] PICKUP task={task.id} at {task.pickup} -> heading to {task.dropoff}")
            elif task.state == TaskState.PICKED_UP or self.sim_robot.has_payload:
                if at_dropoff:
                    task.state = TaskState.DELIVERED
                    self.sim_robot.has_payload = False
                    self.sim_robot.tasks_completed += 1
                    self.sim_robot.current_task_id = None
                    self.sim_robot.target_position = None
                    self.sim_robot.set_state(RobotState.IDLE)
                    self.get_logger().info(f"[{self.robot_id}] DELIVERED task={task.id} at {task.dropoff}! Total={self.sim_robot.tasks_completed}")

        # Build fleet snapshot
        fleet_snapshot = {self.robot_id: self.sim_robot}
        if self.sim_robot.local_world_model:
            for peer_id, belief in self.sim_robot.local_world_model.peer_beliefs.items():
                p_stub = SimRobot(id=peer_id, initial_position=belief.position)
                p_stub.heading = belief.heading
                p_stub.velocity = belief.velocity
                p_stub.planned_path = list(belief.planned_path)
                p_stub.current_task_id = belief.current_task_id
                fleet_snapshot[peer_id] = p_stub

        def is_walkable(pos: Tuple[int, int]) -> bool:
            x, y = pos
            return 0 <= x < self._map_width and 0 <= y < self._map_height

        # Execute FROZEN coordination algorithm
        actions = self._coordinator.step_coordinate(
            robots=fleet_snapshot,
            tasks=self._tasks,
            is_walkable_fn=is_walkable,
            blocked_cells=self._blocked_cells,
            sim_time=sim_time,
            step=self._step_count,
        )

        my_action = actions.get(self.robot_id)
        if my_action is None:
            return

        # Translate Action to cmd_vel Twist
        twist = self._action_to_cmd_vel(my_action)
        self._pub_cmd_vel.publish(twist)
        self._on_cmd_vel(twist)

        # In SIL/standalone mode: integrate kinematics to update position
        if self.wb_robot is None:
            self._update_simulated_kinematics(twist)

    def _action_to_cmd_vel(self, action: RobotAction) -> Twist:
        """Translate coordinator RobotAction into smooth cmd_vel."""
        twist = Twist()
        if action.action_type == ActionType.MOVE:
            target = action.target_cell
            tx, ty, _ = grid_to_world(target[0], target[1], self._map_height)
            dist = math.hypot(tx - self._world_x, ty - self._world_y)
            target_yaw = math.atan2(ty - self._world_y, tx - self._world_x)
            yaw_err = _normalize_angle(target_yaw - self._world_yaw)

            base_speed = action.target_velocity * self.sim_robot.geometry.max_velocity
            if abs(yaw_err) > math.radians(90.0):
                # Sharp turn: stop and rotate in place
                twist.linear.x = 0.0
                twist.angular.z = float(min(2.5, max(-2.5, 2.5 * math.copysign(1.0, yaw_err))))
            else:
                # Smooth continuous arc
                cos_err = max(0.50, math.cos(yaw_err))
                speed = base_speed * cos_err
                twist.linear.x = float(speed)
                twist.angular.z = float(min(2.5, max(-2.5, 2.5 * yaw_err)))

            # If close to target waypoint, update discrete cell position
            if dist < 0.35:
                self.sim_robot.position = target

        elif action.action_type == ActionType.WAIT:
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            self.sim_robot.increment_wait(reason="Coordination wait")

        return twist

    def _update_simulated_kinematics(self, twist: Twist) -> None:
        """Integrate differential motion for state updates."""
        dt = 1.0 / CONTROL_HZ
        self._world_yaw = _normalize_angle(self._world_yaw + twist.angular.z * dt)
        self._world_x += twist.linear.x * math.cos(self._world_yaw) * dt
        self._world_y += twist.linear.x * math.sin(self._world_yaw) * dt

        # Snap to grid
        col, row = world_to_grid(self._world_x, self._world_y, self._map_height)
        self.sim_robot.position = (col, row)

        # Publish Odometry
        odom = Odometry()
        odom.header.frame_id = "world"
        odom.child_frame_id = f"{self.robot_id}/base_link"
        odom.pose.pose.position.x = float(self._world_x)
        odom.pose.pose.position.y = float(self._world_y)
        odom.pose.pose.orientation.z = float(math.sin(self._world_yaw / 2.0))
        odom.pose.pose.orientation.w = float(math.cos(self._world_yaw / 2.0))
        odom.twist.twist = twist
        self._pub_odom.publish(odom)

    def _broadcast_belief(self) -> None:
        """Broadcast state belief to fleet P2P channel."""
        payload = {
            "robot_id": self.robot_id,
            "position": list(self.sim_robot.position),
            "velocity": self.sim_robot.velocity,
            "heading": self.sim_robot.heading,
            "intended_action": self.sim_robot.state.name,
            "planned_path": [list(p) for p in self.sim_robot.planned_path[:10]],
            "current_task_id": self.sim_robot.current_task_id,
            "priority": self.sim_robot.dynamic_priority,
            "timestamp": time.monotonic(),
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._pub_belief.publish(msg)


def main(args=None):
    parser = argparse.ArgumentParser(description="Webots AMR Controller Node")
    parser.add_argument("--robot_id", default="R01")
    parser.add_argument("--col", type=int, default=6)
    parser.add_argument("--row", type=int, default=9)
    parser.add_argument("--policy", default="proposed")
    parsed_args, _ = parser.parse_known_args()

    if _REAL_ROS:
        rclpy.init(args=args)
        node = WebotsAMRNode(
            robot_id=parsed_args.robot_id,
            initial_position=(parsed_args.col, parsed_args.row),
            policy=parsed_args.policy,
        )
        try:
            rclpy.spin(node)
        except (KeyboardInterrupt, Exception):
            pass
        finally:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
    else:
        print(f"[SIL] Running WebotsAMRNode {parsed_args.robot_id} in standalone mode")


if __name__ == "__main__":
    main()
