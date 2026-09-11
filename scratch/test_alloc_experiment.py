import sys
from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID
from coordination.allocator import FleetAwareTaskAllocator, _generate_walkable_path
import numpy as np
from scipy.optimize import linear_sum_assignment
from simulator.task import TaskState

SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909]
SCENARIOS = [
    ScenarioID.S0_NORMAL,
    ScenarioID.S1_HIGH_CONGESTION,
    ScenarioID.S6_TASK_SURGE,
    ScenarioID.S8_FAILURE_AND_CONGESTION,
]

# Define experimental allocator
class ExpFleetAllocator(FleetAwareTaskAllocator):
    def allocate(self, unassigned_tasks, robots, congestion_model=None, is_walkable_fn=None, all_tasks=None):
        assignments = []
        available_candidates = []
        for r in robots.values():
            if not r.is_healthy or r.battery.is_critical or r.state.name == "FAILED":
                continue
            if r.current_task_id is None:
                available_candidates.append((r, r.position, 0.0))
            elif r.next_task_id is None and all_tasks is not None and r.current_task_id in all_tasks:
                cur_t = all_tasks[r.current_task_id]
                if cur_t.state == TaskState.PICKED_UP or getattr(r, "has_payload", False):
                    dist_to_drop = abs(r.position[0] - cur_t.dropoff[0]) + abs(r.position[1] - cur_t.dropoff[1])
                    if dist_to_drop <= 10:
                        start_delay = float(dist_to_drop) * 0.1
                        available_candidates.append((r, cur_t.dropoff, start_delay))

        if not available_candidates:
            return assignments

        sorted_tasks = sorted(
            unassigned_tasks,
            key=lambda t: (t.priority, -(t.deadline or 999999)),
            reverse=True,
        )

        def _cost(cand, task):
            robot, start_pos, start_delay = cand
            path_to_pickup = _generate_walkable_path(start_pos, task.pickup, is_walkable_fn)
            eta_pickup = self.eta_model.estimate_eta(path_to_pickup, congestion_model)
            transit_eta = start_delay + eta_pickup
            path_cong = 0.0
            if congestion_model is not None:
                path_cong = congestion_model.get_path_congestion(path_to_pickup)
            return transit_eta + 0.1 * path_cong - (task.priority - 1.0) * 1.5

        if len(available_candidates) > 1 and len(sorted_tasks) > 1:
            num_cands = len(available_candidates)
            num_tasks = min(len(sorted_tasks), max(num_cands, 24))
            cand_tasks = sorted_tasks[:num_tasks]
            cost_matrix = np.zeros((num_cands, num_tasks), dtype=np.float64)
            for i, c in enumerate(available_candidates):
                for j, t in enumerate(cand_tasks):
                    cost_matrix[i, j] = _cost(c, t)
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            for r_i, c_j in zip(row_ind, col_ind):
                assignments.append((available_candidates[r_i][0].id, cand_tasks[c_j].id))
            return assignments

        for task in sorted_tasks:
            if not available_candidates:
                break
            best_c = min(available_candidates, key=lambda c: _cost(c, task))
            assignments.append((best_c[0].id, task.id))
            available_candidates.remove(best_c)
        return assignments

print("Testing ExpFleetAllocator vs Baseline...")
for sc in SCENARIOS:
    base_times = []
    prop_times = []
    for seed in SEEDS:
        sim_b = BaselineRunner.get_simulation(BaselineType.STOP_AND_WAIT, sc, seed, robot_count=6)
        for _ in range(350):
            sim_b.step()
        base_times.append(sim_b.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

        sim_p = BaselineRunner.get_simulation(BaselineType.OUR_SYSTEM, sc, seed, robot_count=6)
        sim_p.coordinator.fleet_allocator = ExpFleetAllocator()
        for _ in range(350):
            sim_p.step()
        prop_times.append(sim_p.metrics.get_summary().get("average_task_completion_time_sec", 0.0))

    mean_b = sum(base_times) / len(base_times)
    mean_p = sum(prop_times) / len(prop_times)
    red = ((mean_b - mean_p) / mean_b) * 100.0
    print(f"{sc.value:<25} | Base: {mean_b:5.2f}s | Prop: {mean_p:5.2f}s | Red: {red:5.2f}%")
