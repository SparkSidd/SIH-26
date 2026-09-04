"""Wait-For-Graph (WFG) cycle analysis and deadlock detection."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class DeadlockReport:
    """Outcome of deadlock cycle detection."""
    is_deadlocked: bool
    cycles: List[List[str]]  # Lists of robot IDs involved in cycles


class DeadlockDetector:
    """Detects mutual waiting and cyclic deadlocks using a directed Wait-For Graph."""

    @staticmethod
    def detect_deadlocks(
        current_positions: Dict[str, Tuple[int, int]],
        desired_targets: Dict[str, Tuple[int, int]],
        wait_threshold: int = 3,
        robot_wait_steps: Optional[Dict[str, int]] = None,
    ) -> DeadlockReport:
        """Construct Wait-For Graph and detect directed cycles."""
        # WFG: waiting_robot -> robot_occupying_target
        graph: Dict[str, Set[str]] = defaultdict(set)
        pos_to_robot = {pos: r_id for r_id, pos in current_positions.items()}

        wait_steps = robot_wait_steps or {}

        for r_id, target in desired_targets.items():
            if target != current_positions.get(r_id):
                # If target is occupied by someone else, r_id is waiting on them
                if target in pos_to_robot:
                    occupant = pos_to_robot[target]
                    if occupant != r_id and wait_steps.get(r_id, 0) >= wait_threshold:
                        graph[r_id].add(occupant)

        # Detect cycles using DFS
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: List[List[str]] = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, list(path))
                elif neighbor in rec_stack:
                    # Cycle detected
                    idx = path.index(neighbor)
                    cycles.append(path[idx:])

            rec_stack.remove(node)

        for node in list(graph.keys()):
            if node not in visited:
                dfs(node, [])

        return DeadlockReport(
            is_deadlocked=len(cycles) > 0,
            cycles=cycles,
        )
