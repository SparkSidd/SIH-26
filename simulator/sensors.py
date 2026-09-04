"""Sensor abstractions and measurement observation generators."""

from dataclasses import dataclass
from enum import Enum, auto
import math
import random
from typing import Dict, List, Optional, Set, Tuple


class SensorNoiseMode(Enum):
    PERFECT = auto()
    LOW_NOISE = auto()
    MODERATE_NOISE = auto()
    DROPOUT = auto()


@dataclass
class SensorObservation:
    """Represents a local sensory sweep captured by an AMR."""
    robot_id: str
    timestamp: float
    detected_robots: List[Tuple[str, Tuple[int, int]]]   # (robot_id, observed_pos)
    detected_obstacles: Set[Tuple[int, int]]             # Positions of detected static/dynamic obstacles
    self_localized_pos: Tuple[int, int]                  # Self estimated position
    confidence: float = 1.0


class RobotSensorSuite:
    """Simulates on-board AMR perception (LiDAR, proximity sensors, wheel odometry/localization)."""

    def __init__(
        self,
        range_cells: float = 5.0,
        noise_mode: SensorNoiseMode = SensorNoiseMode.LOW_NOISE,
        seed: int = 42,
    ):
        self.range_cells = range_cells
        self.noise_mode = noise_mode
        self.rng = random.Random(seed)

    def scan(
        self,
        robot_id: str,
        robot_pos: Tuple[int, int],
        sim_time: float,
        ground_truth_robots: Dict[str, Tuple[int, int]],
        ground_truth_obstacles: Set[Tuple[int, int]],
    ) -> SensorObservation:
        """Generate sensor observation given true world state without leaking future or global state."""
        # Check for sensor dropout
        if self.noise_mode == SensorNoiseMode.DROPOUT and self.rng.random() < 0.08:
            return SensorObservation(
                robot_id=robot_id,
                timestamp=sim_time,
                detected_robots=[],
                detected_obstacles=set(),
                self_localized_pos=robot_pos,
                confidence=0.2,
            )

        detected_robots = []
        detected_obstacles = set()
        rx, ry = robot_pos

        # 1. Sense nearby robots within sensing radius
        for other_id, other_pos in ground_truth_robots.items():
            if other_id == robot_id:
                continue
            ox, oy = other_pos
            dist = math.hypot(ox - rx, oy - ry)
            if dist <= self.range_cells:
                # Add slight positional noise if in moderate noise mode
                obs_pos = other_pos
                if self.noise_mode == SensorNoiseMode.MODERATE_NOISE and self.rng.random() < 0.05:
                    # Rare ±1 cell perception glitch
                    obs_pos = (ox + self.rng.choice([-1, 0, 1]), oy + self.rng.choice([-1, 0, 1]))
                detected_robots.append((other_id, obs_pos))

        # 2. Sense nearby obstacles within sensing radius
        for obs_pos in ground_truth_obstacles:
            ox, oy = obs_pos
            dist = math.hypot(ox - rx, oy - ry)
            if dist <= self.range_cells:
                detected_obstacles.add(obs_pos)

        # 3. Self-localization
        self_pos = robot_pos
        confidence = 1.0
        if self.noise_mode == SensorNoiseMode.LOW_NOISE:
            confidence = 0.98
        elif self.noise_mode == SensorNoiseMode.MODERATE_NOISE:
            confidence = 0.90

        return SensorObservation(
            robot_id=robot_id,
            timestamp=sim_time,
            detected_robots=detected_robots,
            detected_obstacles=detected_obstacles,
            self_localized_pos=self_pos,
            confidence=confidence,
        )
