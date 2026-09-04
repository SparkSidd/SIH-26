"""Dynamic spatial congestion heatmap and traffic density estimation."""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
import numpy as np


class CongestionModel:
    """Computes real-time congestion scores across warehouse grid cells and aisles."""

    def __init__(self, width: int = 25, height: int = 20, decay_factor: float = 0.95):
        self.width = width
        self.height = height
        self.decay_factor = decay_factor
        
        # Historical occupancy density heatmap: (x, y) -> float
        self.heatmap = np.zeros((width, height), dtype=float)
        
        # Conflict counts per cell: (x, y) -> int
        self.cell_conflict_counts: Dict[Tuple[int, int], int] = defaultdict(int)

    def update_tick(
        self,
        current_robot_positions: Dict[str, Tuple[int, int]],
        active_planned_paths: Optional[Dict[str, List[Tuple[int, int]]]] = None,
    ) -> None:
        """Decay historical heat and integrate current robot locations + future planned paths."""
        # Exponential temporal decay
        self.heatmap *= self.decay_factor

        # Add current robot occupancy
        for r_id, pos in current_robot_positions.items():
            x, y = pos
            if 0 <= x < self.width and 0 <= y < self.height:
                self.heatmap[x, y] += 1.0

        # Add predicted future trajectory footprint
        if active_planned_paths:
            for r_id, path in active_planned_paths.items():
                for step_idx, step_pos in enumerate(path[:6]):  # lookahead 6 steps
                    x, y = step_pos
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.heatmap[x, y] += 0.3 / (step_idx + 1)

    def record_conflict(self, cell: Tuple[int, int]) -> None:
        """Record an intersection conflict at cell."""
        self.cell_conflict_counts[cell] += 1
        x, y = cell
        if 0 <= x < self.width and 0 <= y < self.height:
            self.heatmap[x, y] += 2.0

    def get_cell_congestion(self, cell: Tuple[int, int]) -> float:
        """Get total congestion score for a specific cell."""
        x, y = cell
        if 0 <= x < self.width and 0 <= y < self.height:
            return float(self.heatmap[x, y])
        return 0.0

    def get_path_congestion(self, path: List[Tuple[int, int]]) -> float:
        """Sum congestion score along an entire route."""
        if not path:
            return 0.0
        return sum(self.get_cell_congestion(pos) for pos in path)
