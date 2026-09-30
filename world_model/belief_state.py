"""Perceived belief state of neighboring peer robots."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from world_model.information_age import InformationAge, InformationAgeCategory


@dataclass
class RobotBelief:
    """Belief held by an AMR regarding a specific peer robot."""
    robot_id: str
    position: Tuple[int, int]
    velocity: float = 0.0
    heading: float = 0.0
    intended_action: str = "WAIT"
    planned_path: List[Tuple[int, int]] = field(default_factory=list)
    current_task_id: Optional[str] = None
    priority: float = 1.0
    has_payload: bool = False
    task_state: Optional[str] = None
    target_position: Optional[Tuple[int, int]] = None
    timestamp: float = 0.0
    sequence_number: int = 0
    confidence: float = 1.0
    source: str = "P2P"  # "P2P" or "SENSOR"

    def get_age(self, current_sim_time: float) -> float:
        return max(0.0, current_sim_time - self.timestamp)

    def get_category(self, current_sim_time: float, age_model: InformationAge) -> InformationAgeCategory:
        return age_model.categorize(self.get_age(current_sim_time))
