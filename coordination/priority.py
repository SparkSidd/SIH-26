"""Dynamic priority calculation and starvation prevention aging."""

from typing import Dict, Optional
from simulator.robot import Robot
from simulator.task import Task


class PriorityEngine:
    """Computes dynamic priority scores with anti-starvation aging mechanisms."""

    def __init__(self, aging_rate: float = 0.15):
        self.aging_rate = aging_rate

    def compute_robot_priority(
        self,
        robot: Robot,
        active_task: Optional[Task] = None,
        congestion_at_robot: float = 0.0,
    ) -> float:
        """Calculate composite dynamic priority for an AMR."""
        # 1. Base task priority
        task_urgency = active_task.priority if active_task else 1.0
        
        # 2. Payload priority: Loaded robots executing deliveries get priority over empty deadheading robots
        payload_boost = 1.5 if getattr(robot, "has_payload", False) else 0.0

        # 3. Progress boost: Robots nearing goal get finishing priority to clear corridors
        progress_boost = 0.0
        if active_task:
            target = active_task.dropoff if getattr(robot, "has_payload", False) else active_task.pickup
            dist = abs(robot.position[0] - target[0]) + abs(robot.position[1] - target[1])
            if dist <= 3:
                progress_boost = 1.0 * max(0.0, (4 - dist) / 4.0)

        # 4. Battery health urgency (robots heading to charger get higher priority if low)
        battery_urgency = 0.0
        if robot.battery.is_low:
            battery_urgency = 1.5
        if robot.battery.is_critical:
            battery_urgency = 3.0

        # 5. Starvation aging: boost priority for robots that have been waiting repeatedly
        starvation_boost = robot.wait_steps * self.aging_rate

        # 6. Congestion penalty
        congestion_boost = 0.2 if congestion_at_robot > 2.0 else 0.0

        total_priority = (
            task_urgency
            + payload_boost
            + progress_boost
            + battery_urgency
            + starvation_boost
            + congestion_boost
        )
        return max(0.1, total_priority)
