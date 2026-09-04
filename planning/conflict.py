"""Multi-agent conflict detection across space-time trajectories."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


class ConflictType(Enum):
    VERTEX = auto()             # Same cell at same timestep
    EDGE_SWAP = auto()          # Edge swap crossing simultaneously
    FOLLOWING = auto()          # Insufficient spacing
    INTERSECTION = auto()       # Unsynchronized entry into 4-way intersection
    CHOKE_POINT = auto()        # Opposing flows into single-lane corridor


@dataclass
class PathConflict:
    """Represents a detected trajectory conflict between two robots."""
    conflict_type: ConflictType
    robot_1: str
    robot_2: str
    location_1: Tuple[int, int]
    location_2: Optional[Tuple[int, int]] = None
    timestep: int = 0
    severity: float = 1.0


class ConflictDetector:
    """Detects spatial and temporal path conflicts between planned trajectories."""

    @staticmethod
    def detect_conflicts(
        trajectories: Dict[str, List[Tuple[int, int]]],
        horizon: int = 15,
    ) -> List[PathConflict]:
        """Exhaustively find all vertex and edge conflicts across a set of trajectories."""
        conflicts: List[PathConflict] = []
        robot_ids = list(trajectories.keys())

        for i in range(len(robot_ids)):
            r1 = robot_ids[i]
            path1 = trajectories[r1]
            for j in range(i + 1, len(robot_ids)):
                r2 = robot_ids[j]
                path2 = trajectories[r2]

                max_t = min(horizon, max(len(path1), len(path2)))
                for t in range(max_t):
                    pos1 = path1[min(t, len(path1) - 1)]
                    pos2 = path2[min(t, len(path2) - 1)]

                    # 1. Vertex Conflict
                    if pos1 == pos2:
                        conflicts.append(
                            PathConflict(
                                conflict_type=ConflictType.VERTEX,
                                robot_1=r1,
                                robot_2=r2,
                                location_1=pos1,
                                timestep=t,
                            )
                        )

                    # 2. Edge Swap Conflict
                    if t > 0:
                        prev1 = path1[min(t - 1, len(path1) - 1)]
                        prev2 = path2[min(t - 1, len(path2) - 1)]
                        if pos1 == prev2 and pos2 == prev1 and pos1 != prev1:
                            conflicts.append(
                                PathConflict(
                                    conflict_type=ConflictType.EDGE_SWAP,
                                    robot_1=r1,
                                    robot_2=r2,
                                    location_1=prev1,
                                    location_2=pos1,
                                    timestep=t,
                                )
                            )

        return conflicts
