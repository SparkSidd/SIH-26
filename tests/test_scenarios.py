"""Unit tests for scenario execution across S0 to S9."""

import pytest
from benchmark.scenarios import ScenarioID, ScenarioBuilder


@pytest.mark.parametrize("scenario_id", [
    ScenarioID.S0_NORMAL,
    ScenarioID.S1_HIGH_CONGESTION,
    ScenarioID.S2_COMM_LATENCY,
    ScenarioID.S3_PACKET_LOSS,
    ScenarioID.S4_AISLE_BLOCKAGE,
    ScenarioID.S5_ROBOT_FAILURE,
    ScenarioID.S6_TASK_SURGE,
    ScenarioID.S7_COMM_AND_BLOCKAGE,
    ScenarioID.S8_FAILURE_AND_CONGESTION,
    ScenarioID.S9_FULL_COMBINED_DISTURBANCE,
])
def test_scenario_execution(scenario_id):
    sim = ScenarioBuilder.build_scenario(scenario_id=scenario_id, seed=42, robot_count=6)
    
    # Run 50 simulation ticks
    for _ in range(50):
        sim.step()

    # Safety invariant: ZERO collisions
    assert sim.metrics.total_collisions == 0
    assert len(sim.world.robots) == 6
