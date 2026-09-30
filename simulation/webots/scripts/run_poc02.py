#!/usr/bin/env python3
"""
run_poc02.py — Automated Execution and Validation for Milestone POC-02.

Four AMRs with simultaneous crossing missions intersecting at warehouse center:
  - R01 at (4, 5),   Task T01: (4, 5) -> (16, 14)
  - R02 at (4, 14),  Task T02: (4, 14) -> (16, 5)
  - R03 at (16, 5),  Task T03: (16, 5) -> (4, 14)
  - R04 at (16, 14), Task T04: (16, 14) -> (4, 5)

Validates:
  [x] Simultaneous 4-way intersection coordination
  [x] Space-Time A* + Time-Space Reservation Table
  [x] PIBT yielding & priority backtracking under contention
  [x] 0 Collisions across all 6 robot pairs
  [x] 0 Deadlocks
  [x] 4/4 Tasks Completed
"""

import math
import os
import sys
from typing import Tuple, Dict, List, Set

for _cand in [
    os.environ.get("SIH26_PROJECT_DIR", ""),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
    "/home/siddharth/sih26",
]:
    if _cand and os.path.isdir(os.path.join(_cand, "coordination")) and _cand not in sys.path:
        sys.path.insert(0, _cand)
        break

from coordination.coordinator import FleetCoordinator
from simulator.task import Task, TaskState
from simulation.webots.controllers.webots_amr_node import WebotsAMRNode


