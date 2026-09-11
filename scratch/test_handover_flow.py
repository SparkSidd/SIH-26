"""Test rolling handover integration and test assertion compliance."""
import sys
sys.path.insert(0, r"c:\Users\thega\PROJECTS\SIH'26")

from simulator.simulation import AMRSimulation
from simulator.task import Task, TaskState

sim = AMRSimulation(seed=42)
r1 = sim.world.robots["R1"]

# Verify no crashes and clean handover during 100 steps
for step in range(100):
    sim.step()
    # Check invariant from test_corridor_blockage_regression
    for t_id, task in sim.world.tasks.items():
        if task.state in (TaskState.ASSIGNED, TaskState.PICKED_UP) and task.assigned_robot_id:
            assigned_r = sim.world.robots.get(task.assigned_robot_id)
            assert assigned_r is not None
            if assigned_r.is_healthy:
                assert assigned_r.current_task_id == t_id, f"Invariant violated for {t_id}"

print("Invariant check PASSED across 100 simulation steps!")
