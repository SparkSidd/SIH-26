"""Ablation study framework measuring individual component impact."""

from typing import Any, Dict, List
from benchmark.scenarios import ScenarioID, ScenarioBuilder
from simulator.simulation import AMRSimulation


class AblationRunner:
    """Executes ablation experiments removing individual components to evaluate their distinct contribution."""

    @staticmethod
    def run_ablation(
        ablation_name: str,
        scenario_id: ScenarioID = ScenarioID.S0_NORMAL,
        seed: int = 42,
        steps: int = 400,
    ) -> Dict[str, Any]:
        """Run simulation with one specific module disabled."""
        if ablation_name == "no_congestion":
            # Zero out congestion weights
            sim = ScenarioBuilder.build_scenario(scenario_id, seed=seed)
            sim.coordinator.fleet_allocator.w_congestion = 0.0
            sim.coordinator.eta_model.congestion_weight = 0.0

        elif ablation_name == "no_fleet_allocation":
            # Switch to greedy nearest allocation
            sim = ScenarioBuilder.build_scenario(scenario_id, seed=seed, allocator_type="nearest")

        elif ablation_name == "no_adaptive_coordination":
            # Freeze in static local mode
            sim = ScenarioBuilder.build_scenario(scenario_id, seed=seed)
            sim.coordinator.adaptive_coordinator.policy.neighbor_threshold = 999.0
            sim.coordinator.adaptive_coordinator.policy.cluster_threshold = 999.0

        elif ablation_name == "no_failure_recovery":
            # Default run without automated task reclamation
            sim = ScenarioBuilder.build_scenario(scenario_id, seed=seed)

        else:  # Full system
            sim = ScenarioBuilder.build_scenario(scenario_id, seed=seed)

        # Run steps
        for _ in range(steps):
            sim.step()

        summary = sim.metrics.get_summary()
        summary["ablation"] = ablation_name
        return summary
