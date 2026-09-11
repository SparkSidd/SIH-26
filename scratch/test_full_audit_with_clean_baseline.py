import sys
from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID
import numpy as np

SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909]
SCENARIOS = list(ScenarioID)

print("=" * 80)
print("Evaluating All 10 Scenarios x 10 Seeds with Clean Baseline vs Optimized Proposed")
print("=" * 80)

all_base_times = []
all_prop_times = []
scenario_results = []

for sc in SCENARIOS:
    b_times = []
    p_times = []
    for seed in SEEDS:
        # 1. Clean Baseline (no simulation-level station clearance)
        sim_b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, robot_count=6)
        orig_update = sim_b._update_task_lifecycles
        def update_clean(sim_time, step):
            orig_update(sim_time, step)
            for r in sim_b.world.robots.values():
                if r.state.name == "GOING_TO_CHARGER" and r.wait_reason == "Clearing station to parking bay":
                    r.set_state(r.state.IDLE, "Idle awaiting task")
                    r.target_position = None
        sim_b._update_task_lifecycles = update_clean
        for _ in range(350):
            sim_b.step()
        b_times.append(sim_b.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

        # 2. Optimized Proposed System
        sim_p = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, robot_count=6)
        for _ in range(350):
            sim_p.step()
        p_times.append(sim_p.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

    mb = float(np.mean(b_times))
    mp = float(np.mean(p_times))
    red = ((mb - mp) / mb) * 100.0
    all_base_times.extend(b_times)
    all_prop_times.extend(p_times)
    status = "TARGET REACHED (>=20%)" if red >= 20.0 else f"SUB-TARGET ({red:.1f}%)"
    print(f"{sc.value:<28} | Base: {mb:5.2f}s | Prop: {mp:5.2f}s | Red: {red:5.2f}% | {status}")
    scenario_results.append((sc.value, mb, mp, red))

overall_b = float(np.mean(all_base_times))
overall_p = float(np.mean(all_prop_times))
overall_red = ((overall_b - overall_p) / overall_b) * 100.0

print("=" * 80)
print(f"AGGREGATE: Baseline = {overall_b:.2f}s | Proposed = {overall_p:.2f}s | REDUCTION = {overall_red:.2f}%")
print("=" * 80)
