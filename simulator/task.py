"""Task models and dynamic task generation streams."""

from dataclasses import dataclass, field
from enum import Enum, auto
import random
from typing import List, Optional, Tuple


class TaskState(Enum):
    CREATED = auto()
    QUEUED = auto()
    ASSIGNED = auto()
    MOVING_TO_PICKUP = auto()
    PICKED_UP = auto()
    IN_TRANSIT = auto()
    DELIVERED = auto()
    BLOCKED = auto()
    REASSIGNING = auto()
    FAILED = auto()


@dataclass
class Task:
    """Represents an item transport task in the warehouse."""
    id: str
    pickup: Tuple[int, int]
    dropoff: Tuple[int, int]
    priority: float = 1.0                # Base priority multiplier
    creation_time: float = 0.0
    deadline: Optional[float] = None
    payload_weight: float = 10.0         # kg
    required_capability: str = "standard"
    assigned_robot_id: Optional[str] = None
    state: TaskState = TaskState.CREATED

    # Timestamp & duration breakdown logging
    assigned_time: Optional[float] = None
    pickup_time: Optional[float] = None
    completion_time: Optional[float] = None
    reassignment_count: int = 0
    # Strictly Additive Time-Decomposition (Sum == total_completion_duration)
    assignment_duration: float = 0.0
    travel_duration: float = 0.0
    conflict_wait_duration: float = 0.0
    normal_wait_duration: float = 0.0
    replanning_duration: float = 0.0
    recovery_duration: float = 0.0
    pickup_duration: float = 0.0
    delivery_duration: float = 0.0
    execution_overhead_duration: float = 0.0

    # Non-Additive Diagnostic Telemetry Signals
    congestion_exposure: float = 0.0
    bottleneck_visits: int = 0
    conflicts_experienced: int = 0
    replans_count: int = 0

    # Backward-compatible duration aliases
    travel_time: float = 0.0
    wait_time: float = 0.0
    congestion_delay: float = 0.0
    reroute_time: float = 0.0
    assignment_latency: float = 0.0
    distance_traveled: float = 0.0
    turns_count: int = 0
    stops_count: int = 0

    @property
    def is_active(self) -> bool:
        return self.state in (
            TaskState.CREATED,
            TaskState.QUEUED,
            TaskState.ASSIGNED,
            TaskState.MOVING_TO_PICKUP,
            TaskState.PICKED_UP,
            TaskState.IN_TRANSIT,
            TaskState.BLOCKED,
            TaskState.REASSIGNING,
        )

    @property
    def is_completed(self) -> bool:
        return self.state == TaskState.DELIVERED

    @property
    def total_completion_duration(self) -> Optional[float]:
        if self.completion_time is not None and self.creation_time is not None:
            return self.completion_time - self.creation_time
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pickup": list(self.pickup),
            "dropoff": list(self.dropoff),
            "priority": self.priority,
            "creation_time": round(self.creation_time, 2),
            "deadline": self.deadline,
            "assigned_robot_id": self.assigned_robot_id,
            "state": self.state.name,
            "completion_time": round(self.completion_time, 2) if self.completion_time else None,
            "total_duration": round(self.total_completion_duration, 2) if self.total_completion_duration else None,
            "reassignment_count": self.reassignment_count,
            "travel_time": round(self.travel_time, 2),
            "wait_time": round(self.wait_time, 2),
            "congestion_delay": round(self.congestion_delay, 2),
            "reroute_time": round(self.reroute_time, 2),
            "assignment_latency": round(self.assignment_latency, 2),
            "distance_traveled": round(self.distance_traveled, 1),
            "turns_count": self.turns_count,
            "stops_count": self.stops_count,
            "additive_decomposition": self.to_additive_decomposition(),
        }

    def to_additive_decomposition(self) -> dict:
        """Return strictly additive duration components summing to total duration."""
        return {
            "assignment": round(self.assignment_duration, 3),
            "travel": round(self.travel_duration, 3),
            "conflict_wait": round(self.conflict_wait_duration, 3),
            "normal_wait": round(self.normal_wait_duration, 3),
            "replanning": round(self.replanning_duration, 3),
            "recovery": round(self.recovery_duration, 3),
            "pickup": round(self.pickup_duration, 3),
            "delivery": round(self.delivery_duration, 3),
            "execution_overhead": round(self.execution_overhead_duration, 3),
            "total_duration": round(self.total_completion_duration or 0.0, 3),
        }


class TaskGenerator:
    """Dynamically generates warehouse tasks according to various arrival distributions."""

    def __init__(
        self,
        pickup_stations: List[Tuple[int, int]],
        dropoff_stations: List[Tuple[int, int]],
        mode: str = "poisson",
        arrival_rate: float = 0.2,       # tasks / sec
        seed: int = 42,
    ):
        self.pickup_stations = pickup_stations
        self.dropoff_stations = dropoff_stations
        self.mode = mode
        self.arrival_rate = arrival_rate
        self.rng = random.Random(seed)
        self._task_counter: int = 0
        self._next_arrival_time: float = 0.0

    def generate_step(self, current_time: float, dt: float) -> List[Task]:
        """Generate tasks for the current simulation step."""
        new_tasks = []

        if self.mode == "poisson":
            # Poisson arrival process: probability of arrival in dt is rate * dt
            if current_time >= self._next_arrival_time:
                new_tasks.append(self._create_random_task(current_time))
                # Inter-arrival exponential delay
                inter_arrival = self.rng.expovariate(self.arrival_rate) if self.arrival_rate > 0 else 9999
                self._next_arrival_time = current_time + inter_arrival

        elif self.mode == "uniform":
            if current_time >= self._next_arrival_time:
                new_tasks.append(self._create_random_task(current_time))
                interval = 1.0 / self.arrival_rate if self.arrival_rate > 0 else 9999
                self._next_arrival_time = current_time + interval

        elif self.mode == "burst":
            # Spawns bursts of 3-5 tasks every 20 seconds
            if current_time >= self._next_arrival_time:
                burst_size = self.rng.randint(3, 5)
                for _ in range(burst_size):
                    new_tasks.append(self._create_random_task(current_time))
                self._next_arrival_time = current_time + 20.0

        return new_tasks

    def _create_random_task(self, current_time: float) -> Task:
        """Create a single task with randomized pickup/dropoff and priority."""
        self._task_counter += 1
        task_id = f"TASK_{self._task_counter:04d}"
        pickup = self.rng.choice(self.pickup_stations)
        dropoff = self.rng.choice(self.dropoff_stations)
        
        # Ensure pickup and dropoff are different
        while dropoff == pickup and len(self.dropoff_stations) > 1:
            dropoff = self.rng.choice(self.dropoff_stations)

        priority = self.rng.choice([1.0, 1.2, 1.5, 2.0])
        deadline = current_time + self.rng.uniform(60.0, 180.0)

        return Task(
            id=task_id,
            pickup=pickup,
            dropoff=dropoff,
            priority=priority,
            creation_time=current_time,
            deadline=deadline,
            payload_weight=self.rng.uniform(5.0, 30.0),
        )

    def reset(self) -> None:
        """Reset generator state."""
        self._task_counter = 0
        self._next_arrival_time = 0.0
