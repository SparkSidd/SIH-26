"""Edge hardware resource profiler (CPU %, RAM, execution latency)."""

import os
import time
from typing import Tuple
import psutil


class EdgeResourceMonitor:
    """Profiles computational overhead suitable for embedded edge hardware evaluation."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        # Warmup CPU measurement
        self.process.cpu_percent(interval=None)

    def sample(self) -> Tuple[float, float]:
        """Return (cpu_percent, memory_mb)."""
        cpu = self.process.cpu_percent(interval=None)
        mem_info = self.process.memory_info()
        mem_mb = mem_info.rss / (1024.0 * 1024.0)
        return (cpu, mem_mb)
