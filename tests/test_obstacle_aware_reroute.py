"""Tests for obstacle-aware Space-Time A* rerouting around stationary, opposing, and multiple AMRs."""

import pytest
from planning.astar import SpaceTimeAStarPlanner, PlannerStatusCode
from simulator.simulation import AMRSimulation
from simulator.task import Task, TaskState


def test_reroute_static_obstacle_only():
    """Case 1: Static obstacle only in the corridor."""
    sim = AMRSimulation()
    planner = SpaceTimeAStarPlanner()
    
    start = (2, 4)
    goal = (2, 8)
    blocked = {(2, 6)}
    
    res = planner.plan(
        robot_id="R1",
        start_pos=start,
        goal_pos=goal,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=blocked,
    )
    assert res.is_success, "A* should find path around static obstacle"
    assert (2, 6) not in res.path, "Path must not step on static obstacle"


def test_reroute_stationary_amr_in_corridor():
    """Case 2: Stationary AMR parked directly on the direct corridor path.
    Coordinator's obstacle-aware reroute must treat stationary AMR as obstacle and detour around it.
    """
    sim = AMRSimulation()
    r1 = sim.world.robots["R1"]
    r2 = sim.world.robots["R2"]
    
    r1.position = (2, 4)
    r2.position = (2, 6)  # Stationary AMR in corridor
    r1.wait_steps = 6
    
    task = Task(id="DETOUR_TASK", pickup=(2, 4), dropoff=(2, 8), priority=2.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = r1.id
    r1.current_task_id = task.id
    r1.has_payload = True
    sim.world.add_task(task)
    
    # Run coordinate step
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=10,
    )
    
    # R1 must have received an active waypoint detour that does NOT go through (2, 6)
    wps = sim.coordinator._active_waypoints.get("R1")
    assert wps is not None, "Reroute must produce waypoints around stationary AMR"
    assert (2, 6) not in wps, f"Waypoints must not route through stationary AMR at (2, 6)! Got: {wps}"


def test_reroute_opposing_amr_in_narrow_bottleneck():
    """Case 3: Opposing AMR in bottleneck where (1, 6) is blocked and R2 is at (2, 6)."""
    sim = AMRSimulation()
    r1 = sim.world.robots["R1"]
    r2 = sim.world.robots["R2"]
    
    r1.position = (2, 9)
    r2.position = (2, 6)
    r1.wait_steps = 6
    
    # (1, 6) is also blocked
    sim.warehouse.block_cell((1, 6))
    
    task = Task(id="BOTTLENECK_TASK", pickup=(2, 9), dropoff=(22, 2), priority=2.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = r1.id
    r1.current_task_id = task.id
    r1.has_payload = True
    sim.world.add_task(task)
    
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=15,
    )
    
    wps = sim.coordinator._active_waypoints.get("R1")
    assert wps is not None, "A* must find an alternative detour path"
    assert (2, 6) not in wps, "R1 must not route into oncoming robot at (2, 6)"
    assert (1, 6) not in wps, "R1 must not route into blocked cell at (1, 6)"


def test_reroute_multiple_amrs_in_parallel_aisle():
    """Case 4: Multiple AMRs occupying adjacent cells in corridor."""
    sim = AMRSimulation()
    r1 = sim.world.robots["R1"]
    sim.world.robots["R2"].position = (2, 5)
    sim.world.robots["R3"].position = (2, 6)
    sim.world.robots["R4"].position = (2, 7)
    
    r1.position = (2, 4)
    r1.wait_steps = 6
    
    task = Task(id="MULTI_AMR_TASK", pickup=(2, 4), dropoff=(2, 9), priority=2.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = r1.id
    r1.current_task_id = task.id
    r1.has_payload = True
    sim.world.add_task(task)
    
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=20,
    )
    
    wps = sim.coordinator._active_waypoints.get("R1")
    assert wps is not None
    # None of the occupied cells should be in the waypoints
    assert not any(pos in wps for pos in [(2, 5), (2, 6), (2, 7)]), (
        f"Waypoints must completely route around all 3 occupying AMRs! Got: {wps}"
    )


def test_blockage_and_removal_adaptation():
    """Case 5 & 6: Temporary blockage followed by blockage removal."""
    sim = AMRSimulation()
    planner = SpaceTimeAStarPlanner()
    start = (2, 4)
    goal = (2, 8)
    
    # 5. With blockage at (2, 6)
    res_blocked = planner.plan(
        robot_id="R1",
        start_pos=start,
        goal_pos=goal,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells={(2, 6)},
    )
    assert res_blocked.is_success
    assert (2, 6) not in res_blocked.path
    
    # 6. Blockage cleared
    res_cleared = planner.plan(
        robot_id="R1",
        start_pos=start,
        goal_pos=goal,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=set(),
    )
    assert res_cleared.is_success
    # Straight path through (2, 6) should be restored
    assert (2, 6) in res_cleared.path
    assert res_cleared.cost < res_blocked.cost, "Direct route after clearance should have lower cost than detour"
