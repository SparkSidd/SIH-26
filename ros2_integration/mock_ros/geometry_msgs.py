"""
geometry_msgs.py — Mock geometry_msgs.msg for SIL testing.
Matches geometry_msgs/msg/Twist, Vector3, TwistStamped, Pose, Point, Quaternion.
"""

from dataclasses import dataclass, field


@dataclass
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Twist:
    """geometry_msgs/msg/Twist — linear and angular velocity command."""
    linear: Vector3 = field(default_factory=Vector3)
    angular: Vector3 = field(default_factory=Vector3)

    def __post_init__(self):
        if not isinstance(self.linear, Vector3):
            self.linear = Vector3(**self.linear) if isinstance(self.linear, dict) else Vector3()
        if not isinstance(self.angular, Vector3):
            self.angular = Vector3(**self.angular) if isinstance(self.angular, dict) else Vector3()


@dataclass
class Point:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Quaternion:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0


@dataclass
class Pose:
    position: Point = field(default_factory=Point)
    orientation: Quaternion = field(default_factory=Quaternion)


@dataclass
class PoseWithCovariance:
    pose: Pose = field(default_factory=Pose)
    covariance: list = field(default_factory=lambda: [0.0] * 36)


@dataclass
class TwistWithCovariance:
    twist: Twist = field(default_factory=Twist)
    covariance: list = field(default_factory=lambda: [0.0] * 36)
