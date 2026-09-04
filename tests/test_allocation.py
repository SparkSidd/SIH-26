"""Unit tests for Task Allocators (Baseline vs Fleet-Aware)."""

import pytest
from coordination.allocator import FleetAwareTaskAllocator, BaselineNearestAllocator
from coordination.congestion import CongestionModel
from simulator.robot import Robot
from simulator.task import Task


def test_baseline_nearest_allocation():
    allocator = BaselineNearestAllocator()
    robots = {
        "R1": Robot(id="R1", initial_position=(0, 0)),
        "R2": Robot(id="R2", initial_position=(10, 10)),
    }
    task = Task(id="T1", pickup=(1, 1), dropoff=(2, 2))

    assignments = allocator.allocate([task], robots)
    assert len(assignments) == 1
    # R1 is closer to (1, 1) than R2
    assert assignments[0] == ("R1", "T1")


def test_fleet_aware_congestion_rerouting():
    allocator = FleetAwareTaskAllocator(w_distance=1.0, w_congestion=5.0)
    robots = {
        "R1": Robot(id="R1", initial_position=(0, 0)),
        "R2": Robot(id="R2", initial_position=(2, 2)),
    }
    task = Task(id="T1", pickup=(1, 1), dropoff=(5, 5))

    # Heavy congestion near R2's pickup
    congestion = CongestionModel(width=10, height=10)
    congestion.heatmap[1, 1] = 10.0

    assignments = allocator.allocate([task], robots, congestion_model=congestion)
    assert len(assignments) == 1