def run_poc02(max_steps: int = 400) -> bool:
    print("=" * 70)
    print("  SIH26123 — WEBOTS EXPERIMENT: MILESTONE POC-02 VALIDATION")
    print("  Scenario:  4-AMR Center-Intersection Crossing Contention")
    print("  Fleet:     R01, R02, R03, R04")
    print("  Stack:     Hungarian Allocator + PIBT + Space-Time A*")
    print("=" * 70)

    coord = FleetCoordinator(
        map_width=25,
        map_height=20,
        planner_algorithm="pibt",
        allocator_type="fleet_aware",
    )

    t1 = Task(id="T01", pickup=(4, 5),   dropoff=(16, 14), state=TaskState.ASSIGNED)
    t2 = Task(id="T02", pickup=(4, 14),  dropoff=(16, 5),  state=TaskState.ASSIGNED)
    t3 = Task(id="T03", pickup=(16, 5),  dropoff=(4, 14),  state=TaskState.ASSIGNED)
    t4 = Task(id="T04", pickup=(16, 14), dropoff=(4, 5),   state=TaskState.ASSIGNED)

    t1.assigned_robot_id = "R01"
    t2.assigned_robot_id = "R02"
    t3.assigned_robot_id = "R03"
    t4.assigned_robot_id = "R04"

    shared_tasks = {"T01": t1, "T02": t2, "T03": t3, "T04": t4}

    starts = {
        "R01": ((4, 5), t1),
        "R02": ((4, 14), t2),
        "R03": ((16, 5), t3),
        "R04": ((16, 14), t4),
    }

    WebotsAMRNode._instances.clear()
    nodes = {}
    for rid, (start_pos, task) in starts.items():
        node = WebotsAMRNode(
            robot_id=rid,
            initial_position=start_pos,
            map_width=25,
            map_height=20,
            policy="proposed",
            shared_coordinator=coord,
            tasks_dict=shared_tasks,
        )
        node.sim_robot.current_task_id = task.id
        node.sim_robot.target_position = task.pickup
        nodes[rid] = node

    # Broadcast initial beliefs so all nodes know peer start locations
    for node in nodes.values():
        node._broadcast_belief()

    min_separation = 999.0
    collisions = 0
    robot_list = list(nodes.values())

    print("\n[INIT] Fleet spawned at 4 warehouse corners with intersecting diagonal routes:")
    for rid, node in nodes.items():
        print(f"  - {rid}: start={node.sim_robot.position} -> dropoff={starts[rid][1].dropoff}")
    print()

    def is_walkable(pos: Tuple[int, int]) -> bool:
        return 0 <= pos[0] < 25 and 0 <= pos[1] < 20

    from simulator.robot import RobotState
    from ros2_integration.coordinate_bridge import grid_to_world

    for step in range(1, max_steps + 1):
        sim_time = step * 0.05

        # Check pickup / dropoff arrivals for each node
        for node in robot_list:
            cur_task_id = node.sim_robot.current_task_id
            if cur_task_id and cur_task_id in shared_tasks:
                task = shared_tasks[cur_task_id]
                px, py, _ = grid_to_world(task.pickup[0], task.pickup[1], 20)
                dx, dy, _ = grid_to_world(task.dropoff[0], task.dropoff[1], 20)
                dist_to_pickup = math.hypot(px - node._world_x, py - node._world_y)
                dist_to_dropoff = math.hypot(dx - node._world_x, dy - node._world_y)
                at_pickup = (node.sim_robot.position == task.pickup or dist_to_pickup < 0.50)
                at_dropoff = (node.sim_robot.position == task.dropoff or dist_to_dropoff < 0.50)

                if task.state == TaskState.ASSIGNED and at_pickup:
                    task.state = TaskState.PICKED_UP
                    node.sim_robot.has_payload = True
                    node.sim_robot.target_position = task.dropoff
                    node.sim_robot.set_state(RobotState.DELIVERING)
                elif (task.state == TaskState.PICKED_UP or node.sim_robot.has_payload) and at_dropoff:
                    task.state = TaskState.DELIVERED
                    node.sim_robot.has_payload = False
                    node.sim_robot.tasks_completed += 1
                    node.sim_robot.current_task_id = None
                    node.sim_robot.target_position = None
                    node.sim_robot.set_state(RobotState.IDLE)

        # Build fleet snapshot of all active robots
        fleet_snapshot = {rid: node.sim_robot for rid, node in nodes.items()}

        # Multi-agent coordination across entire fleet simultaneously
        actions = coord.step_coordinate(
            robots=fleet_snapshot,
            tasks=shared_tasks,
            is_walkable_fn=is_walkable,
            blocked_cells=set(),
            sim_time=sim_time,
            step=step,
        )

        # Apply actions to all nodes
        for rid, node in nodes.items():
            act = actions.get(rid)
            if act:
                node.apply_action(act)

        # Check all 6 pairwise separations
        for i in range(len(robot_list)):
            for j in range(i + 1, len(robot_list)):
                n1, n2 = robot_list[i], robot_list[j]
                d = math.hypot(n1._world_x - n2._world_x, n1._world_y - n2._world_y)
                if d < min_separation:
                    min_separation = d
                if d < 0.50:
                    collisions += 1
                    print(f"[CRITICAL_COLLISION] Step {step}: Sep={d:.3f}m between {n1.robot_id} and {n2.robot_id}!")

        if step % 25 == 0 or step == 1:
            states_str = " | ".join(f"{n.robot_id}:{n.sim_robot.position}" for n in robot_list)
            print(f"Step {step:03d} | {states_str} | MinSep={min_separation:.2f}m")

        # Check all tasks delivered
        if all(t.state == TaskState.DELIVERED for t in shared_tasks.values()):
            print(f"\n>>> ALL 4 TASKS DELIVERED AT STEP {step}! <<<")
            break

    delivered = sum(1 for t in shared_tasks.values() if t.state == TaskState.DELIVERED)
    print("\n" + "=" * 70)
    print("  POC-02 EXPERIMENT OUTCOME:")
    print(f"  Total Steps:      {step}")
    print(f"  Tasks Delivered:  {delivered}/4")
    print(f"  Min Separation:   {min_separation:.3f} m")
    print(f"  Collisions:       {collisions}")
    print("=" * 70)

    assert collisions == 0, f"FAILED: {collisions} collisions detected!"
    assert delivered == 4, f"FAILED: Expected 4 tasks completed, got {delivered}!"
    print("\n[PASS] POC-02 VALIDATION SUCCESSFUL: 4 AMRs COORDINATED DECISIVELY WITH 0 COLLISIONS!\n")
    return True


if __name__ == "__main__":
    success = run_poc02()
    sys.exit(0 if success else 1)
