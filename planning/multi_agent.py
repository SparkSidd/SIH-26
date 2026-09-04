"""Multi-Agent path planning coordinator interface and adapters."""

from typing import Callable, Dict, List, Optional, Set, Tuple
from planning.astar import SpaceTimeAStarPlanner, PlannerResult, PlannerStatusCode
from planning.pibt import PIBTPlanner
from planning.reservation import SpaceTimeReservationTable


class MultiAgentPlanner:
    """Unified multi-agent planning interface supporting A*, Space-Time Reservation, and PIBT."""

    def __init__(self, algorithm: str = "pibt", heuristic: str = "manhattan", horizon: int = 80):
        self.algorithm = algorithm
        self.heuristic = heuristic
        self.horizon = horizon
        self.astar = SpaceTimeAStarPlanner(heuristic_type=heuristic, max_horizon=horizon)
        self.pibt = PIBTPlanner()
        self.reservation_table = SpaceTimeReservationTable()

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
        """Compute the next single-step target cell for all active robots with graceful degradation."""
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

            return next_step_cells

        # Space-Time A* with sequential priority reservation
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

        return next_step_cells
