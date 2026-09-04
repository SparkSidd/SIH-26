"""Execution-aware ETA estimation model accounting for congestion, turns, and wait delays."""

import math
from typing import List, Optional, Tuple
from coordination.congestion import CongestionModel


class ETAModel:
    """Calculates realistic arrival times considering kinodynamics and network/congestion delays."""

    def __init__(
        self,
        nominal_speed: float = 1.0,     # cells/sec
        turn_penalty_sec: float = 0.5,  # sec delay per 90 deg turn
        congestion_weight: float = 0.4, # sec delay per congestion score unit
    ):
        self.nominal_speed = nominal_speed
        self.turn_penalty_sec = turn_penalty_sec
        self.congestion_weight = congestion_weight

    def estimate_eta(
        self,
        path: List[Tuple[int, int]],
        congestion_model: Optional[CongestionModel] = None,
        expected_wait_steps: int = 0,
    ) -> float:
        """Estimate execution-aware duration in seconds to traverse path."""
        if not path or len(path) <= 1:
            return 0.0

        # Base physical travel time
        distance = float(len(path) - 1)
        base_time = distance / self.nominal_speed

        # Turn penalties
        turns = 0
        for i in range(1, len(path) - 1):
            p_prev = path[i - 1]
            p_curr = path[i]
            p_next = path[i + 1]
            dx1, dy1 = p_curr[0] - p_prev[0], p_curr[1] - p_prev[1]
            dx2, dy2 = p_next[0] - p_curr[0], p_next[1] - p_curr[1]
            if (dx1, dy1) != (dx2, dy2):
                turns += 1

        turn_delay = turns * self.turn_penalty_sec

        # Congestion delay
        congestion_delay = 0.0
        if congestion_model is not None:
            path_congestion = congestion_model.get_path_congestion(path)
            congestion_delay = path_congestion * self.congestion_weight

        # Waiting delay
        wait_delay = expected_wait_steps * (1.0 / self.nominal_speed)

        return base_time + turn_delay + congestion_delay + wait_delay
