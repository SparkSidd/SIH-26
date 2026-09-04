"""Baseline definitions for rigorous SIH26123 experimental comparison."""

from enum import Enum
from typing import Tuple
from benchmark.scenarios import ScenarioID, ScenarioBuilder
from simulator.simulation import AMRSimulation


class BaselineType(Enum):
    STOP_AND_WAIT = "stop_and_wait"  # Traditional stop-and-wait collision avoidance + nearest allocation
    GREEDY_ASTAR = "greedy_astar"    # Uncoordinated Space-Time A* + nearest allocation
    OUR_SYSTEM = "our_system"        # Fleet-Aware Allocation + PIBT + Congestion + Resilience


class BaselineRunner:
    """Instantiates comparable simulations configured for specific baseline configurations."""

    @staticmethod
    def get_simulation(
        baseline: BaselineType,
        scenario_id: ScenarioID = ScenarioID.S0_NORMAL,
        seed: int = 42,
        robot_count: int = 6,
    ) -> AMRSimulation:
        """Create exact scenario instance configured for the selected baseline."""
        if baseline == BaselineType.STOP_AND_WAIT:
            # Uses uncoordinated A* with reactive stop-and-wait yielding upon conflict + nearest allocator
            return ScenarioBuilder.build_scenario(
                scenario_id=scenario_id,
                seed=seed,
                planner_algorithm="stop_and_wait",
                allocator_type="nearest",
                robot_count=robot_count,
            )

        elif baseline == BaselineType.GREEDY_ASTAR:
            return ScenarioBuilder.build_scenario(
                scenario_id=scenario_id,
                seed=seed,
                planner_algorithm="astar",
                allocator_type="nearest",
                robot_count=robot_count,
            )

        else:  # OUR_SYSTEM
            return ScenarioBuilder.build_scenario(
                scenario_id=scenario_id,
                seed=seed,
                planner_algorithm="pibt",
                allocator_type="fleet_aware",
                robot_count=robot_count,
            )
