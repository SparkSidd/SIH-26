"""
tests/test_ros2_adapter.py — Integration tests for the ROS 2 adapter layer.

Tests run entirely in SIL mode (no WSL2 / Gazebo required).

Coverage:
  - AMRNode lifecycle (init, step, destroy)
  - cmd_vel dispatch correctness
  - Odom feedback → grid cell tracking
  - Belief broadcast and receive (P2P)
  - Single-robot S1 task completion
  - Fleet S4 (choke-point, 6 robots) — 0 collisions
  - Fleet S5 (deadlock recovery, 6 robots)
  - Fleet S8 (haven retreat, 6 robots)
"""

from __future__ import annotations

import math
import json
import time
import pytest
import numpy as np
from typing import Dict, Tuple

# ── SIL imports ──────────────────────────────────────────────────────────────
from ros2_integration.mock_ros import rclpy_stub as rclpy
from ros2_integration.mock_ros.rclpy_stub import Node
from ros2_integration.mock_ros.nav_msgs import Odometry
from ros2_integration.mock_ros.sensor_msgs import LaserScan
from ros2_integration.mock_ros.std_msgs import String
from ros2_integration.mock_ros.geometry_msgs import Twist

from ros2_integration.amr_node import AMRNode
from ros2_integration.coordinate_bridge import grid_to_world, world_to_grid, heading_to_yaw
from ros2_integration.fleet_launcher import (
    ScenarioRunner,
    _make_open_grid,
    _make_choke_grid,
    _make_odom,
    _make_scan_clear,
    _check_collisions,
    MAP_WIDTH,
    MAP_HEIGHT,
    SCENARIOS,
)
from coordination.coordinator import FleetCoordinator
from simulator.task import Task, TaskState


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def rclpy_lifecycle():
    """Ensure rclpy is initialized and shut down cleanly for each test."""
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def open_grid():
    return _make_open_grid()


@pytest.fixture
def choke_grid():
    return _make_choke_grid()


@pytest.fixture
def simple_tasks():
    return {
        "T01": Task(id="T01", pickup=(5, 5), dropoff=(20, 15), state=TaskState.QUEUED),
    }


@pytest.fixture
def coordinator(open_grid):
    return FleetCoordinator(
        map_width=MAP_WIDTH,
        map_height=MAP_HEIGHT,
        planner_algorithm="pibt",
        allocator_type="fleet_aware",
    )


