"""Space-time reservation table for multi-agent conflict-free trajectory coordination."""

from typing import Any, Dict, List, Optional, Set, Tuple


class SpaceTimeReservationTable:
    """Maintains space-time reservations: (x, y, timestep) -> robot_id."""

    def __init__(self):
        # Vertex reservations: (x, y, timestep) -> robot_id
        self.vertex_reservations: Dict[Tuple[int, int, int], str] = {}
        # Edge reservations: ((from_x, from_y), (to_x, to_y), timestep) -> robot_id
        self.edge_reservations: Dict[Tuple[Tuple[int, int], Tuple[int, int], int], str] = {}
        # Invalidation log
        self.invalidated_reservations_count: int = 0

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

    def prune_expired(self, current_timestep: int) -> int:
        """Prune reservations older than current timestep. Return count of pruned entries."""
        initial_count = len(self.vertex_reservations) + len(self.edge_reservations)
        self.vertex_reservations = {k: v for k, v in self.vertex_reservations.items() if k[2] >= current_timestep}
        self.edge_reservations = {k: v for k, v in self.edge_reservations.items() if k[2] >= current_timestep}
        return initial_count - (len(self.vertex_reservations) + len(self.edge_reservations))

    def invalidate_cell(self, pos: Tuple[int, int], from_timestep: int) -> List[str]:
        """Invalidate all reservations touching a cell at or after from_timestep (e.g. dynamic blockage).

        Returns list of affected robot IDs that need replanning.
        """
        affected_robots: Set[str] = set()
        v_keys_to_remove = []
        for (x, y, t), r_id in self.vertex_reservations.items():
            if (x, y) == pos and t >= from_timestep:
                affected_robots.add(r_id)
                v_keys_to_remove.append((x, y, t))

        for k in v_keys_to_remove:
            del self.vertex_reservations[k]
            self.invalidated_reservations_count += 1

        e_keys_to_remove = []
        for (f_pos, t_pos, t), r_id in self.edge_reservations.items():
            if (f_pos == pos or t_pos == pos) and t >= from_timestep:
                affected_robots.add(r_id)
                e_keys_to_remove.append((f_pos, t_pos, t))

        for k in e_keys_to_remove:
            del self.edge_reservations[k]
            self.invalidated_reservations_count += 1

        return sorted(list(affected_robots))

    def get_timeline(self, current_timestep: int, horizon: int = 20) -> List[Dict[str, Any]]:
        """Return structured timeline view of reservations for Digital Twin visualization."""
        timeline: List[Dict[str, Any]] = []

        max_t = current_timestep + horizon
        for (x, y, t), r_id in sorted(self.vertex_reservations.items(), key=lambda item: item[0][2]):
            if current_timestep - 2 <= t <= max_t:
                if t == current_timestep:
                    status = "active"
                elif t > current_timestep:
                    status = "future"
                else:
                    status = "expired"

                timeline.append({
                    "robot_id": r_id,
                    "cell": [x, y],
                    "timestep": t,
                    "delta_t": t - current_timestep,
                    "status": status,
                    "type": "vertex",
                })

        for (f_pos, t_pos, t), r_id in sorted(self.edge_reservations.items(), key=lambda item: item[0][2]):
            if current_timestep <= t <= max_t:
                timeline.append({
                    "robot_id": r_id,
                    "from_cell": list(f_pos),
                    "to_cell": list(t_pos),
                    "timestep": t,
                    "delta_t": t - current_timestep,
                    "status": "active" if t == current_timestep else "future",
                    "type": "edge_transition",
                })

        return timeline
