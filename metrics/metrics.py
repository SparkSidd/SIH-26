"""Fleet metrics engine tracking task completion times, throughput, collisions, deadlocks, and plan vs. execution gap."""

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

        # Plan vs Execution Tracking (MultiRobotBattle pattern)
        self.planned_path_lengths: List[int] = []
        self.planned_makespans: List[float] = []
        self.executed_path_lengths: List[int] = []
        self.executed_makespans: List[float] = []
        self.actual_wait_steps: List[int] = []
        self.actual_reroute_events: int = 0

        # Safety & Invariant Tracking
        self.vertex_conflicts_prevented: int = 0
        self.edge_swap_conflicts_prevented: int = 0
        self.obstacle_conflicts_prevented: int = 0
        self.emergency_stops: int = 0

        # Battery / Energy Tracking
        self.minimum_battery_observed: float = 100.0
        self.charging_events: int = 0
        self.charging_time_total_sec: float = 0.0

    def record_task_completed(self, duration: float) -> None:
        """Record completed task duration."""
        self.task_completion_durations.append(duration)

    def record_planning_latency(self, latency_ms: float) -> None:
        """Record planning decision computation duration."""
        self.planning_latencies_ms.append(latency_ms)

    def record_plan(self, path_length: int, estimated_makespan: float) -> None:
        """Record planner expectations before physical execution."""
        self.planned_path_lengths.append(path_length)
        self.planned_makespans.append(estimated_makespan)

    def record_execution(self, actual_path_length: int, actual_makespan: float, wait_steps: int = 0) -> None:
        """Record actual physical execution outcome after task delivery."""
        self.executed_path_lengths.append(actual_path_length)
        self.executed_makespans.append(actual_makespan)
        self.actual_wait_steps.append(wait_steps)

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
        # Derived throughput equivalent = completed / (sim_time / 60)
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
        sim_time = last_snap.sim_time if last_snap else 0.0

        mean_planned_len = float(np.mean(self.planned_path_lengths)) if self.planned_path_lengths else 0.0
        mean_exec_len = float(np.mean(self.executed_path_lengths)) if self.executed_path_lengths else 0.0
        mean_planned_make = float(np.mean(self.planned_makespans)) if self.planned_makespans else 0.0
        mean_exec_make = float(np.mean(self.executed_makespans)) if self.executed_makespans else 0.0

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
            "median_planning_latency_ms": round(float(np.median(self.planning_latencies_ms)), 2) if self.planning_latencies_ms else 0.0,
            "p95_planning_latency_ms": round(float(np.percentile(self.planning_latencies_ms, 95)), 2) if self.planning_latencies_ms else 0.0,
            "max_planning_latency_ms": round(float(np.max(self.planning_latencies_ms)), 2) if self.planning_latencies_ms else 0.0,
            "plan_vs_execution": {
                "mean_planned_path_length": round(mean_planned_len, 2),
                "mean_executed_path_length": round(mean_exec_len, 2),
                "mean_planned_makespan_sec": round(mean_planned_make, 2),
                "mean_executed_makespan_sec": round(mean_exec_make, 2),
                "path_execution_efficiency_pct": round((mean_planned_len / max(1.0, mean_exec_len)) * 100.0, 1) if mean_exec_len > 0 else 100.0,
            },
            "derived_throughput_equivalent_tasks_per_min": round((len(self.task_completion_durations) / max(0.1, sim_time / 60.0)), 2),
            "battery_summary": {
                "minimum_battery_observed": round(self.minimum_battery_observed, 1),
                "charging_events": self.charging_events,
                "charging_time_total_sec": round(self.charging_time_total_sec, 1),
            },
        }
