"""Formal safety invariants and runtime constraint assertions."""

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from execution.action import RobotAction, ActionType


class SafetyViolationError(RuntimeError):
    """Raised when an unrecoverable safety invariant is violated."""
    pass


@dataclass
class SafetyInvariantReport:
    """Outcome of invariant verification."""
    is_safe: bool
    violation_type: str = ""
    violating_robots: List[str] = None
    details: str = ""


class SafetyInvariants:
    """Enforces mathematical safety invariants across all candidate robot actions."""

    @staticmethod
    def verify_action_batch(
        candidate_actions: Dict[str, RobotAction],
        current_positions: Dict[str, Tuple[int, int]],
        blocked_cells: Set[Tuple[int, int]],
        failed_robot_ids: Set[str],
    ) -> SafetyInvariantReport:
        """Verify that a batch of proposed robot actions violates NO safety invariants."""
        # Target cells mapped to the proposing robot: target_cell -> robot_id
        target_occupancy: Dict[Tuple[int, int], str] = {}

        for robot_id, action in candidate_actions.items():
            target = action.target_cell
            curr_pos = current_positions.get(robot_id, target)

            # Invariant 1: Failed robot cannot move
            if robot_id in failed_robot_ids and target != curr_pos:
                return SafetyInvariantReport(
                    is_safe=False,
                    violation_type="FAILED_ROBOT_MOTION",
                    violating_robots=[robot_id],
                    details=f"Robot {robot_id} is FAILED but attempted to move from {curr_pos} to {target}",
                )

            # Invariant 2: Cannot enter physically blocked cell
            if target in blocked_cells:
                return SafetyInvariantReport(
                    is_safe=False,
                    violation_type="BLOCKED_CELL_ENTRY",
                    violating_robots=[robot_id],
                    details=f"Robot {robot_id} attempted entry into blocked cell {target}",
                )

            # Invariant 3: Vertex Conflict (Two robots attempting the same target cell)
            if target in target_occupancy:
                other_robot = target_occupancy[target]
                return SafetyInvariantReport(
                    is_safe=False,
                    violation_type="VERTEX_CONFLICT",
                    violating_robots=[robot_id, other_robot],
                    details=f"Robots {robot_id} and {other_robot} both targeted cell {target}",
                )
            target_occupancy[target] = robot_id

            # Invariant 4: Edge Swap Conflict (Robot A moves A->B while Robot B moves B->A)
            for other_id, other_action in candidate_actions.items():
                if other_id == robot_id:
                    continue
                other_curr = current_positions.get(other_id, other_action.target_cell)
                other_target = other_action.target_cell
                if target == other_curr and other_target == curr_pos and target != curr_pos:
                    return SafetyInvariantReport(
                        is_safe=False,
                        violation_type="EDGE_SWAP_CONFLICT",
                        violating_robots=[robot_id, other_id],
                        details=f"Edge swap collision between {robot_id} ({curr_pos}->{target}) and {other_id} ({other_curr}->{other_target})",
                    )

        return SafetyInvariantReport(is_safe=True)
