"""Network message representations and protocol definitions."""

from dataclasses import dataclass, field
from enum import Enum, auto
import time
from typing import Any, Dict, Optional


class MessageType(Enum):
    STATE = auto()          # Robot position, velocity, heading
    INTENT = auto()         # Next planned action / destination
    TRAJECTORY = auto()     # Multi-step planned path/space-time reservation
    TASK = auto()           # Task announcement / auction bid
    PRIORITY = auto()       # Dynamic priority update
    CONFLICT = auto()       # Conflict warning at intersection
    YIELD = auto()          # Yielding right of way
    ACK = auto()            # Acknowledgment
    HEARTBEAT = auto()      # Periodic health ping
    FAILURE = auto()        # Emergency hardware failure notification
    BLOCKAGE = auto()       # Aisle blockage discovery broadcast
    RECOVERY = auto()       # Deadlock/failure recovery negotiation


@dataclass
class NetworkMessage:
    """Represents a P2P packet transmitted across the simulated wireless mesh."""
    message_id: str
    sender_id: str
    receiver_id: str                    # "*" for broadcast, or specific robot ID
    message_type: MessageType
    payload: Dict[str, Any]
    creation_time: float
    delivery_time: float = 0.0          # Time when latency delay expires
    sequence_number: int = 0
    ttl: int = 10                       # Time-to-live hops

    def is_broadcast(self) -> bool:
        return self.receiver_id == "*"
