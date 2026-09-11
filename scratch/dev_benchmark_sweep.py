"""Development Benchmark Sweep across S0-S9 on non-validation tuning seeds [11, 23, 77, 99]."""
import sys
import time
import numpy as np
sys.path.insert(0, r"c:\Users\thega\PROJECTS\SIH'26")

from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID

DEV_SEEDS = [11, 23, 77, 99]

def run_dev_sweep(seeds=DEV_SEEDS, label="DEV EVALUATION"):
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
    
    print(f"\n{'='*95}")
    print(f"{label} (Seeds: {seeds})")
    print(f"{'='*95}")
    print(f"{'Scenario':<32} | {'Base Time':<10} | {'Prop Time':<10} | {'Reduction':<12} | {'Base Tasks':<10} | {'Prop Tasks':<10} | {'Coll':<5}")
    print(f"{'-'*95}")
    
    all_base_times = []
    all_prop_times = []
    all_base_tasks = []
    all_prop_tasks = []
    total_collisions = 0
    total_deadlocks = 0
    
    t0 = time.perf_counter()
    
    for sc in scenarios:
        print(f"Running {sc.value}...", end="", flush=True)
        sc_base_times = []
        sc_prop_times = []
        sc_base_tasks = []
        sc_prop_tasks = []
        
        for seed in seeds:
            # Run Stop-and-Wait Baseline
            b_sim = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, 6)
            for _ in range(350):
                b_sim.step()
            b_sum = b_sim.metrics.get_summary()
            
            # Run Our System
            p_sim = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, 6)
            for _ in range(350):
                p_sim.step()
            p_sum = p_sim.metrics.get_summary()
            
            sc_base_times.append(b_sum["average_task_completion_time_sec"])
            sc_prop_times.append(p_sum["average_task_completion_time_sec"])
            sc_base_tasks.append(b_sum["total_tasks_completed"])
            sc_prop_tasks.append(p_sum["total_tasks_completed"])
            
            all_base_times.append(b_sum["average_task_completion_time_sec"])
            all_prop_times.append(p_sum["average_task_completion_time_sec"])
            all_base_tasks.append(b_sum["total_tasks_completed"])
            all_prop_tasks.append(p_sum["total_tasks_completed"])
            
            total_collisions += p_sum["total_collisions"]
            total_deadlocks += p_sum.get("deadlocks_detected", 0)
            
        m_b = float(np.mean(sc_base_times))
        m_p = float(np.mean(sc_prop_times))
        red = ((m_b - m_p) / m_b) * 100.0 if m_b > 0 else 0.0
        
        print(f"\r{sc.value:<32} | {m_b:<10.2f} | {m_p:<10.2f} | {red:+11.2f}% | {np.mean(sc_base_tasks):<10.1f} | {np.mean(sc_prop_tasks):<10.1f} | {total_collisions:<5}", flush=True)
        
    elapsed = time.perf_counter() - t0
    agg_b = float(np.mean(all_base_times))
    agg_p = float(np.mean(all_prop_times))
    agg_red = ((agg_b - agg_p) / agg_b) * 100.0
    agg_b_t = float(np.mean(all_base_tasks))
    agg_p_t = float(np.mean(all_prop_tasks))
    
    print(f"{'='*95}")
    print(f"AGGREGATE SUMMARY: Base={agg_b:.2f}s | Proposed={agg_p:.2f}s | REDUCTION={agg_red:+.2f}%")
    print(f"THROUGHPUT:        Base={agg_b_t:.1f} tasks | Proposed={agg_p_t:.1f} tasks (+{((agg_p_t-agg_b_t)/agg_b_t)*100:.1f}%)")
    print(f"SAFETY:            Collisions={total_collisions} | Deadlocks={total_deadlocks}")
    print(f"WALL-CLOCK TIME:   {elapsed:.1f}s ({len(scenarios)*len(seeds)*2} simulation runs)")
    print(f"{'='*95}\n")
    
    return {
        "aggregate_reduction": agg_red,
        "base_time": agg_b,
        "prop_time": agg_p,
        "total_collisions": total_collisions,
        "total_deadlocks": total_deadlocks,
    }

if __name__ == "__main__":
    seeds = [int(s) for s in sys.argv[1:]] if len(sys.argv) > 1 else DEV_SEEDS
    run_dev_sweep(seeds=seeds)
