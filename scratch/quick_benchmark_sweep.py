"""Quick benchmark sweep across scenarios S0-S9 to evaluate aggregate progress."""
import sys
import numpy as np
sys.path.insert(0, r"c:\Users\thega\PROJECTS\SIH'26")

from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID

def run_sweep(seeds=[42, 101]):
    scenarios = [
        ScenarioID.S0_NORMAL,
        ScenarioID.S1_HIGH_CONGESTION,
        ScenarioID.S2_COMM_LATENCY,
        ScenarioID.S3_PACKET_LOSS,
        ScenarioID.S4_AISLE_BLOCKAGE,
        ScenarioID.S5_ROBOT_FAILURE,
        ScenarioID.S6_TASK_SURGE,
        ScenarioID.S7_COMM_AND_BLOCKAGE,
        ScenarioID.S8_FAILURE_AND_CONGESTION,
        ScenarioID.S9_FULL_COMBINED_DISTURBANCE,
    ]
    
    print(f"\n{'='*85}")
    print(f"BENCHMARK SWEEP (Seeds: {seeds})")
    print(f"{'='*85}")
    print(f"{'Scenario':<32} | {'Base Time':<10} | {'Our Time':<10} | {'Improvement':<12} | {'Base Tasks':<10} | {'Our Tasks':<10}")
    print(f"{'-'*85}")
    
    all_base = []
    all_our = []
    
    for sc in scenarios:
        sc_base = []
        sc_our = []
        sc_bt = []
        sc_ot = []
        
        for seed in seeds:
            # Baseline
            b_sim = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, 6)
            for _ in range(350):
                b_sim.step()
            b_sum = b_sim.metrics.get_summary()
            
            # Our system
            o_sim = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, 6)
            for _ in range(350):
                o_sim.step()
            o_sum = o_sim.metrics.get_summary()
            
            sc_base.append(b_sum["average_task_completion_time_sec"])
            sc_our.append(o_sum["average_task_completion_time_sec"])
            sc_bt.append(b_sum["total_tasks_completed"])
            sc_ot.append(o_sum["total_tasks_completed"])
            
            all_base.append(b_sum["average_task_completion_time_sec"])
            all_our.append(o_sum["average_task_completion_time_sec"])
            
        mean_b = float(np.mean(sc_base))
        mean_o = float(np.mean(sc_our))
        imp = ((mean_b - mean_o) / mean_b) * 100.0 if mean_b > 0 else 0.0
        
        print(f"{sc.value:<32} | {mean_b:<10.2f} | {mean_o:<10.2f} | {imp:+11.2f}% | {np.mean(sc_bt):<10.1f} | {np.mean(sc_ot):<10.1f}")
        
    agg_b = float(np.mean(all_base))
    agg_o = float(np.mean(all_our))
    agg_imp = ((agg_b - agg_o) / agg_b) * 100.0
    print(f"{'='*85}")
    print(f"AGGREGATE: Baseline = {agg_b:.2f}s, Proposed = {agg_o:.2f}s, Reduction = {agg_imp:+.2f}%")
    print(f"{'='*85}\n")

if __name__ == "__main__":
    run_sweep(seeds=[42])
