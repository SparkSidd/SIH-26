"""Integration tests for immediate 1-step target Wait-For-Graph (WFG) deadlock detection and resolution."""

import pytest
from planning.deadlock import DeadlockDetector, DeadlockReport
from simulator.simulation import AMRSimulation
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState


def test_wfg_two_robot_head_to_head_cycle():
    """Verify 2-robot mutual waiting cycle detection:
    Robot A at X wanting Y, Robot B at Y wanting X.
    Detector must create A -> B and B -> A and report is_deadlocked=True.
    """
    pos_A = (5, 5)
    pos_B = (5, 6)
    
    current_positions = {"R_A": pos_A, "R_B": pos_B}
    # Immediate 1-step movement intentions
    desired_targets = {"R_A": pos_B, "R_B": pos_A}
    robot_wait_steps = {"R_A": 4, "R_B": 4}
    
    report = DeadlockDetector.detect_deadlocks(
        current_positions=current_positions,
        desired_targets=desired_targets,
        wait_threshold=3,
        robot_wait_steps=robot_wait_steps,
    )
    
    assert report.is_deadlocked, "Head-to-head cycle must be detected!"
    assert len(report.cycles) >= 1, "At least one cycle should be reported."
    
    # Flatten cycle
    cycle_nodes = set(report.cycles[0])
    assert cycle_nodes == {"R_A", "R_B"}, f"Cycle should contain R_A and R_B, got {cycle_nodes}"


def test_wfg_three_robot_ring_cycle():
    """Verify 3-robot cycle detection:
    A -> B -> C -> A.
    """
    pos_A = (2, 2)
    pos_B = (2, 3)
    pos_C = (3, 3)
    
    current_positions = {"R_A": pos_A, "R_B": pos_B, "R_C": pos_C}
    desired_targets = {"R_A": pos_B, "R_B": pos_C, "R_C": pos_A}
    robot_wait_steps = {"R_A": 5, "R_B": 5, "R_C": 5}
    
    report = DeadlockDetector.detect_deadlocks(
        current_positions=current_positions,
        desired_targets=desired_targets,
        wait_threshold=3,
        robot_wait_steps=robot_wait_steps,
    )
    
    assert report.is_deadlocked, "3-robot ring cycle must be detected!"
    assert len(report.cycles) >= 1
    cycle_nodes = set(report.cycles[0])
    assert cycle_nodes == {"R_A", "R_B", "R_C"}, f"Cycle should contain R_A, R_B, R_C, got {cycle_nodes}"


def test_coordinator_deadlock_resolution_policy():
    """Verify that coordinator applies deadlock resolution (priority boost / replan)
    and breaks the deadlock so robots make progress rather than persisting forever.
    """
    sim = AMRSimulation(seed=77)
    
    # Setup two robots facing each other in a corridor cell
    r1 = sim.world.robots["R1"]
    r2 = sim.world.robots["R2"]
    
    r1.position = (2, 5)
    r2.position = (2, 6)
    r1.planned_path = []
    r2.planned_path = []
    r1.wait_steps = 6
    r2.wait_steps = 6
    
    # R1 desires to move down corridor to (2, 10); R2 desires to move up corridor to (2, 2)
    t1 = Task(id="DL_T1", pickup=(2, 5), dropoff=(2, 10), priority=1.0)
    t1.state = TaskState.PICKED_UP
    t1.assigned_robot_id = r1.id
    r1.current_task_id = t1.id
    r1.has_payload = True
    sim.world.add_task(t1)
    
    t2 = Task(id="DL_T2", pickup=(2, 6), dropoff=(2, 2), priority=1.0)
    t2.state = TaskState.PICKED_UP
    t2.assigned_robot_id = r2.id
    r2.current_task_id = t2.id
    r2.has_payload = True
    sim.world.add_task(t2)
    
    initial_p1 = r1.dynamic_priority
    initial_p2 = r2.dynamic_priority
    
    # Coordinate step
    actions = sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=20,
    )
    
    # One of the robots in cycle should receive priority boost to break deadlock
    assert (r1.priority_boost > 0 or r2.priority_boost > 0 or 
            r1.dynamic_priority > initial_p1 or r2.dynamic_priority > initial_p2), (
        "Deadlock resolution policy must boost priority on cycle breaker!"
    )
    
    # Now simulate 30 steps to verify deadlock is resolved and robots make progress
    r1_start = r1.position
    r2_start = r2.position
    for _ in range(30):
        sim.step()
        
    # At least one robot must have moved from starting position
    moved = (r1.position != r1_start) or (r2.position != r2_start)
    assert moved, "Deadlock must not persist forever — at least one robot must make progress!"
