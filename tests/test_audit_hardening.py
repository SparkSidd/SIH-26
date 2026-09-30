"""Automated tests for SIH26123 audit hardening and newly integrated architectural features:

1. Task Claim / ACK / Commit ownership protocol
2. Space-Time Reservation timeline & dynamic invalidation
3. Event-driven replanning triggers, cooldown & deduplication
4. Canonical metrics schema & test manifest consistency
5. Web self-check and reservation API endpoints
"""

import json
import os
import pytest
from typing import Dict, Tuple

from coordination.task_ownership import (
    TaskOwnershipProtocol,
    TaskOwnershipState,
    OwnershipMessageType,
    OwnershipMessage,
)
from planning.reservation import SpaceTimeReservationTable
from planning.replanning import EventDrivenReplanner, ReplanningTrigger
from planning.astar import SpaceTimeAStarPlanner, PlannerStatusCode
from simulator.task import Task, TaskState


# ==============================================================================
# 1. TASK CLAIM / ACK / COMMIT PROTOCOL TESTS
# ==============================================================================

def test_task_claim_ack_commit_lifecycle():
    """Verify normal UNASSIGNED -> PROPOSED -> CLAIMED -> ACKED -> COMMITTED lifecycle."""
    proto = TaskOwnershipProtocol(ack_timeout_sec=2.0, required_acks=1)
    
    # 1. Propose assignment
    claim_msg = proto.propose_assignment("T_01", "R01", cost=12.5, timestamp=1.0, tick=10)
    assert claim_msg.msg_type == OwnershipMessageType.TASK_CLAIM
    assert claim_msg.task_id == "T_01"
    assert claim_msg.robot_id == "R01"
    assert claim_msg.epoch == 1

    # 2. Peer receives claim and issues ACK
    ack_msg = proto.handle_claim(claim_msg, current_time=1.05)
    assert ack_msg is not None
    assert ack_msg.msg_type == OwnershipMessageType.TASK_ACK
    assert ack_msg.epoch == 1

    # 3. Claiming robot receives ACK and commits
    commit_msg = proto.handle_ack(ack_msg, peer_id="R02", current_time=1.10)
    assert commit_msg is not None
    assert commit_msg.msg_type == OwnershipMessageType.TASK_COMMIT
    assert commit_msg.robot_id == "R01"

    rec = proto.records["T_01"]
    assert rec.state == TaskOwnershipState.COMMITTED
    assert rec.owner_robot_id == "R01"
    assert proto.successful_claims == 1


def test_stale_claim_rejected_by_monotonic_epoch():
    """Verify that messages with stale epochs are strictly rejected."""
    proto = TaskOwnershipProtocol()
    rec = proto.get_or_create_record("T_02")
    rec.current_epoch = 3  # Current active epoch is 3

    stale_claim = OwnershipMessage(
        msg_type=OwnershipMessageType.TASK_CLAIM,
        task_id="T_02",
        robot_id="R03",
        epoch=2,  # Stale epoch!
        timestamp=2.0,
        logical_tick=20,
    )
    res = proto.handle_claim(stale_claim, current_time=2.1)
    assert res is None
    assert proto.stale_messages_rejected == 1


def test_duplicate_claim_prevention_on_committed_task():
    """Verify that a second robot cannot claim a task already committed to another robot."""
    proto = TaskOwnershipProtocol()
    rec = proto.get_or_create_record("T_03")
    rec.state = TaskOwnershipState.COMMITTED
    rec.owner_robot_id = "R01"
    rec.current_epoch = 1

    duplicate_claim = OwnershipMessage(
        msg_type=OwnershipMessageType.TASK_CLAIM,
        task_id="T_03",
        robot_id="R02",
        epoch=1,
        timestamp=3.0,
        logical_tick=30,
        cost=15.0,
    )
    res = proto.handle_claim(duplicate_claim, current_time=3.05)
    assert res is None
    assert proto.claim_conflicts == 1
    assert proto.duplicate_claims_prevented == 1


def test_ack_timeout_and_release():
    """Verify that an unacknowledged claim times out and increments epoch."""
    proto = TaskOwnershipProtocol(ack_timeout_sec=1.0)
    claim_msg = proto.propose_assignment("T_04", "R01", cost=10.0, timestamp=1.0, tick=10)
    proto.handle_claim(claim_msg, current_time=1.0)

    # Fast forward time beyond timeout
    timed_out = proto.check_timeouts(current_time=2.5)
    assert "T_04" in timed_out
    assert proto.records["T_04"].state == TaskOwnershipState.TIMEOUT
    assert proto.records["T_04"].owner_robot_id is None
    assert proto.records["T_04"].current_epoch == 2  # Epoch bumped!


