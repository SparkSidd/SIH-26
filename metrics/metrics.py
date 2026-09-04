"""Fleet metrics engine tracking task completion times, throughput, collisions, and deadlocks."""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class FleetMetricsSnapshot:
    """Snapshot of fleet metrics at a specific simulation timestep."""
    step: int
    sim_time: float
    total_tasks_completed: int
    total_tasks_created: int
    active_robots: int
    total_waiting_steps: int
    total_collisions: int
    total_deadlocks: int
    total_safety_interventions: int
    total_messages_sent: int
    total_messages_dropped: int
    average_task_completion_time: float
    throughput_tasks_per_min: float
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    average_planning_latency_ms: float = 0.0


class FleetMetrics:
    """Gathers and calculates comprehensive fleet operational statistics."""

    def __init__(self):
        self.snapshots: List[FleetMetricsSnapshot] = []
        self.task_completion_durations: List[float] = []
        self.total_collisions: int = 0
        self.total_deadlocks: int = 0
        self.total_safety_interventions: int = 0
        self.total_replannings: int = 0
        self.planning_latencies_ms: List[float] = []

    def record_task_completed(self, duration: float) -> None:
        """Record completed task duration."""
        self.task_completion_durations.append(duration)

    def record_planning_latency(self, latency_ms: float) -> None:
        """Record planning decision computation duration."""
        self.planning_latencies_ms.append(latency_ms)

    def record_snapshot(
        self,
        step: int,
        sim_time: float,
        total_created: int,
        total_completed: int,
        active_robots: int,
        waiting_steps: int,
        messages_sent: int,
        messages_dropped: int,
        cpu_pct: float = 0.0,
        mem_mb: float = 0.0,
    ) -> FleetMetricsSnapshot:
        """Capture periodic time-series snapshot."""
        avg_time = float(np.mean(self.task_completion_durations)) if self.task_completion_durations else 0.0
        # Throughput = completed / (sim_time / 60)
        throughput = (total_completed / (sim_time / 60.0)) if sim_time > 0 else 0.0
        avg_latency = float(np.mean(self.planning_latencies_ms[-20:])) if self.planning_latencies_ms else 0.0

        snapshot = FleetMetricsSnapshot(
            step=step,
            sim_time=sim_time,
            total_tasks_completed=total_completed,
            total_tasks_created=total_created,
            active_robots=active_robots,
            total_waiting_steps=waiting_steps,
            total_collisions=self.total_collisions,
            total_deadlocks=self.total_deadlocks,
            total_safety_interventions=self.total_safety_interventions,
            total_messages_sent=messages_sent,
            total_messages_dropped=messages_dropped,
            average_task_completion_time=round(avg_time, 2),
            throughput_tasks_per_min=round(throughput, 2),
            cpu_percent=round(cpu_pct, 1),
            memory_mb=round(mem_mb, 1),
            average_planning_latency_ms=round(avg_latency, 2),
        )

        self.snapshots.append(snapshot)
        return snapshot

    def get_summary(self) -> Dict[str, Any]:
        """Compute aggregate benchmark summary statistics."""
        avg_time = float(np.mean(self.task_completion_durations)) if self.task_completion_durations else 0.0
        median_time = float(np.median(self.task_completion_durations)) if self.task_completion_durations else 0.0
        std_time = float(np.std(self.task_completion_durations)) if self.task_completion_durations else 0.0

        last_snap = self.snapshots[-1] if self.snapshots else None

        return {
            "total_tasks_completed": len(self.task_completion_durations),
            "average_task_completion_time_sec": round(avg_time, 2),
            "median_task_completion_time_sec": round(median_time, 2),
            "std_task_completion_time_sec": round(std_time, 2),
            "total_collisions": self.total_collisions,
            "total_deadlocks": self.total_deadlocks,
            "total_safety_interventions": self.total_safety_interventions,
            "total_waiting_steps": last_snap.total_waiting_steps if last_snap else 0,
            "total_messages_sent": last_snap.total_messages_sent if last_snap else 0,
            "total_messages_dropped": last_snap.total_messages_dropped if last_snap else 0,
            "average_planning_latency_ms": round(float(np.mean(self.planning_latencies_ms)), 2) if self.planning_latencies_ms else 0.0,
        }
