"""Network environmental conditions: packet loss, latency, jitter, partitions."""

from dataclasses import dataclass, field
from typing import Set, Tuple


@dataclass
class NetworkConditions:
    """Configures the physical transmission characteristics of the P2P wireless network."""
    latency_ms: float = 25.0            # Average network latency in milliseconds
    jitter_ms: float = 5.0              # Latency jitter
    packet_loss_rate: float = 0.05      # Probability (0.0 to 1.0) of packet drop
    burst_loss_prob: float = 0.01       # Probability of entering a burst loss streak
    burst_duration_steps: int = 5       # Number of consecutive dropped steps in a burst
    is_partitioned: bool = False        # If True, partitions fleet into isolated groups
    partition_groups: Set[Tuple[str, ...]] = field(default_factory=set)

    def can_communicate_partition(self, sender: str, receiver: str) -> bool:
        """Check if sender and receiver are in the same network partition."""
        if not self.is_partitioned:
            return True
        for group in self.partition_groups:
            if sender in group and receiver in group:
                return True
        return False
