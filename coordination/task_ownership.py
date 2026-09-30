"""Distributed Task Claim / ACK / Commit Ownership Protocol.

Borrows the decentralized task ownership pattern (inspired by ACE/contract protocols)
without replacing Hungarian bipartite allocation. Hungarian remains the optimal
assignment mechanism, while this layer provides the distributed consensus/ownership
commit protocol to guarantee that no two AMRs execute the same task, stale assignment
messages are rejected via monotonic epochs, and failed robot tasks are safely reclaimed.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
import time
from typing import Any, Dict, List, Optional, Set, Tuple


class TaskOwnershipState(Enum):
    UNASSIGNED = auto()
    PROPOSED = auto()
    CLAIMED = auto()
    ACKED = auto()
    COMMITTED = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    TIMEOUT = auto()
    RELEASED = auto()
    RECLAIMED = auto()


class OwnershipMessageType(Enum):
    TASK_CLAIM = auto()
    TASK_ACK = auto()
    TASK_COMMIT = auto()
    TASK_RELEASE = auto()
    TASK_RECLAIM = auto()
    TASK_HEARTBEAT = auto()


@dataclass
class OwnershipMessage:
    """Explicit message semantics for distributed task ownership."""
    msg_type: OwnershipMessageType
    task_id: str
    robot_id: str
    epoch: int
    timestamp: float
    logical_tick: int
    cost: float = 0.0
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskOwnershipRecord:
    task_id: str
    current_epoch: int = 1
    state: TaskOwnershipState = TaskOwnershipState.UNASSIGNED
    owner_robot_id: Optional[str] = None
    claim_timestamp: float = 0.0
    ack_timestamp: float = 0.0
    commit_timestamp: float = 0.0
    acks_received: Set[str] = field(default_factory=set)
    cost: float = 0.0


class TaskOwnershipProtocol:
    """Manages distributed task ownership lifecycle, epoch gating, and reclaim logic."""

    def __init__(self, ack_timeout_sec: float = 2.0, required_acks: int = 1):
        self.ack_timeout_sec = ack_timeout_sec
        self.required_acks = required_acks
        self.records: Dict[str, TaskOwnershipRecord] = {}

        # Telemetry metrics
        self.claim_attempts: int = 0
        self.successful_claims: int = 0
        self.ack_latencies_ms: List[float] = []
        self.claim_conflicts: int = 0
        self.stale_messages_rejected: int = 0
        self.task_reclaims: int = 0
        self.duplicate_claims_prevented: int = 0

    def get_or_create_record(self, task_id: str) -> TaskOwnershipRecord:
        if task_id not in self.records:
            self.records[task_id] = TaskOwnershipRecord(task_id=task_id)
        return self.records[task_id]

    def propose_assignment(self, task_id: str, robot_id: str, cost: float, timestamp: float, tick: int) -> OwnershipMessage:
        """Called when Hungarian allocator proposes assigning a task to a robot."""
        rec = self.get_or_create_record(task_id)
        rec.state = TaskOwnershipState.PROPOSED
        rec.cost = cost
        self.claim_attempts += 1

        msg = OwnershipMessage(
            msg_type=OwnershipMessageType.TASK_CLAIM,
            task_id=task_id,
            robot_id=robot_id,
            epoch=rec.current_epoch,
            timestamp=timestamp,
            logical_tick=tick,
            cost=cost,
        )
        return msg

    def handle_claim(self, msg: OwnershipMessage, current_time: float) -> Optional[OwnershipMessage]:
        """Peer receives a TASK_CLAIM. Validate epoch and conflict, return ACK if valid."""
        rec = self.get_or_create_record(msg.task_id)

        # 1. Monotonic Epoch Check: Reject stale messages
        if msg.epoch < rec.current_epoch:
            self.stale_messages_rejected += 1
            return None

        # 2. Duplicate / Conflict Check
        if rec.state in (TaskOwnershipState.COMMITTED, TaskOwnershipState.EXECUTING):
            if rec.owner_robot_id != msg.robot_id:
                self.claim_conflicts += 1
                self.duplicate_claims_prevented += 1
                # Reject claim: task already owned
                return None

        if rec.state == TaskOwnershipState.CLAIMED:
            if rec.owner_robot_id != msg.robot_id:
                # Conflict: two robots claimed same task in same epoch
                self.claim_conflicts += 1
                if msg.cost < rec.cost:
                    # Lower cost wins, pre-empt prior claim
                    rec.owner_robot_id = msg.robot_id
                    rec.cost = msg.cost
                    rec.claim_timestamp = current_time
                    rec.acks_received.clear()
                else:
                    self.duplicate_claims_prevented += 1
                    return None

        rec.state = TaskOwnershipState.CLAIMED
        rec.owner_robot_id = msg.robot_id
        rec.claim_timestamp = current_time

        # Generate ACK
        return OwnershipMessage(
            msg_type=OwnershipMessageType.TASK_ACK,
            task_id=msg.task_id,
            robot_id=msg.robot_id,
            epoch=rec.current_epoch,
            timestamp=current_time,
            logical_tick=msg.logical_tick,
            cost=msg.cost,
        )

    def handle_ack(self, ack_msg: OwnershipMessage, peer_id: str, current_time: float) -> Optional[OwnershipMessage]:
        """Claiming robot receives an ACK from a peer."""
        rec = self.get_or_create_record(ack_msg.task_id)

        if ack_msg.epoch < rec.current_epoch:
            self.stale_messages_rejected += 1
            return None

        if rec.owner_robot_id != ack_msg.robot_id:
            return None

        rec.acks_received.add(peer_id)
        latency = max(0.0, (current_time - rec.claim_timestamp) * 1000.0)
        self.ack_latencies_ms.append(latency)

        if len(rec.acks_received) >= self.required_acks and rec.state in (TaskOwnershipState.CLAIMED, TaskOwnershipState.PROPOSED):
            rec.state = TaskOwnershipState.ACKED
            rec.ack_timestamp = current_time
            # Commit ownership
            rec.state = TaskOwnershipState.COMMITTED
            rec.commit_timestamp = current_time
            self.successful_claims += 1

            return OwnershipMessage(
                msg_type=OwnershipMessageType.TASK_COMMIT,
                task_id=ack_msg.task_id,
                robot_id=ack_msg.robot_id,
                epoch=rec.current_epoch,
                timestamp=current_time,
                logical_tick=ack_msg.logical_tick,
                cost=rec.cost,
            )
        return None

    def check_timeouts(self, current_time: float) -> List[str]:
        """Check for un-acknowledged claims that have timed out."""
        timed_out_tasks: List[str] = []
        for task_id, rec in self.records.items():
            if rec.state == TaskOwnershipState.CLAIMED:
                if current_time - rec.claim_timestamp > self.ack_timeout_sec:
                    rec.state = TaskOwnershipState.TIMEOUT
                    rec.owner_robot_id = None
                    rec.current_epoch += 1
                    rec.acks_received.clear()
                    timed_out_tasks.append(task_id)
        return timed_out_tasks

    def reclaim_task_on_failure(self, task_id: str, failed_robot_id: str, current_time: float) -> OwnershipMessage:
        """When a robot fails, its active committed task is reclaimed under a bumped epoch."""
        rec = self.get_or_create_record(task_id)
        rec.state = TaskOwnershipState.RECLAIMED
        rec.owner_robot_id = None
        rec.current_epoch += 1
        rec.acks_received.clear()
        self.task_reclaims += 1

        return OwnershipMessage(
            msg_type=OwnershipMessageType.TASK_RECLAIM,
            task_id=task_id,
            robot_id=failed_robot_id,
            epoch=rec.current_epoch,
            timestamp=current_time,
            logical_tick=0,
            payload={"reason": "ROBOT_FAILURE", "previous_owner": failed_robot_id},
        )

    def mark_completed(self, task_id: str, robot_id: str) -> bool:
        """Mark task completed. Prevent duplicate completions."""
        rec = self.get_or_create_record(task_id)
        if rec.state == TaskOwnershipState.COMPLETED:
            # Already completed by someone
            return False
        if rec.owner_robot_id is not None and rec.owner_robot_id != robot_id:
            # Not authorized to complete
            return False
        rec.state = TaskOwnershipState.COMPLETED
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Return ownership protocol performance metrics."""
        mean_ack_lat = (sum(self.ack_latencies_ms) / len(self.ack_latencies_ms)) if self.ack_latencies_ms else 0.0
        return {
            "claim_attempts": self.claim_attempts,
            "successful_claims": self.successful_claims,
            "mean_ack_latency_ms": round(mean_ack_lat, 2),
            "claim_conflicts": self.claim_conflicts,
            "stale_messages_rejected": self.stale_messages_rejected,
            "task_reclaims": self.task_reclaims,
            "duplicate_claims_prevented": self.duplicate_claims_prevented,
        }
