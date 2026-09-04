"""Information age tracking and confidence decay models."""

from dataclasses import dataclass
from enum import Enum, auto


class InformationAgeCategory(Enum):
    FRESH = auto()      # < 0.3 sec
    RECENT = auto()     # 0.3 - 1.0 sec
    STALE = auto()      # 1.0 - 3.0 sec
    UNKNOWN = auto()    # > 3.0 sec / no data


@dataclass
class InformationAge:
    """Computes freshness and confidence of received remote robot states."""
    fresh_threshold: float = 0.3
    recent_threshold: float = 1.0
    stale_threshold: float = 3.0

    def categorize(self, age_seconds: float) -> InformationAgeCategory:
        """Classify age of information."""
        if age_seconds < self.fresh_threshold:
            return InformationAgeCategory.FRESH
        elif age_seconds < self.recent_threshold:
            return InformationAgeCategory.RECENT
        elif age_seconds < self.stale_threshold:
            return InformationAgeCategory.STALE
        return InformationAgeCategory.UNKNOWN

    def compute_confidence(self, age_seconds: float, initial_confidence: float = 1.0) -> float:
        """Exponential decay function for state confidence."""
        if age_seconds < 0:
            return initial_confidence
        # Half-life of 1.0 second
        decay = 2.0 ** (-age_seconds / 1.0)
        return max(0.0, min(1.0, initial_confidence * decay))
