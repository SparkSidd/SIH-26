"""Unit tests for conflict detection and geometric collision checking."""

import pytest
from planning.conflict import ConflictDetector, ConflictType
from safety.collision_checker import CollisionChecker


def test_vertex_conflict_detection():
    # R1 and R2 both arrive at (2, 2) at timestep 2
    trajectories = {
        "R1": [(0, 2), (1, 2), (2, 2)],
        "R2": [(2, 0), (2, 1), (2, 2)],
    }

    conflicts = ConflictDetector.detect_conflicts(trajectories)
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictType.VERTEX
    assert conflicts[0].location_1 == (2, 2)
    assert conflicts[0].timestep == 2


def test_edge_swap_conflict_detection():
    # R1 moves (1, 0) -> (2, 0) while R2 moves (2, 0) -> (1, 0) at timestep 1
    trajectories = {
        "R1": [(1, 0), (2, 0)],
        "R2": [(2, 0), (1, 0)],
    }

    conflicts = ConflictDetector.detect_conflicts(trajectories)
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictType.EDGE_SWAP
    assert conflicts[0].timestep == 1


def test_continuous_geometric_collision():
    # Two robots at (0.0, 0.0) and (0.5, 0.0) with radius 0.45 (total radius = 0.9 + margin)
    assert CollisionChecker.check_distance((0.0, 0.0), (0.5, 0.0), 0.45, 0.45, safety_margin=0.1) is True
    # Two robots far apart
    assert CollisionChecker.check_distance((0.0, 0.0), (2.0, 0.0), 0.45, 0.45, safety_margin=0.1) is False
