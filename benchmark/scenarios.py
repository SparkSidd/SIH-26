"""Standardized Benchmark Scenarios S0 to S9."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
from simulator.simulation import AMRSimulation
from simulator.warehouse import Warehouse


class ScenarioID(Enum):
    S0_NORMAL = "S0_NORMAL"
    S1_HIGH_CONGESTION = "S1_HIGH_CONGESTION"
    S2_COMM_LATENCY = "S2_COMM_LATENCY"
    S3_PACKET_LOSS = "S3_PACKET_LOSS"
    S4_AISLE_BLOCKAGE = "S4_AISLE_BLOCKAGE"
    S5_ROBOT_FAILURE = "S5_ROBOT_FAILURE"
    S6_TASK_SURGE = "S6_TASK_SURGE"
    S7_COMM_AND_BLOCKAGE = "S7_COMM_AND_BLOCKAGE"
    S8_FAILURE_AND_CONGESTION = "S8_FAILURE_AND_CONGESTION"
    S9_FULL_COMBINED_DISTURBANCE = "S9_FULL_COMBINED_DISTURBANCE"


class ScenarioBuilder:
    """Constructs configured AMRSimulation environments for standardized benchmark scenarios."""

    @staticmethod
    def build_scenario(
        scenario_id: ScenarioID,
        seed: int = 42,
        planner_algorithm: str = "pibt",
        allocator_type: str = "fleet_aware",
        robot_count: int = 6,
    ) -> AMRSimulation:
        """Instantiate simulation parameterized for the given scenario."""
        # Base warehouse setup
        layout = "choke_point" if scenario_id in (ScenarioID.S1_HIGH_CONGESTION, ScenarioID.S8_FAILURE_AND_CONGESTION) else "corridor_heavy"
        warehouse = Warehouse(width=25, height=20, layout_type=layout)

        sim = AMRSimulation(
            warehouse=warehouse,
            robot_count=robot_count,
            planner_algorithm=planner_algorithm,
            allocator_type=allocator_type,
            timestep=0.1,
            seed=seed,
            realtime_factor=0.0,  # Max speed for headless benchmarks
        )

        # Apply specific scenario parameters
        if scenario_id == ScenarioID.S0_NORMAL:
            sim.task_generator.arrival_rate = 0.2

        elif scenario_id == ScenarioID.S1_HIGH_CONGESTION:
            sim.task_generator.arrival_rate = 0.6  # High demand

        elif scenario_id == ScenarioID.S2_COMM_LATENCY:
            sim.comm_mesh.conditions.latency_ms = 250.0  # 250ms latency

        elif scenario_id == ScenarioID.S3_PACKET_LOSS:
            sim.comm_mesh.conditions.packet_loss_rate = 0.25  # 25% loss

        elif scenario_id == ScenarioID.S4_AISLE_BLOCKAGE:
            # Block central corridor at step 200
            sim.schedule_blockage(step=200, cell=(7, 10))

        elif scenario_id == ScenarioID.S5_ROBOT_FAILURE:
            # Fail robot R2 at step 250
            sim.schedule_failure(step=250, robot_id="R2", reason="Motor driver fault")

        elif scenario_id == ScenarioID.S6_TASK_SURGE:
            sim.task_generator.mode = "burst"

        elif scenario_id == ScenarioID.S7_COMM_AND_BLOCKAGE:
            sim.comm_mesh.conditions.packet_loss_rate = 0.20
            sim.schedule_blockage(step=200, cell=(7, 10))

        elif scenario_id == ScenarioID.S8_FAILURE_AND_CONGESTION:
            sim.task_generator.arrival_rate = 0.5
            sim.schedule_failure(step=200, robot_id="R3", reason="Choke point stall")

        elif scenario_id == ScenarioID.S9_FULL_COMBINED_DISTURBANCE:
            sim.comm_mesh.conditions.packet_loss_rate = 0.25
            sim.comm_mesh.conditions.latency_ms = 200.0
            sim.task_generator.arrival_rate = 0.5
            sim.schedule_blockage(step=200, cell=(7, 10))
            sim.schedule_failure(step=300, robot_id="R2", reason="Subsystem overload")

        return sim
