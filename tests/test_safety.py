"""Unit tests for Safety Supervisor invariant enforcement and zero-collision proof."""

import pytest
from execution.action import RobotAction, ActionType
from safety.invariants import SafetyInvariants
from safety.supervisor import SafetySupervisor


def test_safety_invariants_vertex_conflict_rejection():
    # Two robots propose same cell (2, 2)
    candidate_actions = {
        "R1": RobotAction(action_type=ActionType.MOVE, target_cell=(2, 2)),
        "R2": RobotAction(action_type=ActionType.MOVE, target_cell=(2, 2)),
    }
    current_pos = {"R1": (1, 2), "R2": (3, 2)}

    report = SafetyInvariants.verify_action_batch(
        candidate_actions=candidate_actions,
        current_positions=current_pos,
        blocked_cells=set(),
        failed_robot_ids=set(),
    )
    assert report.is_safe is False
    assert report.violation_type == "VERTEX_CONFLICT"


def test_safety_invariants_edge_swap_rejection():
    candidate_actions = {
        "R1": RobotAction(action_type=ActionType.MOVE, target_cell=(2, 0)),
        "R2": RobotAction(action_type=ActionType.MOVE, target_cell=(1, 0)),
    }
    current_pos = {"R1": (1, 0), "R2": (2, 0)}

    report = SafetyInvariants.verify_action_batch(
        candidate_actions=candidate_actions,
        current_positions=current_pos,
        blocked_cells=set(),
        failed_robot_ids=set(),
    )
    assert report.is_safe is False
    assert report.violation_type == "EDGE_SWAP_CONFLICT"


def test_supervisor_filter_yields_lower_priority():
    supervisor = SafetySupervisor()
    candidate_actions = {
        "R1": RobotAction(action_type=ActionType.MOVE, target_cell=(2, 2)),
        "R2": RobotAction(action_type=ActionType.MOVE, target_cell=(2, 2)),
    }
    current_pos = {"R1": (1, 2), "R2": (3, 2)}
    priorities = {"R1": 2.0, "R2": 1.0}

    approved = supervisor.filter_actions(
        candidate_actions=candidate_actions,
        current_positions=current_pos,
        blocked_cells=set(),
        failed_robot_ids=set(),
        robot_priorities=priorities,
    )

    # R1 gets cell (2, 2)
    assert approved["R1"].target_cell == (2, 2)
    # R2 is forced to WAIT in its current position (3, 2)
    assert approved["R2"].action_type == ActionType.WAIT
    assert approved["R2"].target_cell == (3, 2)
    assert supervisor.total_interventions == 1
