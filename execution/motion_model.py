"""Kinematic motion models for discrete and continuous AMR simulation."""

import math
from typing import Tuple
from simulator.robot import Robot, RobotGeometry, RobotState


class MotionModel:
    """Handles kinematic state integration, velocity limits, and orientation."""

    def __init__(self, geometry: RobotGeometry):
        self.geometry = geometry

    def calculate_heading_to(self, current_pos: Tuple[int, int], target_pos: Tuple[int, int]) -> float:
        """Calculate target heading angle in radians from current to next cell."""
        dx = target_pos[0] - current_pos[0]
        dy = target_pos[1] - current_pos[1]
        return math.atan2(dy, dx)

    def step_discrete_motion(
        self,
        robot: Robot,
        target_pos: Tuple[int, int],
        dt: float,
    ) -> None:
        """Update robot state for discrete grid step."""
        if target_pos != robot.position:
            robot.previous_position = robot.position
            robot.heading = self.calculate_heading_to(robot.position, target_pos)
            robot.position = target_pos
            robot.velocity = self.geometry.max_velocity
            robot.total_distance_traveled += 1.0
            robot.battery.step_discharge(moving=True)
            robot.reset_wait()
        else:
            # Robot is waiting / stationary
            robot.velocity = 0.0
            robot.battery.step_discharge(moving=False)
            robot.increment_wait()
            
        robot.total_steps_active += 1
