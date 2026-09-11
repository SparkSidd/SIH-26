import sys, os
sys.path.insert(0, os.path.abspath("."))
import time
from benchmark.scenarios import ScenarioBuilder, ScenarioID
from benchmark.baselines import BaselineRunner, BaselineType

DEV_SEEDS = [11, 23, 77, 99]
SCENARIOS = [
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

def run_dev_sweep():
    t0 = time.time()
    total_baseline_time = 0.0
    total_proposed_time = 0.0
    total_runs = 0
    total_collisions = 0

    per_scenario = {}

    for sc in SCENARIOS:
        sc_base = []
        sc_prop = []
        for seed in DEV_SEEDS:
            # Baseline
            sim_b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed=seed)
            for _ in range(350):
                sim_b.step()
            b_res = sim_b.metrics.get_summary()
            b_t = b_res['average_task_completion_time_sec']
            sc_base.append(b_t)

            # Proposed
            sim_p = ScenarioBuilder.build_scenario(sc, seed=seed)
            for _ in range(350):
                sim_p.step()
            p_res = sim_p.metrics.get_summary()
            p_t = p_res['average_task_completion_time_sec']
            sc_prop.append(p_t)
            total_collisions += p_res.get('total_collisions', 0)

            total_baseline_time += b_t
            total_proposed_time += p_t
            total_runs += 1

        b_mean = sum(sc_base) / len(sc_base)
        p_mean = sum(sc_prop) / len(sc_prop)
        red = (b_mean - p_mean) / b_mean * 100
        per_scenario[sc.value] = (b_mean, p_mean, red)
        print(f"[{sc.value[:18]:<18}] Base: {b_mean:.2f}s | Prop: {p_mean:.2f}s | Red: {red:+.2f}%")

    overall_base = total_baseline_time / total_runs
    overall_prop = total_proposed_time / total_runs
    overall_red = (overall_base - overall_prop) / overall_base * 100
    elapsed = time.time() - t0

    print("=" * 60)
    print(f"DEV SEEDS SWEEP (40 runs, {elapsed:.1f}s)")
    print(f"Overall Baseline: {overall_base:.2f}s")
    print(f"Overall Proposed: {overall_prop:.2f}s")
    print(f"Overall Reduction: {overall_red:.2f}%")
    print(f"Proposed Collisions: {total_collisions}")
    print("=" * 60)

if __name__ == "__main__":
    run_dev_sweep()
