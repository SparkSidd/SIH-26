"""Static and dynamic obstacles in the warehouse environment."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple


class ObstacleType(Enum):
    WALL = auto()
    SHELF = auto()
    TEMPORARY_BLOCKAGE = auto()
    DYNAMIC_HUMAN = auto()
    FAILED_ROBOT = auto()


@dataclass
class Obstacle:
    """Represents an obstacle occupying a cell in the warehouse."""
    id: str
    position: Tuple[int, int]
    obstacle_type: ObstacleType
    is_static: bool = True
    start_time: float = 0.0
    duration: Optional[float] = None  # None = permanent

    def is_active_at(self, sim_time: float) -> bool:
        """Check if obstacle is active at given simulation time."""
        if sim_time < self.start_time:
            return False
        if self.duration is not None and sim_time >= (self.start_time + self.duration):
            return False
        return True
