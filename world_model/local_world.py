"""Decentralized Local World Model maintained independently on each AMR."""

from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from simulator.sensors import SensorObservation
from world_model.belief_state import RobotBelief
from world_model.information_age import InformationAge, InformationAgeCategory


class DecentralizationViolationError(RuntimeError):
    """Raised if any planning or allocation module attempts unauthorized access to global ground truth."""
    pass


class LocalWorldModel:
    """Independent world representation stored in on-board robot memory."""

    def __init__(
        self,
        self_id: str,
        map_width: int,
        map_height: int,
        static_grid: np.ndarray,
    ):
        self.self_id: str = self_id
        self.map_width: int = map_width
        self.map_height: int = map_height
        # Copy of static layout (walls and shelves) known a priori to AMR
        self.static_grid: np.ndarray = np.copy(static_grid)
        
        # Peer beliefs: robot_id -> RobotBelief
        self.peer_beliefs: Dict[str, RobotBelief] = {}
        
        # Locally detected dynamic obstacles and temporary blockages
        self.known_blocked_cells: Set[Tuple[int, int]] = set()
        
        # Local task registry known to this robot
        self.known_task_ids: Set[str] = set()
        
        # Information aging engine
        self.age_model = InformationAge()

    def update_from_sensor_observation(self, obs: SensorObservation) -> None:
        """Update local beliefs based on on-board sensory scan."""
        # 1. Update detected obstacles
        for obs_cell in obs.detected_obstacles:
            self.known_blocked_cells.add(obs_cell)

        # 2. Update peer positions spotted via sensor
        for peer_id, peer_pos in obs.detected_robots:
            if peer_id not in self.peer_beliefs:
                self.peer_beliefs[peer_id] = RobotBelief(
                    robot_id=peer_id,
                    position=peer_pos,
                    timestamp=obs.timestamp,
                    confidence=obs.confidence,
                    source="SENSOR",
                )
            else:
                belief = self.peer_beliefs[peer_id]
                belief.position = peer_pos
                belief.timestamp = obs.timestamp
                belief.confidence = obs.confidence
                belief.source = "SENSOR"

    def update_from_peer_message(
        self,
        sender_id: str,
        position: Tuple[int, int],
        velocity: float,
        heading: float,
        intended_action: str,
        planned_path: List[Tuple[int, int]],
        current_task_id: Optional[str],
        priority: float,
        timestamp: float,
        sequence_number: int,
    ) -> None:
        """Update local belief based on received P2P packet."""
        age = self.age_model.compute_confidence(0.0)
        self.peer_beliefs[sender_id] = RobotBelief(
            robot_id=sender_id,
            position=position,
            velocity=velocity,
            heading=heading,
            intended_action=intended_action,
            planned_path=list(planned_path),
            current_task_id=current_task_id,
            priority=priority,
            timestamp=timestamp,
            sequence_number=sequence_number,
            confidence=age,
            source="P2P",
        )

    def is_cell_traversable(self, pos: Tuple[int, int], current_time: float) -> bool:
        """Check if cell is considered traversable according to local world model."""
        x, y = pos
        if not (0 <= x < self.map_width and 0 <= y < self.map_height):
            return False
        # Static walls / shelves
        if self.static_grid[x, y] in (1, 2):
            return False
        # Known blocked cells
        if pos in self.known_blocked_cells:
            return False
        return True

    def get_known_robot_positions(self, current_time: float, max_age: float = 2.0) -> Dict[str, Tuple[int, int]]:
        """Get positions of peers whose belief is within acceptable age threshold."""
        valid_positions = {}
        for r_id, belief in self.peer_beliefs.items():
            if belief.get_age(current_time) <= max_age:
                valid_positions[r_id] = belief.position
        return valid_positions

    def get_future_reservations(self, current_time: float) -> Dict[Tuple[int, int, int], str]:
        """Extract space-time reservations (x, y, timestep_offset) broadcasted by peers."""
        reservations = {}
        for r_id, belief in self.peer_beliefs.items():
            category = belief.get_category(current_time, self.age_model)
            if category in (InformationAgeCategory.FRESH, InformationAgeCategory.RECENT):
                for step_idx, step_pos in enumerate(belief.planned_path):
                    reservations[(step_pos[0], step_pos[1], step_idx)] = r_id
        return reservations
