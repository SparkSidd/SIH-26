"""
sensor_msgs.py — Mock sensor_msgs.msg for SIL testing.
Matches LaserScan, Imu.
"""

from dataclasses import dataclass, field
from typing import List
from ros2_integration.mock_ros.geometry_msgs import Vector3, Quaternion
from ros2_integration.mock_ros.std_msgs import Header


@dataclass
class LaserScan:
    """sensor_msgs/msg/LaserScan — 2D LiDAR scan."""
    header: Header = field(default_factory=Header)
    angle_min: float = -1.5708      # -90 deg
    angle_max: float = 1.5708       # +90 deg
    angle_increment: float = 0.0087  # ~0.5 deg
    time_increment: float = 0.0
    scan_time: float = 0.1
    range_min: float = 0.1
    range_max: float = 10.0
    ranges: List[float] = field(default_factory=list)
    intensities: List[float] = field(default_factory=list)


@dataclass
class Imu:
    """sensor_msgs/msg/Imu — IMU data."""
    header: Header = field(default_factory=Header)
    orientation: Quaternion = field(default_factory=Quaternion)
    orientation_covariance: List[float] = field(default_factory=lambda: [0.0] * 9)
    angular_velocity: Vector3 = field(default_factory=Vector3)
    angular_velocity_covariance: List[float] = field(default_factory=lambda: [0.0] * 9)
    linear_acceleration: Vector3 = field(default_factory=Vector3)
    linear_acceleration_covariance: List[float] = field(default_factory=lambda: [0.0] * 9)
