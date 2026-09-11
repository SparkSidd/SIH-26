"""Dynamic spatial congestion heatmap, traffic density estimation, and normalized Congestion Index."""

from collections import defaultdict
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np


class CongestionModel:
    """Computes real-time congestion scores and a normalized 0-100 Congestion Index across warehouse grid cells."""

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
        """Get raw cumulative congestion score for a specific cell."""
        x, y = cell
        if 0 <= x < self.width and 0 <= y < self.height:
            return float(self.heatmap[x, y])
        return 0.0

    def get_path_congestion(self, path: List[Tuple[int, int]]) -> float:
        """Sum congestion score along an entire route."""
        if not path:
            return 0.0
        return sum(self.get_cell_congestion(pos) for pos in path)

    def get_normalized_congestion(self, cell: Tuple[int, int]) -> float:
        """Normalized Congestion Index (0-100) using a smooth saturating exponential.
        
        Formula: Index = 100 * (1 - exp(-raw_heat / 4.0))
        - raw = 0.0  -> 0.0 (Nominal clear cell)
        - raw = 1.0  -> 22.1 (Light transient traffic)
        - raw = 4.0  -> 63.2 (Moderate queue)
        - raw >= 10.0 -> >= 91.8 (Severe bottleneck / choke point)
        """
        raw = self.get_cell_congestion(cell)
        return round(float(100.0 * (1.0 - math.exp(-raw / 4.0))), 1)

    def get_normalized_heatmap(self) -> np.ndarray:
        """Return 2D array of normalized 0-100 Congestion Indices."""
        return np.round(100.0 * (1.0 - np.exp(-self.heatmap / 4.0)), 1)

    def get_peak_congestion_index(self) -> float:
        """Get the peak normalized Congestion Index across the entire warehouse."""
        raw_peak = float(np.max(self.heatmap)) if self.heatmap.size > 0 else 0.0
        return round(float(100.0 * (1.0 - math.exp(-raw_peak / 4.0))), 1)

    def get_average_congestion_index(self) -> float:
        """Get the average normalized Congestion Index across active cells."""
        raw_mean = float(np.mean(self.heatmap)) if self.heatmap.size > 0 else 0.0
        return round(float(100.0 * (1.0 - math.exp(-raw_mean / 4.0))), 1)

    def get_hotspot_info(self) -> Dict[str, Any]:
        """Identify peak congestion hotspot coordinates, index (0-100), and human-readable label."""
        if self.heatmap.size == 0:
            return {"cell": [0, 0], "index": 0.0, "raw": 0.0, "label": "Nominal (Clear)"}

        max_idx = np.unravel_index(np.argmax(self.heatmap), self.heatmap.shape)
        cell = (int(max_idx[0]), int(max_idx[1]))
        raw_peak = float(self.heatmap[cell[0], cell[1]])
        norm_idx = self.get_normalized_congestion(cell)

        # Classify zone
        x, y = cell
        if norm_idx < 15.0:
            label = "Nominal (Clear)"
        elif x <= 2 and y <= 2:
            label = f"Depot / Charger Zone ({x},{y})"
        elif 4 <= x <= 20 and 5 <= y <= 15:
            label = f"Central Storage Corridor ({x},{y})"
        else:
            label = f"Intersection ({x},{y})"

        return {
            "cell": [cell[0], cell[1]],
            "index": norm_idx,
            "raw": round(raw_peak, 2),
            "label": label,
        }
