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

print(f"{'Scenario':<25} | {'System':<10} | {'Compl':<6} | {'Assign':<7} | {'Travel':<7} | {'ConfWait':<8} | {'NormWait':<8} | {'Pick/Del':<8}")
print("-" * 90)

for sc in SCENARIOS:
    for sys_type in [BaselineType.STOP_AND_WAIT, BaselineType.OUR_SYSTEM]:
        totals = {"duration": 0.0, "assign": 0.0, "travel": 0.0, "conf_wait": 0.0, "norm_wait": 0.0, "handover": 0.0, "count": 0}
        for seed in SEEDS:
            sim = BaselineRunner.get_simulation(sys_type, sc, seed, robot_count=6)
            for _ in range(350):
                sim.step()
            from simulator.task import TaskState
            for t in sim.world.tasks.values():
                if t.state == TaskState.DELIVERED:
                    totals["duration"] += t.total_completion_duration
                    totals["assign"] += t.assignment_latency
                    totals["travel"] += t.travel_duration
                    totals["conf_wait"] += t.conflict_wait_duration
                    totals["norm_wait"] += t.normal_wait_duration
                    totals["handover"] += (t.pickup_duration + t.delivery_duration)
                    totals["count"] += 1
        
        n = max(1, totals["count"])
        print(f"{sc.value:<25} | {sys_type.value:<10} | {totals['duration']/n:6.2f} | {totals['assign']/n:7.2f} | {totals['travel']/n:7.2f} | {totals['conf_wait']/n:8.2f} | {totals['norm_wait']/n:8.2f} | {totals['handover']/n:8.2f}")
