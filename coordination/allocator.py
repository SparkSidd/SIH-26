from collections import deque
import math
from typing import Callable, Dict, List, Optional, Set, Tuple
try:
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from coordination.congestion import CongestionModel
from coordination.eta import ETAModel
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState


def _generate_manhattan_path(start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Generate a simple rectilinear path between two points for ETA estimation."""
    path = [start]
    curr_x, curr_y = start
    end_x, end_y = end

    # Move horizontally first, then vertically
    step_x = 1 if end_x >= curr_x else -1
    for x in range(curr_x + step_x, end_x + step_x, step_x):
        path.append((x, curr_y))
        curr_x = x

    step_y = 1 if end_y >= curr_y else -1
    for y in range(curr_y + step_y, end_y + step_y, step_y):
        path.append((curr_x, y))

    return path


_PATH_CACHE: Dict[Tuple[Tuple[int, int], Tuple[int, int]], List[Tuple[int, int]]] = {}

def _generate_walkable_path(
    start: Tuple[int, int],
    end: Tuple[int, int],
    is_walkable_fn: Optional[Callable[[Tuple[int, int]], bool]] = None,
) -> List[Tuple[int, int]]:
    """Generate shortest obstacle-aware walkable path between two points, falling back to rectilinear."""
    if is_walkable_fn is None or start == end:
        return _generate_manhattan_path(start, end)

    cache_key = (start, end)
    if cache_key in _PATH_CACHE:
        return list(_PATH_CACHE[cache_key])

    queue = deque([start])
    visited: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    found = False

    while queue:
        curr = queue.popleft()
        if curr == end:
            found = True
            break
        x, y = curr
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nbr = (x + dx, y + dy)
            if nbr not in visited:
                if nbr == end or is_walkable_fn(nbr):
                    visited[nbr] = curr
                    queue.append(nbr)

    if not found:
        return _generate_manhattan_path(start, end)

    path = []
    curr = end
    while curr is not None:
        path.append(curr)
        curr = visited[curr]
    path.reverse()
    _PATH_CACHE[cache_key] = path
    return list(path)


class BaselineNearestAllocator:
    """Baseline 1/2: Greedily assigns pending task to nearest idle robot based purely on Manhattan distance."""

    @staticmethod
    def allocate(
        unassigned_tasks: List[Task],
        robots: Dict[str, Robot],
        congestion_model: Optional[CongestionModel] = None,
        is_walkable_fn: Optional[Callable[[Tuple[int, int]], bool]] = None,
        all_tasks: Optional[Dict[str, Task]] = None,
    ) -> List[Tuple[str, str]]:
        """Return list of (robot_id, task_id) assignments."""
        assignments: List[Tuple[str, str]] = []
        available_robots = [
            r for r in robots.values()
            if r.current_task_id is None and r.is_healthy and r.state != RobotState.FAILED
        ]

        for task in unassigned_tasks:
            if not available_robots:
                break

            best_robot = min(
                available_robots,
                key=lambda r: abs(r.position[0] - task.pickup[0]) + abs(r.position[1] - task.pickup[1]),
            )

            assignments.append((best_robot.id, task.id))
            available_robots.remove(best_robot)

        return assignments


class FleetAwareTaskAllocator:
    """Fleet-Aware Closed-Loop Task Allocator.
    
    Evaluates marginal cost considering distance, execution-aware ETA,
    corridor congestion along the path, battery reserves, workload balance,
    and rolling handover task lookahead.
    """

    def __init__(
        self,
        w_distance: float = 1.2,
        w_eta: float = 1.2,
        w_congestion: float = 1.5,
        w_battery: float = 0.5,
        w_deadline: float = 2.0,
        w_imbalance: float = 0.0,
    ):
        self.w_distance = w_distance
        self.w_eta = w_eta
        self.w_congestion = w_congestion
        self.w_battery = w_battery
        self.w_deadline = w_deadline
        self.w_imbalance = w_imbalance
        self.eta_model = ETAModel(nominal_speed=10.0, turn_penalty_sec=0.1, congestion_weight=0.08)

    def allocate(
        self,
        unassigned_tasks: List[Task],
        robots: Dict[str, Robot],
        congestion_model: Optional[CongestionModel] = None,
        is_walkable_fn: Optional[Callable[[Tuple[int, int]], bool]] = None,
        all_tasks: Optional[Dict[str, Task]] = None,
    ) -> List[Tuple[str, str]]:
        """Compute optimal fleet task assignment considering multi-criteria marginal cost and rolling handover."""
        assignments: List[Tuple[str, str]] = []

        # Find idle healthy robots
        available_candidates: List[Tuple[Robot, Tuple[int, int], float]] = []
        for r in robots.values():
            if not r.is_healthy or r.battery.is_critical or r.state == RobotState.FAILED:
                continue

            if r.current_task_id is None:
                # Fully idle robot available immediately at its current position
                available_candidates.append((r, r.position, 0.0))
            elif r.next_task_id is None and all_tasks is not None and r.current_task_id in all_tasks:
                # Rolling Handover Lookahead:
                # If robot is currently carrying payload and within 6 steps of dropoff,
                # it is a prime candidate to pre-assign the next task from its dropoff station!
                cur_t = all_tasks[r.current_task_id]
                if cur_t.state == TaskState.PICKED_UP or getattr(r, "has_payload", False):
                    dist_to_drop = abs(r.position[0] - cur_t.dropoff[0]) + abs(r.position[1] - cur_t.dropoff[1])
                    if dist_to_drop <= 10:
                        start_delay = float(dist_to_drop) * 0.1  # 0.1s per cell tick
                        available_candidates.append((r, cur_t.dropoff, start_delay))

        if not available_candidates:
            return assignments

        # Calculate minimum tasks completed for fleet workload balancing
        healthy_robots = [r for r in robots.values() if r.is_healthy]
        min_completed = min((getattr(r, "tasks_completed", 0) for r in healthy_robots), default=0)

        # Sort tasks by priority descending and earliest deadline
        sorted_tasks = sorted(
            unassigned_tasks,
            key=lambda t: (t.priority, -(t.deadline or 999999)),
            reverse=True,
        )

        def _compute_cost(candidate: Tuple[Robot, Tuple[int, int], float], task: Task) -> float:
            robot, start_pos, start_delay = candidate

            # 1. Path Generation & Physical Distance (Obstacle-Aware Walkable BFS)
            path_to_pickup = _generate_walkable_path(start_pos, task.pickup, is_walkable_fn)
            path_pickup_to_drop = _generate_walkable_path(task.pickup, task.dropoff, is_walkable_fn)
            total_distance = (len(path_to_pickup) - 1) + (len(path_pickup_to_drop) - 1)

            # 2. Execution-Aware ETA (includes turns, wait steps, and corridor traffic)
            eta_pickup = self.eta_model.estimate_eta(path_to_pickup, congestion_model)
            eta_drop = self.eta_model.estimate_eta(path_pickup_to_drop, congestion_model)
            total_eta = start_delay + eta_pickup + eta_drop

            # 3. Path Congestion Along Routes
            path_cong = 0.0
            if congestion_model is not None:
                path_cong = congestion_model.get_path_congestion(path_to_pickup) + \
                            congestion_model.get_path_congestion(path_pickup_to_drop)

            # 4. Fleet Workload Balance Penalty (prevents task starvation of other AMRs)
            completed_count = getattr(robot, "tasks_completed", 0)
            imbalance = max(0.0, float(completed_count - min_completed))

            # 5. Battery Reserves Penalty
            battery_penalty = max(0.0, (100.0 - robot.battery.current_charge) / 25.0)

            # 6. Task Urgency Discount
            urgency_discount = (task.priority - 1.0) * 1.5

            empty_transit_dist = float(len(path_to_pickup) - 1)

            return (
                self.w_eta * total_eta
                + 0.15 * empty_transit_dist
                + self.w_congestion * (path_cong * 0.05)
                + self.w_imbalance * imbalance
                + self.w_battery * battery_penalty
                - urgency_discount
            )

        # Global minimum fleet cost assignment via Hungarian algorithm if multiple candidates
        if HAS_SCIPY and len(available_candidates) > 1 and len(sorted_tasks) > 1:
            num_cands = len(available_candidates)
            num_tasks = min(len(sorted_tasks), max(num_cands, 24))
            cand_tasks = sorted_tasks[:num_tasks]

            cost_matrix = np.zeros((num_cands, num_tasks), dtype=np.float64)
            for i, cand in enumerate(available_candidates):
                for j, t in enumerate(cand_tasks):
                    cost_matrix[i, j] = _compute_cost(cand, t)

            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            for r_i, c_j in zip(row_ind, col_ind):
                cand_robot, _, _ = available_candidates[r_i]
                assigned_task = cand_tasks[c_j]
                assignments.append((cand_robot.id, assigned_task.id))
            return assignments

        # Greedy fallback if single robot or single task
        for task in sorted_tasks:
            if not available_candidates:
                break

            best_candidate = None
            lowest_cost = float("inf")

            for candidate in available_candidates:
                cost = _compute_cost(candidate, task)
                if cost < lowest_cost:
                    lowest_cost = cost
                    best_candidate = candidate

            if best_candidate is not None:
                robot, _, _ = best_candidate
                assignments.append((robot.id, task.id))
                available_candidates.remove(best_candidate)

        return assignments
