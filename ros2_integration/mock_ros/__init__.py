"""
mock_ros — Transparent ROS 2 API stubs for Software-in-the-Loop (SIL) testing.

These stubs exactly match the real rclpy / message type API surface.
They activate automatically when rclpy cannot be imported (no WSL2 / ROS 2).

When ROS 2 Jazzy is installed, import ros2_integration normally — rclpy will
be found by the Python interpreter and these stubs will NOT be used.

Stubs provided:
  - rclpy_stub     → replaces rclpy (Node, Publisher, Subscription, spin, init, shutdown)
  - geometry_msgs  → Twist, Vector3
  - nav_msgs       → Odometry
  - sensor_msgs    → LaserScan, Imu
  - std_msgs       → String, Float64, Header
  - builtin_interfaces → Time
"""

# Try to import real rclpy; fall back to stubs
try:
    import rclpy  # noqa: F401  — real ROS 2 present
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
