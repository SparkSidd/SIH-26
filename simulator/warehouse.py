"""Warehouse layout representation, zones, stations, and grid utilities."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple
import numpy as np


class CellType(Enum):
    FREE = 0
    WALL = 1
    SHELF = 2
    PICKUP = 3
    DROPOFF = 4
    CHARGING = 5
    BLOCKED = 6


@dataclass
class WarehouseZone:
    """Represents a named functional zone in the warehouse."""
    name: str
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    zone_type: str = "general"

    def contains(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


class Warehouse:
    """Represents the 2D grid warehouse map."""

    def __init__(
        self,
        width: int = 25,
        height: int = 20,
        layout_type: str = "corridor_heavy",
        pickup_stations: Optional[List[Tuple[int, int]]] = None,
        dropoff_stations: Optional[List[Tuple[int, int]]] = None,
        charging_stations: Optional[List[Tuple[int, int]]] = None,
    ):
        self.width = width
        self.height = height
        self.layout_type = layout_type
        self.grid = np.zeros((width, height), dtype=int)
        
        self.pickup_stations: List[Tuple[int, int]] = pickup_stations or []
        self.dropoff_stations: List[Tuple[int, int]] = dropoff_stations or []
        self.charging_stations: List[Tuple[int, int]] = charging_stations or []
        self.zones: Dict[str, WarehouseZone] = {}
        self.blocked_cells: Set[Tuple[int, int]] = set()

        self._build_layout()

    def _build_layout(self) -> None:
        """Construct static walls, shelves, corridors, and stations."""
        # 1. Outer boundary walls
        for x in range(self.width):
            self.grid[x, 0] = CellType.WALL.value
            self.grid[x, self.height - 1] = CellType.WALL.value
        for y in range(self.height):
            self.grid[0, y] = CellType.WALL.value
            self.grid[self.width - 1, y] = CellType.WALL.value

        # 2. Interior layout depending on layout_type
        if self.layout_type == "corridor_heavy":
            # Traditional aisle layout with storage shelves arranged in parallel racks
            for x in range(4, self.width - 4, 3):
                for y in range(3, self.height - 3):
                    # Leave cross-aisles at top, center, and bottom
                    if y not in (self.height // 2, self.height // 2 - 1):
                        self.grid[x, y] = CellType.SHELF.value
                        self.grid[x + 1, y] = CellType.SHELF.value

        elif self.layout_type == "intersection_heavy":
            # Grid of small shelf blocks creating many 4-way intersections
            for x in range(3, self.width - 3, 4):
                for y in range(3, self.height - 3, 4):
                    self.grid[x:x+2, y:y+2] = CellType.SHELF.value

        elif self.layout_type == "choke_point":
            # A central dividing wall with only 2 narrow choke passages
            mid_x = self.width // 2
            for y in range(1, self.height - 1):
                if y not in (self.height // 4, 3 * self.height // 4):
                    self.grid[mid_x, y] = CellType.WALL.value

        elif self.layout_type == "dense":
            # High-density rack setup
            for x in range(2, self.width - 2, 2):
                for y in range(2, self.height - 2, 2):
                    self.grid[x, y] = CellType.SHELF.value

        # 3. Default stations if none provided
        if not self.pickup_stations:
            self.pickup_stations = [(2, 2), (2, self.height // 2), (2, self.height - 3)]
        if not self.dropoff_stations:
            self.dropoff_stations = [(self.width - 3, 2), (self.width - 3, self.height // 2), (self.width - 3, self.height - 3)]
        if not self.charging_stations:
            self.charging_stations = [(1, 1), (1, self.height - 2), (self.width - 2, 1), (self.width - 2, self.height - 2)]

        for px, py in self.pickup_stations:
            if self.is_within_bounds((px, py)):
                self.grid[px, py] = CellType.PICKUP.value

        for dx, dy in self.dropoff_stations:
            if self.is_within_bounds((dx, dy)):
                self.grid[dx, dy] = CellType.DROPOFF.value

        for cx, cy in self.charging_stations:
            if self.is_within_bounds((cx, cy)):
                self.grid[cx, cy] = CellType.CHARGING.value

        # 4. Define default zones
        mid_x = self.width // 2
        self.zones["inbound"] = WarehouseZone("inbound", 0, mid_x - 3, 0, self.height - 1, "pickup")
        self.zones["storage"] = WarehouseZone("storage", mid_x - 2, mid_x + 2, 0, self.height - 1, "transit")
        self.zones["outbound"] = WarehouseZone("outbound", mid_x + 3, self.width - 1, 0, self.height - 1, "dropoff")

    def is_within_bounds(self, pos: Tuple[int, int]) -> bool:
        """Check if (x, y) coordinates fall within map boundaries."""
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def is_static_walkable(self, pos: Tuple[int, int]) -> bool:
        """Check if cell is structurally free from permanent walls or storage racks (ignoring dynamic temporary blockages)."""
        if not self.is_within_bounds(pos):
            return False
        cell_val = self.grid[pos[0], pos[1]]
        return cell_val not in (CellType.WALL.value, CellType.SHELF.value)

    def is_walkable(self, pos: Tuple[int, int]) -> bool:
        """Check if cell is free to be traversed by a robot."""
        if not self.is_within_bounds(pos):
            return False
        if pos in self.blocked_cells:
            return False
        cell_val = self.grid[pos[0], pos[1]]
        return cell_val not in (CellType.WALL.value, CellType.SHELF.value)

    def get_neighbors(self, pos: Tuple[int, int], include_wait: bool = False) -> List[Tuple[int, int]]:
        """Get 4-directional walkable neighboring cells (plus wait/stay if requested)."""
        x, y = pos
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        if include_wait:
            candidates.append((x, y))
        return [c for c in candidates if self.is_walkable(c)]

    @property
    def protected_cells(self) -> set:
        """Cells that must never be blocked (stations, charging pads)."""
        protected = set()
        protected.update(tuple(p) for p in self.pickup_stations)
        protected.update(tuple(p) for p in self.dropoff_stations)
        protected.update(tuple(p) for p in self.charging_stations)
        return protected

    def block_cell(self, pos: Tuple[int, int]) -> bool:
        """Temporarily block a cell. Returns False if the cell is protected."""
        if not self.is_within_bounds(pos):
            return False
        # Never block pickup/dropoff/charging stations
        if pos in self.protected_cells:
            return False
        self.blocked_cells.add(pos)
        return True

    def unblock_cell(self, pos: Tuple[int, int]) -> None:
        """Remove temporary blockage from a cell."""
        self.blocked_cells.discard(pos)

    def get_free_cells(self) -> List[Tuple[int, int]]:
        """Return list of all free traversable cells."""
        free = []
        for x in range(self.width):
            for y in range(self.height):
                if self.is_walkable((x, y)):
                    free.append((x, y))
        return free
