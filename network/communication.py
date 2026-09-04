"""Simulated P2P wireless communication mesh with in-flight queue and channel dynamics."""

from collections import defaultdict
import random
from typing import Dict, List, Optional, Set, Tuple

from network.message import NetworkMessage, MessageType
from network.network_conditions import NetworkConditions
from network.topology import NetworkTopology, NetworkTopologyType


class CommunicationMesh:
    """Manages decentralized P2P packet transmission, channel delays, and loss models."""

    def __init__(
        self,
        conditions: Optional[NetworkConditions] = None,
        topology: Optional[NetworkTopology] = None,
        seed: int = 42,
    ):
        self.conditions = conditions or NetworkConditions()
        self.topology = topology or NetworkTopology()
        self.rng = random.Random(seed)

        # In-flight message queue: messages currently traveling across wireless medium
        self._in_flight: List[NetworkMessage] = []
        
        # Inbox buffers for each robot: robot_id -> List[NetworkMessage]
        self._inboxes: Dict[str, List[NetworkMessage]] = defaultdict(list)
        
        # Metrics
        self.total_messages_sent: int = 0
        self.total_messages_delivered: int = 0
        self.total_messages_dropped: int = 0
        self.total_bytes_transmitted: int = 0
        
        self._msg_counter: int = 0

    def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        msg_type: MessageType,
        payload: dict,
        current_sim_time: float,
    ) -> None:
        """Enqueue a message from a sender to a target receiver (or '*' for broadcast)."""
        self._msg_counter += 1
        msg_id = f"MSG_{self._msg_counter:06d}"
        
        # Calculate simulated latency (base + jitter)
        latency_sec = max(0.001, (self.conditions.latency_ms + self.rng.uniform(-self.conditions.jitter_ms, self.conditions.jitter_ms)) / 1000.0)
        delivery_time = current_sim_time + latency_sec

        msg = NetworkMessage(
            message_id=msg_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=msg_type,
            payload=payload,
            creation_time=current_sim_time,
            delivery_time=delivery_time,
        )

        self._in_flight.append(msg)
        self.total_messages_sent += 1
        # Approximate byte size
        self.total_bytes_transmitted += 128 + len(str(payload))

    def step_deliver(
        self,
        current_sim_time: float,
        robot_positions: Dict[str, Tuple[int, int]],
        active_robot_ids: Set[str],
    ) -> None:
        """Deliver all in-flight messages whose delivery delay has elapsed."""
        remaining_in_flight = []

        for msg in self._in_flight:
            if current_sim_time >= msg.delivery_time:
                # Time to deliver or drop
                self._process_delivery(msg, robot_positions, active_robot_ids)
            else:
                remaining_in_flight.append(msg)

        self._in_flight = remaining_in_flight

    def _process_delivery(
        self,
        msg: NetworkMessage,
        robot_positions: Dict[str, Tuple[int, int]],
        active_robot_ids: Set[str],
    ) -> None:
        """Process packet delivery checks for single target or broadcast peers."""
        destinations = []
        if msg.is_broadcast():
            destinations = [r_id for r_id in active_robot_ids if r_id != msg.sender_id]
        else:
            if msg.receiver_id in active_robot_ids:
                destinations = [msg.receiver_id]

        for dest_id in destinations:
            # 1. Check packet loss
            if self.rng.random() < self.conditions.packet_loss_rate:
                self.total_messages_dropped += 1
                continue

            # 2. Check partition constraints
            if not self.conditions.can_communicate_partition(msg.sender_id, dest_id):
                self.total_messages_dropped += 1
                continue

            # 3. Check spatial topology / range connectivity
            if not self.topology.is_connected(msg.sender_id, dest_id, robot_positions):
                self.total_messages_dropped += 1
                continue

            # Delivered successfully to destination inbox
            self._inboxes[dest_id].append(msg)
            self.total_messages_delivered += 1

    def receive_inbox(self, robot_id: str) -> List[NetworkMessage]:
        """Fetch and flush received messages for a given robot."""
        messages = self._inboxes[robot_id]
        self._inboxes[robot_id] = []
        return messages
