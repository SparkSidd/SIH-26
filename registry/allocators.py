"""Allocators Registry."""

from typing import Any, Dict
from coordination.allocator import FleetAwareTaskAllocator, BaselineNearestAllocator

ALLOCATORS: Dict[str, Any] = {
    "nearest": BaselineNearestAllocator,
    "fleet_aware": FleetAwareTaskAllocator,
}


def get_allocator(name: str, **kwargs) -> Any:
    """Retrieve allocator by registry name."""
    if name not in ALLOCATORS:
        raise ValueError(f"Unknown allocator '{name}'. Available: {list(ALLOCATORS.keys())}")
    return ALLOCATORS[name](**kwargs)
