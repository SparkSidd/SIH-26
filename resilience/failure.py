"""Simulated robot hardware faults and heartbeat monitoring."""

from typing import Dict, List, Optional, Set
from events.event import Event, EventType
from events.event_bus import EventBus
from simulator.robot import Robot, RobotState


class FailureManager:
    """Simulates AMR hardware faults (motor stall, sensor failure) and detects dead peers."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        self.failed_robots: Set[str] = set()

    def inject_failure(self, robot: Robot, reason: str, sim_time: float, step: int) -> None:
        """Trigger hardware failure on a specific AMR."""
        robot.is_healthy = False
        robot.failure_reason = reason
        robot.set_state(RobotState.FAILED, f"Hardware Failure: {reason}")
        self.failed_robots.add(robot.id)

        if self.event_bus:
            self.event_bus.publish(
                Event(
                    event_type=EventType.ROBOT_FAILED,
                    sim_time=sim_time,
                    step=step,
                    source="FailureManager",
                    data={"robot_id": robot.id, "reason": reason, "position": list(robot.position)},
                    description=f"Robot {robot.id} suffered failure: {reason}",
                )
            )

    def recover_robot(self, robot: Robot, sim_time: float, step: int) -> None:
        """Restore failed robot back to operational status."""
        robot.is_healthy = True
        robot.failure_reason = ""
        robot.set_state(RobotState.IDLE, "Recovered from failure")
        self.failed_robots.discard(robot.id)

        if self.event_bus:
            self.event_bus.publish(
                Event(
                    event_type=EventType.ROBOT_RECOVERED,
                    sim_time=sim_time,
                    step=step,
                    source="FailureManager",
                    data={"robot_id": robot.id},
                    description=f"Robot {robot.id} restored to healthy operation",
                )
            )
