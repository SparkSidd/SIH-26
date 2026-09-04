"""Space-time reservation table for multi-agent conflict-free trajectory coordination."""

from typing import Dict, Optional, Set, Tuple


class SpaceTimeReservationTable:
    """Maintains 3D space-time reservations: (x, y, time_step) -> robot_id."""

    def __init__(self):
        # Vertex reservations: (x, y, timestep) -> robot_id
        self.vertex_reservations: Dict[Tuple[int, int, int], str] = {}
        # Edge reservations: ((from_x, from_y), (to_x, to_y), timestep) -> robot_id
        self.edge_reservations: Dict[Tuple[Tuple[int, int], Tuple[int, int], int], str] = {}

    def reserve_vertex(self, pos: Tuple[int, int], timestep: int, robot_id: str) -> bool:
        """Reserve a cell at a specific timestep if not already occupied."""
        key = (pos[0], pos[1], timestep)
        if key in self.vertex_reservations and self.vertex_reservations[key] != robot_id:
            return False
        self.vertex_reservations[key] = robot_id
        return True

    def reserve_edge(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], timestep: int, robot_id: str) -> bool:
        """Reserve a directed edge transition (from_pos -> to_pos) at timestep."""
        # Check reverse edge collision (edge swap)
        reverse_key = (to_pos, from_pos, timestep)
        if reverse_key in self.edge_reservations and self.edge_reservations[reverse_key] != robot_id:
            return False
        key = (from_pos, to_pos, timestep)
        self.edge_reservations[key] = robot_id
        return True

    def is_vertex_reserved(self, pos: Tuple[int, int], timestep: int, exclude_robot_id: Optional[str] = None) -> bool:
        """Check if vertex is occupied by another robot."""
        key = (pos[0], pos[1], timestep)
        if key in self.vertex_reservations:
            return self.vertex_reservations[key] != exclude_robot_id
        return False

    def is_edge_reserved(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], timestep: int, exclude_robot_id: Optional[str] = None) -> bool:
        """Check if reverse edge is occupied (edge swap conflict)."""
        reverse_key = (to_pos, from_pos, timestep)
        if reverse_key in self.edge_reservations:
            return self.edge_reservations[reverse_key] != exclude_robot_id
        return False

    def clear_robot(self, robot_id: str) -> None:
        """Clear all space-time reservations for a given robot."""
        self.vertex_reservations = {k: v for k, v in self.vertex_reservations.items() if v != robot_id}
        self.edge_reservations = {k: v for k, v in self.edge_reservations.items() if v != robot_id}

    def clear(self) -> None:
        """Clear entire reservation table."""
        self.vertex_reservations.clear()
        self.edge_reservations.clear()