def make_node(robot_id: str, pos: Tuple[int, int], grid, coordinator, tasks) -> AMRNode:
    return AMRNode(
        robot_id=robot_id,
        initial_position=pos,
        static_grid=grid,
        fleet_coordinator=coordinator,
        tasks=tasks,
        map_width=MAP_WIDTH,
        map_height=MAP_HEIGHT,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1. AMRNode lifecycle
# ──────────────────────────────────────────────────────────────────────────────

class TestAMRNodeLifecycle:
    def test_node_init(self, open_grid, coordinator, simple_tasks):
        """Node initializes with correct robot_id, position, and topics."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        assert node.robot_id == "R01"
        assert node.robot.position == (2, 2)
        assert node.robot.is_healthy is True
        node.destroy_node()

    def test_node_has_publishers(self, open_grid, coordinator, simple_tasks):
        """Node creates cmd_vel and belief publishers."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        # Publishers exist and have not yet published anything
        assert node._pub_cmd_vel is not None
        assert node._pub_belief is not None
        assert node._pub_cmd_vel.publish_count == 0
        node.destroy_node()

    def test_node_has_subscriptions(self, open_grid, coordinator, simple_tasks):
        """Node subscribes to odom, scan, and peer_beliefs."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        assert node._sub_odom is not None
        assert node._sub_scan is not None
        assert node._sub_peer_beliefs is not None
        node.destroy_node()

    def test_node_destroy(self, open_grid, coordinator, simple_tasks):
        """destroy_node() cleans up without error."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        node.destroy_node()  # Must not raise


# ──────────────────────────────────────────────────────────────────────────────
# 2. cmd_vel dispatch correctness
# ──────────────────────────────────────────────────────────────────────────────

class TestCmdVelDispatch:
    def test_cmd_vel_published_after_step(self, open_grid, coordinator, simple_tasks):
        """Coordination step publishes at least one cmd_vel."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        # Inject odom so robot knows its position
        odom = _make_odom((2, 2), 0.0)
        node._on_odom(odom)
        # Manually fire coordination timer once
        node._coordination_step()
        assert node._pub_cmd_vel.publish_count >= 1
        node.destroy_node()

    def test_wait_produces_zero_twist(self, open_grid, coordinator, simple_tasks):
        """When action is WAIT, cmd_vel should be zero."""
        from execution.action import RobotAction, ActionType
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        action = RobotAction(action_type=ActionType.WAIT, target_cell=(2, 2))
        twist = node._action_to_cmd_vel(action)
        assert twist.linear.x == 0.0
        assert twist.angular.z == 0.0
        node.destroy_node()

    def test_move_produces_nonzero_linear(self, open_grid, coordinator, simple_tasks):
        """When action is MOVE and heading is aligned, linear.x should be positive."""
        from execution.action import RobotAction, ActionType
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        # Set robot world yaw to match East (heading to (3, 2))
        node._world_yaw = 0.0  # East
        action = RobotAction(
            action_type=ActionType.MOVE,
            target_cell=(3, 2),
            target_velocity=1.0,
        )
        twist = node._action_to_cmd_vel(action)
        # When heading aligned, linear.x should be > 0
        assert twist.linear.x > 0.0, f"Expected positive linear.x, got {twist.linear.x}"
        node.destroy_node()

    def test_estop_produces_zero_twist(self, open_grid, coordinator, simple_tasks):
        """ESTOP action must result in zero twist."""
        from execution.action import RobotAction, ActionType
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        action = RobotAction(action_type=ActionType.ESTOP, target_cell=(2, 2))
        twist = node._action_to_cmd_vel(action)
        assert twist.linear.x == 0.0
        assert twist.angular.z == 0.0
        node.destroy_node()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Odometry feedback → grid cell tracking
# ──────────────────────────────────────────────────────────────────────────────

class TestOdomFeedback:
    def test_odom_updates_grid_position(self, open_grid, coordinator, simple_tasks):
        """Receiving odom for a different grid cell updates robot.position."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        # Inject odom for cell (3, 2)
        odom = _make_odom((3, 2), 0.0)
        node._on_odom(odom)
        assert node.robot.position == (3, 2), \
            f"Expected (3,2) but got {node.robot.position}"
        node.destroy_node()

    def test_odom_updates_yaw(self, open_grid, coordinator, simple_tasks):
        """Receiving odom updates the stored world_yaw."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        expected_yaw = math.pi / 2  # North
        odom = _make_odom((2, 2), expected_yaw)
        node._on_odom(odom)
        assert abs(node._world_yaw - expected_yaw) < 0.01, \
            f"Expected yaw ≈{expected_yaw:.3f}, got {node._world_yaw:.3f}"
        node.destroy_node()

    def test_odom_out_of_bounds_clamped(self, open_grid, coordinator, simple_tasks):
        """Odom outside grid boundaries is clamped to valid range."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        # World coords far outside grid
        from ros2_integration.mock_ros.nav_msgs import Odometry
        odom = Odometry()
        odom.pose.pose.position.x = 9999.0
        odom.pose.pose.position.y = 9999.0
        odom.pose.pose.orientation.w = 1.0
        node._on_odom(odom)
        col, row = node.robot.position
        assert 0 <= col < MAP_WIDTH
        assert 0 <= row < MAP_HEIGHT
        node.destroy_node()


# ──────────────────────────────────────────────────────────────────────────────
# 4. Coordinate bridge
# ──────────────────────────────────────────────────────────────────────────────

class TestCoordinateBridge:
    def test_grid_to_world_origin(self):
        """Grid cell (0,0) maps to world origin (or near)."""
        x, y, z = grid_to_world(0, 0, MAP_HEIGHT)
        assert x == pytest.approx(0.0)
        assert z == pytest.approx(0.0)

    def test_grid_to_world_roundtrip(self):
        """world_to_grid(grid_to_world(col, row)) == (col, row)."""
        for col, row in [(0, 0), (12, 10), (24, 19), (5, 7)]:
            wx, wy, _ = grid_to_world(col, row, MAP_HEIGHT)
            gc, gr = world_to_grid(wx, wy, MAP_HEIGHT)
            assert (gc, gr) == (col, row), \
                f"Roundtrip failed: ({col},{row}) → ({wx:.2f},{wy:.2f}) → ({gc},{gr})"

    def test_heading_east(self):
        """Moving East (col+1) produces yaw ≈ 0 rad."""
        yaw = heading_to_yaw((5, 5), (6, 5))
        assert abs(yaw) < 0.01, f"East yaw should be ~0, got {yaw:.3f}"

    def test_heading_west(self):
        """Moving West (col-1) produces yaw ≈ ±π rad."""
        yaw = heading_to_yaw((5, 5), (4, 5))
        assert abs(abs(yaw) - math.pi) < 0.01, f"West yaw should be ~π, got {yaw:.3f}"


# ──────────────────────────────────────────────────────────────────────────────
# 5. P2P belief sync
# ──────────────────────────────────────────────────────────────────────────────

class TestBeliefSync:
    def test_own_belief_not_applied(self, open_grid, coordinator, simple_tasks):
        """Robot ignores its own belief broadcast (no self-update)."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        payload = json.dumps({
            "robot_id": "R01",  # same as self
            "position": [5, 5],  # different position
            "velocity": 0.0,
            "heading": 0.0,
            "intended_action": "WAIT",
            "planned_path": [],
            "current_task_id": None,
            "priority": 1.0,
            "timestamp": time.monotonic(),
            "seq": 0,
        })
        msg = String()
        msg.data = payload
        node._on_peer_belief(msg)
        # Position should NOT have changed
        assert node.robot.position == (2, 2)
        node.destroy_node()

    def test_peer_belief_updates_local_world(self, open_grid, coordinator, simple_tasks):
        """Belief from peer robot updates local world model."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        payload = json.dumps({
            "robot_id": "R02",
            "position": [10, 5],
            "velocity": 1.5,
            "heading": 0.0,
            "intended_action": "MOVE",
            "planned_path": [[11, 5], [12, 5]],
            "current_task_id": "T01",
            "priority": 1.2,
            "timestamp": time.monotonic(),
            "seq": 3,
        })
        msg = String()
        msg.data = payload
        node._on_peer_belief(msg)
        assert "R02" in node.robot.local_world_model.peer_beliefs
        belief = node.robot.local_world_model.peer_beliefs["R02"]
        assert belief.position == (10, 5)
        node.destroy_node()

    def test_belief_broadcast_publishes(self, open_grid, coordinator, simple_tasks):
        """_broadcast_belief() publishes a valid JSON message."""
        node = make_node("R01", (2, 2), open_grid, coordinator, simple_tasks)
        node._broadcast_belief()
        assert node._pub_belief.publish_count == 1
        node.destroy_node()


