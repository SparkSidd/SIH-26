"""Comprehensive unit and integration tests for the learning-guided priority decision layer."""

import os
import torch
import pytest

from benchmark.scenarios import ScenarioID, ScenarioBuilder
from coordination.coordinator import FleetCoordinator
from coordination.priority import PriorityEngine
from learning.checkpoint_loader import CheckpointLoader
from learning.config import LearningConfig
from learning.inference import InferenceEngine
from learning.model_adapter import RLRHPPPriorityNet
from learning.observation_adapter import ObservationAdapter
from learning.priority_policy import PriorityPolicy
from simulator.robot import Robot, RobotBattery
from simulator.task import Task, TaskState


@pytest.fixture
def sample_robots():
    robots = {}
    for i in range(6):
        r_id = f"AMR_{i:02d}"
        r = Robot(id=r_id, initial_position=(i * 2 + 1, 3))
        r.velocity = 1.0
        r.heading = 90.0
        r.battery = RobotBattery(current_charge=85.0 - i * 5)
        robots[r_id] = r
    return robots


@pytest.fixture
def sample_tasks():
    tasks = {}
    for i in range(3):
        t_id = f"task_{i:02d}"
        tasks[t_id] = Task(
            id=t_id,
            pickup=(i * 2 + 1, 3),
            dropoff=(i * 2 + 1, 10),
            priority=2.0 + i,
            state=TaskState.ASSIGNED,
            assigned_robot_id=f"AMR_{i:02d}",
        )
    return tasks


def test_checkpoint_loader_and_hash():
    """Verify checkpoint saving, SHA-256 calculation, and loading integrity."""
    config = LearningConfig()
    model = RLRHPPPriorityNet(config)
    tmp_path = os.path.join("results", "test_checkpoint.pt")
    
    file_hash = CheckpointLoader.save_checkpoint(
        model, tmp_path, config, training_stage="test_unit"
    )
    assert len(file_hash) == 64
    assert os.path.exists(tmp_path)
    assert os.path.exists(tmp_path + ".meta.json")

    # Load back
    loaded_model = RLRHPPPriorityNet(config)
    success, msg, meta = CheckpointLoader.load_checkpoint(loaded_model, tmp_path)
    assert success is True
    assert meta["sha256"] == file_hash

    # Clean up
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    if os.path.exists(tmp_path + ".meta.json"):
        os.remove(tmp_path + ".meta.json")


def test_observation_adapter_decentralization_and_shapes(sample_robots, sample_tasks):
    """Verify observation adapter adheres to decentralized feature space and produces correct tensor dimensions."""
    adapter = ObservationAdapter(grid_width=24, grid_height=16, feature_dim=14)
    active_ids = list(sample_robots.keys())
    target_goals = {r_id: (5, 5) for r_id in active_ids}

    obs_tensor = adapter.encode_fleet_state(
        active_robot_ids=active_ids,
        robots=sample_robots,
        tasks=sample_tasks,
        target_goals=target_goals,
        congestion_at_robots={r: 0.5 for r in active_ids},
        blocked_cells=set(),
    )

    # Tensor shape check: [1, N_agents, 14]
    assert obs_tensor.shape == (1, 6, 14)
    # Check normalized ranges [0, 1] or bounded
    assert not torch.isnan(obs_tensor).any()
    assert not torch.isinf(obs_tensor).any()
    assert (obs_tensor >= -1.0).all() and (obs_tensor <= 2.0).all()


def test_inference_output_and_timing(sample_robots):
    """Verify that inference yields valid positive priority scores with microsecond latency tracking."""
    config = LearningConfig()
    model = RLRHPPPriorityNet(config)
    inference = InferenceEngine(model, config)

    active_ids = list(sample_robots.keys())
    dummy_obs = torch.rand((1, len(active_ids), config.feature_dim))

    success, priorities, msg = inference.predict_priorities(active_ids, dummy_obs)
    assert success is True
    assert len(priorities) == len(active_ids)
    for r_id in active_ids:
        assert r_id in priorities
        assert priorities[r_id] >= 1.0  # Normalized positive priority

    assert inference.total_inferences == 1
    assert inference.last_latency_ms > 0.0


