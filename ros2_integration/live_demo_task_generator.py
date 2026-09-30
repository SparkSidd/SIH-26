"""
live_demo_task_generator.py — Continuous Task Injection Adapter for Gazebo Live Demo.

Feeds a deterministic, continuous stream of warehouse tasks into the shared
task registry used by AMRNode / FleetCoordinator.

This is ONLY used for the live Gazebo demo scenarios (LIVE_TEST_SINGLE,
LIVE_TEST_TWO, LIVE_DEMO). The frozen benchmark scenarios use their own
static task list.

Architecture:
  TaskGenerator -> shared _tasks dict <- AMRNode(_coordination_step)
                                       ^
                                FleetCoordinator.step_coordinate()
                                (allocator assigns QUEUED -> ASSIGNED)

DO NOT modify FleetCoordinator, allocator, or task lifecycle semantics here.
"""

from __future__ import annotations

import json
import os
import random
import time
import logging
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# -- ROS2 / SIL import routing -----------------------------------------------
_FORCE_MOCK = os.environ.get("USE_MOCK_ROS", "").lower() in ("1", "true")
if not _FORCE_MOCK:
    try:
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import String
        _ROS2_REAL = True
    except ImportError:
        _FORCE_MOCK = True

if _FORCE_MOCK:
    from ros2_integration.mock_ros import rclpy_stub as rclpy
    from ros2_integration.mock_ros.rclpy_stub import Node
    from ros2_integration.mock_ros.std_msgs import String
    _ROS2_REAL = False

# -- Project imports ----------------------------------------------------------
import sys
for _cand in [
    os.environ.get("SIH26_PROJECT_DIR", ""),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
]:
    if _cand and os.path.isdir(os.path.join(_cand, "coordination")) and _cand not in sys.path:
        sys.path.insert(0, _cand)
        break

from simulator.task import Task, TaskState


# -- Live Demo Scenario Definitions -------------------------------------------

# LIVE_TEST_SINGLE -- 1 robot, open floor, repeating mission loop
LIVE_TEST_SINGLE_TASKS = [
    ((5, 5),   (16, 14)),
    ((16, 14), (5, 5)),
    ((5, 14),  (16, 5)),
    ((16, 5),  (5, 14)),
    ((10, 5),  (15, 14)),
]

# LIVE_TEST_TWO -- 2 robots, opposing routes to test head-on yielding
LIVE_TEST_TWO_TASKS = [
    ((5, 10),  (16, 10)),
    ((16, 10), (5, 10)),
    ((3, 3),   (20, 16)),
    ((20, 16), (3, 3)),
    ((3, 16),  (20, 3)),
    ((20, 3),  (3, 16)),
]

# LIVE_DEMO -- 6 robots, continuous high-density task stream (all open-aisle coordinates)
LIVE_DEMO_TASKS = [
    ((3, 2),   (21, 17)),
    ((3, 5),   (21, 14)),
    ((3, 8),   (21, 11)),
    ((3, 11),  (21, 8)),
    ((3, 14),  (21, 5)),
    ((3, 17),  (21, 2)),
    ((5, 3),   (17, 16)),
    ((5, 16),  (17, 3)),
    ((8, 5),   (16, 14)),
    ((8, 14),  (16, 5)),
    ((5, 10),  (19, 10)),
    ((10, 3),  (14, 17)),
    ((10, 17), (14, 3)),
    ((10, 6),  (8, 13)),
    ((10, 13), (8, 6)),
    ((15, 2),  (5, 17)),
]

SCENARIO_TASK_POOLS = {
    "LIVE_TEST_SINGLE": LIVE_TEST_SINGLE_TASKS,
    "LIVE_TEST_TWO":    LIVE_TEST_TWO_TASKS,
    "LIVE_DEMO":        LIVE_DEMO_TASKS,
}

# Robot start positions per live scenario (grid coords)
SCENARIO_ROBOT_STARTS = {
    "LIVE_TEST_SINGLE": [(2, 10)],
    "LIVE_TEST_TWO":    [(2, 10), (20, 10)],
    "LIVE_DEMO":        [(2, 2), (2, 10), (2, 17), (10, 10), (5, 5), (5, 14)],
}

# Pre-assigned initial tasks (ASSIGNED state so coordinator sees them immediately)
SCENARIO_INITIAL_ASSIGNMENTS = {
    "LIVE_TEST_SINGLE": [
        ("T01", (5, 10), (20, 10)),
    ],
    "LIVE_TEST_TWO": [
        ("T01", (5, 10),  (20, 10)),
        ("T02", (20, 10), (5, 10)),
    ],
    "LIVE_DEMO": [
        ("T01", (5,  2),  (20, 17)),
        ("T02", (5, 10),  (20,  5)),
        ("T03", (5, 17),  (20, 10)),
        ("T04", (10,  5), (15, 15)),
        ("T05", (15,  2), ( 5, 17)),
        ("T06", (15, 17), ( 5,  2)),
    ],
}


