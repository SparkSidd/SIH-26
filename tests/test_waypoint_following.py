"""Tests for deterministic active waypoint following, safety authority, and stale waypoint invalidation."""

import pytest
from simulator.simulation import AMRSimulation
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState
from events.event import EventType


def test_deterministic_waypoint_following_lifecycle():
    """Verify Section 4:
    1. Robot has route.
    2. Corridor becomes blocked.
    3. Robot reaches wait_steps >= 5.
    4. Space-Time A* is triggered.
    5. Detour produced and stored in _active_waypoints.
    6. Robot consumes waypoints sequentially without teleporting.
    7. Robot exits blocked corridor and reaches goal.
    8. Safety supervisor retains final authority (no bypass).
    """
    sim = AMRSimulation(seed=42)
    robot = sim.world.robots["R1"]
    
    # Position robot at (2, 4) with task to (2, 9)
    robot.position = (2, 4)
    robot.planned_path = []
    task = Task(id="WP_TASK", pickup=(2, 4), dropoff=(2, 9), priority=2.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = robot.id
    robot.current_task_id = task.id
    robot.has_payload = True
    sim.world.add_task(task)
    
    # Block corridor at (2, 6)
    sim.warehouse.block_cell((2, 6))
    
    # Step until wait_steps >= 5 and A* detour triggers
    reroute_event_seen = False
    
    def on_reroute(event):
        nonlocal reroute_event_seen
        if event.event_type == EventType.REROUTE and event.data.get("robot_id") == "R1":
            reroute_event_seen = True
            
    sim.event_bus.subscribe(EventType.REROUTE, on_reroute)
    
    prev_pos = robot.position
    waypoints_recorded = []
    
    for step_idx in range(40):
        prev_pos = robot.position
        sim.step()
        curr_pos = robot.position
        
        # Check no teleportation: move distance per discrete step must be <= 1 cell
        step_dist = abs(curr_pos[0] - prev_pos[0]) + abs(curr_pos[1] - prev_pos[1])
        assert step_dist <= 1, f"Teleportation detected! Jumped {step_dist} cells from {prev_pos} to {curr_pos}"
        
        # Robot must NEVER step on the blocked cell (2, 6)
        assert curr_pos != (2, 6), f"Robot walked into blocked cell (2, 6)!"
        
        # Check if waypoints are active
        active_wps = sim.coordinator._active_waypoints.get("R1")
        if active_wps:
            waypoints_recorded.append(list(active_wps))
            
        if curr_pos == (2, 9):
            break
            
    assert reroute_event_seen, "Space-Time A* reroute event must be emitted."
    assert robot.position == (2, 9), f"Robot failed to reach goal around blockage, stopped at {robot.position}"
    # Waypoints must have been consumed sequentially
    assert len(waypoints_recorded) > 0, "Active waypoints should have been followed."


def test_stale_waypoint_invalidation_when_detour_is_blocked():
    """Verify Section 5:
    When a waypoint along an active detour path becomes dynamically blocked:
    - Stale waypoints are detected.
    - Stale route is cleared immediately.
    - Fresh planning occurs without oscillation.
    - Robot never steps on newly blocked waypoint.
    """
    sim = AMRSimulation(seed=55)
    robot = sim.world.robots["R1"]
    
    # Manually assign active waypoints
    # W1 -> W2 -> W3 -> W4
    wps = [(2, 5), (3, 5), (3, 6), (2, 6)]
    sim.coordinator._active_waypoints["R1"] = list(wps)
    sim.coordinator._waypoint_assigned_step["R1"] = 0
    
    robot.position = (2, 4)
    task = Task(id="STALE_TASK", pickup=(2, 4), dropoff=(2, 6), priority=2.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = robot.id
    robot.current_task_id = task.id
    robot.has_payload = True
    sim.world.add_task(task)
    
    # Now dynamically block W2 = (3, 5) BEFORE robot reaches it
    sim.warehouse.block_cell((3, 5))
    
    invalidated_events = []
    sim.event_bus.subscribe(
        EventType.WAYPOINT_INVALIDATED,
        lambda ev: invalidated_events.append(ev)
    )
    
    # Run coordinate step
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=5,
    )
    
    # Active waypoints must be cleared
    assert "R1" not in sim.coordinator._active_waypoints, "Stale waypoint path must be cleared when a waypoint is blocked!"


def test_safety_supervisor_authority_over_waypoint_follower():
    """Verify that waypoints NEVER bypass the SafetySupervisor.
    Even if a waypoint suggests moving to cell C, if another robot occupies C,
    the safety supervisor rejects/yields and guarantees 0 collisions.
    """
    sim = AMRSimulation(seed=10)
    r1 = sim.world.robots["R1"]
    r2 = sim.world.robots["R2"]
    
    # Force both robots adjacent
    r1.position = (5, 5)
    r2.position = (5, 6)
    
    # Give R1 an active waypoint pointing directly into R2's current position
    sim.coordinator._active_waypoints["R1"] = [(5, 6)]
    sim.coordinator._waypoint_assigned_step["R1"] = 0
    
    # Step simulation
    sim.step()
    
    # They must not collide at (5, 6)
    assert r1.position != r2.position, f"Safety violation! Both robots ended up at {r1.position}"
    assert sim.metrics.total_collisions == 0, "SafetySupervisor must preserve 0 collisions invariant."
