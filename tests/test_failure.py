"""Unit tests for robot failure injection and task recovery."""

import pytest
from resilience.failure import FailureManager
from resilience.recovery import TaskRecoveryManager
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState


def test_robot_failure_and_recovery():
    failure_mgr = FailureManager()
    recovery_mgr = TaskRecoveryManager()

    robot = Robot(id="R1", initial_position=(2, 2))
    task = Task(id="T1", pickup=(2, 2), dropoff=(5, 5), state=TaskState.ASSIGNED, assigned_robot_id="R1")
    robot.current_task_id = "T1"
    tasks = {"T1": task}

    # Inject failure
    failure_mgr.inject_failure(robot, "Motor overheating", sim_time=10.0, step=100)
    assert robot.is_healthy is False
    assert robot.state == RobotState.FAILED

    # Recover task
    recovered_task = recovery_mgr.handle_robot_failure(robot, tasks, sim_time=10.0, step=100)
    assert recovered_task is not None
    assert recovered_task.state == TaskState.QUEUED
    assert recovered_task.assigned_robot_id is None
    assert robot.current_task_id is None
