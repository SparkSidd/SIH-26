"""Multi-Agent path planning coordinator interface and adapters."""

import time
from typing import Callable, Dict, List, Optional, Set, Tuple
from planning.astar import SpaceTimeAStarPlanner, PlannerResult, PlannerStatusCode
from planning.pibt import PIBTPlanner
from planning.reservation import SpaceTimeReservationTable


class MultiAgentPlanner:
    """Unified multi-agent planning interface supporting Stop-and-Wait, A* (Reservations), and PIBT."""

    def __init__(self, algorithm: str = "pibt", heuristic: str = "manhattan", horizon: int = 80):
        self.algorithm = algorithm
        self.heuristic = heuristic
        self.horizon = horizon
        self.astar = SpaceTimeAStarPlanner(heuristic_type=heuristic, max_horizon=horizon)
        self.pibt = PIBTPlanner()
        self.reservation_table = SpaceTimeReservationTable()
        self.last_planning_latency_ms: float = 0.0

    def plan_fleet_step(
        self,
        robot_ids: List[str],
        current_positions: Dict[str, Tuple[int, int]],
        target_goals: Dict[str, Tuple[int, int]],
        priorities: Dict[str, float],
        is_walkable_fn: Callable[[Tuple[int, int]], bool],
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
        current_step: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """Compute the next single-step target cell for all active robots with microsecond timing."""
        t_start = time.perf_counter()
        next_step_cells: Dict[str, Tuple[int, int]] = {}

        if self.algorithm == "pibt":
            pibt_results = self.pibt.plan_step(
                robot_ids=robot_ids,
                current_positions=current_positions,
                target_goals=target_goals,
                priorities=priorities,
                is_walkable_fn=is_walkable_fn,
                blocked_cells=blocked_cells,
            )
            # Check for any unhandled robots and apply graceful fallback
            for r_id in robot_ids:
                if r_id in pibt_results:
                    next_step_cells[r_id] = pibt_results[r_id]
                else:
                    # Tier 2 Fallback: Space-Time A* search
                    curr_pos = current_positions[r_id]
                    goal_pos = target_goals.get(r_id, curr_pos)
                    res = self.astar.plan(
                        robot_id=r_id,
                        start_pos=curr_pos,
                        goal_pos=goal_pos,
                        is_walkable_fn=is_walkable_fn,
                        blocked_cells=blocked_cells,
                        start_timestep=current_step,
                    )
                    if res.is_success and len(res.path) > 1:
                        next_step_cells[r_id] = res.path[1]
                    else:
                        # Tier 3 Fallback: Stationary WAIT
                        next_step_cells[r_id] = curr_pos

            self.last_planning_latency_ms = (time.perf_counter() - t_start) * 1000.0
            return next_step_cells

        elif self.algorithm == "stop_and_wait":
            # Traditional Reactive Stop-and-Wait Baseline:
            # 1. Each robot determines preferred next step via static unreserved A*
            preferred_next: Dict[str, Tuple[int, int]] = {}
            for r_id in robot_ids:
                curr_pos = current_positions[r_id]
                goal_pos = target_goals.get(r_id, curr_pos)
                res = self.astar.plan(
                    robot_id=r_id,
                    start_pos=curr_pos,
                    goal_pos=goal_pos,
                    is_walkable_fn=is_walkable_fn,
                    blocked_cells=blocked_cells,
                    start_timestep=current_step,
                )
                if res.is_success and len(res.path) > 1:
                    preferred_next[r_id] = res.path[1]
                else:
                    preferred_next[r_id] = curr_pos

            # 2. Sort robots by priority descending
            sorted_robots = sorted(
                robot_ids,
                key=lambda r: priorities.get(r, 1.0),
                reverse=True,
            )

            # 3. Resolve conflicts reactively: lower priority yields and waits
            occupied_next: Dict[Tuple[int, int], str] = {}
            for r_id in sorted_robots:
                curr_pos = current_positions[r_id]
                cand = preferred_next.get(r_id, curr_pos)

                # Vertex conflict: candidate cell already claimed by higher-priority robot
                vertex_conflict = cand in occupied_next
                # Swap conflict: cand is curr_pos of other robot AND other robot is heading to curr_pos
                swap_conflict = False
                for other_pos, other_id in occupied_next.items():
                    if other_pos == curr_pos and cand == current_positions.get(other_id):
                        swap_conflict = True
                        break

                if vertex_conflict or swap_conflict:
                    # Reactive Stop-and-Wait: robot halts in place
                    next_step_cells[r_id] = curr_pos
                    occupied_next[curr_pos] = r_id
                else:
                    next_step_cells[r_id] = cand
                    occupied_next[cand] = r_id

            self.last_planning_latency_ms = (time.perf_counter() - t_start) * 1000.0
            return next_step_cells

        # Default / "astar" / Greedy Space-Time A* with sequential priority reservation
        self.reservation_table.clear()

        # Sort robots by priority descending
        sorted_robots = sorted(
            robot_ids,
            key=lambda r: priorities.get(r, 1.0),
            reverse=True,
        )

        for r_id in sorted_robots:
            curr_pos = current_positions[r_id]
            goal_pos = target_goals.get(r_id, curr_pos)

            res = self.astar.plan(
                robot_id=r_id,
                start_pos=curr_pos,
                goal_pos=goal_pos,
                is_walkable_fn=is_walkable_fn,
                reservation_table=self.reservation_table,
                blocked_cells=blocked_cells,
                start_timestep=current_step,
            )

            if res.is_success and len(res.path) > 1:
                next_cell = res.path[1]
                # Reserve full trajectory in reservation table
                for t_idx, step_pos in enumerate(res.path):
                    self.reservation_table.reserve_vertex(step_pos, current_step + t_idx, r_id)
                next_step_cells[r_id] = next_cell
            else:
                next_step_cells[r_id] = curr_pos
                self.reservation_table.reserve_vertex(curr_pos, current_step + 1, r_id)

        self.last_planning_latency_ms = (time.perf_counter() - t_start) * 1000.0
        return next_step_cells
