"""Unit tests for execution layer and motion kinematics."""

import pytest
from execution.action import RobotAction, ActionType
from execution.executor import ActionExecutor
from simulator.robot import Robot, RobotState


def test_action_executor_move():
    executor = ActionExecutor()
    robot = Robot(id="R1", initial_position=(2, 2))

    action = RobotAction(action_type=ActionType.MOVE, target_cell=(3, 2))
    executor.execute_action(robot, action, dt=0.1)

    assert robot.position == (3, 2)
    assert robot.previous_position == (2, 2)
    assert robot.total_distance_traveled == 1.0
    assert robot.wait_steps == 0


def test_action_executor_wait():
    executor = ActionExecutor()
    robot = Robot(id="R1", initial_position=(2, 2))

    action = RobotAction(action_type=ActionType.WAIT, target_cell=(2, 2))
    executor.execute_action(robot, action, dt=0.1)

    assert robot.position == (2, 2)
    assert robot.wait_steps == 1
    assert robot.velocity == 0.0
