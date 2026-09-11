"""
coordinate_bridge.py — Bidirectional coordinate conversion between grid and ROS 2 world frame.

The frozen coordination stack operates on a discrete (col, row) integer grid.
ROS 2 / Gazebo uses a continuous (x, y, z) world-frame in metres with yaw heading.

Conversion rules:
  - 1 grid cell  = CELL_SIZE_M metres (default 1.0 m)
  - Grid origin  = ROS world (0.0, 0.0)
  - Grid col     = ROS +X axis
  - Grid row     = ROS +Y axis  (note: rows increase downward in grid; +Y is up in ROS)
  - Row flip     = enabled if FLIP_Y is True (default True for standard ROS convention)
  - Heading      = direction from current → next cell, expressed as yaw in radians

Grid heading convention (used by MotionModel and planner):
  - East  (+col): 0 rad
  - North (-row): +π/2 rad  (with FLIP_Y=True)
  - West  (-col): ±π rad
  - South (+row): -π/2 rad  (with FLIP_Y=True)
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
CELL_SIZE_M: float = 1.0      # metres per grid cell
FLIP_Y: bool = True            # flip row → Y axis (grid row 0 = ROS max Y)
GRID_ROWS: int = 20            # default warehouse height (matches benchmark)
ROBOT_Z: float = 0.0           # robot ground-plane Z in world frame


def grid_to_world(col: int, row: int, grid_rows: int = GRID_ROWS) -> Tuple[float, float, float]:
    """
    Convert grid cell (col, row) → ROS 2 world frame (x, y, z) in metres.

    Args:
        col: grid column (0-indexed, increases East)
        row: grid row    (0-indexed, increases South in grid)
        grid_rows: total grid height (for Y-flip calculation)

    Returns:
        (x, y, z) in ROS 2 world frame
    """
    x = col * CELL_SIZE_M
    if FLIP_Y:
        y = (grid_rows - 1 - row) * CELL_SIZE_M
    else:
        y = row * CELL_SIZE_M
    return x, y, ROBOT_Z


def world_to_grid(
    x: float,
    y: float,
    grid_rows: int = GRID_ROWS,
) -> Tuple[int, int]:
    """
    Convert ROS 2 world frame (x, y) → nearest grid cell (col, row).

    Args:
        x: world X in metres
        y: world Y in metres
        grid_rows: total grid height (for Y-flip)

    Returns:
        (col, row) as integers
    """
    col = int(round(x / CELL_SIZE_M))
    if FLIP_Y:
        row = int(round((grid_rows - 1) - y / CELL_SIZE_M))
    else:
        row = int(round(y / CELL_SIZE_M))
    return col, row


def heading_to_yaw(
    current_pos: Tuple[int, int],
    next_pos: Tuple[int, int],
) -> float:
    """
    Compute ROS 2 yaw (radians) for motion from current_pos → next_pos on grid.

    Grid convention: col increases East (+X), row increases South (+Y in grid = -Y in ROS with FLIP_Y).

    Returns:
        Yaw in radians, range (-π, π].
    """
    dc = next_pos[0] - current_pos[0]  # Δcol (+East)
    dr = next_pos[1] - current_pos[1]  # Δrow (+South in grid)

    dx = dc * CELL_SIZE_M
    dy = (-dr if FLIP_Y else dr) * CELL_SIZE_M  # flip row to ROS Y convention
    return math.atan2(dy, dx)


def yaw_to_grid_heading(yaw: float) -> Tuple[int, int]:
    """
    Snap a continuous yaw (radians) to the nearest 4-direction grid heading.

    Returns:
        (dcol, drow) representing the cardinal direction
    """
    # Normalize to [0, 2π)
    yaw = yaw % (2 * math.pi)
    # Map to 4 quadrants
    if yaw < math.pi / 4 or yaw >= 7 * math.pi / 4:
        return (1, 0)   # East
    elif yaw < 3 * math.pi / 4:
        return (0, -1)  # North (ROS +Y → grid -row when FLIP_Y)
    elif yaw < 5 * math.pi / 4:
        return (-1, 0)  # West
    else:
        return (0, 1)   # South


def cmd_vel_to_grid_direction(
    linear_x: float,
    angular_z: float,
    current_yaw: float,
) -> Optional[Tuple[int, int]]:
    """
    Estimate grid direction delta from a cmd_vel Twist message.

    Used for odom-based grid cell tracking during SIL replay.

    Returns:
        (dcol, drow) if robot is moving; None if stationary.
    """
    MOTION_THRESHOLD = 0.05  # m/s minimum to be considered "moving"
    if abs(linear_x) < MOTION_THRESHOLD:
        return None
    projected_yaw = current_yaw + angular_z * 0.1  # approximate 100ms step
    return yaw_to_grid_heading(projected_yaw)


def path_to_waypoints_world(
    path: list,
    grid_rows: int = GRID_ROWS,
) -> list:
    """
    Convert a list of grid cells [(col, row), ...] → world-frame waypoints [(x, y, z), ...].

    Args:
        path: list of (col, row) tuples from PIBT / STA* planner
        grid_rows: total grid height

    Returns:
        list of (x, y, z) world-frame coordinates
    """
    return [grid_to_world(c, r, grid_rows) for c, r in path]
