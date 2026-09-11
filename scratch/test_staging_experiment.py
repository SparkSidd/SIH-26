import sys, os
sys.path.insert(0, os.path.abspath("."))
import copy
from benchmark.scenarios import ScenarioBuilder, ScenarioID
from benchmark.baselines import BaselineRunner, BaselineType

def test_staging():
    print("Testing Idle Staging Effect on S0, S1, S6 (seed 42)...")
    for sc_id in [ScenarioID.S0_NORMAL, ScenarioID.S1_HIGH_CONGESTION, ScenarioID.S6_TASK_SURGE]:
        # 1. Baseline
        b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc_id, seed=42)
        for _ in range(350):
            b.step()
        b_sum = b.metrics.get_summary()

        # 2. Current Proposed
        p = ScenarioBuilder.build_scenario(sc_id, seed=42)
        for _ in range(350):
            p.step()
        p_sum = p.metrics.get_summary()

        b_time = b_sum['average_task_completion_time_sec']
        p_time = p_sum['average_task_completion_time_sec']
        red = (b_time - p_time) / b_time * 100

        print(f"[{sc_id.value[:10]}] Baseline: {b_time:.2f}s | Proposed: {p_time:.2f}s | Reduction: {red:.2f}% | Tasks: {p_sum['total_tasks_completed']}")

if __name__ == "__main__":
    test_staging()
