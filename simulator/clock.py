"""Deterministic Simulation Clock."""

import time
from typing import Optional


class SimulationClock:
    """Manages deterministic simulation time and stepping."""

    def __init__(self, timestep: float = 0.1, realtime_factor: float = 1.0):
        self.timestep: float = timestep
        self.realtime_factor: float = realtime_factor
        self.current_step: int = 0
        self.sim_time: float = 0.0
        self.is_paused: bool = False
        self._last_wall_time: Optional[float] = None

    def tick(self) -> float:
        """Advance clock by one deterministic timestep."""
        if not self.is_paused:
            self.current_step += 1
            self.sim_time = round(self.current_step * self.timestep, 6)
            
            if self.realtime_factor > 0:
                target_delay = self.timestep / self.realtime_factor
                if self._last_wall_time is not None:
                    elapsed = time.time() - self._last_wall_time
                    if elapsed < target_delay:
                        time.sleep(target_delay - elapsed)
                self._last_wall_time = time.time()

        return self.sim_time

    def pause(self) -> None:
        """Pause simulation clock."""
        self.is_paused = True

    def resume(self) -> None:
        """Resume simulation clock."""
        self.is_paused = False
        self._last_wall_time = time.time()

    def reset(self) -> None:
        """Reset clock back to initial state."""
        self.current_step = 0
        self.sim_time = 0.0
        self.is_paused = False
        self._last_wall_time = None

    @property
    def current_time(self) -> float:
        """Alias for sim_time."""
        return self.sim_time
