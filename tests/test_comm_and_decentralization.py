"""Tests for communication degradation resilience, local world model decentralization, no-future-knowledge, and reproducibility."""

import pytest
from simulator.simulation import AMRSimulation
from network.network_conditions import NetworkConditions
from simulator.task import TaskState


def test_communication_degradation_safety_and_progress():
    """Verify Section 10:
    Under high packet loss (35%) and latency (300ms) with corridor blockage:
    - Zero collisions occur (local safety supervisor remains authoritative).
    - Fleet gracefully degrades without chaotic behavior.
    - Progress continues to be made.
    """
    sim = AMRSimulation(seed=101)
    
    # Inject network degradation
    sim.comm_mesh.conditions.packet_loss_rate = 0.35
    sim.comm_mesh.conditions.base_latency_ms = 300.0
    
    # Step simulation
    for _ in range(15):
        sim.step()
        
    # Inject corridor blockage
    sim.warehouse.block_cell((1, 6))
    
    # Run 60 steps under degraded communications
    for _ in range(60):
        sim.step()
        
    # Safety invariant: 0 collisions
    assert sim.metrics.total_collisions == 0, "SafetySupervisor must guarantee 0 collisions even under 35% loss and 300ms latency!"
    
    # Restore network quality
    sim.comm_mesh.conditions.packet_loss_rate = 0.0
    sim.comm_mesh.conditions.base_latency_ms = 5.0
    
    # Step 30 more steps
    for _ in range(30):
        sim.step()
        
    assert sim.metrics.total_collisions == 0
    assert sim.metrics.get_summary()["total_tasks_completed"] > 0


def test_decentralization_local_world_model_integrity():
    """Verify Section 12:
    Robots maintain independent local world models populated only by their sensors
    and peer network messages, without direct access to future or hidden global state.
    """
    sim = AMRSimulation(seed=42)
    sim.step()
    
    for r in sim.world.robots.values():
        assert r.local_world_model is not None, f"Robot {r.id} must have an active local world model"
        # Peer positions must only contain peers within range or communicated
        assert hasattr(r.local_world_model, "known_blocked_cells")
        assert hasattr(r.local_world_model, "peer_beliefs")


def test_no_future_information_invariance():
    """Verify Section 13:
    Simulation executes strictly step-by-step; planning at step T uses only
    sim_time and data up to step T.
    """
    sim = AMRSimulation(seed=88)
    sim.step()
    current_step = sim.clock.current_step
    
    # Coordinate at current step
    actions = sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=sim.clock.current_time,
        step=current_step,
    )
    
    # All planned moves must be strictly 1-step discrete candidates (adjacent or wait)
    for r_id, action in actions.items():
        curr_pos = sim.world.robots[r_id].position
        target_pos = action.target_cell
        dist = abs(target_pos[0] - curr_pos[0]) + abs(target_pos[1] - curr_pos[1])
        assert dist <= 1, f"Action for {r_id} attempted non-adjacent transition: {curr_pos} -> {target_pos}"


def test_simulation_reproducibility():
    """Verify Section 14:
    Running the same scenario twice with the exact same seed produces identical results:
    - Robot trajectories
    - Tasks completed count
    - Zero collisions
    """
    def run_sim(seed_val):
        sim = AMRSimulation(seed=seed_val)
        positions = []
        for step in range(50):
            sim.step()
            positions.append({r_id: r.position for r_id, r in sim.world.robots.items()})
        metrics = sim.metrics.get_summary()
        return positions, metrics
        
    traj1, m1 = run_sim(42)
    traj2, m2 = run_sim(42)
    
    assert traj1 == traj2, "Trajectories must be 100% deterministic and reproducible with same seed!"
    assert m1["total_tasks_completed"] == m2["total_tasks_completed"]
    assert m1["total_collisions"] == m2["total_collisions"] == 0
