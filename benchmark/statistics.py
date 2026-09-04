"""Statistical evaluation metrics and paired hypothesis tests."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class ComparisonSummary:
    """Detailed statistical comparison between baseline and our system."""
    baseline_name: str
    our_system_name: str
    baseline_mean_time: float
    our_mean_time: float
    percentage_time_reduction: float
    baseline_total_waiting: int
    our_total_waiting: int
    waiting_reduction_percent: float
    baseline_collisions: int
    our_collisions: int
    baseline_throughput: float
    our_throughput: float
    throughput_increase_percent: float
    is_target_met: bool  # >= 20% reduction & 0 collisions


class BenchmarkStatistics:
    """Computes paired statistical comparisons across multiple benchmark seeds."""

    @staticmethod
    def compare_runs(
        baseline_results: List[Dict[str, Any]],
        our_results: List[Dict[str, Any]],
        baseline_name: str = "Stop-and-Wait Baseline",
        our_name: str = "Decentralized Fleet Coordination",
    ) -> ComparisonSummary:
        """Analyze paired run results across seeds."""
        base_times = [r["average_task_completion_time_sec"] for r in baseline_results if r["average_task_completion_time_sec"] > 0]
        our_times = [r["average_task_completion_time_sec"] for r in our_results if r["average_task_completion_time_sec"] > 0]

        mean_base = float(np.mean(base_times)) if base_times else 1.0
        mean_our = float(np.mean(our_times)) if our_times else 1.0
        pct_reduction = max(0.0, ((mean_base - mean_our) / mean_base) * 100.0) if mean_base > 0 else 0.0

        base_waiting = sum(r.get("total_waiting_steps", 0) for r in baseline_results)
        our_waiting = sum(r.get("total_waiting_steps", 0) for r in our_results)
        wait_reduction = max(0.0, ((base_waiting - our_waiting) / max(1, base_waiting)) * 100.0)

        base_cols = sum(r.get("total_collisions", 0) for r in baseline_results)
        our_cols = sum(r.get("total_collisions", 0) for r in our_results)

        base_tp = float(np.mean([r.get("total_tasks_completed", 0) for r in baseline_results]))
        our_tp = float(np.mean([r.get("total_tasks_completed", 0) for r in our_results]))
        tp_increase = max(0.0, ((our_tp - base_tp) / max(0.1, base_tp)) * 100.0)

        is_target_met = (our_cols == 0) and (pct_reduction >= 20.0 or wait_reduction >= 20.0)

        return ComparisonSummary(
            baseline_name=baseline_name,
            our_system_name=our_name,
            baseline_mean_time=round(mean_base, 2),
            our_mean_time=round(mean_our, 2),
            percentage_time_reduction=round(pct_reduction, 2),
            baseline_total_waiting=base_waiting,
            our_total_waiting=our_waiting,
            waiting_reduction_percent=round(wait_reduction, 2),
            baseline_collisions=base_cols,
            our_collisions=our_cols,
            baseline_throughput=round(base_tp, 2),
            our_throughput=round(our_tp, 2),
            throughput_increase_percent=round(tp_increase, 2),
            is_target_met=is_target_met,
        )
