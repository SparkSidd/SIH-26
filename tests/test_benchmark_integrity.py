"""Automated integrity validation for canonical benchmark artifacts (Section 20).

Validates that:
- exactly 10 scenarios
- exactly 10 seeds
- 100 paired experiments
- 200 total executions
- every pair has baseline + proposed
- every scenario has 10 seeds
- aggregate means match raw run data
- aggregate reduction matches formula
- collision counts match raw runs
- deadlock counts match raw runs
"""

import json
import math
import os
import statistics
import pytest


RAW_RUNS_PATH = "results/canonical/raw_runs.jsonl"
CANONICAL_JSON_PATH = "results/CANONICAL_SIH_METRICS.json"
MANIFEST_PATH = "results/canonical/benchmark_manifest.json"


@pytest.fixture(scope="module")
def benchmark_data():
    assert os.path.exists(RAW_RUNS_PATH), f"Missing {RAW_RUNS_PATH}"
    assert os.path.exists(CANONICAL_JSON_PATH), f"Missing {CANONICAL_JSON_PATH}"

    raw_runs = []
    with open(RAW_RUNS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw_runs.append(json.loads(line))

    with open(CANONICAL_JSON_PATH, "r", encoding="utf-8") as f:
        canonical = json.load(f)

    return {"raw_runs": raw_runs, "canonical": canonical}


def test_execution_and_pairing_counts(benchmark_data):
    raw_runs = benchmark_data["raw_runs"]
    canonical = benchmark_data["canonical"]

    # 200 total executions
    assert len(raw_runs) == 200, f"Expected 200 raw runs, found {len(raw_runs)}"
    assert canonical["experiment_design"]["total_simulation_executions"] == 200

    # 100 baseline and 100 proposed
    baseline_runs = [r for r in raw_runs if r["algorithm"] == "BASELINE"]
    proposed_runs = [r for r in raw_runs if r["algorithm"] == "PROPOSED"]
    assert len(baseline_runs) == 100, f"Expected 100 baseline runs, found {len(baseline_runs)}"
    assert len(proposed_runs) == 100, f"Expected 100 proposed runs, found {len(proposed_runs)}"
    assert canonical["experiment_design"]["paired_experiments"] == 100


def test_scenario_and_seed_completeness(benchmark_data):
    raw_runs = benchmark_data["raw_runs"]
    canonical = benchmark_data["canonical"]

    expected_scenarios = {
        "S0_NORMAL",
        "S1_HIGH_CONGESTION",
        "S2_COMM_LATENCY",
        "S3_PACKET_LOSS",
        "S4_AISLE_BLOCKAGE",
        "S5_ROBOT_FAILURE",
        "S6_TASK_SURGE",
        "S7_COMM_AND_BLOCKAGE",
        "S8_FAILURE_AND_CONGESTION",
        "S9_FULL_COMBINED_DISTURBANCE",
    }
    expected_seeds = {42, 101, 202, 303, 404, 505, 606, 707, 808, 909}

    scenarios_found = {r["scenario"] for r in raw_runs}
    seeds_found = {r["seed"] for r in raw_runs}

    assert scenarios_found == expected_scenarios
    assert seeds_found == expected_seeds

    assert len(canonical["scenarios"]) == 10
    assert set(canonical["experiment_design"]["seeds"]) == expected_seeds

    # Check that every pair (scenario, seed) has exactly 1 BASELINE and 1 PROPOSED
    for sc in expected_scenarios:
        for sd in expected_seeds:
            b_matches = [r for r in raw_runs if r["scenario"] == sc and r["seed"] == sd and r["algorithm"] == "BASELINE"]
            p_matches = [r for r in raw_runs if r["scenario"] == sc and r["seed"] == sd and r["algorithm"] == "PROPOSED"]
            assert len(b_matches) == 1, f"Missing or duplicate baseline for {sc}, seed {sd}"
            assert len(p_matches) == 1, f"Missing or duplicate proposed for {sc}, seed {sd}"


def test_aggregate_metrics_mathematical_consistency(benchmark_data):
    raw_runs = benchmark_data["raw_runs"]
    canonical = benchmark_data["canonical"]

    baseline_runs = [r for r in raw_runs if r["algorithm"] == "BASELINE"]
    proposed_runs = [r for r in raw_runs if r["algorithm"] == "PROPOSED"]

    calc_b_mean = round(float(statistics.mean(r["completion_time_sec"] for r in baseline_runs)), 2)
    calc_p_mean = round(float(statistics.mean(r["completion_time_sec"] for r in proposed_runs)), 2)
    calc_reduction = round(((calc_b_mean - calc_p_mean) / calc_b_mean) * 100.0, 2)

    hm = canonical["headline_metrics"]
    assert math.isclose(hm["baseline_mean_sec"], calc_b_mean, rel_tol=1e-2), f"Baseline mismatch: {hm['baseline_mean_sec']} vs {calc_b_mean}"
    assert math.isclose(hm["proposed_mean_sec"], calc_p_mean, rel_tol=1e-2), f"Proposed mismatch: {hm['proposed_mean_sec']} vs {calc_p_mean}"
    assert math.isclose(hm["aggregate_reduction_pct"], calc_reduction, rel_tol=1e-2), f"Reduction mismatch: {hm['aggregate_reduction_pct']} vs {calc_reduction}"


def test_safety_and_deadlock_counts_match_raw_runs(benchmark_data):
    raw_runs = benchmark_data["raw_runs"]
    canonical = benchmark_data["canonical"]

    proposed_runs = [r for r in raw_runs if r["algorithm"] == "PROPOSED"]
    proposed_collisions = sum(r.get("collisions", 0) for r in proposed_runs)
    proposed_deadlocks = sum(r.get("deadlocks", 0) for r in proposed_runs)

    baseline_runs = [r for r in raw_runs if r["algorithm"] == "BASELINE"]
    baseline_collisions = sum(r.get("collisions", 0) for r in baseline_runs)

    assert canonical["safety_audit"]["inter_robot_collisions_observed"] == proposed_collisions
    assert canonical["safety_audit"]["deadlocks_observed"] == proposed_deadlocks
    assert canonical["safety_audit"]["baseline_collisions_observed"] == baseline_collisions
    assert proposed_collisions == 0, "Non-zero collision count observed in proposed system"
    assert proposed_deadlocks == 0, "Non-zero deadlock count observed in proposed system"


def test_manifest_metadata_traceability():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        assert manifest["paired_experiments"] == 100
        assert manifest["total_executions"] == 200
        assert manifest["scenario_count"] == 10
        assert manifest["seed_count"] == 10
        assert os.path.exists(manifest["raw_runs"])
