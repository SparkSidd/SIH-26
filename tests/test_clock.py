"""Unit tests for SimulationClock and determinism."""

import pytest
from simulator.clock import SimulationClock


def test_clock_tick_advance():
    clock = SimulationClock(timestep=0.1, realtime_factor=0.0)
    assert clock.current_step == 0
    assert clock.sim_time == 0.0

    t1 = clock.tick()
    assert clock.current_step == 1
    assert t1 == 0.1

    t2 = clock.tick()
    assert clock.current_step == 2
    assert t2 == 0.2


def test_clock_pause_resume():
    clock = SimulationClock(timestep=0.1, realtime_factor=0.0)
    clock.tick()
    assert clock.current_step == 1

    clock.pause()
    assert clock.is_paused is True
    clock.tick()
    # Should not advance while paused
    assert clock.current_step == 1

    clock.resume()
    assert clock.is_paused is False
    clock.tick()
    assert clock.current_step == 2


def test_clock_reset():
    clock = SimulationClock(timestep=0.1, realtime_factor=0.0)
    for _ in range(10):
        clock.tick()
    assert clock.current_step == 10

    clock.reset()
    assert clock.current_step == 0
    assert clock.sim_time == 0.0
