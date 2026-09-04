"""Observation adapter for decentralized fleet coordination.

Maps robot state, local world model beliefs, and valid P2P packets
into normalized PyTorch tensors without any future or hidden state leakage.
"""

from typing import Dict, List, Optional, Set, Tuple
import math
import torch

from simulator.robot import Robot
from simulator.task import Task, TaskState


class ObservationAdapter:
    """Encodes decentralized AMR fleet states into normalized neural network observations."""

    def __init__(self, grid_width: int = 24, grid_height: int = 16, feature_dim: int = 14):
        self.grid_width = float(grid_width)
        self.grid_height = float(grid_height)
        self.feature_dim = feature_dim

    def encode_fleet_state(
        self,
        active_robot_ids: List[str],
        robots: Dict[str, Robot],
        tasks: Dict[str, Task],
        target_goals: Dict[str, Tuple[int, int]],
        congestion_at_robots: Optional[Dict[str, float]] = None,
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
    ) -> torch.Tensor:
        """Encode active robot states into a normalized batch tensor [1, N_agents, feature_dim].
        
        Strict decentralization constraints:
        - Uses only current positions and valid P2P beliefs.
        - No future path or future task arrival information is included.
        """
        congestion_map = congestion_at_robots or {}
        agent_vectors: List[List[float]] = []

        for r_id in active_robot_ids:
            robot = robots.get(r_id)
            if not robot:
                # Pad with zeros if robot missing
                agent_vectors.append([0.0] * self.feature_dim)
                continue

            rx, ry = robot.position
            norm_x = rx / max(1.0, self.grid_width - 1.0)
            norm_y = ry / max(1.0, self.grid_height - 1.0)
            norm_vel = min(1.0, robot.velocity)
            norm_heading = (robot.heading % 360) / 360.0

            has_payload = 1.0 if getattr(robot, "has_payload", False) else 0.0

            # Target goal relative distance
            goal = target_goals.get(r_id, robot.position)
            dx = (goal[0] - rx) / max(1.0, self.grid_width)
            dy = (goal[1] - ry) / max(1.0, self.grid_height)
            manhattan_dist = (abs(goal[0] - rx) + abs(goal[1] - ry)) / (self.grid_width + self.grid_height)

            # Active task urgency
            active_task = tasks.get(robot.current_task_id) if robot.current_task_id else None
            task_urgency = (active_task.priority / 5.0) if active_task else 0.2

            # Starvation / wait steps
            norm_wait = min(1.0, robot.wait_steps / 10.0)

            # Battery state
            norm_battery = robot.battery.current_charge / 100.0
            battery_low = 1.0 if robot.battery.is_low else 0.0

            # Local perceived congestion
            cong = min(1.0, congestion_map.get(r_id, 0.0) / 3.0)

            # Communication health (1.0 = healthy, degraded if packet drops occur)
            comm_health = 1.0 if robot.is_healthy else 0.0

            # 14 distinct normalized features
            feats = [
                norm_x,
                norm_y,
                norm_vel,
                norm_heading,
                has_payload,
                dx,
                dy,
                manhattan_dist,
                task_urgency,
                norm_wait,
                norm_battery,
                battery_low,
                cong,
                comm_health,
            ]
            agent_vectors.append(feats)

        # Output shape: [1, N_agents, feature_dim]
        tensor_obs = torch.tensor([agent_vectors], dtype=torch.float32)
        return tensor_obs
