"""Priority Inheritance Backtracking (PIBT) Decentralized Multi-Agent Planner."""

import math
import random
from typing import Callable, Dict, List, Optional, Set, Tuple


class PIBTPlanner:
    """Decentralized Priority Inheritance Backtracking (PIBT) Planner.
    
    Generates 1-step collision-free movement decisions for the entire fleet
    by recursively pushing lower-priority agents out of conflicting cells.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def plan_step(
        self,
        robot_ids: List[str],
        current_positions: Dict[str, Tuple[int, int]],
        target_goals: Dict[str, Tuple[int, int]],
        priorities: Dict[str, float],
        is_walkable_fn: Callable[[Tuple[int, int]], bool],
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
    ) -> Dict[str, Tuple[int, int]]:
        """Compute next 1-step movement for each robot using PIBT."""
        blocked = blocked_cells or set()
        
        # Next cell decisions: robot_id -> next_pos
        next_positions: Dict[str, Tuple[int, int]] = {}
        # Reserved target cells: target_pos -> occupying_robot_id
        reserved_targets: Dict[Tuple[int, int], str] = {}
        
        # Sort robots by priority descending
        sorted_robots = sorted(
            robot_ids,
            key=lambda r: (priorities.get(r, 1.0), self.rng.random()),
            reverse=True,
        )

        for robot_id in sorted_robots:
            if robot_id not in next_positions:
                self._pibt_resolve(
                    robot_id=robot_id,
                    current_positions=current_positions,
                    target_goals=target_goals,
                    next_positions=next_positions,
                    reserved_targets=reserved_targets,
                    is_walkable_fn=is_walkable_fn,
                    blocked_cells=blocked,
                )

        # Fill any unresolved robots with their current position (WAIT)
        for r_id in robot_ids:
            if r_id not in next_positions:
                next_positions[r_id] = current_positions[r_id]

        return next_positions

    def _pibt_resolve(
        self,
        robot_id: str,
        current_positions: Dict[str, Tuple[int, int]],
        target_goals: Dict[str, Tuple[int, int]],
        next_positions: Dict[str, Tuple[int, int]],
        reserved_targets: Dict[Tuple[int, int], str],
        is_walkable_fn: Callable[[Tuple[int, int]], bool],
        blocked_cells: Set[Tuple[int, int]],
        visited_in_chain: Optional[Set[str]] = None,
    ) -> bool:
        """Recursive priority inheritance attempt to place robot_id into its best candidate cell."""
        if visited_in_chain is None:
            visited_in_chain = set()

        if robot_id in visited_in_chain:
            return False

        visited_in_chain.add(robot_id)
        curr_pos = current_positions[robot_id]
        goal_pos = target_goals.get(robot_id, curr_pos)

        # Get candidate next cells (4-neighbors + wait)
        candidates = [
            (curr_pos[0] + 1, curr_pos[1]),
            (curr_pos[0] - 1, curr_pos[1]),
            (curr_pos[0], curr_pos[1] + 1),
            (curr_pos[0], curr_pos[1] - 1),
            curr_pos,
        ]

        # Filter walkable & unblocked
        valid_candidates = [c for c in candidates if is_walkable_fn(c) and c not in blocked_cells]

        # Sort candidates by distance to goal
        valid_candidates.sort(
            key=lambda c: (
                abs(c[0] - goal_pos[0]) + abs(c[1] - goal_pos[1]),
                0 if c != curr_pos else 0.1,  # Prefer moving over staying if distance is equal
            )
        )

        for candidate in valid_candidates:
            # Check if candidate is already reserved by an agent
            if candidate in reserved_targets:
                continue

            # Check edge swap conflict with already decided agents
            edge_conflict = False
            for other_id, other_next in next_positions.items():
                if other_next == curr_pos and current_positions.get(other_id) == candidate and candidate != curr_pos:
                    edge_conflict = True
                    break
            if edge_conflict:
                continue

            # Tentatively reserve
            reserved_targets[candidate] = robot_id
            next_positions[robot_id] = candidate

            # Check if candidate is currently occupied by another robot that hasn't moved yet
            occupant_id = None
            for other_id, other_curr in current_positions.items():
                if other_id != robot_id and other_curr == candidate and other_id not in next_positions:
                    occupant_id = other_id
                    break

            if occupant_id is None:
                # Target cell is completely free
                return True

            # Target cell has an occupant -> Inherit priority and push occupant recursively
            pushed_success = self._pibt_resolve(
                robot_id=occupant_id,
                current_positions=current_positions,
                target_goals=target_goals,
                next_positions=next_positions,
                reserved_targets=reserved_targets,
                is_walkable_fn=is_walkable_fn,
                blocked_cells=blocked_cells,
                visited_in_chain=set(visited_in_chain),
            )

            if pushed_success:
                return True

            # Backtrack if push failed
            del reserved_targets[candidate]
            del next_positions[robot_id]

        # Could not find any valid move, stay at current position if possible
        if curr_pos not in reserved_targets:
            reserved_targets[curr_pos] = robot_id
            next_positions[robot_id] = curr_pos
            return True

        return False