# ──────────────────────────────────────────────────────────────────────────────
# 6. Scenario-level SIL tests
# ──────────────────────────────────────────────────────────────────────────────

class TestScenarioS1:
    """S1 — Open warehouse, 4 robots, basic navigation."""

    def test_s1_completes(self):
        """S1 runs without collision and completes all tasks."""
        # Re-init since autouse fixture already called init/shutdown
        # ScenarioRunner handles its own lifecycle
        rclpy.shutdown()  # undo autouse to let runner manage it
        runner = ScenarioRunner("S1", verbose=False)
        try:
            runner.setup()
            result = runner.run()
        finally:
            runner.teardown()
        rclpy.init()  # restore for cleanup

        assert result["total_collisions"] == 0, \
            f"S1 collision: {result['collision_log']}"
        assert result["completed_tasks"] == result["total_tasks"], \
            f"S1 incomplete: {result['completed_tasks']}/{result['total_tasks']}"
        assert result["passed"] is True


class TestScenarioS4:
    """S4 — Choke-point avoidance, 6 robots."""

    def test_s4_no_collision(self):
        """S4 runs with 0 collisions."""
        rclpy.shutdown()
        runner = ScenarioRunner("S4", verbose=False)
        try:
            runner.setup()
            result = runner.run()
        finally:
            runner.teardown()
        rclpy.init()

        assert result["total_collisions"] == 0, \
            f"S4 collision detected: {result['collision_log']}"

    def test_s4_completes(self):
        """S4 completes all tasks within timeout."""
        rclpy.shutdown()
        runner = ScenarioRunner("S4", verbose=False)
        try:
            runner.setup()
            result = runner.run()
        finally:
            runner.teardown()
        rclpy.init()

        assert result["completed_tasks"] == result["total_tasks"], \
            f"S4 incomplete: {result['completed_tasks']}/{result['total_tasks']}"


class TestScenarioS5:
    """S5 — Deadlock recovery, 6 robots with opposing task pairs."""

    def test_s5_no_permanent_deadlock(self):
        """S5 resolves deadlocks — no tasks left incomplete at timeout."""
        rclpy.shutdown()
        runner = ScenarioRunner("S5", verbose=False)
        try:
            runner.setup()
            result = runner.run()
        finally:
            runner.teardown()
        rclpy.init()

        assert result["total_collisions"] == 0, \
            f"S5 collision: {result['collision_log']}"
        assert result["total_deadlocks"] == 0, \
            f"S5 deadlock: {result['total_deadlocks']} tasks stuck"


class TestScenarioS8:
    """S8 — Haven retreat under congestion, choke layout."""

    def test_s8_no_collision(self):
        """S8 runs with 0 collisions even under heavy choke congestion."""
        rclpy.shutdown()
        runner = ScenarioRunner("S8", verbose=False)
        try:
            runner.setup()
            result = runner.run()
        finally:
            runner.teardown()
        rclpy.init()

        assert result["total_collisions"] == 0, \
            f"S8 collision: {result['collision_log']}"


# ──────────────────────────────────────────────────────────────────────────────
# 7. Collision detection utility
# ──────────────────────────────────────────────────────────────────────────────

class TestCollisionDetection:
    def test_no_collision_different_positions(self, open_grid, coordinator):
        tasks = {}
        n1 = make_node("R01", (2, 2), open_grid, coordinator, tasks)
        n2 = make_node("R02", (5, 5), open_grid, coordinator, tasks)
        nodes = {"R01": n1, "R02": n2}
        collisions = _check_collisions(nodes)
        assert len(collisions) == 0
        n1.destroy_node()
        n2.destroy_node()

    def test_collision_same_position(self, open_grid, coordinator):
        tasks = {}
        n1 = make_node("R01", (5, 5), open_grid, coordinator, tasks)
        n2 = make_node("R02", (5, 5), open_grid, coordinator, tasks)
        nodes = {"R01": n1, "R02": n2}
        collisions = _check_collisions(nodes)
        assert len(collisions) == 1
        n1.destroy_node()
        n2.destroy_node()
