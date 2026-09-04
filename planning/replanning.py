"""Dynamic path repair and local rerouting under unexpected blockages."""

from typing import Callable, List, Optional, Set, Tuple
from planning.astar import SpaceTimeAStarPlanner, PlannerResult, PlannerStatusCode
from planning.reservation import SpaceTimeReservationTable


class PathReplanner:
    """Handles adaptive local path repair when current route becomes blocked or conflicted."""

    def __init__(self, planner: Optional[SpaceTimeAStarPlanner] = None):
        self.planner = planner or SpaceTimeAStarPlanner()

    def replan_path(
        self,
        robot_id: str,
        current_pos: Tuple[int, int],
        goal_pos: Tuple[int, int],
        is_walkable_fn: Callable[[Tuple[int, int]], bool],
        reservation_table: Optional[SpaceTimeReservationTable] = None,
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
        current_step: int = 0,
    ) -> PlannerResult:
        """Trigger A* replanning with updated blockage and reservation knowledge."""
        return self.planner.plan(
            robot_id=robot_id,
            start_pos=current_pos,
            goal_pos=goal_pos,
            is_walkable_fn=is_walkable_fn,
            reservation_table=reservation_table,
            blocked_cells=blocked_cells,
            start_timestep=current_step,
        )
