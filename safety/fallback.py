"""Safety fallback generator for resolving rejected or hazardous candidate actions."""

from typing import Dict, Tuple
from execution.action import RobotAction, ActionType


class SafetyFallback:
    """Generates guaranteed-safe fallback maneuvers when planner output is rejected."""

    @staticmethod
    def create_wait_fallback(robot_id: str, current_pos: Tuple[int, int], reason: str = "") -> RobotAction:
        """Fallback: Robot remains stationary in current safe cell."""
        return RobotAction(
            action_type=ActionType.WAIT,
            target_cell=current_pos,
            reason=f"Safety Fallback (WAIT): {reason}",
            is_safety_override=True,
        )

    @staticmethod
    def create_estop_fallback(robot_id: str, current_pos: Tuple[int, int], reason: str = "") -> RobotAction:
        """Fallback: Immediate Emergency Stop."""
        return RobotAction(
            action_type=ActionType.ESTOP,
            target_cell=current_pos,
            reason=f"Safety Fallback (ESTOP): {reason}",
            is_safety_override=True,
        )