def test_deterministic_fallback_on_nan():
    """Verify that NaN inputs cleanly trigger deterministic fallback without crashing."""
    config = LearningConfig()
    model = RLRHPPPriorityNet(config)
    inference = InferenceEngine(model, config)

    active_ids = ["AMR_00", "AMR_01"]
    nan_obs = torch.tensor([[[float("nan")] * config.feature_dim, [1.0] * config.feature_dim]])

    success, priorities, msg = inference.predict_priorities(active_ids, nan_obs)
    assert success is False
    assert "NaN or Inf" in msg
    assert inference.fallback_count == 1


def test_priority_policy_fallback_when_disabled(sample_robots, sample_tasks):
    """Verify that when learning is disabled, PriorityPolicy automatically computes deterministic scores."""
    config = LearningConfig(enabled=False)
    policy = PriorityPolicy(config=config)
    active_ids = list(sample_robots.keys())
    target_goals = {r_id: (5, 5) for r_id in active_ids}

    priorities, is_fallback, status = policy.get_fleet_priorities(
        active_robot_ids=active_ids,
        robots=sample_robots,
        tasks=sample_tasks,
        target_goals=target_goals,
    )

    assert is_fallback is True
    assert "Fallback" in status
    assert len(priorities) == len(active_ids)


def test_priority_policy_fallback_on_missing_checkpoint(sample_robots, sample_tasks):
    """Verify graceful fallback when checkpoint path does not exist."""
    config = LearningConfig(enabled=True, checkpoint_path="non_existent_file.pt")
    policy = PriorityPolicy(config=config)
    active_ids = list(sample_robots.keys())
    target_goals = {r_id: (5, 5) for r_id in active_ids}

    priorities, is_fallback, status = policy.get_fleet_priorities(
        active_robot_ids=active_ids,
        robots=sample_robots,
        tasks=sample_tasks,
        target_goals=target_goals,
    )

    assert is_fallback is True
    assert "Model checkpoint not loaded" in status
    assert len(priorities) == len(active_ids)


def test_end_to_end_simulation_with_learning():
    """Verify that an end-to-end simulation executes safely with learning enabled."""
    sim = ScenarioBuilder.build_scenario(
        scenario_id=ScenarioID.S1_HIGH_CONGESTION,
        seed=42,
        learning_enabled=True,
    )
    assert sim.coordinator.learning_policy is not None
    assert sim.coordinator.learning_policy.config.enabled is True

    # Advance 40 simulation steps
    for _ in range(40):
        sim.step()

    summary = sim.metrics.get_summary()
    assert summary["total_collisions"] == 0
    assert summary["total_tasks_completed"] >= 0
    assert sim.coordinator.learning_telemetry["enabled"] is True


def test_safety_supervisor_authority_over_learning():
    """Verify that the SafetySupervisor maintains absolute veto authority regardless of learned priorities."""
    from execution.action import RobotAction, ActionType
    from safety.supervisor import SafetySupervisor
    
    supervisor = SafetySupervisor()
    robots = {
        "AMR_00": Robot(id="AMR_00", initial_position=(5, 5)),
        "AMR_01": Robot(id="AMR_01", initial_position=(5, 6)),
    }
    # Both attempt to move into the exact same cell (5, 7)
    candidate_actions = {
        "AMR_00": RobotAction(action_type=ActionType.MOVE, target_cell=(5, 7)),
        "AMR_01": RobotAction(action_type=ActionType.MOVE, target_cell=(5, 7)),
    }
    # Learned model gave AMR_00 higher priority
    priorities = {"AMR_00": 9.9, "AMR_01": 1.2}
    current_positions = {r_id: r.position for r_id, r in robots.items()}

    approved = supervisor.filter_actions(
        candidate_actions=candidate_actions,
        current_positions=current_positions,
        blocked_cells=set(),
        failed_robot_ids=set(),
        robot_priorities=priorities,
    )
    
    # AMR_00 gets (5, 7), AMR_01 is forced to yield (WAIT at its current position)
    assert approved["AMR_00"].target_cell == (5, 7)
    assert approved["AMR_01"].target_cell == (5, 6)
    assert approved["AMR_01"].action_type == ActionType.WAIT
