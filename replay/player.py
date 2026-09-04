"""Simulation replay player for post-run analysis."""

import json
from typing import Any, Dict, List, Optional
from replay.recorder import ReplayFrame


class SimulationPlayer:
    """Loads and plays back recorded simulation runs."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.metadata: Dict[str, Any] = {}
        self.frames: List[Dict[str, Any]] = []
        self.current_frame_idx: int = 0
        self._load()

    def _load(self) -> None:
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.metadata = data.get("metadata", {})
            self.frames = data.get("frames", [])

    @property
    def total_frames(self) -> int:
        return len(self.frames)

    def get_current_frame(self) -> Optional[Dict[str, Any]]:
        if 0 <= self.current_frame_idx < len(self.frames):
            return self.frames[self.current_frame_idx]
        return None

    def step_forward(self) -> Optional[Dict[str, Any]]:
        if self.current_frame_idx < len(self.frames) - 1:
            self.current_frame_idx += 1
        return self.get_current_frame()

    def step_backward(self) -> Optional[Dict[str, Any]]:
        if self.current_frame_idx > 0:
            self.current_frame_idx -= 1
        return self.get_current_frame()

    def seek(self, frame_index: int) -> Optional[Dict[str, Any]]:
        self.current_frame_idx = max(0, min(frame_index, len(self.frames) - 1))
        return self.get_current_frame()
