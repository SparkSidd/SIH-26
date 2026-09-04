"""Scenarios Registry."""

from typing import Any, Dict
from benchmark.scenarios import ScenarioID, ScenarioBuilder

SCENARIOS: Dict[str, ScenarioID] = {
    "S0_NORMAL": ScenarioID.S0_NORMAL,
    "S1_HIGH_CONGESTION": ScenarioID.S1_HIGH_CONGESTION,
    "S2_COMM_LATENCY": ScenarioID.S2_COMM_LATENCY,
    "S3_PACKET_LOSS": ScenarioID.S3_PACKET_LOSS,
    "S4_AISLE_BLOCKAGE": ScenarioID.S4_AISLE_BLOCKAGE,
    "S5_ROBOT_FAILURE": ScenarioID.S5_ROBOT_FAILURE,
    "S6_TASK_SURGE": ScenarioID.S6_TASK_SURGE,
    "S7_COMM_AND_BLOCKAGE": ScenarioID.S7_COMM_AND_BLOCKAGE,
    "S8_FAILURE_AND_CONGESTION": ScenarioID.S8_FAILURE_AND_CONGESTION,
    "S9_FULL_COMBINED_DISTURBANCE": ScenarioID.S9_FULL_COMBINED_DISTURBANCE,
}


def get_scenario(name: str, **kwargs) -> Any:
    """Retrieve and build scenario by name."""
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{name}'. Available: {list(SCENARIOS.keys())}")
    return ScenarioBuilder.build_scenario(SCENARIOS[name], **kwargs)
