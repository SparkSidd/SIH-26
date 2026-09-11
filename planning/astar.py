"""Space-Time A* Planner with explicit outcome status codes and reservation awareness."""

from dataclasses import dataclass, field
from enum import Enum, auto
import heapq
import math
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import numpy as np

from planning.reservation import SpaceTimeReservationTable


class PlannerStatusCode(Enum):
    SUCCESS = auto()
    PARTIAL_PLAN = auto()
    NO_PATH = auto()
    TIMEOUT = auto()
    INVALID_PLAN = auto()
    STALE_STATE = auto()


@dataclass
class PlannerResult:
    """Standardized outcome returned by all trajectory and path planners."""
    status: PlannerStatusCode
    path: List[Tuple[int, int]] = field(default_factory=list)
    cost: float = 0.0
    computation_time_ms: float = 0.0
    expanded_nodes: int = 0
    message: str = ""

    @property
    def is_success(self) -> bool:
        return self.status in (PlannerStatusCode.SUCCESS, PlannerStatusCode.PARTIAL_PLAN) and len(self.path) > 0


class SpaceTimeAStarPlanner:
    """Computes collision-free shortest space-time paths in 3D (x, y, t)."""

    def __init__(
        self,
        heuristic_type: str = "manhattan",
        max_horizon: int = 80,
        timeout_ms: float = 60.0,
    ):
        self.heuristic_type = heuristic_type
        self.max_horizon = max_horizon
        self.timeout_ms = timeout_ms

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Admissible heuristic calculation."""
        if self.heuristic_type == "euclidean":
            return math.hypot(a[0] - b[0], a[1] - b[1])
        # Default: Manhattan
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def plan(
        self,
        robot_id: str,
        start_pos: Tuple[int, int],
        goal_pos: Tuple[int, int],
        is_walkable_fn: Callable[[Tuple[int, int]], bool],
        reservation_table: Optional[SpaceTimeReservationTable] = None,
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
        start_timestep: int = 0,
        congestion_model: Optional[Any] = None,
        preferred_directions: Optional[Dict[Tuple[int, int], Tuple[int, int]]] = None,
    ) -> PlannerResult:
        """Find optimal space-time path from start to goal considering kinodynamics and congestion."""
        t_start = time.perf_counter()
        blocked = blocked_cells or set()

        if start_pos == goal_pos:
            return PlannerResult(
                status=PlannerStatusCode.SUCCESS,
                path=[start_pos],
                cost=0.0,
                computation_time_ms=(time.perf_counter() - t_start) * 1000.0,
                message="Already at goal",
            )

        if not is_walkable_fn(start_pos) or not is_walkable_fn(goal_pos) or goal_pos in blocked:
            return PlannerResult(
                status=PlannerStatusCode.NO_PATH,
                path=[],
                computation_time_ms=(time.perf_counter() - t_start) * 1000.0,
                message="Start or goal position is not walkable",
            )

        # Priority Queue: (f_score, h_score, timestep, (x, y))
        open_set = []
        start_h = self.heuristic(start_pos, goal_pos)
        heapq.heappush(open_set, (start_h, start_h, 0, start_pos))

        # g_score: (pos, timestep) -> g_cost
        g_scores: Dict[Tuple[Tuple[int, int], int], float] = {(start_pos, 0): 0.0}
        
        # came_from: (pos, timestep) -> (prev_pos, prev_timestep)
        came_from: Dict[Tuple[Tuple[int, int], int], Tuple[Tuple[int, int], int]] = {}

        best_partial_node = (start_pos, 0)
        best_partial_h = start_h
        expanded_nodes = 0

        while open_set:
            # Check timeout
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            if elapsed_ms > self.timeout_ms:
                # Return best partial plan towards goal
                partial_path = self._reconstruct_path(came_from, best_partial_node)
                return PlannerResult(
                    status=PlannerStatusCode.TIMEOUT,
                    path=partial_path,
                    cost=len(partial_path),
                    computation_time_ms=elapsed_ms,
                    expanded_nodes=expanded_nodes,
                    message="Planning timeout exceeded; partial path returned",
                )

            current_f, current_h, t_rel, current_pos = heapq.heappop(open_set)
            t_abs = start_timestep + t_rel
            expanded_nodes += 1

            # Goal test
            if current_pos == goal_pos:
                full_path = self._reconstruct_path(came_from, (current_pos, t_rel))
                return PlannerResult(
                    status=PlannerStatusCode.SUCCESS,
                    path=full_path,
                    cost=len(full_path) - 1,
                    computation_time_ms=(time.perf_counter() - t_start) * 1000.0,
                    expanded_nodes=expanded_nodes,
                    message="Full optimal path found",
                )

            # Track best partial state
            if current_h < best_partial_h:
                best_partial_h = current_h
                best_partial_node = (current_pos, t_rel)

            if t_rel >= self.max_horizon:
                continue

            # Generate actions: Move to 4-neighbors; only WAIT if avoiding dynamic reservations
            neighbors = [
                (current_pos[0] + 1, current_pos[1]),
                (current_pos[0] - 1, current_pos[1]),
                (current_pos[0], current_pos[1] + 1),
                (current_pos[0], current_pos[1] - 1),
            ]
            if reservation_table is not None:
                neighbors.append(current_pos)  # Wait in place

            next_t_rel = t_rel + 1
            next_t_abs = t_abs + 1

            for next_pos in neighbors:
                if not is_walkable_fn(next_pos) or next_pos in blocked:
                    continue

                # Check space-time reservation table
                if reservation_table is not None:
                    # Check vertex reservation
                    if reservation_table.is_vertex_reserved(next_pos, next_t_abs, exclude_robot_id=robot_id):
                        continue
                    # Check edge swap reservation
                    if reservation_table.is_edge_reserved(current_pos, next_pos, next_t_abs, exclude_robot_id=robot_id):
                        continue

                # Execution-Aware step cost: distance + turn penalty + congestion + flow
                step_cost = 1.0 if next_pos != current_pos else 1.2
                if (current_pos, t_rel) in came_from and next_pos != current_pos:
                    prev_pos, _ = came_from[(current_pos, t_rel)]
                    dx_prev = current_pos[0] - prev_pos[0]
                    dy_prev = current_pos[1] - prev_pos[1]
                    dx_new = next_pos[0] - current_pos[0]
                    dy_new = next_pos[1] - current_pos[1]
                    if (dx_prev, dy_prev) != (dx_new, dy_new):
                        step_cost += 0.2  # Soft turn penalty

                if congestion_model is not None and next_pos != current_pos:
                    cell_cong = congestion_model.get_cell_congestion(next_pos)
                    step_cost += 0.5 * min(cell_cong, 20.0)

                if preferred_directions is not None and next_pos != current_pos:
                    pref_dir = preferred_directions.get(current_pos) or preferred_directions.get(next_pos)
                    if pref_dir is not None:
                        actual_dir = (next_pos[0] - current_pos[0], next_pos[1] - current_pos[1])
                        if actual_dir == (-pref_dir[0], -pref_dir[1]):
                            rem_dist = abs(current_pos[0] - goal_pos[0]) + abs(current_pos[1] - goal_pos[1])
                            step_cost += 2.4 if rem_dist > 2 else 0.3
                        elif actual_dir == pref_dir:
                            step_cost -= 0.15  # With-flow incentive

                tentative_g = g_scores[(current_pos, t_rel)] + step_cost
                state_key = (next_pos, next_t_rel)

                if state_key not in g_scores or tentative_g < g_scores[state_key]:
                    g_scores[state_key] = tentative_g
                    h_cost = self.heuristic(next_pos, goal_pos)
                    f_cost = tentative_g + h_cost
                    came_from[state_key] = (current_pos, t_rel)
                    heapq.heappush(open_set, (f_cost, h_cost, next_t_rel, next_pos))

        # Open set exhausted without reaching goal
        if best_partial_node[0] != start_pos:
            partial_path = self._reconstruct_path(came_from, best_partial_node)
            return PlannerResult(
                status=PlannerStatusCode.PARTIAL_PLAN,
                path=partial_path,
                cost=len(partial_path),
                computation_time_ms=(time.perf_counter() - t_start) * 1000.0,
                expanded_nodes=expanded_nodes,
                message="Partial path towards goal found",
            )

        return PlannerResult(
            status=PlannerStatusCode.NO_PATH,
            path=[],
            computation_time_ms=(time.perf_counter() - t_start) * 1000.0,
            expanded_nodes=expanded_nodes,
            message="No feasible path to goal",
        )

    def _reconstruct_path(
        self,
        came_from: Dict[Tuple[Tuple[int, int], int], Tuple[Tuple[int, int], int]],
        current_node: Tuple[Tuple[int, int], int],
    ) -> List[Tuple[int, int]]:
        """Backtrack from end state to extract path coordinates."""
        path = [current_node[0]]
        curr = current_node
        while curr in came_from:
            curr = came_from[curr]
            path.append(curr[0])
        path.reverse()
        return path