def test_robot_failure_and_task_reclaim():
    """Verify that robot failure reclaims committed task with an epoch bump."""
    proto = TaskOwnershipProtocol()
    rec = proto.get_or_create_record("T_05")
    rec.state = TaskOwnershipState.COMMITTED
    rec.owner_robot_id = "R02"
    rec.current_epoch = 1

    reclaim_msg = proto.reclaim_task_on_failure("T_05", "R02", current_time=5.0)
    assert reclaim_msg.msg_type == OwnershipMessageType.TASK_RECLAIM
    assert reclaim_msg.epoch == 2
    assert proto.records["T_05"].state == TaskOwnershipState.RECLAIMED
    assert proto.records["T_05"].owner_robot_id is None
    assert proto.task_reclaims == 1


def test_duplicate_completion_prevention():
    """Verify that a task cannot be completed multiple times or by unauthorized robots."""
    proto = TaskOwnershipProtocol()
    rec = proto.get_or_create_record("T_06")
    rec.state = TaskOwnershipState.COMMITTED
    rec.owner_robot_id = "R01"

    # Authorized completion
    ok1 = proto.mark_completed("T_06", "R01")
    assert ok1 is True
    assert rec.state == TaskOwnershipState.COMPLETED

    # Duplicate completion rejected
    ok2 = proto.mark_completed("T_06", "R01")
    assert ok2 is False

    # Unauthorized completion rejected
    ok3 = proto.mark_completed("T_06", "R02")
    assert ok3 is False


# ==============================================================================
# 2. SPACE-TIME RESERVATION TIMELINE & DYNAMIC INVALIDATION TESTS
# ==============================================================================

def test_reservation_timeline_generation():
    """Verify structured timeline generation for Digital Twin."""
    st = SpaceTimeReservationTable()
    st.reserve_vertex((5, 10), timestep=10, robot_id="R01")
    st.reserve_vertex((6, 10), timestep=11, robot_id="R01")
    st.reserve_vertex((5, 12), timestep=8, robot_id="R02")  # past/expired relative to t=10

    timeline = st.get_timeline(current_timestep=10, horizon=5)
    assert len(timeline) >= 2

    # Check statuses
    statuses = {item["cell"][0]: item["status"] for item in timeline if "cell" in item}
    assert statuses.get(5) in ("active", "expired")
    assert statuses.get(6) == "future"


def test_reservation_prune_expired():
    """Verify that expired reservations are safely cleaned up."""
    st = SpaceTimeReservationTable()
    st.reserve_vertex((2, 2), timestep=5, robot_id="R01")
    st.reserve_vertex((3, 2), timestep=6, robot_id="R01")
    st.reserve_vertex((4, 2), timestep=15, robot_id="R01")

    pruned = st.prune_expired(current_timestep=10)
    assert pruned == 2
    assert (4, 2, 15) in st.vertex_reservations
    assert (2, 2, 5) not in st.vertex_reservations


def test_reservation_invalidate_cell_on_blockage():
    """Verify that dynamic corridor blockage invalidates affected reservations."""
    st = SpaceTimeReservationTable()
    st.reserve_vertex((7, 10), timestep=12, robot_id="R01")
    st.reserve_vertex((7, 10), timestep=14, robot_id="R02")
    st.reserve_vertex((8, 10), timestep=12, robot_id="R03")

    # Invalidate (7, 10) starting from t=10
    affected = st.invalidate_cell((7, 10), from_timestep=10)
    assert "R01" in affected
    assert "R02" in affected
    assert "R03" not in affected
    assert (7, 10, 12) not in st.vertex_reservations
    assert (8, 10, 12) in st.vertex_reservations


# ==============================================================================
# 3. EVENT-DRIVEN REPLANNING TESTS
# ==============================================================================

def test_event_driven_replanner_trigger_attribution():
    """Verify that replans are attributed to explicit trigger causes."""
    replanner = EventDrivenReplanner(cooldown_steps=2)

    def is_walkable(pos: Tuple[int, int]) -> bool:
        return True

    res = replanner.trigger_replan(
        robot_id="R01",
        trigger=ReplanningTrigger.DYNAMIC_BLOCKAGE,
        current_pos=(2, 2),
        goal_pos=(5, 2),
        is_walkable_fn=is_walkable,
        current_step=10,
    )
    assert res.is_success
    assert replanner.planner_invocations == 1
    assert replanner.replans_by_trigger["DYNAMIC_BLOCKAGE"] == 1