def make_initial_tasks(scenario: str, robot_ids: List[str]) -> Dict[str, Task]:
    """
    Create the initial task dict for a live demo scenario.
    Tasks start as ASSIGNED so each robot has an immediate mission.
    Returns a shared task dict that AMRNodes will reference.
    """
    sc = scenario.upper()
    initial_defs = SCENARIO_INITIAL_ASSIGNMENTS.get(sc, SCENARIO_INITIAL_ASSIGNMENTS["LIVE_DEMO"])
    tasks: Dict[str, Task] = {}
    t_now = time.monotonic()

    for i, (tid, pickup, dropoff) in enumerate(initial_defs):
        t = Task(id=tid, pickup=pickup, dropoff=dropoff, state=TaskState.ASSIGNED)
        t.creation_time = t_now
        t.assigned_time = t_now
        if i < len(robot_ids):
            t.assigned_robot_id = robot_ids[i]
        tasks[tid] = t
        logger.info(
            "[TaskGen] Initial task %s pickup=%s dropoff=%s -> %s",
            tid, pickup, dropoff, robot_ids[i] if i < len(robot_ids) else "unassigned"
        )

    return tasks


class LiveDemoTaskGenerator(Node):
    """
    ROS 2 node that continuously injects new QUEUED tasks into the shared task
    registry. AMRNode's FleetCoordinator allocator assigns QUEUED -> ASSIGNED.

    Backpressure: stops injecting when max_queued_tasks already QUEUED.
    Telemetry: logs fleet status at 0.2 Hz (every 5 seconds).
    """

    TASK_EVENT_TOPIC = "/fleet/task_events"

    def __init__(
        self,
        scenario: str,
        tasks: Dict[str, Task],
        seed: int = 42,
        inject_interval_s: float = 8.0,
        max_queued_tasks: int = 4,
    ):
        super().__init__("live_demo_task_generator")
        self._scenario = scenario.upper()
        self._tasks = tasks
        self._seed = seed
        self._interval = inject_interval_s
        self._max_queued = max_queued_tasks
        self._rng = random.Random(seed)
        self._task_pool = SCENARIO_TASK_POOLS.get(self._scenario, LIVE_DEMO_TASKS)
        self._pool_idx = 0
        self._seq = len(tasks)
        self._lock = threading.Lock()
        self._start_time = time.monotonic()

        self._pub_events = self.create_publisher(String, self.TASK_EVENT_TOPIC, 20)
        self._inject_timer = self.create_timer(inject_interval_s, self._inject_task)
        self._telemetry_timer = self.create_timer(5.0, self._log_telemetry_summary)

        self.get_logger().info(
            f"[TaskGen] STARTED scenario={self._scenario} "
            f"interval={inject_interval_s:.1f}s seed={seed} "
            f"initial_tasks={len(tasks)}"
        )

    def _count_queued(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.state == TaskState.QUEUED)

    def _inject_task(self) -> None:
        """Create and inject one new QUEUED task into the shared registry."""
        queued = self._count_queued()
        if queued >= self._max_queued:
            self.get_logger().debug(
                f"[TaskGen] Backpressure — {queued} tasks queued, skipping"
            )
            return

        pickup, dropoff = self._task_pool[self._pool_idx % len(self._task_pool)]
        self._pool_idx += 1
        self._seq += 1

        tid = f"T_GEN_{self._seq:04d}"
        t_now = time.monotonic()
        elapsed = t_now - self._start_time

        task = Task(id=tid, pickup=pickup, dropoff=dropoff, state=TaskState.QUEUED)
        task.creation_time = t_now

        with self._lock:
            self._tasks[tid] = task

        msg = String()
        msg.data = json.dumps({
            "event": "TASK_CREATED",
            "task_id": tid,
            "pickup": list(pickup),
            "dropoff": list(dropoff),
            "timestamp": t_now,
            "elapsed_s": round(elapsed, 1),
        })
        self._pub_events.publish(msg)

        self.get_logger().info(
            f"[{elapsed:07.2f}] TASK_CREATED {tid} pickup={pickup} dropoff={dropoff}"
        )

    def _log_telemetry_summary(self) -> None:
        """Publish human-readable fleet telemetry at 0.2 Hz."""
        elapsed = time.monotonic() - self._start_time
        with self._lock:
            states: Dict[str, int] = {}
            for t in self._tasks.values():
                s = t.state.name
                states[s] = states.get(s, 0) + 1

        delivered  = states.get("DELIVERED", 0)
        in_flight  = states.get("PICKED_UP", 0)
        assigned   = states.get("ASSIGNED", 0)
        queued     = states.get("QUEUED", 0)
        total      = len(self._tasks)

        self.get_logger().info(
            f"[{elapsed:07.2f}] FLEET_STATUS "
            f"total={total} delivered={delivered} "
            f"in_flight={in_flight} assigned={assigned} queued={queued}"
        )


def main(args=None):
    """Entry point for standalone task generator node."""
    if not _ROS2_REAL:
        print("[ERROR] Real rclpy required for standalone task generator.")
        return

    rclpy.init(args=args)
    from rcl_interfaces.msg import ParameterDescriptor
    dyn = ParameterDescriptor(dynamic_typing=True)

    temp = Node("task_gen_init")
    temp.declare_parameter("scenario", "LIVE_DEMO", dyn)
    temp.declare_parameter("seed", 42, dyn)
    temp.declare_parameter("interval", 8.0, dyn)
    temp.declare_parameter("max_queued", 4, dyn)
    scenario = str(temp.get_parameter("scenario").value)
    seed     = int(temp.get_parameter("seed").value)
    interval = float(temp.get_parameter("interval").value)
    max_q    = int(temp.get_parameter("max_queued").value)
    temp.destroy_node()

    tasks: Dict[str, Task] = {}
    node = LiveDemoTaskGenerator(
        scenario=scenario, tasks=tasks,
        seed=seed, inject_interval_s=interval, max_queued_tasks=max_q,
    )
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
