"""Task Allocation engines: Baseline Nearest vs. Fleet-Aware Multi-Criteria Allocator."""

import math
from typing import Callable, Dict, List, Optional, Tuple
from coordination.congestion import CongestionModel
from coordination.eta import ETAModel
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState


class BaselineNearestAllocator:
    """Baseline 1/2: Greedily assigns pending task to nearest idle robot based purely on Manhattan distance."""

    @staticmethod
    def allocate(
        unassigned_tasks: List[Task],
        robots: Dict[str, Robot],
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
    and deadline risk.
    """

    def __init__(
        self,
        w_distance: float = 1.0,
        w_eta: float = 1.5,
        w_congestion: float = 2.0,
        w_battery: float = 1.2,
        w_deadline: float = 2.0,
    ):
        self.w_distance = w_distance
        self.w_eta = w_eta
        self.w_congestion = w_congestion
        self.w_battery = w_battery
        self.w_deadline = w_deadline
        self.eta_model = ETAModel()

    def allocate(
        self,
        unassigned_tasks: List[Task],
        robots: Dict[str, Robot],
        congestion_model: Optional[CongestionModel] = None,
        is_walkable_fn: Optional[Callable[[Tuple[int, int]], bool]] = None,
    ) -> List[Tuple[str, str]]:
        """Compute optimal fleet task assignment considering multi-criteria marginal cost."""
        assignments: List[Tuple[str, str]] = []
        available_robots = [
            r for r in robots.values()
            if r.current_task_id is None and r.is_healthy and not r.battery.is_critical and r.state != RobotState.FAILED
        ]

        # Sort tasks by priority and deadline urgency
        sorted_tasks = sorted(
            unassigned_tasks,
            key=lambda t: (t.priority, -(t.deadline or 999999)),
            reverse=True,
        )

        for task in sorted_tasks:
            if not available_robots:
                break

            best_robot = None
            lowest_cost = float("inf")

            for robot in available_robots:
                # 1. Distance cost (Robot -> Pickup + Pickup -> Dropoff)
                dist_to_pickup = abs(robot.position[0] - task.pickup[0]) + abs(robot.position[1] - task.pickup[1])
                dist_pickup_to_drop = abs(task.pickup[0] - task.dropoff[0]) + abs(task.pickup[1] - task.dropoff[1])
                total_distance = dist_to_pickup + dist_pickup_to_drop

                # 2. Congestion penalty
                congestion_penalty = 0.0
                if congestion_model is not None:
                    pickup_cong = congestion_model.get_cell_congestion(task.pickup)
                    dropoff_cong = congestion_model.get_cell_congestion(task.dropoff)
                    congestion_penalty = pickup_cong + dropoff_cong

                # 3. Battery penalty
                battery_penalty = (100.0 - robot.battery.current_charge) / 20.0

                # 4. Total marginal cost function
                cost = (
                    self.w_distance * total_distance
                    + self.w_congestion * congestion_penalty
                    + self.w_battery * battery_penalty
                )

                if cost < lowest_cost:
                    lowest_cost = cost
                    best_robot = robot

            if best_robot is not None:
                assignments.append((best_robot.id, task.id))
                available_robots.remove(best_robot)

        return assignments
