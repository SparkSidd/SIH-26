"""Network topology models: Full Mesh, Range Limited, Partitioned."""

from enum import Enum, auto
import math
from typing import Dict, List, Tuple


class NetworkTopologyType(Enum):
    FULL_MESH = auto()          # Every robot can reach every other robot directly
    RANGE_LIMITED = auto()      # Communication constrained by maximum physical radio range
    PARTITIONED = auto()        # Partitioned sub-networks


class NetworkTopology:
    """Calculates dynamic peer connectivity based on topology mode and AMR spatial distance."""

    def __init__(self, topology_type: NetworkTopologyType = NetworkTopologyType.RANGE_LIMITED, comm_range: float = 8.0):
        self.topology_type = topology_type
        self.comm_range = comm_range

    def is_connected(
        self,
        sender_id: str,
        receiver_id: str,
        robot_positions: Dict[str, Tuple[int, int]],
    ) -> bool:
        """Evaluate if two robots can exchange P2P packets at the current timestep."""
        if sender_id == receiver_id:
            return True

        if self.topology_type == NetworkTopologyType.FULL_MESH:
            return True

        if self.topology_type == NetworkTopologyType.RANGE_LIMITED:
            if sender_id not in robot_positions or receiver_id not in robot_positions:
                return False
            sx, sy = robot_positions[sender_id]
            rx, ry = robot_positions[receiver_id]
            dist = math.hypot(sx - rx, sy - ry)
            return dist <= self.comm_range

        return True
