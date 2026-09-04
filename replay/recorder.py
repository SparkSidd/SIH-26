"""Exact simulation trajectory and event recorder for deterministic playback."""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional
from events.event import Event


@dataclass
class ReplayFrame:
    """Represents a single simulation state snapshot."""
    step: int
    sim_time: float
    robots: Dict[str, Any]
    tasks: Dict[str, Any]
    blocked_cells: List[List[int]]
    events: List[Dict[str, Any]]
    metrics: Dict[str, Any]


class SimulationRecorder:
    """Serializes experiment traces to JSON for 100% deterministic playback."""

    def __init__(self, metadata: Optional[Dict[str, Any]] = None):
        self.metadata = metadata or {}
        self.frames: List[ReplayFrame] = []

    def record_step(
        self,
        step: int,
        sim_time: float,
        robots: Dict[str, Any],
        tasks: Dict[str, Any],
        blocked_cells: List[List[int]],
        events_this_step: List[Event],
        metrics_dict: Dict[str, Any],
    ) -> None:
        """Capture one time step frame."""
        frame = ReplayFrame(
            step=step,
            sim_time=sim_time,
            robots=robots,
            tasks=tasks,
            blocked_cells=blocked_cells,
            events=[e.to_dict() for e in events_this_step],
            metrics=metrics_dict,
        )
        self.frames.append(frame)

    def save_to_file(self, filepath: str) -> None:
        """Export replay log to JSON file."""
        data = {
            "metadata": self.metadata,
            "total_frames": len(self.frames),
            "frames": [
                {
                    "step": f.step,
                    "sim_time": f.sim_time,
                    "robots": f.robots,
                    "tasks": f.tasks,
                    "blocked_cells": f.blocked_cells,
                    "events": f.events,
                    "metrics": f.metrics,
                }
                for f in self.frames
            ],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
