"""Ground truth simulator world container (isolated from decentralized planning)."""

from typing import Dict, List, Optional, Set, Tuple
from simulator.obstacle import Obstacle
from simulator.robot import Robot
from simulator.task import Task
from simulator.warehouse import Warehouse


class SimulatorWorld:
    """Ground truth physical simulation world."""

    def __init__(self, warehouse: Warehouse):
        self.warehouse = warehouse
        self.robots: Dict[str, Robot] = {}
        self.tasks: Dict[str, Task] = {}
        self.obstacles: Dict[str, Obstacle] = {}
        self.active_blockages: Set[Tuple[int, int]] = set()

    def add_robot(self, robot: Robot) -> None:
        self.robots[robot.id] = robot

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def add_obstacle(self, obstacle: Obstacle) -> None:
        self.obstacles[obstacle.id] = obstacle
        if obstacle.is_static:
            self.warehouse.block_cell(obstacle.position)

    def get_ground_truth_robot_positions(self) -> Dict[str, Tuple[int, int]]:
        """Return dict of current true robot coordinates."""
        return {r_id: robot.position for r_id, robot in self.robots.items()}

    def get_ground_truth_obstacles(self, sim_time: float) -> Set[Tuple[int, int]]:
        """Return set of all active obstacles at the given simulation time."""
        active = set(self.warehouse.blocked_cells)
        for obs in self.obstacles.values():
            if obs.is_active_at(sim_time):
                active.add(obs.position)
        return active
