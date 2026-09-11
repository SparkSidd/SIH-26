import sys
from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID

SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909]

print("Testing Baseline without station clearance vs Proposed with station clearance...")

for sc in [ScenarioID.S0_NORMAL, ScenarioID.S1_HIGH_CONGESTION, ScenarioID.S6_TASK_SURGE, ScenarioID.S8_FAILURE_AND_CONGESTION]:
    base_times = []
    prop_times = []
    for seed in SEEDS:
        # Run baseline without station clearance:
        sim_b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, robot_count=6)
        # Temporarily disable station clearance in step for baseline
        orig_update = sim_b._update_task_lifecycles
        def update_without_clearance(sim_time, step):
            orig_update(sim_time, step)
            # Revert any GOING_TO_CHARGER forced by clearance
            for r in sim_b.world.robots.values():
                if r.state.name == "GOING_TO_CHARGER" and r.wait_reason == "Clearing station to parking bay":
                    r.set_state(r.state.IDLE, "Idle awaiting task")
                    r.target_position = None
        sim_b._update_task_lifecycles = update_without_clearance

        for _ in range(350):
            sim_b.step()
        base_times.append(sim_b.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

        # Run proposed (with our optimized coordinator)
        sim_p = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, robot_count=6)
        for _ in range(350):
            sim_p.step()
        prop_times.append(sim_p.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

    mb = sum(base_times) / len(base_times)
    mp = sum(prop_times) / len(prop_times)
    red = ((mb - mp) / mb) * 100.0
    print(f"{sc.value:<25} | Baseline: {mb:5.2f}s | Proposed: {mp:5.2f}s | Reduction: {red:5.2f}%")
