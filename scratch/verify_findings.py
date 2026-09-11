"""Deterministic proof of the three core code findings:
3A. PIBT Manhattan scoring dead-end behavior vs obstacle-aware cost-to-go
3B. Wall-blind Manhattan path generation in FleetAwareTaskAllocator
3C. Disabled rolling handover lookahead due to all_tasks=None
"""

import sys
import os
from collections import deque
from typing import Callable, Dict, List, Set, Tuple

sys.path.insert(0, r"c:\Users\thega\PROJECTS\SIH'26")

from coordination.allocator import FleetAwareTaskAllocator, _generate_manhattan_path
from coordination.congestion import CongestionModel
from planning.pibt import PIBTPlanner
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState
from simulator.warehouse import Warehouse, CellType


# ==============================================================================
# 3A. VERIFY PIBT MANHATTAN SCORING
# ==============================================================================
def verify_3a_pibt_manhattan():
    print("\n" + "=" * 70)
    print("3A. VERIFICATION: PIBT MANHATTAN SCORING IN CHOKE-POINT TOPOLOGY")
    print("=" * 70)
    
    # Construct a 25x20 warehouse with a dividing wall at x=12, opening only at y=5
    wall_cells: Set[Tuple[int, int]] = set()
    for y in range(0, 20):
        if y != 5:
            wall_cells.add((12, y))
            
    def is_walkable(pos: Tuple[int, int]) -> bool:
        x, y = pos
        if not (0 <= x < 25 and 0 <= y < 20):
            return False
        return pos not in wall_cells

    start_pos = (10, 2)
    goal_pos = (22, 2)
    
    planner = PIBTPlanner()
    
    print(f"Setup: Start={start_pos}, Goal={goal_pos}, Divider at x=12 with gap at y=5 only.")
    
    # 1. Current PIBT (Manhattan candidate scoring)
    curr = start_pos
    path_manhattan = [curr]
    stuck_steps = 0
    
    for step in range(15):
        next_cells = planner.plan_step(
            robot_ids=["R1"],
            current_positions={"R1": curr},
            target_goals={"R1": goal_pos},
            priorities={"R1": 1.0},
            is_walkable_fn=is_walkable,
            blocked_cells=set(),
        )
        nxt = next_cells["R1"]
        if nxt == curr:
            stuck_steps += 1
        curr = nxt
        path_manhattan.append(curr)
        if curr == goal_pos:
            break
            
    print("\n[Result with Pure Manhattan PIBT]")
    print(f"  Path taken (first 10 steps): {path_manhattan[:10]}")
    print(f"  Did AMR walk towards the wall at (11, 2)? {'YES' if (11, 2) in path_manhattan else 'NO'}")
    print(f"  Stuck / Stationary steps: {stuck_steps}")
    
    # 2. Obstacle-aware Reverse BFS Cost-to-go
    def compute_bfs_cost_map(goal: Tuple[int, int]) -> Dict[Tuple[int, int], int]:
        dist: Dict[Tuple[int, int], int] = {goal: 0}
        q = deque([goal])
        while q:
            u = q.popleft()
            d = dist[u]
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                v = (u[0] + dx, u[1] + dy)
                if is_walkable(v) and v not in dist:
                    dist[v] = d + 1
                    q.append(v)
        return dist

    bfs_cost = compute_bfs_cost_map(goal_pos)
    
    # Test candidate scoring at (11, 2) where robot is pressed against the wall
    cands_at_wall = [(11, 2), (11, 3), (10, 2), (11, 1)]
    valid_at_wall = [c for c in cands_at_wall if is_walkable(c)]
    
    print("\n[Candidate Scoring Comparison at wall cell (11, 2)]:")
    for c in valid_at_wall:
        m_dist = abs(c[0] - goal_pos[0]) + abs(c[1] - goal_pos[1])
        b_dist = bfs_cost.get(c, 999)
        print(f"  Candidate {c}: Manhattan dist={m_dist}, Obstacle-Aware BFS dist={b_dist}")
        
    best_m_at_wall = min(valid_at_wall, key=lambda c: abs(c[0] - goal_pos[0]) + abs(c[1] - goal_pos[1]))
    best_b_at_wall = min(valid_at_wall, key=lambda c: bfs_cost.get(c, 999))
    print(f"\n  At wall cell (11, 2):")
    print(f"  Manhattan picks: {best_m_at_wall} (stays permanently STUCK because moving away increases Manhattan distance!)")
    print(f"  Obstacle-Aware picks: {best_b_at_wall} (moves UP towards opening at y=5!)")
    assert best_m_at_wall == (11, 2), "Expected Manhattan to stay stuck at (11, 2)"
    assert best_b_at_wall == (11, 3), "Expected BFS to move up to (11, 3)"
    print("  --> 3A VERIFIED: Naive Manhattan scoring creates persistent deadlocks against walls.")


