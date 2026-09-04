"""Task reclamation and dynamic reassignment upon robot failure."""

from typing import Dict, Optional
from events.event import Event, EventType
from events.event_bus import EventBus
from simulator.robot import Robot
from simulator.task import Task, TaskState


class TaskRecoveryManager:
    """Recovers and reclaims active tasks from disabled or failed AMRs."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus

    def handle_robot_failure(
        self,
        failed_robot: Robot,
        tasks: Dict[str, Task],
        sim_time: float,
        step: int,
    ) -> Optional[Task]:
        """Reclaim abandoned task and re-enqueue for peer pickup."""
        if not failed_robot.current_task_id:
            return None

        task_id = failed_robot.current_task_id
        task = tasks.get(task_id)

        if task and task.state != TaskState.DELIVERED:
            # Task was not finished: release and boost priority for rapid reallocation
            task.state = TaskState.QUEUED
            task.assigned_robot_id = None
            task.priority += 1.0  # Boost priority
            task.reassignment_count += 1
            failed_robot.current_task_id = None

            if self.event_bus:
                self.event_bus.publish(
                    Event(
                        event_type=EventType.TASK_REASSIGNED,
                        sim_time=sim_time,
                        step=step,
                        source="TaskRecoveryManager",
                        data={"task_id": task.id, "previous_robot": failed_robot.id},
                        description=f"Task {task.id} reclaimed from failed robot {failed_robot.id} and re-queued",
                    )
                )

            return task

        return None
