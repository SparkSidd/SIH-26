"""Unit tests for PIBT Multi-Agent Planner."""

import pytest
from planning.pibt import PIBTPlanner


def test_pibt_non_conflicting_steps():
    planner = PIBTPlanner()
    is_walkable = lambda pos: 0 <= pos[0] < 10 and 0 <= pos[1] < 10

    robot_ids = ["R1", "R2"]
    current_positions = {"R1": (0, 0), "R2": (5, 5)}
    target_goals = {"R1": (3, 0), "R2": (8, 5)}
    priorities = {"R1": 1.0, "R2": 1.0}

    next_pos = planner.plan_step(
        robot_ids=robot_ids,
        current_positions=current_positions,
        target_goals=target_goals,
        priorities=priorities,
        is_walkable_fn=is_walkable,
    )

    assert next_pos["R1"] == (1, 0)
    assert next_pos["R2"] == (6, 5)


def test_pibt_head_on_conflict_priority():
    planner = PIBTPlanner()
    is_walkable = lambda pos: 0 <= pos[0] < 10 and 0 <= pos[1] < 10

    # R1 at (1, 0) targeting (3, 0) with high priority
    # R2 at (2, 0) targeting (0, 0) with low priority
    robot_ids = ["R1", "R2"]
    current_positions = {"R1": (1, 0), "R2": (2, 0)}
    target_goals = {"R1": (3, 0), "R2": (0, 0)}
    priorities = {"R1": 2.0, "R2": 1.0}

    next_pos = planner.plan_step(
        robot_ids=robot_ids,
        current_positions=current_positions,
        target_goals=target_goals,
        priorities=priorities,
        is_walkable_fn=is_walkable,
    )

    # R1 has higher priority -> pushes R2 or steps into (2, 0) while R2 sidesteps or moves
    assert next_pos["R1"] != next_pos["R2"]
    # No vertex collision
    assert len(set(next_pos.values())) == 2
