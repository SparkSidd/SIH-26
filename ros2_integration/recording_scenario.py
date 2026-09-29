"""
ros2_integration/recording_scenario.py
─────────────────────────────────────────────────────────────────────────────
DETERMINISTIC RECORDING SCENARIO — SIH26123

Official scenario for the SIH video recording.
Fixed seed, fixed robot positions, fixed task set, fixed blockage timing.
Produces the SAME outcome every run.

Scenario timeline (sim time):
  0–15s:    Wide warehouse view, 6 AMRs idle then receive tasks
  15–35s:   Normal operation — robots navigate, PIBT resolving contention
  35–55s:   Multi-robot contention zone — PIBT yielding visible
  55–65s:   Blockage injected at (12, 10)-(12, 11) [INJECTED_BLOCKAGE]
  65–85s:   Space-Time A* replanning — robot(s) take alternate route
  85–100s:  Blockage cleared, robot reaches delivery
  100–115s: Remaining tasks complete
  115–135s: All 6 tasks delivered — metrics displayed

SIL validation command:
  python -m ros2_integration.recording_scenario --validate

Gazebo launch:
  SIH26_PROFILE=recording bash run_live_fleet.sh RECORDING_DEMO proposed true recording
"""

from __future__ import annotations
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FIXED seed and parameters — do NOT change without regenerating the video
# ─────────────────────────────────────────────────────────────────────────────

RECORDING_SEED         = 42
RECORDING_TIMEOUT      = 400   # steps — generous limit for video scenario
RECORDING_BLOCKAGE_STEP = 55   # step at which blockage is injected (≈5.5s sim)

RECORDING_ROBOT_STARTS = [
    (2,  2),   # R01 — SW corner
    (2, 10),   # R02 — West mid
    (2, 17),   # R03 — NW corner
    (10, 10),  # R04 — Centre
    (5,  5),   # R05 — W-SW
    (5, 14),   # R06 — W-NW
]

RECORDING_TASKS = [
    # (task_id, pickup_cell, dropoff_cell)
    ("T01", (5,  2),  (20, 17)),  # R01/R02 path — long cross-warehouse
    ("T02", (5, 10),  (20,  5)),  # R02 path — mid crossing
    ("T03", (5, 17),  (20, 10)),  # R03 path — NW to mid-east
    ("T04", (10,  5), (15, 15)),  # R04 path — centre diagonal
    ("T05", (15,  2), ( 5, 17)),  # R05 path — reverse diagonal (contention)
    ("T06", (15, 17), ( 5,  2)),  # R06 path — reverse diagonal (contention)
]

# Blockage location: mid-warehouse choke point triggers SCENARIO_C-style replanning
RECORDING_BLOCKAGE_CELLS = [(12, 10), (12, 11)]

# Camera preset sequence for the video (manual operator reference)
CAMERA_SEQUENCE = [
    (  0, "OVERVIEW",     "Wide warehouse — 6 AMRs, task assignment visible"),
    ( 15, "FLEET_VIEW",   "Normal operation, PIBT coordination"),
    ( 35, "BOTTLENECK_VIEW", "Multi-robot contention at corridor"),
    ( 55, "RECOVERY_VIEW",  "Blockage injected — SPACE-TIME A* REPLANNING"),
    ( 85, "FLEET_VIEW",   "Robot completed alternate route, delivery"),
    (115, "TOP_DOWN_DEBUG", "All tasks completed, final metrics"),
]


def get_recording_scenario_config() -> dict:
    """Return scenario configuration compatible with SCENARIOS dict format."""
    return {
        "name": "OFFICIAL_RECORDING — Deterministic SIH Video Scenario",
        "grid_fn": None,               # caller must supply open grid
        "num_robots": 6,
        "robot_starts": RECORDING_ROBOT_STARTS,
        "tasks": RECORDING_TASKS,
        "blockage_step": RECORDING_BLOCKAGE_STEP,
        "blockage_cells": RECORDING_BLOCKAGE_CELLS,
        "timeout_steps": RECORDING_TIMEOUT,
        "seed": RECORDING_SEED,
    }


def validate_recording_scenario() -> dict:
    """
    Run the recording scenario in SIL mode and verify correctness.
    Returns the result dict from ScenarioRunner.
    Fails if: collisions > 0, deadlocks > 0, completed_tasks < 6.
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import numpy as np
    from ros2_integration.fleet_launcher import ScenarioRunner, SCENARIOS, MAP_WIDTH, MAP_HEIGHT, _make_open_grid
    from ros2_integration.perf_config import apply_logging_profile, get_profile

    apply_logging_profile(get_profile("recording"))

    # Inject recording config into SCENARIOS temporarily
    cfg = get_recording_scenario_config()
    cfg["grid_fn"] = _make_open_grid
    SCENARIOS["RECORDING_DEMO"] = cfg

    runner = ScenarioRunner("RECORDING_DEMO", verbose=False)
    runner.setup()
    result = runner.run()

    # Cleanup
    del SCENARIOS["RECORDING_DEMO"]

    # Assertions
    assert result["total_collisions"] == 0, (
        f"FAIL: {result['total_collisions']} collisions in recording scenario"
    )
    assert result["completed_tasks"] >= 6, (
        f"FAIL: Only {result['completed_tasks']}/6 tasks completed"
    )
    assert result["total_deadlocks"] == 0, (
        f"FAIL: {result['total_deadlocks']} unresolved deadlocks"
    )

    return result


def print_camera_cues():
    """Print the camera switching cues for the video operator."""
    print("\n" + "="*60)
    print("  CAMERA CUE SHEET — SIH26123 Recording Scenario")
    print("="*60)
    for t, preset, desc in CAMERA_SEQUENCE:
        print(f"  t={t:>4}s  [{preset:<20}]  {desc}")
    print("="*60 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SIH Recording Scenario Tool")
    parser.add_argument("--validate", action="store_true",
                        help="Run SIL validation of the recording scenario")
    parser.add_argument("--camera-cues", action="store_true",
                        help="Print camera switching cues")
    args = parser.parse_args()

    if args.camera_cues or not args.validate:
        print_camera_cues()

    if args.validate:
        print("Running SIL validation of recording scenario...")
        t0 = time.perf_counter()
        result = validate_recording_scenario()
        t1 = time.perf_counter()
        print(f"\n{'='*60}")
        print(f"  RECORDING SCENARIO VALIDATION RESULT")
        print(f"{'='*60}")
        print(f"  PASSED:     {result['passed']}")
        print(f"  Tasks:      {result['completed_tasks']}/{result['total_tasks']}")
        print(f"  Collisions: {result['total_collisions']}")
        print(f"  Deadlocks:  {result['total_deadlocks']}")
        print(f"  Steps:      {result['steps']}")
        print(f"  Wall time:  {t1-t0:.3f}s")
        print(f"{'='*60}\n")
        sys.exit(0 if result["passed"] else 1)
