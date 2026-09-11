"""
nav_msgs.py — Mock nav_msgs.msg for SIL testing.
Matches nav_msgs/msg/Odometry.
"""

from dataclasses import dataclass, field
from ros2_integration.mock_ros.geometry_msgs import Pose, PoseWithCovariance, Twist, TwistWithCovariance
from ros2_integration.mock_ros.std_msgs import Header


@dataclass
class Odometry:
    """nav_msgs/msg/Odometry — robot pose and velocity in world frame."""
    header: Header = field(default_factory=Header)
    child_frame_id: str = ""
    pose: PoseWithCovariance = field(default_factory=PoseWithCovariance)
    twist: TwistWithCovariance = field(default_factory=TwistWithCovariance)
