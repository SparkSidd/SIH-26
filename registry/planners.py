"""Planners Registry."""

from typing import Any, Callable, Dict
from planning.astar import SpaceTimeAStarPlanner
from planning.pibt import PIBTPlanner
from planning.multi_agent import MultiAgentPlanner

PLANNERS: Dict[str, Any] = {
    "astar": SpaceTimeAStarPlanner,
    "pibt": PIBTPlanner,
    "multi_agent": MultiAgentPlanner,
}


def get_planner(name: str, **kwargs) -> Any:
    """Retrieve planner by registry name."""
    if name not in PLANNERS:
        raise ValueError(f"Unknown planner '{name}'. Available: {list(PLANNERS.keys())}")
    return PLANNERS[name](**kwargs)
