"""
fleet_launcher.py — Software-in-the-Loop (SIL) fleet execution harness.

Launches 1–6 AMRNode instances, drives them through a scenario using
synthetic odom/scan messages (no Gazebo needed), collects metrics, and
reports PASS/FAIL per scenario.

Usage
-----
  python -m ros2_integration.fleet_launcher --scenario S1
  python -m ros2_integration.fleet_launcher --scenario S4 --robots 6
  python -m ros2_integration.fleet_launcher --all

Pass criteria (SIL):
  - 0 inter-robot collisions
  - 0 deadlocks (all tasks complete within timeout)
  - 100% task completion rate

This harness is fully deterministic and uses the same scenario definitions
as the Python benchmark (scenarios/warehouse_scenarios.py).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# ROS 2 / SIL import routing
# ──────────────────────────────────────────────────────────────────────────────
try:
    import rclpy
    _ROS2_REAL = True
except ImportError:
    from ros2_integration.mock_ros import rclpy_stub as rclpy
    _ROS2_REAL = False

# ──────────────────────────────────────────────────────────────────────────────
# Project imports (frozen stack — DO NOT MODIFY)
# ──────────────────────────────────────────────────────────────────────────────
from coordination.coordinator import FleetCoordinator
from simulator.task import Task, TaskState, TaskGenerator
from simulator.robot import Robot, RobotState
from ros2_integration.amr_node import AMRNode, SIL_STEP_DT
from ros2_integration.coordinate_bridge import grid_to_world, world_to_grid, GRID_ROWS, heading_to_yaw
from ros2_integration.mock_ros.nav_msgs import Odometry
from ros2_integration.mock_ros.sensor_msgs import LaserScan
from ros2_integration.mock_ros.std_msgs import Header
from ros2_integration.mock_ros.geometry_msgs import Pose, PoseWithCovariance, Point, Quaternion, Twist, TwistWithCovariance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fleet_launcher")

from safety.invariants import SafetyInvariants

# ──────────────────────────────────────────────────────────────────────────────
# Scenario definitions  (grid positions, task lists, fleet sizes)
# These mirror the benchmark scenarios from the frozen test suite.
# ──────────────────────────────────────────────────────────────────────────────

# Warehouse dimensions (matches benchmark)
MAP_WIDTH = 25
MAP_HEIGHT = 20

def _make_open_grid() -> np.ndarray:
    """25×20 open grid with no internal walls (S1-style)."""
    grid = np.zeros((MAP_WIDTH, MAP_HEIGHT), dtype=int)
    # Outer border as walls
    grid[0, :] = 1
    grid[-1, :] = 1
    grid[:, 0] = 1
    grid[:, -1] = 1
    return grid


def _make_choke_grid() -> np.ndarray:
    """25×20 grid with a central dividing wall and two choke passages (S4-style)."""
    grid = _make_open_grid()
    mid_x = MAP_WIDTH // 2  # x=12
    for y in range(1, MAP_HEIGHT - 1):
        if y not in (5, 14):  # Two choke passages at y=5 and y=14
            grid[mid_x, y] = 1
    return grid


SCENARIOS = {
    # ── Live Demonstration Modes ──────────────────────────────────────────────
    "LIVE_TEST_SINGLE": {
        "name": "Live Single Robot Continuous Demo",
        "grid_fn": _make_open_grid,
        "num_robots": 1,
        "robot_starts": [(6, 9)],
        "tasks": [
            ("T01", (6, 5), (18, 14)),
        ],
        "timeout_steps": 200,
    },
    "LIVE_TEST_TWO": {
        "name": "Live Two Robot Yielding Demo",
        "grid_fn": _make_open_grid,
        "num_robots": 2,
        "robot_starts": [(6, 9), (18, 9)],
        "tasks": [
            ("T01", (6, 5), (18, 14)),
            ("T02", (18, 14), (6, 5)),
        ],
        "timeout_steps": 200,
    },
    "LIVE_DEMO": {
        "name": "Live Fleet 6-Robot Continuous Demo",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(4, 5), (4, 14), (10, 5), (10, 14), (16, 5), (16, 14)],
        "tasks": [
            ("T01", (6, 5), (18, 14)),
            ("T02", (18, 14), (6, 5)),
            ("T03", (6, 14), (18, 5)),
            ("T04", (18, 5), (6, 14)),
            ("T05", (10, 5), (15, 14)),
            ("T06", (15, 14), (10, 5)),
        ],
        "timeout_steps": 300,
    },

    # ── Official SIH Presentation Scenarios (Section 28) ──────────────────────
    "SCENARIO_A": {
        "name": "Scenario A — Normal Operation (6 AMRs)",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (2, 10), (2, 17), (10, 10), (5, 5), (5, 14)],
        "tasks": [
            ("T01", (5, 2), (20, 17)),
            ("T02", (5, 10), (20, 5)),
            ("T03", (5, 17), (20, 10)),
            ("T04", (10, 5), (15, 15)),
            ("T05", (15, 2), (5, 17)),
            ("T06", (15, 17), (5, 2)),
        ],
        "timeout_steps": 200,
    },
    "SCENARIO_B": {
        "name": "Scenario B — Congestion at Choke Points",
        "grid_fn": _make_choke_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (2, 7), (2, 12), (2, 17), (5, 5), (5, 14)],
        "tasks": [
            ("T01", (3, 3), (20, 16)),
            ("T02", (3, 8), (20, 3)),
            ("T03", (3, 13), (20, 8)),
            ("T04", (3, 16), (20, 13)),
            ("T05", (6, 5), (21, 5)),
            ("T06", (6, 14), (21, 14)),
        ],
        "timeout_steps": 350,
    },
    "SCENARIO_C": {
        "name": "Scenario C — Blockage Recovery & Space-Time A* Detour",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (2, 10), (2, 17), (10, 10), (5, 5), (5, 14)],
        "tasks": [
            ("T01", (5, 2), (20, 17)),
            ("T02", (5, 10), (20, 5)),
            ("T03", (5, 17), (20, 10)),
            ("T04", (10, 5), (15, 15)),
            ("T05", (15, 2), (5, 17)),
            ("T06", (15, 17), (5, 2)),
        ],
        "blockage_step": 10,
        "blockage_cells": [(12, 10), (12, 11)],
        "timeout_steps": 250,
    },
    "SCENARIO_D": {
        "name": "Scenario D — Multi-Robot Contention & PIBT Yielding",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(4, 5), (4, 14), (10, 5), (10, 14), (16, 5), (16, 14)],
        "tasks": [
            ("T01", (6, 5), (18, 14)),
            ("T02", (18, 14), (6, 5)),
            ("T03", (6, 14), (18, 5)),
            ("T04", (18, 5), (6, 14)),
            ("T05", (10, 5), (15, 14)),
            ("T06", (15, 14), (10, 5)),
        ],
        "timeout_steps": 300,
    },
    "SCENARIO_E": {
        "name": "Scenario E — Deadlock Stress & Wait-For Graph Recovery",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (22, 17), (2, 17), (22, 2), (12, 2), (12, 17)],
        "tasks": [
            ("T01", (2, 2), (22, 17)),
            ("T02", (22, 17), (2, 2)),
            ("T03", (2, 17), (22, 2)),
            ("T04", (22, 2), (2, 17)),
            ("T05", (12, 2), (12, 17)),
            ("T06", (12, 17), (12, 2)),
        ],
        "timeout_steps": 400,
    },
    "SCENARIO_F": {
        "name": "Scenario F — AMR Failure & Dynamic Task Reassignment",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (2, 10), (2, 17), (10, 10), (5, 5), (5, 14)],
        "tasks": [
            ("T01", (5, 2), (20, 17)),
            ("T02", (5, 10), (20, 5)),
            ("T03", (5, 17), (20, 10)),
            ("T04", (10, 5), (15, 15)),
            ("T05", (15, 2), (5, 17)),
            ("T06", (15, 17), (5, 2)),
        ],
        "failure_step": 12,
        "failure_robot": "R04",
        "timeout_steps": 300,
    },

    # ── Legacy Numerical Aliases (Frozen test backward compatibility) ─────────
    "S1": {
        "name": "Open Warehouse — Basic Navigation",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (2, 10), (2, 17), (10, 10), (5, 5), (5, 14)],
        "tasks": [
            ("T01", (5, 2), (20, 17)),
            ("T02", (5, 10), (20, 5)),
            ("T03", (5, 17), (20, 10)),
            ("T04", (10, 5), (15, 15)),
            ("T05", (15, 2), (5, 17)),
            ("T06", (15, 17), (5, 2)),
        ],
        "timeout_steps": 200,
    },
    "S4": {
        "name": "Choke-Point Avoidance",
        "grid_fn": _make_choke_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (2, 7), (2, 12), (2, 17), (5, 5), (5, 14)],
        "tasks": [
            ("T01", (3, 3), (20, 16)),
            ("T02", (3, 8), (20, 3)),
            ("T03", (3, 13), (20, 8)),
            ("T04", (3, 16), (20, 13)),
            ("T05", (6, 5), (21, 5)),
            ("T06", (6, 14), (21, 14)),
        ],
        "timeout_steps": 350,
    },
    "S5": {
        "name": "Deadlock Recovery",
        "grid_fn": _make_open_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (22, 17), (2, 17), (22, 2), (12, 2), (12, 17)],
        "tasks": [
            ("T01", (2, 2), (22, 17)),   # Opposing pairs → potential deadlock
            ("T02", (22, 17), (2, 2)),
            ("T03", (2, 17), (22, 2)),
            ("T04", (22, 2), (2, 17)),
            ("T05", (12, 2), (12, 17)),
            ("T06", (12, 17), (12, 2)),
        ],
        "timeout_steps": 400,
    },
    "S8": {
        "name": "Haven Retreat Under Congestion",
        "grid_fn": _make_choke_grid,
        "num_robots": 6,
        "robot_starts": [(2, 2), (2, 5), (2, 8), (2, 11), (2, 14), (2, 17)],
        "tasks": [
            ("T01", (3, 2), (22, 17)),
            ("T02", (3, 5), (22, 14)),
            ("T03", (3, 8), (22, 11)),
            ("T04", (3, 11), (22, 8)),
            ("T05", (3, 14), (22, 5)),
            ("T06", (3, 17), (22, 2)),
        ],
        "timeout_steps": 450,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic odom publisher (SIL physics model)
# ──────────────────────────────────────────────────────────────────────────────

def _make_odom(
    grid_pos: Tuple[int, int],
    yaw: float,
    linear_vel: float = 0.0,
    map_height: int = MAP_HEIGHT,
) -> Odometry:
    """Build a synthetic Odometry message for a robot at the given grid position."""
    wx, wy, wz = grid_to_world(grid_pos[0], grid_pos[1], map_height)
    q_z = math.sin(yaw / 2.0)
    q_w = math.cos(yaw / 2.0)

    msg = Odometry()
    msg.header.frame_id = "world"
    msg.pose.pose.position.x = wx
    msg.pose.pose.position.y = wy
    msg.pose.pose.position.z = wz
    msg.pose.pose.orientation.x = 0.0
    msg.pose.pose.orientation.y = 0.0
    msg.pose.pose.orientation.z = q_z
    msg.pose.pose.orientation.w = q_w
    msg.twist.twist.linear.x = linear_vel
    return msg


def _make_scan_clear(range_max: float = 5.0, num_rays: int = 36) -> LaserScan:
    """Build a clear (no obstacle) LiDAR scan message."""
    msg = LaserScan()
    msg.range_min = 0.1
    msg.range_max = range_max
    msg.angle_min = -math.pi
    msg.angle_max = math.pi
    msg.angle_increment = 2 * math.pi / num_rays
    msg.ranges = [range_max] * num_rays
    return msg


def _make_scan_with_obstacle(
    obstacle_angle: float,
    obstacle_dist: float,
    range_max: float = 5.0,
    num_rays: int = 36,
) -> LaserScan:
    """Build a LiDAR scan with a single obstacle at the given angle/distance."""
    msg = _make_scan_clear(range_max, num_rays)
    angle_inc = 2 * math.pi / num_rays
    ray_idx = int((obstacle_angle + math.pi) / angle_inc) % num_rays
    msg.ranges[ray_idx] = obstacle_dist
    return msg


# ──────────────────────────────────────────────────────────────────────────────
# Collision detection
# ──────────────────────────────────────────────────────────────────────────────

def _check_collisions(nodes: Dict[str, AMRNode]) -> List[Tuple[str, str]]:
    """Return pairs of robots at the same grid cell (collision)."""
    positions: Dict[Tuple[int, int], str] = {}
    collisions = []
    for robot_id, node in nodes.items():
        pos = node.robot.position
        if pos in positions:
            collisions.append((positions[pos], robot_id))
        else:
            positions[pos] = robot_id
    return collisions


# ──────────────────────────────────────────────────────────────────────────────
# ScenarioRunner
# ──────────────────────────────────────────────────────────────────────────────

class ScenarioRunner:
    """Runs a single scenario in SIL mode and collects metrics."""

    def __init__(self, scenario_name: str, verbose: bool = False):
        if scenario_name not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_name}. Available: {list(SCENARIOS)}")
        self.scenario_name = scenario_name
        self.cfg = SCENARIOS[scenario_name]
        self.verbose = verbose

        self._grid: np.ndarray = self.cfg["grid_fn"]()
        self._tasks: Dict[str, Task] = {}
        self._nodes: Dict[str, AMRNode] = {}
        self._coordinator: Optional[FleetCoordinator] = None

        # Metrics
        self.total_collisions = 0
        self.total_deadlocks = 0
        self.total_tasks = 0
        self.completed_tasks = 0
        self.step_count = 0
        self.elapsed_seconds = 0.0

    def _build_tasks(self) -> Dict[str, Task]:
        tasks = {}
        for task_id, pickup, dropoff in self.cfg["tasks"]:
            t = Task(
                id=task_id,
                pickup=pickup,
                dropoff=dropoff,
                priority=1.0,
                creation_time=0.0,
                state=TaskState.QUEUED,
            )
            tasks[task_id] = t
        return tasks

    def setup(self) -> None:
        """Initialize coordinator, tasks, and AMRNodes."""
        rclpy.init()
        self._tasks = self._build_tasks()
        self.total_tasks = len(self._tasks)

        self._coordinator = FleetCoordinator(
            map_width=MAP_WIDTH,
            map_height=MAP_HEIGHT,
            planner_algorithm="pibt",
            allocator_type="fleet_aware",
        )

        robot_starts = self.cfg["robot_starts"]
        robot_ids = [f"R{i+1:02d}" for i in range(self.cfg["num_robots"])]

        for i, robot_id in enumerate(robot_ids):
            start = robot_starts[i]
            node = AMRNode(
                robot_id=robot_id,
                initial_position=start,
                static_grid=self._grid,
                fleet_coordinator=self._coordinator,
                tasks=self._tasks,
                map_width=MAP_WIDTH,
                map_height=MAP_HEIGHT,
            )
            self._nodes[robot_id] = node

        logger.info(
            "[%s] Setup complete — %d robots, %d tasks, grid %dx%d",
            self.scenario_name,
            len(self._nodes),
            self.total_tasks,
            MAP_WIDTH,
            MAP_HEIGHT,
        )

    def run(self) -> Dict:
        """
        Execute the scenario in SIL mode.

        SIL Physics Model (direct-step):
          Each step calls FleetCoordinator.step_coordinate() directly for all robots,
          then advances robot positions based on the returned RobotAction (discrete
          grid physics). This avoids wall-clock timer dependencies and produces
          deterministic, reproducible results identical to the Python benchmark.

        Step sequence:
          1. Build fleet snapshot (all robot positions + beliefs)
          2. Call coordinator.step_coordinate() → get actions for all robots
          3. Apply discrete physics: advance each robot by 1 cell if action=MOVE
          4. Tick task lifecycle (pickup/dropoff detection)
          5. Check collisions
          6. Check completion; repeat until done or timeout
        """
        from execution.action import ActionType

        timeout_steps = self.cfg["timeout_steps"]
        t_start = time.monotonic()
        collision_log: List[dict] = []
        deadlock_step: Optional[int] = None

        # Pre-build obstacle set for O(1) is_walkable lookups.
        # numpy[x,y] indexing was called 32k-52k times per scenario (top CPU cost).
        # frozenset membership test is 3x faster than numpy element access.
        _obstacle_set = frozenset(
            (x, y)
            for x in range(MAP_WIDTH)
            for y in range(MAP_HEIGHT)
            if self._grid[x, y] in (1, 2)
        )

        def is_walkable(pos: Tuple[int, int]) -> bool:
            x, y = pos
            if not (0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT):
                return False
            return (x, y) not in _obstacle_set

        for step in range(timeout_steps):
            self.step_count = step
            sim_time = float(step) * SIL_STEP_DT

            # ── 1. Task lifecycle (assign queued tasks BEFORE coordinator runs) ─
            self._tick_task_lifecycle(step)

            # ── Dynamic Scenario Events (Blockage / AMR Failure) ──────────────
            if "blockage_step" in self.cfg and step == self.cfg["blockage_step"]:
                for bc in self.cfg.get("blockage_cells", []):
                    logger.info("[%s] [INJECTED_BLOCKAGE] Dynamic blockage introduced at cell %s",
                                self.scenario_name, bc)
                    for node in self._nodes.values():
                        node._blocked_cells.add(bc)

            if "failure_step" in self.cfg and step == self.cfg["failure_step"]:
                fail_id = self.cfg["failure_robot"]
                if fail_id in self._nodes:
                    failed_node = self._nodes[fail_id]
                    failed_node.robot.set_state(RobotState.FAILED, reason="Emulated hardware fault")
                    reclaim_task_id = failed_node.robot.current_task_id
                    if reclaim_task_id and reclaim_task_id in self._tasks:
                        rt = self._tasks[reclaim_task_id]
                        rt.state = TaskState.QUEUED
                        rt.assigned_robot_id = None
                        rt.priority += 2.0
                        failed_node.robot.current_task_id = None
                        failed_node.robot.target_position = None
                        logger.info("[%s] [AMR_FAILURE] %s marked FAILED — task %s requeued for fleet reallocation",
                                    self.scenario_name, fail_id, reclaim_task_id)

            # ── 2. Build combined fleet snapshot for coordinator ───────────────
            fleet_snapshot: Dict[str, Robot] = {
                rid: node.robot for rid, node in self._nodes.items()
            }
            blocked: Set[Tuple[int, int]] = set()
            for node in self._nodes.values():
                blocked |= node._blocked_cells

            # ── 3. Run coordinator ────────────────────────────────────────────
            try:
                actions = self._coordinator.step_coordinate(
                    robots=fleet_snapshot,
                    tasks=self._tasks,
                    is_walkable_fn=is_walkable,
                    blocked_cells=blocked,
                    sim_time=sim_time,
                    step=step,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s] Coordinator error at step %d: %s",
                             self.scenario_name, step, exc)
                continue

            # ── 4. Apply discrete physics ─────────────────────────────────────
            for robot_id, node in self._nodes.items():
                action = actions.get(robot_id)
                if action is None:
                    continue
                robot = node.robot
                if not robot.is_healthy:
                    continue  # Failed robot remains stationary (Invariant 1)

                if action.action_type == ActionType.MOVE:
                    target = action.target_cell
                    # Validate move (only 1 cell, must be walkable and unblocked)
                    dc = abs(target[0] - robot.position[0])
                    dr = abs(target[1] - robot.position[1])
                    if (dc + dr) == 1 and is_walkable(target) and target not in blocked:
                        node._motion_model.step_discrete_motion(robot, target, SIL_STEP_DT)
                        node._world_yaw = heading_to_yaw(robot.previous_position, robot.position)
                        odom = _make_odom(robot.position, node._world_yaw, robot.velocity)
                        node._on_odom(odom)
                elif action.action_type == ActionType.WAIT:
                    robot.increment_wait(reason="Coordination wait")
                elif action.action_type == ActionType.PICK:
                    robot.has_payload = True
                elif action.action_type == ActionType.DROP:
                    robot.has_payload = False
                elif action.action_type == ActionType.ESTOP:
                    robot.set_state(RobotState.FAILED, reason="E-stop")

                node._cmd_vel_latencies.append(0.1)
                node._step_count += 1

            # ── 5. Formal Invariant & Collision Verification ──────────────────
            curr_positions = {rid: node.robot.position for rid, node in self._nodes.items()}
            failed_ids = {rid for rid, node in self._nodes.items() if not node.robot.is_healthy}
            inv_report = SafetyInvariants.verify_action_batch(
                candidate_actions=actions,
                current_positions=curr_positions,
                blocked_cells=blocked,
                failed_robot_ids=failed_ids,
            )
            if not inv_report.is_safe:
                self.total_collisions += 1
                collision_log.append({"step": step, "type": inv_report.violation_type, "details": inv_report.details})
                logger.error("[%s] [INVARIANT_BREACH] at step %d: %s (%s)",
                             self.scenario_name, step, inv_report.violation_type, inv_report.details)

            collisions = _check_collisions(self._nodes)
            if collisions:
                for r1, r2 in collisions:
                    self.total_collisions += 1
                    collision_log.append({"step": step, "robots": [r1, r2]})
                    logger.warning("[%s] COLLISION at step %d: %s vs %s",
                                   self.scenario_name, step, r1, r2)

            # ── 6. Completion check ───────────────────────────────────────────
            self.completed_tasks = sum(
                1 for t in self._tasks.values() if t.state == TaskState.DELIVERED
            )

            if self.verbose and step % 20 == 0:
                positions = {rid: n.robot.position for rid, n in self._nodes.items()}
                logger.info("[%s] Step %d: %d/%d tasks done | pos: %s",
                            self.scenario_name, step,
                            self.completed_tasks, self.total_tasks, positions)

            if self.completed_tasks >= self.total_tasks:
                logger.info("[%s] All %d tasks completed at step %d ✓",
                            self.scenario_name, self.total_tasks, step)
                break

        else:
            remaining = self.total_tasks - self.completed_tasks
            if remaining > 0:
                self.total_deadlocks = remaining
                deadlock_step = timeout_steps
                logger.warning("[%s] TIMEOUT at step %d — %d tasks incomplete",
                               self.scenario_name, timeout_steps, remaining)

        self.elapsed_seconds = time.monotonic() - t_start

        # ── Collect per-robot metrics ─────────────────────────────────────────
        robot_metrics = {rid: node.get_metrics() for rid, node in self._nodes.items()}

        result = {
            "scenario": self.scenario_name,
            "scenario_name": self.cfg["name"],
            "passed": (self.total_collisions == 0 and self.total_deadlocks == 0
                       and self.completed_tasks >= self.total_tasks),
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "total_collisions": self.total_collisions,
            "total_deadlocks": self.total_deadlocks,
            "steps": self.step_count,
            "elapsed_s": round(self.elapsed_seconds, 3),
            "collision_log": collision_log,
            "deadlock_step": deadlock_step,
            "robot_metrics": robot_metrics,
        }
        return result

    def _tick_task_lifecycle(self, step: int) -> None:
        """
        Drive task state transitions based on robot positions.

        Mirrors the task pickup/dropoff logic in simulation.py:
          QUEUED → ASSIGNED (when idle robot assigned by coordinator)
          ASSIGNED → PICKED_UP (when robot reaches pickup cell)
          PICKED_UP → DELIVERED (when robot reaches dropoff cell)

        This method intentionally does NOT modify the coordination stack —
        it only reads robot.position and updates task.state.
        """
        sim_time = float(step) * SIL_STEP_DT

        # ── 1. Assign QUEUED tasks to idle robots ────────────────────────────
        idle_robots = [
            node.robot for node in self._nodes.values()
            if node.robot.is_healthy and node.robot.current_task_id is None
            and node.robot.state in (RobotState.IDLE, RobotState.TASK_ASSIGNED)
        ]
        queued_tasks = [
            t for t in self._tasks.values()
            if t.state == TaskState.QUEUED
        ]
        for robot, task in zip(idle_robots, queued_tasks):
            task.state = TaskState.ASSIGNED
            task.assigned_robot_id = robot.id
            task.assigned_time = sim_time
            robot.current_task_id = task.id
            robot.target_position = task.pickup
            robot.set_state(RobotState.TASK_ASSIGNED, "Task assigned by SIL harness")
            if robot.local_world_model:
                robot.local_world_model.known_task_ids.add(task.id)

        # ── 2. Pickup and delivery detection ────────────────────────────────
        for node in self._nodes.values():
            robot = node.robot
            if not robot.is_healthy or not robot.current_task_id:
                continue
            task = self._tasks.get(robot.current_task_id)
            if task is None:
                continue

            # Arrived at pickup
            if (task.state == TaskState.ASSIGNED
                    and robot.position == task.pickup):
                task.state = TaskState.PICKED_UP
                task.pickup_time = sim_time
                robot.has_payload = True
                robot.target_position = task.dropoff
                robot.set_state(RobotState.DELIVERING, "Arrived at pickup")

            # Arrived at dropoff
            elif (task.state == TaskState.PICKED_UP
                  and robot.position == task.dropoff):
                task.state = TaskState.DELIVERED
                task.completion_time = sim_time
                robot.has_payload = False
                robot.tasks_completed += 1
                node._tasks_completed += 1
                robot.current_task_id = None
                robot.target_position = None
                robot.reset_wait()
                robot.set_state(RobotState.IDLE, "Delivered payload")

    def teardown(self) -> None:
        """Clean up nodes and rclpy."""
        for node in self._nodes.values():
            node.destroy_node()
        rclpy.shutdown()


# ──────────────────────────────────────────────────────────────────────────────
# Report printer
# ──────────────────────────────────────────────────────────────────────────────

def print_report(results: List[Dict]) -> None:
    sep = "=" * 70
    print("\n" + sep)
    print("  SIH26123 -- ROS 2 Adapter SIL Validation Report")
    print(sep)
    all_passed = True
    for r in results:
        status = "[PASS]" if r["passed"] else "[FAIL]"
        if not r["passed"]:
            all_passed = False
        print(f"\n  {status} {r['scenario']} -- {r['scenario_name']}")
        print(f"         Tasks:      {r['completed_tasks']}/{r['total_tasks']} completed")
        print(f"         Collisions: {r['total_collisions']}")
        print(f"         Deadlocks:  {r['total_deadlocks']}")
        print(f"         Steps:      {r['steps']}")
        print(f"         Wall time:  {r['elapsed_s']:.3f} s")

        # Per-robot summary
        for rid, m in r["robot_metrics"].items():
            lat = m["cmd_vel_latency_mean_ms"]
            print(f"           {rid}: tasks={m['tasks_completed']} "
                  f"dist={m['total_distance']:.1f} "
                  f"latency={lat:.3f}ms "
                  f"bat={m['battery']:.1f}%")

    print("\n" + sep)
    overall = "ALL SCENARIOS PASSED" if all_passed else "SOME SCENARIOS FAILED"
    print(f"  {overall}")
    print(sep + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="SIH26123 ROS 2 SIL Fleet Launcher"
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIOS.keys()),
        help="Run a single scenario",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all validation scenarios (S1, S4, S5, S8)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable per-step progress logging",
    )
    parser.add_argument(
        "--json-out",
        help="Write JSON results to this file",
    )
    args = parser.parse_args(argv)

    if not args.scenario and not args.all:
        parser.print_help()
        return 1

    scenarios_to_run = list(SCENARIOS.keys()) if args.all else [args.scenario]
    results = []

    for scenario_name in scenarios_to_run:
        runner = ScenarioRunner(scenario_name, verbose=args.verbose)
        try:
            runner.setup()
            result = runner.run()
            results.append(result)
        finally:
            runner.teardown()

    print_report(results)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(results, f, indent=2)
        logger.info("Results written to %s", args.json_out)

    all_passed = all(r["passed"] for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
