"""Aisle blockage detection, peer broadcast, and automated rerouting."""

from typing import Dict, List, Optional, Set, Tuple
from events.event import Event, EventType
from events.event_bus import EventBus
from simulator.robot import Robot


class BlockageHandler:
    """Detects unexpected aisle blockages, broadcasts notifications, and triggers rerouting."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        self.active_blockages: Set[Tuple[int, int]] = set()

    def register_blockage(self, cell: Tuple[int, int], sim_time: float, step: int) -> None:
        """Register newly identified blocked corridor cell."""
        self.active_blockages.add(cell)
        if self.event_bus:
            self.event_bus.publish(
                Event(
                    event_type=EventType.AISLE_BLOCKED,
                    sim_time=sim_time,
                    step=step,
                    source="BlockageHandler",
                    data={"cell": list(cell)},
                    description=f"Aisle blocked at coordinate {cell}",
                )
            )

    def clear_blockage(self, cell: Tuple[int, int], sim_time: float, step: int) -> None:
        """Clear resolved blockage."""
        self.active_blockages.discard(cell)
        if self.event_bus:
            self.event_bus.publish(
                Event(
                    event_type=EventType.AISLE_CLEARED,
                    sim_time=sim_time,
                    step=step,
                    source="BlockageHandler",
                    data={"cell": list(cell)},
                    description=f"Aisle cleared at coordinate {cell}",
                )
            )

    def find_affected_robots(self, robots: Dict[str, Robot], blocked_cell: Tuple[int, int]) -> List[str]:
        """Identify which robots have planned routes passing through the blocked cell."""
        affected = []
        for r_id, robot in robots.items():
            if blocked_cell in robot.planned_path:
                affected.append(r_id)
        return affected
