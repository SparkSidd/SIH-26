"""Battery health supervision and charging station schedule manager."""

from typing import Dict, List, Optional, Set, Tuple
from events.event import Event, EventType
from events.event_bus import EventBus
from simulator.robot import Robot, RobotState


class ChargingManager:
    """Monitors battery levels and routes low-battery AMRs to charging pads."""

    def __init__(self, charging_stations: List[Tuple[int, int]], event_bus: Optional[EventBus] = None):
        self.charging_stations = charging_stations
        self.event_bus = event_bus
        self.station_occupancy: Dict[Tuple[int, int], Optional[str]] = {pad: None for pad in charging_stations}

    def check_fleet_battery(self, robots: Dict[str, Robot], sim_time: float, step: int) -> None:
        """Inspect battery levels across all robots and trigger charging requests."""
        for robot_id, robot in robots.items():
            if robot.battery.is_critical and robot.state != RobotState.CHARGING:
                if self.event_bus:
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.ROBOT_LOW_BATTERY,
                            sim_time=sim_time,
                            step=step,
                            source="ChargingManager",
                            data={"robot_id": robot_id, "battery": robot.battery.current_charge},
                            description=f"Robot {robot_id} has critical battery ({robot.battery.current_charge:.1f}%)",
                        )
                    )

    def get_nearest_free_station(self, robot_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Find the closest unoccupied charging pad."""
        free_stations = [pad for pad, occupant in self.station_occupancy.items() if occupant is None]
        if not free_stations:
            # Fall back to closest even if occupied
            return min(self.charging_stations, key=lambda s: abs(s[0] - robot_pos[0]) + abs(s[1] - robot_pos[1]))
        return min(free_stations, key=lambda s: abs(s[0] - robot_pos[0]) + abs(s[1] - robot_pos[1]))
