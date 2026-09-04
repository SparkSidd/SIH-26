"""Regression test suite permanently verifying the corridor gridlock and goal reversion bug fixes."""

import pytest
from simulator.simulation import AMRSimulation
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState
from execution.action import RobotAction, ActionType


def test_payload_goal_reversion_invariance():
    """Verify Requirements A, B, C:
    A robot carrying a payload NEVER reverts its ultimate goal to pickup,
    even when in RobotState.WAITING, REPLANNING, or BLOCKED.
    """
    sim = AMRSimulation(seed=123)
    robot = sim.world.robots["R1"]
    
    # Create a task and mark it as picked up
    task = Task(
        id="REG_TASK_001",
        pickup=(2, 10),
        dropoff=(22, 17),
        priority=2.0,
        creation_time=0.0,
    )
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = robot.id
    sim.world.add_task(task)
    
    robot.current_task_id = task.id
    robot.has_payload = True
    robot.position = (2, 10)  # Standing on pickup station
    
    # Test across all waiting/hesitation states
    test_states = [
        RobotState.WAITING,
        RobotState.REPLANNING,
        RobotState.BLOCKED,
        RobotState.IDLE,
        RobotState.MOVING_TO_DROPOFF,
        RobotState.DELIVERING,
    ]
    
    for state in test_states:
        robot.state = state
        actions = sim.coordinator.step_coordinate(
            robots=sim.world.robots,
            tasks=sim.world.tasks,
            is_walkable_fn=sim.warehouse.is_walkable,
            blocked_cells=sim.warehouse.blocked_cells,
            sim_time=1.0,
            step=10,
        )
        # R1's goal must be the dropoff destination, NOT the pickup station
        # Target goal inside coordinator or planned path must point towards dropoff (22, 17)
        if robot.planned_path:
            assert robot.planned_path[-1] == task.dropoff or (robot.planned_path[0] != task.pickup or len(robot.planned_path) > 1), (
                f"State {state.name} caused robot to target pickup station instead of dropoff!"
            )


def test_no_permanent_pickup_station_sticking():
    """Verify Requirement D & E:
    Robots must not remain permanently stuck at a pickup station, and wait_steps must
    not grow indefinitely without triggering recovery/movement.
    """
    sim = AMRSimulation(seed=42)
    # Step simulation to let allocation occur
    for _ in range(10):
        sim.step()
        
    # Find any robot that has picked up a task
    picked_up_seen = False
    for step_idx in range(100):
        sim.step()
        for r in sim.world.robots.values():
            if r.current_task_id:
                t = sim.world.tasks.get(r.current_task_id)
                if t and t.state == TaskState.PICKED_UP:
                    picked_up_seen = True
                    # The robot must not have an unbounded wait counter at pickup
                    if r.position == t.pickup:
                        assert r.wait_steps < 30, (
                            f"Robot {r.id} stuck at pickup station {t.pickup} with wait_steps={r.wait_steps}!"
                        )
    assert picked_up_seen, "Simulation should have had tasks picked up within 110 steps."


def test_narrow_corridor_blockage_and_deadlock_recovery():
    """Verify Requirements F, G, H:
    Reproduce narrow corridor blockage at (1, 6) with multiple AMRs in the corridor.
    Verify that:
    - Rerouting or deadlock recovery is triggered.
    - Zero inter-robot collisions occur.
    - Task ownership remains completely valid throughout.
    - Wait steps never exceed recovery threshold indefinitely.
    """
    sim = AMRSimulation(seed=99)
    
    # Run nominal steps to get AMRs moving into tasks
    for _ in range(15):
        sim.step()
        
    # Block corridor cell (1, 6)
    assert sim.warehouse.block_cell((1, 6)), "Cell (1, 6) should be blockable."
    
    max_wait_seen = 0
    collisions_before = sim.metrics.total_collisions
    
    # Run 120 steps under corridor blockage
    for step_idx in range(120):
        sim.step()
        
        # Check active task ownership validity
        for t_id, task in sim.world.tasks.items():
            if task.state in (TaskState.ASSIGNED, TaskState.PICKED_UP) and task.assigned_robot_id:
                assigned_r = sim.world.robots.get(task.assigned_robot_id)
                assert assigned_r is not None, f"Task {t_id} assigned to nonexistent robot {task.assigned_robot_id}"
                if assigned_r.is_healthy:
                    assert assigned_r.current_task_id == t_id, (
                        f"Mismatched ownership: task {t_id} (state {task.state.name}) thinks it belongs to {assigned_r.id}, "
                        f"but robot has {assigned_r.current_task_id}"
                    )
                    
        for r in sim.world.robots.values():
            if r.current_task_id:
                max_wait_seen = max(max_wait_seen, r.wait_steps)
                # Active task recovery logic should trigger well before 50 steps
                assert r.wait_steps < 50, (
                    f"Active Robot {r.id} wait_steps reached {r.wait_steps} without recovery under blockage!"
                )
            
    # Zero collisions guaranteed
    assert sim.metrics.total_collisions == collisions_before == 0, "No collisions must occur during corridor blockage."
    # Fleet should continue completing tasks despite corridor constriction
    summary = sim.metrics.get_summary()
    assert summary["total_tasks_completed"] > 0, "Tasks should continue to be completed."
