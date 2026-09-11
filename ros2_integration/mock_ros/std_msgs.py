"""
std_msgs.py — Mock std_msgs.msg for SIL testing.
"""

from dataclasses import dataclass, field


@dataclass
class Header:
    """std_msgs/msg/Header."""
    stamp_sec: int = 0
    stamp_nanosec: int = 0
    frame_id: str = ""


@dataclass
class String:
    """std_msgs/msg/String."""
    data: str = ""


@dataclass
class Float64:
    """std_msgs/msg/Float64."""
    data: float = 0.0


@dataclass
class Bool:
    """std_msgs/msg/Bool."""
    data: bool = False
