"""Compare official benchmark runner vs diagnostic runner under exact identical conditions."""
import sys
import os
import json
sys.path.insert(0, r"c:\Users\thega\PROJECTS\SIH'26")

from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID
from benchmark.sih_metrics_audit import SIHMetricsAuditor

def compare_parity():
    auditor = SIHMetricsAuditor(steps_per_run=350, robot_count=6)
    target_scenarios = [
        ScenarioID.S0_NORMAL,
        ScenarioID.S1_HIGH_CONGESTION,
        ScenarioID.S6_TASK_SURGE,
        ScenarioID.S8_FAILURE_AND_CONGESTION,
    ]
    
    print("=" * 80)
    print("PARITY RECONCILIATION: OFFICIAL AUDITOR vs DIRECT SIMULATION (Seed 42)")
    print("=" * 80)
    
    for sc in target_scenarios:
        print(f"\n--- Scenario: {sc.value} (Seed 42) ---")
        for b_type in [BaselineType.STOP_AND_WAIT, BaselineType.OUR_SYSTEM]:
            # Method A: Official benchmark auditor
            official_res = auditor.run_single_simulation(b_type, sc, 42)
            
            # Method B: Direct simulation run
            sim = BaselineRunner.get_simulation(
                baseline=b_type,
                scenario_id=sc,
                seed=42,
                robot_count=6,
            )
            for _ in range(350):
                sim.step()
            summary = sim.metrics.get_summary()
            
            # Tasks inspection
            completed_tasks = [t for t in sim.world.tasks.values() if t.is_completed]
            durations = [t.total_completion_duration for t in completed_tasks if t.total_completion_duration is not None]
            
            print(f"[{b_type.value}]")
            print(f"  Official Auditor:")
            print(f"    Tasks Completed: {official_res['tasks_completed']}")
            print(f"    Avg Completion Time: {official_res['avg_completion_time_sec']}s")
            print(f"    Waiting Steps: {official_res['total_waiting_steps']}")
            print(f"  Direct Simulation:")
            print(f"    Tasks Completed: {summary['total_tasks_completed']} (world completed: {len(completed_tasks)})")
            print(f"    Avg Completion Time: {summary['average_task_completion_time_sec']}s (durations mean: {sum(durations)/len(durations):.3f}s)")
            print(f"    Waiting Steps: {summary['total_waiting_steps']}")
            
            # Check for parity
            time_match = abs(official_res['avg_completion_time_sec'] - summary['average_task_completion_time_sec']) < 1e-4
            task_match = official_res['tasks_completed'] == summary['total_tasks_completed']
            print(f"  PARITY CHECK: {'MATCH' if (time_match and task_match) else 'MISMATCH'}")

if __name__ == "__main__":
    compare_parity()
