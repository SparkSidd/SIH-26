"""Event definitions for the AMR Fleet Coordination system."""

from dataclasses import dataclass, field
from enum import Enum, auto
import time
from typing import Any, Dict, Optional


class EventType(Enum):
    """Enumeration of all system event types."""
    SIMULATION_STARTED = auto()
    SIMULATION_PAUSED = auto()
    SIMULATION_RESUMED = auto()
    SIMULATION_STOPPED = auto()
    SIMULATION_TICK = auto()

    TASK_CREATED = auto()
    TASK_ASSIGNED = auto()
    TASK_PICKED_UP = auto()
    TASK_COMPLETED = auto()
    TASK_BLOCKED = auto()
    TASK_REASSIGNED = auto()
    TASK_FAILED = auto()

    ROBOT_SPAWNED = auto()
    ROBOT_MOVED = auto()
    ROBOT_WAITING = auto()
    ROBOT_STATE_CHANGED = auto()
    ROBOT_LOW_BATTERY = auto()
    ROBOT_CHARGING = auto()
    ROBOT_FAILED = auto()
    ROBOT_RECOVERED = auto()

    CONFLICT_DETECTED = auto()
    DEADLOCK_DETECTED = auto()
    DEADLOCK_RESOLVED = auto()

    AISLE_BLOCKED = auto()
    AISLE_CLEARED = auto()

    COMMUNICATION_SENT = auto()
    COMMUNICATION_DELIVERED = auto()
    COMMUNICATION_LOST = auto()
    COMMUNICATION_RESTORED = auto()

    COORDINATION_ESCALATED = auto()
    COORDINATION_DEESCALATED = auto()

    PLANNER_STARTED = auto()
    PLANNER_SUCCESS = auto()
    PLANNER_TIMEOUT = auto()
    PLANNER_FAILED = auto()
    REPLANNING_TRIGGERED = auto()
    REROUTE = auto()

    SAFETY_INTERVENTION = auto()
    CRITICAL_SAFETY_VIOLATION = auto()

    PROTECTED_CELL_BLOCK_REJECTED = auto()
    WAYPOINT_INVALIDATED = auto()

    BENCHMARK_STEP = auto()
    BENCHMARK_COMPLETED = auto()


@dataclass
class Event:
    """Represents an event published on the event bus."""
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    sim_time: float = 0.0
    step: int = 0
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging/serialization."""
        return {
            "event_type": self.event_type.name,
            "timestamp": self.timestamp,
            "sim_time": self.sim_time,
            "step": self.step,
            "source": self.source,
            "data": self.data,
            "description": self.description,
        }
