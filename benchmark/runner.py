"""Headless Benchmark Suite Runner executing paired scenario matrices across seeds."""

import json
import os
import time
from typing import Any, Dict, List, Optional
from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.reports import BenchmarkReporter
from benchmark.scenarios import ScenarioID
from benchmark.statistics import BenchmarkStatistics, ComparisonSummary


class BenchmarkRunner:
    """Executes paired benchmark suites comparing baselines against our decentralized system."""

    def __init__(
        self,
        seeds: Optional[List[int]] = None,
        steps_per_run: int = 500,
        output_dir: str = "results/benchmarks",
    ):
        self.seeds = seeds or [42, 101, 202, 303, 404]
        self.steps_per_run = steps_per_run
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def run_scenario_comparison(
        self,
        scenario_id: ScenarioID = ScenarioID.S0_NORMAL,
        robot_count: int = 6,
    ) -> ComparisonSummary:
        """Run paired comparisons across all seeds for a specific scenario."""
        print(f"\n=======================================================")
        print(f" BENCHMARKING SCENARIO: {scenario_id.value} (Robots={robot_count}, Seeds={len(self.seeds)})")
        print(f"=======================================================")

        baseline_results: List[Dict[str, Any]] = []
        our_results: List[Dict[str, Any]] = []

        for idx, seed in enumerate(self.seeds):
            print(f" -> Running Seed {seed} ({idx+1}/{len(self.seeds)})...")
            
            # 1. Run Baseline (Stop-and-Wait)
            t0 = time.time()
            base_sim = BaselineRunner.get_simulation(
                baseline=BaselineType.STOP_AND_WAIT,
                scenario_id=scenario_id,
                seed=seed,
                robot_count=robot_count,
            )
            for _ in range(self.steps_per_run):
                base_sim.step()
            base_summary = base_sim.metrics.get_summary()
            baseline_results.append(base_summary)

            # 2. Run Our Decentralized System
            our_sim = BaselineRunner.get_simulation(
                baseline=BaselineType.OUR_SYSTEM,
                scenario_id=scenario_id,
                seed=seed,
                robot_count=robot_count,
            )
            for _ in range(self.steps_per_run):
                our_sim.step()
            our_summary = our_sim.metrics.get_summary()
            our_results.append(our_summary)

        # Compute aggregate statistical comparison
        summary = BenchmarkStatistics.compare_runs(
            baseline_results=baseline_results,
            our_results=our_results,
            baseline_name="Stop-and-Wait Baseline",
            our_name="Decentralized Fleet System",
        )

        # Generate reproducibility manifest and report
        manifest = BenchmarkReporter.generate_manifest(
            experiment_id=f"EXP_{scenario_id.value}_{int(time.time())}",
            scenario_name=scenario_id.value,
            seed=self.seeds[0],
            robot_count=robot_count,
            algorithm_stack="PIBT + FleetAwareAllocator + AdaptiveCoordination + SafetySupervisor",
        )

        manifest_path = os.path.join(self.output_dir, f"{scenario_id.value}_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        report_path = os.path.join(self.output_dir, f"{scenario_id.value}_report.md")
        md_content = BenchmarkReporter.generate_markdown_report(
            summary=summary,
            scenario_name=scenario_id.value,
            seeds=self.seeds,
            output_filepath=report_path,
        )

        print("\n--- RESULTS SUMMARY ---")
        print(f"Collisions: Baseline={summary.baseline_collisions} | Ours={summary.our_collisions}")
        print(f"Avg Completion Time: Baseline={summary.baseline_mean_time:.1f}s | Ours={summary.our_mean_time:.1f}s (-{summary.percentage_time_reduction:.1f}%)")
        print(f"Total Waiting Steps: Baseline={summary.baseline_total_waiting} | Ours={summary.our_total_waiting} (-{summary.waiting_reduction_percent:.1f}%)")
        print(f"Verdict: {'PASSED (SIH Target Exceeded)' if summary.is_target_met else 'UNDER REVIEW'}")
        print(f"Report saved to: {report_path}\n")

        return summary
