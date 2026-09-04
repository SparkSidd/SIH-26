"""Trajectory generation from discrete waypoints to continuous control targets."""

from dataclasses import dataclass
import math
from typing import List, Tuple


@dataclass
class TrajectoryWaypoint:
    """Represents a continuous waypoint along an AMR trajectory."""
    x: float
    y: float
    target_time: float
    target_velocity: float = 1.0
    target_heading: float = 0.0


class TrajectoryGenerator:
    """Translates grid cell sequences into continuous time-parameterized trajectories."""

    @staticmethod
    def generate_trajectory(
        path: List[Tuple[int, int]],
        start_time: float,
        dt_per_cell: float = 1.0,
        nominal_speed: float = 1.0,
    ) -> List[TrajectoryWaypoint]:
        """Convert list of (x, y) grid coordinates into timed trajectory waypoints."""
        waypoints: List[TrajectoryWaypoint] = []
        if not path:
            return waypoints

        for idx, pos in enumerate(path):
            t = start_time + idx * dt_per_cell
            heading = 0.0
            if idx < len(path) - 1:
                next_pos = path[idx + 1]
                heading = math.atan2(next_pos[1] - pos[1], next_pos[0] - pos[0])
            elif idx > 0:
                prev_pos = path[idx - 1]
                heading = math.atan2(pos[1] - prev_pos[1], pos[0] - prev_pos[0])

            waypoints.append(
                TrajectoryWaypoint(
                    x=float(pos[0]),
                    y=float(pos[1]),
                    target_time=t,
                    target_velocity=nominal_speed,
                    target_heading=heading,
                )
            )

        return waypoints
