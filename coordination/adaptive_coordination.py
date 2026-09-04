"""Adaptive Coordination Intensity Engine: LOCAL, NEIGHBOR, CLUSTER modes."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple


class CoordinationMode(Enum):
    LOCAL = auto()          # Low density: Minimal P2P traffic, local reactive avoidance
    NEIGHBOR = auto()       # Moderate traffic: Exchange intent, trajectories, dynamic priority
    CLUSTER = auto()        # Severe congestion / choke point: Multi-agent cooperative conflict negotiation


@dataclass
class CoordinationPolicy:
    """Configures escalation triggers based on congestion and conflict thresholds."""
    local_threshold: float = 0.25
    neighbor_threshold: float = 0.55
    cluster_threshold: float = 0.80


class AdaptiveCoordinator:
    """Dynamically adjusts fleet coordination intensity based on local and spatial traffic metrics."""

    def __init__(self, policy: Optional[CoordinationPolicy] = None):
        self.policy = policy or CoordinationPolicy()
        self.current_mode: CoordinationMode = CoordinationMode.LOCAL
        self.mode_history: List[Tuple[float, CoordinationMode]] = []

    def evaluate_mode(
        self,
        average_congestion: float,
        recent_conflicts_count: int,
        is_aisle_blocked: bool,
        has_deadlocks: bool,
        sim_time: float,
    ) -> CoordinationMode:
        """Determine appropriate coordination mode given fleet conditions."""
        # Extreme triggers -> Immediate CLUSTER escalation
        if has_deadlocks or is_aisle_blocked or recent_conflicts_count >= 3:
            new_mode = CoordinationMode.CLUSTER
        elif average_congestion >= self.policy.neighbor_threshold or recent_conflicts_count >= 1:
            new_mode = CoordinationMode.NEIGHBOR
        else:
            new_mode = CoordinationMode.LOCAL

        if new_mode != self.current_mode:
            self.current_mode = new_mode
            self.mode_history.append((sim_time, new_mode))

        return self.current_mode
