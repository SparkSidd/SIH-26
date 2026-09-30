"""Event-driven replanning engine with explicit triggers, cooldown, and telemetry.

Borrows event-driven replanning design patterns (inspired by LCBA) to eliminate
blind periodic replanning loops and provide traceable trigger categorization.
"""

from collections import defaultdict
from enum import Enum, auto
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from planning.astar import SpaceTimeAStarPlanner, PlannerResult, PlannerStatusCode
from planning.reservation import SpaceTimeReservationTable


class ReplanningTrigger(Enum):
    TASK_COMPLETED = auto()
    NEW_URGENT_TASK = auto()
    TASK_TIMEOUT = auto()
    ROBOT_FAILURE = auto()
    BATTERY_THRESHOLD = auto()
    DYNAMIC_BLOCKAGE = auto()
    RESERVATION_INVALIDATION = auto()
    COMMUNICATION_TOPOLOGY_CHANGE = auto()
    DEADLOCK_DETECTED = auto()
    PATH_DEVIATION = auto()
    HEARTBEAT_TIMEOUT = auto()


class EventDrivenReplanner:
    """Manages event-driven replanning triggers, deduplication, cooldowns, and audit telemetry."""

    def __init__(
        self,
        planner: Optional[SpaceTimeAStarPlanner] = None,
        cooldown_steps: int = 3,
    ):
        self.planner = planner or SpaceTimeAStarPlanner()
        self.cooldown_steps = cooldown_steps

        # Cooldown tracker: robot_id -> last_replan_step
        self.last_replan_step: Dict[str, int] = {}

        # Telemetry metrics
        self.replans_by_trigger: Dict[str, int] = defaultdict(int)
        self.planner_invocations: int = 0
        self.successful_replans: int = 0
        self.failed_replans: int = 0
        self.unnecessary_replans_avoided: int = 0
        self.replanning_latencies_ms: List[float] = []

    def should_replan(
        self,
        robot_id: str,
        trigger: ReplanningTrigger,
        current_step: int,
        is_urgent: bool = False,
    ) -> bool:
        """Evaluate if replanning should proceed or be suppressed by cooldown/deduplication."""
        if is_urgent or trigger in (ReplanningTrigger.ROBOT_FAILURE, ReplanningTrigger.DYNAMIC_BLOCKAGE, ReplanningTrigger.DEADLOCK_DETECTED):
            # Critical triggers bypass normal cooldown
            return True

        last_step = self.last_replan_step.get(robot_id, -999)
        if current_step - last_step < self.cooldown_steps:
            self.unnecessary_replans_avoided += 1
            return False

        return True

    def trigger_replan(
        self,
        robot_id: str,
        trigger: ReplanningTrigger,
        current_pos: Tuple[int, int],
        goal_pos: Tuple[int, int],
        is_walkable_fn: Callable[[Tuple[int, int]], bool],
        reservation_table: Optional[SpaceTimeReservationTable] = None,
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
        current_step: int = 0,
        is_urgent: bool = False,
    ) -> PlannerResult:
        """Execute event-driven replan, recording trigger attribution and performance."""
        if not self.should_replan(robot_id, trigger, current_step, is_urgent):
            # Return suppressed/skipped status
            return PlannerResult(
                status=PlannerStatusCode.NO_PATH,
                path=[],
                expanded_nodes=0,
                computation_time_ms=0.0,
                message="Replanning skipped: within cooldown window",
            )

        self.planner_invocations += 1
        self.replans_by_trigger[trigger.name] += 1
        self.last_replan_step[robot_id] = current_step

        t0 = time.perf_counter()
        result = self.planner.plan(
            robot_id=robot_id,
            start_pos=current_pos,
            goal_pos=goal_pos,
            is_walkable_fn=is_walkable_fn,
            reservation_table=reservation_table,
            blocked_cells=blocked_cells,
            start_timestep=current_step,
        )
        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.replanning_latencies_ms.append(t_elapsed_ms)

        if result.is_success:
            self.successful_claims = getattr(self, "successful_claims", 0)
            self.successful_replans += 1
        else:
            self.failed_replans += 1

        return result

    def get_telemetry(self) -> Dict[str, Any]:
        """Return replanning audit telemetry."""
        mean_latency = (sum(self.replanning_latencies_ms) / len(self.replanning_latencies_ms)) if self.replanning_latencies_ms else 0.0
        return {
            "planner_invocations": self.planner_invocations,
            "successful_replans": self.successful_replans,
            "failed_replans": self.failed_replans,
            "unnecessary_replans_avoided": self.unnecessary_replans_avoided,
            "mean_replanning_latency_ms": round(mean_latency, 2),
            "replans_by_trigger": dict(self.replans_by_trigger),
        }


# Backward-compatible PathReplanner alias
class PathReplanner(EventDrivenReplanner):
    """Backward-compatible wrapper for existing call sites."""

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
        return self.trigger_replan(
            robot_id=robot_id,
            trigger=ReplanningTrigger.DYNAMIC_BLOCKAGE,
            current_pos=current_pos,
            goal_pos=goal_pos,
            is_walkable_fn=is_walkable_fn,
            reservation_table=reservation_table,
            blocked_cells=blocked_cells,
            current_step=current_step,
            is_urgent=True,
        )
