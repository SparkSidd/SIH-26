"""Unit tests for Wait-For-Graph deadlock cycle detection."""

import pytest
from planning.deadlock import DeadlockDetector


def test_deadlock_cycle_detection():
    # R1 at (0,0) wants (1,0) (held by R2)
    # R2 at (1,0) wants (1,1) (held by R3)
    # R3 at (1,1) wants (0,0) (held by R1)
    current_pos = {
        "R1": (0, 0),
        "R2": (1, 0),
        "R3": (1, 1),
    }
    desired_targets = {
        "R1": (1, 0),
        "R2": (1, 1),
        "R3": (0, 0),
    }
    wait_steps = {"R1": 5, "R2": 5, "R3": 5}

    report = DeadlockDetector.detect_deadlocks(
        current_positions=current_pos,
        desired_targets=desired_targets,
        wait_threshold=3,
        robot_wait_steps=wait_steps,
    )

    assert report.is_deadlocked is True
    assert len(report.cycles) >= 1
