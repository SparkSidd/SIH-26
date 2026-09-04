"""Tests verifying that pickup stations, dropoff bays, and charging pads cannot be blocked."""

import pytest
from simulator.simulation import AMRSimulation
from web.server import ControlCenterManager
from events.event import EventType


def test_warehouse_protected_cells_rejection():
    """Verify that warehouse rejects blocking protected stations and charging pads."""
    sim = AMRSimulation()
    wh = sim.warehouse
    
    # 1. Pickup stations
    for station in wh.pickup_stations:
        assert station in wh.protected_cells, f"Station {station} should be protected"
        ok = wh.block_cell(station)
        assert not ok, f"block_cell should return False for pickup station {station}"
        assert station not in wh.blocked_cells, f"Station {station} must not be in blocked_cells"
        
    # 2. Dropoff stations
    for station in wh.dropoff_stations:
        assert station in wh.protected_cells, f"Dropoff {station} should be protected"
        ok = wh.block_cell(station)
        assert not ok, f"block_cell should return False for dropoff station {station}"
        assert station not in wh.blocked_cells, f"Dropoff {station} must not be in blocked_cells"
        
    # 3. Charging stations
    for pad in wh.charging_stations:
        assert pad in wh.protected_cells, f"Charging pad {pad} should be protected"
        ok = wh.block_cell(pad)
        assert not ok, f"block_cell should return False for charging pad {pad}"
        assert pad not in wh.blocked_cells, f"Charging pad {pad} must not be in blocked_cells"


def test_control_center_manager_protected_cell_rejection_event():
    """Verify that ControlCenterManager rejects blockage of protected cell and emits PROTECTED_CELL_BLOCK_REJECTED."""
    manager = ControlCenterManager()
    sim = manager.sim
    
    rejected_events = []
    sim.event_bus.subscribe(
        EventType.PROTECTED_CELL_BLOCK_REJECTED,
        lambda ev: rejected_events.append(ev)
    )
    
    # Attempt to block pickup station (2, 2)
    ok = manager.block_cell(2, 2)
    assert not ok, "Manager must reject blocking protected station (2, 2)"
    assert (2, 2) not in sim.warehouse.blocked_cells
    assert len(rejected_events) == 1, "PROTECTED_CELL_BLOCK_REJECTED event must be emitted"
    assert rejected_events[0].data.get("cell") == [2, 2]


def test_normal_cell_blockage_allowed():
    """Verify that non-protected corridor cells can be blocked and unblocked normally."""
    manager = ControlCenterManager()
    sim = manager.sim
    
    corridor_cell = (1, 6)
    assert corridor_cell not in sim.warehouse.protected_cells
    
    # Block
    ok = manager.block_cell(*corridor_cell)
    assert ok, f"Manager should successfully block normal corridor cell {corridor_cell}"
    assert corridor_cell in sim.warehouse.blocked_cells
    
    # Unblock
    ok_unblock = manager.unblock_cell(*corridor_cell)
    assert ok_unblock
    assert corridor_cell not in sim.warehouse.blocked_cells
