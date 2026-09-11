import sys
from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID
from simulator.robot import RobotState

SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909]
SCENARIOS = [
    ScenarioID.S0_NORMAL,
    ScenarioID.S1_HIGH_CONGESTION,
    ScenarioID.S6_TASK_SURGE,
    ScenarioID.S8_FAILURE_AND_CONGESTION,
]

print("Testing Inbound Staging (clearing to Westbound parking bays (1, 1) and (1, 18))...")

# Function to run simulation with West-clearing for proposed system
def run_eval():
    for sc in SCENARIOS:
        base_times = []
        prop_times = []
        for seed in SEEDS:
            # Baseline (unmodified)
            sim_b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, robot_count=6)
            for _ in range(350):
                sim_b.step()
            base_times.append(sim_b.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

            # Proposed with Inbound Staging
            sim_p = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, robot_count=6)
            for _ in range(350):
                # Check for idle robots at dropoff stations and send them toward inbound staging (1, 1) or (1, 18)
                for r in sim_p.world.robots.values():
                    if r.is_healthy and r.state == RobotState.IDLE and r.current_task_id is None:
                        if r.position[0] > 18:  # In outbound zone
                            # Choose closer inbound bay (1, 1) or (1, 18)
                            target = (1, 1) if r.position[1] < 10 else (1, 18)
                            r.set_state(RobotState.GOING_TO_CHARGER, "Repositioning toward inbound staging")
                            r.target_position = target
                sim_p.step()
            prop_times.append(sim_p.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

        mb = sum(base_times) / len(base_times)
        mp = sum(prop_times) / len(prop_times)
        red = ((mb - mp) / mb) * 100.0
        print(f"{sc.value:<25} | Base: {mb:5.2f}s | Prop: {mp:5.2f}s | Red: {red:5.2f}%")

if __name__ == "__main__":
    run_eval()
