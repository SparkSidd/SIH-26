"""Autonomous Mobile Robot (AMR) model, geometry, battery, and state machine."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional, Tuple


class RobotState(Enum):
    IDLE = auto()
    TASK_ASSIGNED = auto()
    MOVING_TO_PICKUP = auto()
    PICKING = auto()
    MOVING_TO_DROPOFF = auto()
    DELIVERING = auto()
    WAITING = auto()
    BLOCKED = auto()
    REPLANNING = auto()
    LOW_BATTERY = auto()
    GOING_TO_CHARGER = auto()
    CHARGING = auto()
    FAILED = auto()
    RECOVERING = auto()


@dataclass
class RobotGeometry:
    """Detailed geometric footprint and kinematic constraints of the AMR."""
    footprint: str = "box"
    radius: float = 0.45            # meters (bounding radius for collision circles)
    length: float = 0.8             # meters
    width: float = 0.6              # meters
    safety_margin: float = 0.15     # meters buffer
    max_velocity: float = 1.5       # m/s
    max_acceleration: float = 1.0   # m/s^2
    turning_radius: float = 0.0     # 0.0 = differential / omnidirectional


@dataclass
class RobotBattery:
    """Battery state and discharge model."""
    capacity: float = 100.0         # %
    current_charge: float = 100.0   # %
    discharge_rate: float = 0.02    # % per moving step
    idle_discharge: float = 0.002   # % per idle step
    charge_rate: float = 0.5        # % per charging step
    low_threshold: float = 20.0
    critical_threshold: float = 10.0

    @property
    def is_low(self) -> bool:
        return self.current_charge <= self.low_threshold

    @property
    def is_critical(self) -> bool:
        return self.current_charge <= self.critical_threshold

    def step_discharge(self, moving: bool) -> None:
        loss = self.discharge_rate if moving else self.idle_discharge
        self.current_charge = max(0.0, self.current_charge - loss)

    def step_charge(self) -> None:
        self.current_charge = min(self.capacity, self.current_charge + self.charge_rate)


class Robot:
    """Autonomous Mobile Robot representation in the warehouse simulator."""

    def __init__(
        self,
        id: str,
        initial_position: Tuple[int, int],
        geometry: Optional[RobotGeometry] = None,
        battery: Optional[RobotBattery] = None,
        comm_range: float = 8.0,
        max_payload: float = 50.0,
    ):
        self.id = id
        self.position: Tuple[int, int] = initial_position
        self.previous_position: Tuple[int, int] = initial_position
        self.heading: float = 0.0                   # radians (0 = East, pi/2 = North, etc.)
        self.velocity: float = 0.0                  # m/s
        self.geometry: RobotGeometry = geometry or RobotGeometry()
        self.battery: RobotBattery = battery or RobotBattery()
        self.comm_range: float = comm_range
        self.max_payload: float = max_payload

        # State machine
        self.state: RobotState = RobotState.IDLE
        self.current_task_id: Optional[str] = None
        self.next_task_id: Optional[str] = None
        self.target_position: Optional[Tuple[int, int]] = None
        self.has_payload: bool = False
        self.tasks_completed: int = 0
        
        # Planned discrete path / continuous trajectory
        self.planned_path: List[Tuple[int, int]] = []
        self.trajectory_waypoints: List[Any] = []
        
        # Health & fault flags
        self.is_healthy: bool = True
        self.failure_reason: str = ""
        
        # Priority & starvation tracking
        self.base_priority: float = 1.0
        self.priority_boost: float = 0.0
        self.wait_steps: int = 0
        self.wait_reason: str = "Idle awaiting task"
        self.total_distance_traveled: float = 0.0
        self.total_steps_active: int = 0

        # Local world model (assigned in local_world.py)
        self.local_world_model: Optional[Any] = None

    @property
    def dynamic_priority(self) -> float:
        """Calculates dynamic priority considering base urgency and starvation aging."""
        return self.base_priority + self.priority_boost

    def set_state(self, new_state: RobotState, reason: str = "") -> None:
        """Explicit state machine transition."""
        self.state = new_state
        if reason:
            self.wait_reason = reason
        if new_state in (RobotState.IDLE, RobotState.CHARGING, RobotState.FAILED):
            if not reason:
                if new_state == RobotState.IDLE:
                    self.wait_reason = "Idle awaiting task"
                elif new_state == RobotState.CHARGING:
                    self.wait_reason = "Charging at station"
                elif new_state == RobotState.FAILED:
                    self.wait_reason = "Hardware fault / E-stop"

    def reset_wait(self) -> None:
        """Reset starvation wait counter and priority boost upon moving."""
        self.wait_steps = 0
        self.priority_boost = 0.0
        self.wait_reason = ""

    def increment_wait(self, boost_rate: float = 0.1, reason: str = "") -> None:
        """Increment wait counter and boost priority to avoid starvation."""
        self.wait_steps += 1
        self.priority_boost += boost_rate
        if reason:
            self.wait_reason = reason
        elif not self.wait_reason or self.wait_reason == "Idle awaiting task":
            self.wait_reason = "Waiting for path clearance"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position": list(self.position),
            "heading": self.heading,
            "velocity": self.velocity,
            "battery": round(self.battery.current_charge, 2),
            "state": self.state.name,
            "current_task_id": self.current_task_id,
            "next_task_id": self.next_task_id,
            "tasks_completed": self.tasks_completed,
            "dynamic_priority": round(self.dynamic_priority, 2),
            "wait_steps": self.wait_steps,
            "wait_reason": self.wait_reason,
            "is_healthy": self.is_healthy,
            "has_payload": self.has_payload,
        }
