"""
ros2_integration — ROS 2 Adapter Layer for SIH26123 AMR Fleet Coordination.

This package bridges the frozen coordination stack (CHECKPOINT_FINAL_PRE_GAZEBO)
to ROS 2 + Gazebo Harmonic. It runs in two modes:

  1. Software-in-the-Loop (SIL): When rclpy is not installed, transparent mock
     stubs replace the real ROS 2 API, allowing full integration testing on
     Windows without WSL2. All code is rclpy-API-compatible.

  2. Real ROS 2: When rclpy is installed (WSL2 + ROS 2 Jazzy), the stubs are
     bypassed and real ROS 2 messaging is used with Gazebo Harmonic physics.

DO NOT modify the coordination stack (coordinator.py, planner, allocator).
All changes are confined to this package.
"""

__version__ = "1.0.0"
__checkpoint__ = "CHECKPOINT_FINAL_PRE_GAZEBO"