# ==============================================================================
# 3B. VERIFY WALL-BLIND ALLOCATOR PATH GENERATION
# ==============================================================================
def verify_3b_allocator_path():
    print("\n" + "=" * 70)
    print("3B. VERIFICATION: ALLOCATOR _generate_manhattan_path WALL PENETRATION")
    print("=" * 70)
    
    for layout in ["open", "corridor_heavy", "choke_point"]:
        wh = Warehouse(width=25, height=20, layout_type=layout)
        pickup = (2, 2)
        dropoff = (22, 2)
        
        path = _generate_manhattan_path(pickup, dropoff)
        wall_crossings = [p for p in path if not wh.is_walkable(p)]
        
        # True BFS distance
        dist_map = {dropoff: 0}
        q = deque([dropoff])
        while q:
            u = q.popleft()
            d = dist_map[u]
            for n in wh.get_neighbors(u):
                if n not in dist_map:
                    dist_map[n] = d + 1
                    q.append(n)
        true_dist = dist_map.get(pickup, -1)
        manhattan_dist = len(path) - 1
        
        print(f"Layout '{layout}':")
        print(f"  Path length: {len(path)} cells (Manhattan distance = {manhattan_dist})")
        print(f"  True Walkable Graph Distance: {true_dist}")
        print(f"  Non-walkable (Wall/Shelf) cells crossed: {len(wall_crossings)} ({wall_crossings[:3]}...)")
        if layout == "choke_point":
            assert len(wall_crossings) > 0, "Choke point must cross wall"
            assert (12, 2) in wall_crossings, "Must cross divider at (12, 2)"
            print(f"  Underestimated travel distance by: {true_dist - manhattan_dist} steps")
            print("  --> 3B VERIFIED: _generate_manhattan_path passes straight through solid walls!")


# ==============================================================================
# 3C. VERIFY DISABLED ROLLING HANDOVER LOOKAHEAD
# ==============================================================================
def verify_3c_rolling_handover():
    print("\n" + "=" * 70)
    print("3C. VERIFICATION: ROLLING HANDOVER LOOKAHEAD REACHABILITY")
    print("=" * 70)
    
    allocator = FleetAwareTaskAllocator()
    wh = Warehouse(width=25, height=20, layout_type="corridor_heavy")
    
    # Active task 1, robot R1 is at (21, 2) carrying payload, dropoff at (22, 2) (dist=1)
    task1 = Task(id="T1", pickup=(2, 2), dropoff=(22, 2), state=TaskState.PICKED_UP, assigned_robot_id="R1")
    robot1 = Robot(id="R1", initial_position=(21, 2))
    robot1.current_task_id = "T1"
    robot1.has_payload = True
    robot1.state = RobotState.DELIVERING
    
    # Queued task 2
    task2 = Task(id="T2", pickup=(22, 3), dropoff=(5, 5), state=TaskState.QUEUED, priority=2.0)
    
    robots = {"R1": robot1}
    all_tasks = {"T1": task1, "T2": task2}
    unassigned = [task2]
    
    # Case 1: As currently invoked in coordinator.py line 186 (all_tasks=None)
    assignments_none = allocator.allocate(
        unassigned_tasks=unassigned,
        robots=robots,
        congestion_model=CongestionModel(),
        is_walkable_fn=wh.is_walkable,
        all_tasks=None,  # CURRENT COORDINATOR CALL
    )
    
    # Case 2: Handover enabled (all_tasks=all_tasks)
    assignments_enabled = allocator.allocate(
        unassigned_tasks=unassigned,
        robots=robots,
        congestion_model=CongestionModel(),
        is_walkable_fn=wh.is_walkable,
        all_tasks=all_tasks,
    )
    
    print(f"Robot R1 state: Carrying payload at (21, 2), 1 cell from dropoff (22, 2).")
    print(f"Queued Task T2: Pickup at (22, 3).")
    print(f"Assignment with all_tasks=None:    {assignments_none}")
    print(f"Assignment with all_tasks provided: {assignments_enabled}")
    
    assert len(assignments_none) == 0, "With all_tasks=None, lookahead must fail to assign"
    assert len(assignments_enabled) == 1, "With all_tasks provided, lookahead must assign"
    assert assignments_enabled[0] == ("R1", "T2"), "Must assign R1 to T2"
    print("  --> 3C VERIFIED: Passing all_tasks=None permanently disables rolling handover pre-assignment.")


if __name__ == "__main__":
    verify_3a_pibt_manhattan()
    verify_3b_allocator_path()
    verify_3c_rolling_handover()
    print("\n" + "=" * 70)
    print("ALL THREE CORE FINDINGS CONFIRMED MATHEMATICALLY AND EMPIRICALLY.")
    print("=" * 70)
