import sys
from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID
from coordination.allocator import FleetAwareTaskAllocator

SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909]
SCENARIOS = [
    ScenarioID.S0_NORMAL,
    ScenarioID.S1_HIGH_CONGESTION,
    ScenarioID.S6_TASK_SURGE,
    ScenarioID.S8_FAILURE_AND_CONGESTION,
]

print("Running baseline vs proposed across 4 key scenarios...")
for sc in SCENARIOS:
    base_times = []
    prop_times = []
    for seed in SEEDS:
        sim_b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, robot_count=6)
        for _ in range(350):
            sim_b.step()
        sum_b = sim_b.metrics.get_summary()
        base_times.append(sum_b.get("average_task_completion_time_sec", 0.0))

        sim_p = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, robot_count=6)
        for _ in range(350):
            sim_p.step()
        sum_p = sim_p.metrics.get_summary()
        prop_times.append(sum_p.get("average_task_completion_time_sec", 0.0))

    mean_b = sum(base_times) / len(base_times)
    mean_p = sum(prop_times) / len(prop_times)
    red = ((mean_b - mean_p) / mean_b) * 100.0
    print(f"{sc.value:<25} | Base: {mean_b:5.2f}s | Prop: {mean_p:5.2f}s | Red: {red:5.2f}%")
