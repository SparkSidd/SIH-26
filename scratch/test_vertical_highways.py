import sys
from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID

SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909]
SCENARIOS = [
    ScenarioID.S0_NORMAL,
    ScenarioID.S1_HIGH_CONGESTION,
    ScenarioID.S6_TASK_SURGE,
    ScenarioID.S8_FAILURE_AND_CONGESTION,
]

# Baseline vs current vs with vertical highways
print("Testing Vertical Highway Directions...")
for sc in SCENARIOS:
    base_times = []
    prop_times = []
    for seed in SEEDS:
        sim_b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, robot_count=6)
        for _ in range(350):
            sim_b.step()
        base_times.append(sim_b.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

        sim_p = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, robot_count=6)
        # Add alternating vertical corridors in corridor_heavy:
        if sc not in (ScenarioID.S1_HIGH_CONGESTION, ScenarioID.S8_FAILURE_AND_CONGESTION):
            for x, v_dir in [(6, (0, -1)), (9, (0, 1)), (12, (0, -1)), (15, (0, 1)), (18, (0, -1)), (21, (0, 1))]:
                for y in range(3, 17):
                    if y not in (9, 10):
                        sim_p.coordinator.preferred_directions[(x, y)] = v_dir
        for _ in range(350):
            sim_p.step()
        prop_times.append(sim_p.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

    mean_b = sum(base_times) / len(base_times)
    mean_p = sum(prop_times) / len(prop_times)
    red = ((mean_b - mean_p) / mean_b) * 100.0
    print(f"{sc.value:<25} | Base: {mean_b:5.2f}s | Prop: {mean_p:5.2f}s | Red: {red:5.2f}%")