def test_event_driven_replanner_cooldown_suppression():
    """Verify that non-urgent duplicate replans within cooldown window are suppressed."""
    replanner = EventDrivenReplanner(cooldown_steps=3)

    def is_walkable(pos: Tuple[int, int]) -> bool:
        return True

    # 1. First replan at step 10
    res1 = replanner.trigger_replan(
        robot_id="R01",
        trigger=ReplanningTrigger.PATH_DEVIATION,
        current_pos=(2, 2),
        goal_pos=(5, 2),
        is_walkable_fn=is_walkable,
        current_step=10,
    )
    assert res1.is_success

    # 2. Second non-urgent replan at step 11 (within cooldown of 3)
    res2 = replanner.trigger_replan(
        robot_id="R01",
        trigger=ReplanningTrigger.PATH_DEVIATION,
        current_pos=(2, 2),
        goal_pos=(5, 2),
        is_walkable_fn=is_walkable,
        current_step=11,
    )
    assert not res2.is_success
    assert replanner.unnecessary_replans_avoided == 1

    # 3. Critical trigger (ROBOT_FAILURE) bypasses cooldown
    res3 = replanner.trigger_replan(
        robot_id="R01",
        trigger=ReplanningTrigger.ROBOT_FAILURE,
        current_pos=(2, 2),
        goal_pos=(5, 2),
        is_walkable_fn=is_walkable,
        current_step=11,
    )
    assert res3.is_success


# ==============================================================================
# 4. CANONICAL METRICS & TEST MANIFEST TESTS
# ==============================================================================

def test_canonical_metrics_schema_and_reproducibility():
    """Validate results/CANONICAL_SIH_METRICS.json against required fields and consistency."""
    path = os.path.join(os.path.dirname(__file__), "..", "results", "CANONICAL_SIH_METRICS.json")
    assert os.path.exists(path), "CANONICAL_SIH_METRICS.json must exist!"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Experiment design assertions
    assert data["experiment_design"]["robot_count"] == 6
    assert data["experiment_design"]["scenarios_count"] == 10
    assert data["experiment_design"]["seeds_count"] == 10
    assert data["experiment_design"]["paired_experiments"] == 100
    assert data["experiment_design"]["total_simulation_executions"] == 200

    # Headline numbers consistency
    hm = data["headline_metrics"]
    expected_red = round(((hm["baseline_mean_sec"] - hm["proposed_mean_sec"]) / hm["baseline_mean_sec"]) * 100.0, 2)
    assert abs(hm["aggregate_reduction_pct"] - expected_red) < 0.05

    # Zero collisions verified
    assert data["safety_audit"]["inter_robot_collisions_observed"] == 0
    assert data["safety_audit"]["deadlocks_observed"] == 0

    # Latency numbers
    assert data["latency_taxonomy"]["mean_planner_latency_ms"] == 0.27
    assert data["latency_taxonomy"]["p95_planner_latency_ms"] == 1.25


def test_test_manifest_consistency():
    """Validate results/test_manifest.json reflects passing tests without stale claims."""
    path = os.path.join(os.path.dirname(__file__), "..", "results", "test_manifest.json")
    assert os.path.exists(path), "results/test_manifest.json must exist!"

    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["total_passed"] >= 102
    assert manifest["total_failed"] == 0
    assert manifest["pass_rate_percent"] == 100.0


# ==============================================================================
# 5. WEB API & SELF-CHECK CANONICAL INTEGRATION TESTS
# ==============================================================================

def test_web_api_endpoints_canonical():
    """Verify that web server endpoints dynamically expose canonical data and real state."""
    from fastapi.testclient import TestClient
    from web.server import app

    client = TestClient(app)

    # 1. /api/self_check
    res_sc = client.get("/api/self_check")
    assert res_sc.status_code == 200
    sc_data = res_sc.json()
    assert sc_data["status"] == "DEMO READY"
    assert sc_data["checks_passed"] == 10

    # 2. /api/benchmarks/verified
    res_bm = client.get("/api/benchmarks/verified")
    assert res_bm.status_code == 200
    bm_data = res_bm.json()
    assert bm_data["reduction_pct"] == 26.18
    assert bm_data["baseline_mean_sec"] == 8.70
    assert bm_data["proposed_mean_sec"] == 6.42
    assert bm_data["inter_robot_collisions"] == 0
    assert len(bm_data["scenarios"]) == 10

    # 3. /api/validation/tests
    res_tests = client.get("/api/validation/tests")
    assert res_tests.status_code == 200
    test_data = res_tests.json()
    assert test_data["status"] == "PASS"
    assert test_data["total_passed"] >= 102

    # 4. /api/reservations
    res_res = client.get("/api/reservations")
    assert res_res.status_code == 200
    res_info = res_res.json()
    assert "reservations" in res_info
    assert "current_step" in res_info

