"""Test impact of guiding PIBT with planned path waypoints."""
import sys
sys.path.insert(0, r"c:\Users\thega\PROJECTS\SIH'26")

from benchmark.baselines import BaselineRunner, BaselineType
from benchmark.scenarios import ScenarioID

def test_s1_with_path_guidance():
    sim = BaselineRunner.get_simulation(
        baseline=BaselineType.OUR_SYSTEM,
        scenario_id=ScenarioID.S1_HIGH_CONGESTION,
        seed=42,
        robot_count=6,
    )
    
    # Run 350 steps
    for step in range(350):
        sim.step()
        
    summary = sim.metrics.get_summary()
    completed = [t for t in sim.world.tasks.values() if t.is_completed]
    durations = [t.total_completion_duration for t in completed if t.total_completion_duration is not None]
    
    print(f"[OUR_SYSTEM S1 with current coordinator]")
    print(f"  Completed Tasks: {len(completed)}")
    print(f"  Avg Completion Time: {summary['average_task_completion_time_sec']}s (durations mean: {sum(durations)/len(durations):.3f}s)")
    print(f"  Total Wait Steps: {summary['total_waiting_steps']}")

if __name__ == "__main__":
    test_s1_with_path_guidance()
