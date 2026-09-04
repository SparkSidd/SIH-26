"""Continuous geometric collision checking and lookahead sweep verification."""

import math
from typing import Dict, List, Tuple
from simulator.robot import RobotGeometry


class CollisionChecker:
    """Performs spatial geometric bounding-circle and trajectory sweep collision checks."""

    @staticmethod
    def check_distance(
        pos1: Tuple[float, float],
        pos2: Tuple[float, float],
        r1: float,
        r2: float,
        safety_margin: float = 0.1,
    ) -> bool:
        """Check if two circular bounding footprints overlap."""
        dist = math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])
        min_allowed = r1 + r2 + safety_margin
        return dist < min_allowed

    @staticmethod
    def check_continuous_sweep(
        start1: Tuple[float, float],
        end1: Tuple[float, float],
        start2: Tuple[float, float],
        end2: Tuple[float, float],
        radius1: float,
        radius2: float,
        steps: int = 5,
    ) -> bool:
        """Interpolate intermediate trajectory positions to check for mid-tick geometric collisions."""
        for step in range(steps + 1):
            alpha = step / float(steps)
            p1 = (start1[0] + alpha * (end1[0] - start1[0]), start1[1] + alpha * (end1[1] - start1[1]))
            p2 = (start2[0] + alpha * (end2[0] - start2[0]), start2[1] + alpha * (end2[1] - start2[1]))
            if CollisionChecker.check_distance(p1, p2, radius1, radius2):
                return True
        return False
