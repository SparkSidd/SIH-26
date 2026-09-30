"""
ros2_integration/perf_config.py — Three performance profiles for SIH26123.

Profile   Purpose
─────────────────────────────────────────────────────────────────────
normal    Balanced: full sensors, moderate rendering, modest logging.
debug     Maximum observability: all sensors, all logging, visualize.
recording Optimized for video: minimal draw calls, no shadows, quiet.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import logging
import os


@dataclass(frozen=True)
class PerfProfile:
    name: str
    description: str

    # Gazebo physics
    physics_max_step_size: float = 0.01
    physics_real_time_update_rate: int = 0
    physics_real_time_factor: float = 1.0
    physics_ode_iters: int = 20
    physics_ode_sor: float = 1.3
    physics_max_contacts: int = 10

    # Sensor rates
    lidar_update_rate: int = 5
    lidar_ray_count: int = 72
    lidar_visualize: bool = False
    lidar_range_max: float = 10.0
    lidar_noise_stddev: float = 0.01
    imu_update_rate: int = 50
    odom_publish_frequency: int = 20

    # Rendering
    shadows_enabled: bool = True
    sun_cast_shadows: bool = True
    specular_highlights: bool = True
    render_floor_grid: bool = True
    render_cargo_clutter: bool = True
    camera_update_rate: int = 15

    # Logging
    log_level: int = logging.INFO
    sil_step_verbose_interval: int = 20
    ros2_log_level: str = "warn"

    # SIL (frozen — never change)
    sil_step_dt: float = 0.1


PROFILES: dict = {
    "normal": PerfProfile(
        name="normal",
        description="Balanced simulation — full sensors, smooth 60Hz physics",
        physics_max_step_size=0.0166667,
        physics_real_time_update_rate=60,
        physics_ode_iters=15,
        physics_max_contacts=10,
        lidar_update_rate=5,
        lidar_ray_count=72,
        lidar_visualize=False,
        imu_update_rate=50,
        odom_publish_frequency=50,
        shadows_enabled=False,
        sun_cast_shadows=False,
        specular_highlights=False,
        render_floor_grid=True,
        render_cargo_clutter=False,
        camera_update_rate=10,
        log_level=logging.INFO,
        sil_step_verbose_interval=20,
        ros2_log_level="warn",
    ),
    "debug": PerfProfile(
        name="debug",
        description="Maximum observability — all sensors, all logging, LiDAR rays",
        physics_max_step_size=0.0166667,
        physics_real_time_update_rate=60,
        physics_ode_iters=30,
        physics_max_contacts=30,
        lidar_update_rate=10,
        lidar_ray_count=180,
        lidar_visualize=True,
        lidar_noise_stddev=0.0,
        imu_update_rate=100,
        odom_publish_frequency=50,
        shadows_enabled=True,
        sun_cast_shadows=True,
        specular_highlights=True,
        render_floor_grid=True,
        render_cargo_clutter=True,
        camera_update_rate=30,
        log_level=logging.DEBUG,
        sil_step_verbose_interval=5,
        ros2_log_level="info",
    ),
    "recording": PerfProfile(
        name="recording",
        description="SIH video optimized — minimal rendering/sensor overhead",
        # Physics: 0.016s step (60 Hz physics) — stable for diff-drive at 1.5 m/s
        # (max wheel travel per step = 1.5 * 0.016 = 0.024m, far below 0.1m cell)
        physics_max_step_size=0.0166667,
        physics_real_time_update_rate=60,
        physics_ode_iters=10,
        physics_max_contacts=5,
        # LiDAR: 3 Hz / 36 rays — detects SCENARIO_C blockage within 0.33s of injection
        lidar_update_rate=3,
        lidar_ray_count=36,
        lidar_visualize=False,
        lidar_range_max=8.0,
        lidar_noise_stddev=0.01,
        # IMU/odom: high-fidelity 50Hz odometry for smooth tracking
        imu_update_rate=25,
        odom_publish_frequency=50,
        # Rendering: shadows off = ~30-40% render time savings on complex scene
        shadows_enabled=False,
        sun_cast_shadows=False,
        specular_highlights=False,
        render_floor_grid=False,
        render_cargo_clutter=False,
        camera_update_rate=5,
        # Logging: suppress INFO spam
        log_level=logging.WARNING,
        sil_step_verbose_interval=0,
        ros2_log_level="error",
    ),
}


def get_profile(name: Optional[str] = None) -> PerfProfile:
    """Return the named profile. Falls back to SIH26_PROFILE env var, then 'recording'."""
    if name is None:
        name = os.environ.get("SIH26_PROFILE", "recording").lower()
    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Available: {list(PROFILES)}")
    return PROFILES[name]


def apply_logging_profile(profile: PerfProfile) -> None:
    """Configure Python root logger per the profile."""
    logging.getLogger().setLevel(profile.log_level)
    if profile.name == "recording":
        for name in ("fleet_launcher", "rclpy", "fleet_safety_hud", "coordination"):
            logging.getLogger(name).setLevel(logging.WARNING)
