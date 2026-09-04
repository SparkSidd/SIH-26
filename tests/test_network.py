"""Unit tests for P2P network simulation and information age."""

import pytest
from network.communication import CommunicationMesh
from network.message import MessageType
from network.network_conditions import NetworkConditions
from world_model.information_age import InformationAge, InformationAgeCategory


def test_network_latency_delivery():
    # 50ms latency -> 0.05s
    cond = NetworkConditions(latency_ms=50.0, jitter_ms=0.0, packet_loss_rate=0.0)
    mesh = CommunicationMesh(conditions=cond)

    mesh.send_message(
        sender_id="R1",
        receiver_id="R2",
        msg_type=MessageType.STATE,
        payload={"pos": [1, 2]},
        current_sim_time=0.0,
    )

    robot_positions = {"R1": (0, 0), "R2": (1, 1)}
    active_ids = {"R1", "R2"}

    # At t=0.02s: message should still be in-flight
    mesh.step_deliver(0.02, robot_positions, active_ids)
    assert len(mesh.receive_inbox("R2")) == 0

    # At t=0.06s: latency delay elapsed -> delivered to R2
    mesh.step_deliver(0.06, robot_positions, active_ids)
    inbox = mesh.receive_inbox("R2")
    assert len(inbox) == 1
    assert inbox[0].payload["pos"] == [1, 2]


def test_information_age_categorization():
    model = InformationAge(fresh_threshold=0.3, recent_threshold=1.0, stale_threshold=3.0)

    assert model.categorize(0.1) == InformationAgeCategory.FRESH
    assert model.categorize(0.5) == InformationAgeCategory.RECENT
    assert model.categorize(1.8) == InformationAgeCategory.STALE
    assert model.categorize(4.0) == InformationAgeCategory.UNKNOWN
