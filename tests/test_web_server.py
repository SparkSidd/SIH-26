"""Tests for Web Adapter, Serializers and Control Endpoints."""

import pytest
from fastapi.testclient import TestClient
from simulator.simulation import AMRSimulation
from web.serializers import SimulationStateSerializer
from web.server import app, manager


@pytest.fixture
def client():
    return TestClient(app)


def test_simulation_state_serializer():
    sim = AMRSimulation(robot_count=6, seed=42)
    sim.step()

    snapshot = SimulationStateSerializer.serialize_state(sim, scenario_name="S0_NORMAL")

    assert "clock" in snapshot
    assert "warehouse" in snapshot
    assert "robots" in snapshot
    assert "tasks" in snapshot
    assert "congestion" in snapshot
    assert "network" in snapshot
    assert "kpis" in snapshot
    assert "events" in snapshot

    # Verify 6 robots with required fields
    assert len(snapshot["robots"]) == 6
    r0 = snapshot["robots"][0]
    assert "id" in r0
    assert "position" in r0
    assert "battery" in r0
    assert "coordination_mode" in r0
    assert "local_world_model" in r0
    assert "safety" in r0
    assert "planner" in r0

    # Verify warehouse
    wh = snapshot["warehouse"]
    assert wh["width"] == 25
    assert wh["height"] == 20
    assert len(wh["walls"]) > 0
    assert len(wh["shelves"]) > 0


def test_api_state_endpoint(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "robots" in data
    assert len(data["robots"]) == 6
    assert data["kpis"]["total_collisions"] == 0


def test_api_control_step_and_pause(client):
    # Pause
    res = client.post("/api/control/pause")
    assert res.status_code == 200
    assert res.json()["is_paused"] is True

    # Step
    initial_step = manager.sim.clock.current_step
    res = client.post("/api/control/step")
    assert res.status_code == 200
    assert manager.sim.clock.current_step == initial_step + 1

    # Play
    res = client.post("/api/control/play")
    assert res.status_code == 200
    assert res.json()["is_paused"] is False


def test_api_disturbance_injection(client):
    # 1. Block cell
    res = client.post("/api/control/block_cell", json={"x": 7, "y": 10})
    assert res.status_code == 200
    assert (7, 10) in manager.sim.warehouse.blocked_cells

    # 2. Unblock cell
    res = client.post("/api/control/unblock_cell", json={"x": 7, "y": 10})
    assert res.status_code == 200
    assert (7, 10) not in manager.sim.warehouse.blocked_cells

    # 3. Fail robot
    res = client.post("/api/control/fail_robot", json={"robot_id": "R2", "reason": "Test fault"})
    assert res.status_code == 200
    assert manager.sim.world.robots["R2"].is_healthy is False

    # 4. Recover robot
    res = client.post("/api/control/recover_robot", json={"robot_id": "R2"})
    assert res.status_code == 200
    assert manager.sim.world.robots["R2"].is_healthy is True

    # 5. Task surge
    res = client.post("/api/control/task_surge")
    assert res.status_code == 200
    assert res.json()["added_tasks"] == 5

    # 6. Network conditions
    res = client.post("/api/control/network", json={"latency_ms": 150.0, "packet_loss_rate": 0.2})
    assert res.status_code == 200
    assert manager.sim.comm_mesh.conditions.latency_ms == 150.0
    assert manager.sim.comm_mesh.conditions.packet_loss_rate == 0.2


def test_api_algorithm_switching(client):
    # Switch to baseline
    res = client.post("/api/control/algorithm", json={"algorithm": "BASELINE_STOP_AND_WAIT"})
    assert res.status_code == 200
    assert manager.current_algorithm == "BASELINE_STOP_AND_WAIT"
    assert manager.sim.coordinator.multi_agent_planner.algorithm == "astar"

    # Switch back to proposed
    res = client.post("/api/control/algorithm", json={"algorithm": "PROPOSED"})
    assert res.status_code == 200
    assert manager.current_algorithm == "PROPOSED"
    assert manager.sim.coordinator.multi_agent_planner.algorithm == "pibt"
