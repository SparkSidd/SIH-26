"""Experiment: Idle Robot Staging / Rebalancing (Track O).

Hypothesis: AMRs dropping off at x=22 spend ~20 steps traveling empty across the warehouse
when a new task arrives at pickup (x=2). Repositioning idle AMRs from dropoff (x>18) toward
staging cells (x=6..8) along empty westbound aisles reduces empty dispatch latency and
travel duration without causing conflicts.
"""
import sys
import numpy as np
sys.path.insert(0, r"c:\Users\thega\PROJECTS\SIH'26")

from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID

DEV_SEEDS = [11, 23, 77, 99]

def test_idle_repositioning():
    for sc in [ScenarioID.S0_NORMAL, ScenarioID.S1_HIGH_CONGESTION, ScenarioID.S6_TASK_SURGE]:
        base_times = []
        prop_times = []
        for seed in [11, 23]:
            # Baseline
            b_sim = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed=seed)
            for _ in range(350):
                b_sim.step()
            base_times.append(b_sim.metrics.get_summary()["average_task_completion_time_sec"])
            
            # Current Proposed
            p_sim = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed=seed)
            for _ in range(350):
                p_sim.step()
            prop_times.append(p_sim.metrics.get_summary()["average_task_completion_time_sec"])
            
        mb = np.mean(base_times)
        mp = np.mean(prop_times)
        red = (mb - mp) / mb * 100
        print(f"{sc.value}: Baseline={mb:.2f}s | CurrentProposed={mp:.2f}s | Red={red:+.2f}%")

if __name__ == "__main__":
    test_idle_repositioning()
