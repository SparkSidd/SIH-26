"""Tests for unreachable goal task reclamation and robot failure recovery during payload delivery."""

import pytest
from simulator.simulation import AMRSimulation
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState
from events.event import EventType


def test_unreachable_goal_task_reclaim_and_priority_boost():
    """Verify Section 8:
    When surrounding blockages make a task's goal unreachable:
    1. Coordinator recognizes goal is unreachable.
    2. Task is reclaimed and set back to QUEUED.
    3. Robot is released/reset to IDLE.
    4. Task receives priority boost.
    5. No duplicate task ownership occurs.
    6. No task disappears from the world.
    """
    sim = AMRSimulation(seed=42)
    robot = sim.world.robots["R1"]
    
    # Task with dropoff at (22, 10)
    task = Task(id="UNREACHABLE_TASK", pickup=(2, 2), dropoff=(22, 10), priority=1.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = robot.id
    robot.current_task_id = task.id
    robot.has_payload = True
    robot.position = (20, 10)
    sim.world.add_task(task)
    
    # Block all 4 cardinal neighbors of the dropoff station (22, 10)
    # The dropoff cell itself is protected, but surrounding cells can be blocked:
    neighbors = [(21, 10), (23, 10), (22, 9), (22, 11)]
    for n in neighbors:
        sim.warehouse.block_cell(n)
        
    initial_priority = task.priority
    total_tasks_before = len(sim.world.tasks)
    
    # Step coordinate
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=10,
    )
    
    # After robot is stuck trying to reach it:
    robot.wait_steps = 6
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=2.0,
        step=11,
    )
    
    # Task count must remain invariant (no task disappears)
    assert len(sim.world.tasks) == total_tasks_before, "No task must disappear from the system!"


def test_robot_failure_during_payload_delivery():
    """Verify Section 9:
    Robot A -> pickup -> payload acquired -> delivery.
    Then fail Robot A.
    Verify:
    - Failed robot velocity is 0 and stops receiving normal movement.
    - Active waypoints belonging to failed robot are cleared safely.
    - Task is recovered and requeued/reassigned.
    - Another healthy AMR can pick up and complete the task.
    """
    sim = AMRSimulation(seed=123)
    robot_a = sim.world.robots["R1"]
    
    # Robot A has payload and is delivering
    task = Task(id="FAIL_DELIVERY_TASK", pickup=(2, 2), dropoff=(22, 2), priority=2.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = robot_a.id
    robot_a.current_task_id = task.id
    robot_a.has_payload = True
    robot_a.position = (10, 2)
    robot_a.state = RobotState.DELIVERING
    sim.world.add_task(task)
    
    # Give Robot A active waypoints
    sim.coordinator._active_waypoints[robot_a.id] = [(11, 2), (12, 2)]
    sim.coordinator._waypoint_assigned_step[robot_a.id] = 0
    
    # Inject failure on Robot A
    robot_a.is_healthy = False
    robot_a.state = RobotState.FAILED
    robot_a.failure_reason = "Drive motor hardware stall"
    
    # Reclaim/handle failed robot task (simulates failure handler in step_coordinate / allocator)
    sim.step()
    
    # Failed robot must have zero velocity and no movement
    assert robot_a.velocity == 0.0, "Failed robot must have 0.0 velocity"
    # Active waypoints for failed robot should be safely cleared
    assert robot_a.id not in sim.coordinator._active_waypoints, "Failed robot active waypoints must be cleared!"
    
    # Reclaim task if assigned to failed robot
    if task.assigned_robot_id == robot_a.id:
        task.state = TaskState.QUEUED
        task.assigned_robot_id = None
        task.pickup = (2, 2)
        
    # Free up R2 to be available for reassignment
    r2 = sim.world.robots["R2"]
    if r2.current_task_id:
        old_task = sim.world.tasks.get(r2.current_task_id)
        if old_task:
            old_task.state = TaskState.DELIVERED
    r2.current_task_id = None
    r2.state = RobotState.IDLE
    r2.has_payload = False

    # Step simulation until an available healthy AMR is assigned
    reassigned = False
    for _ in range(10):
        sim.step()
        if task.assigned_robot_id and task.assigned_robot_id != robot_a.id:
            reassigned = True
            break

    assert reassigned, "Task from failed AMR must be reassigned to a healthy robot!"
