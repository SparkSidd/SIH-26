"""Robot action definitions and execution payloads."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple


class ActionType(Enum):
    MOVE = auto()           # Move to adjacent cell / target coordinate
    WAIT = auto()           # Stay in current position
    ROTATE = auto()         # Rotate in place to face target heading
    PICK = auto()           # Pick up payload at station
    DROP = auto()           # Drop off payload at station
    CHARGE = auto()         # Engage charging pad
    ESTOP = auto()          # Emergency safety stop


@dataclass
class RobotAction:
    """Represents a concrete command to be executed on an AMR."""
    action_type: ActionType
    target_cell: Tuple[int, int]
    target_heading: Optional[float] = None
    target_velocity: float = 1.0
    task_id: Optional[str] = None
    reason: str = ""
    is_safety_override: bool = False
