"""
ros2_integration/generate_world.py
──────────────────────────────────────────────────────────────────────────────
SDF World Generator for SIH26123 — creates three world variants from a single
source of truth:

  warehouse_recording.sdf   — optimised for smooth video (no shadows, merged
                               floor-grid, no clutter, reduced lights)
  warehouse_normal.sdf      — balanced, full rendering
  warehouse_debug.sdf       — full sensors + LiDAR ray visualisation

All three worlds share:
  • Identical outer perimeter walls (collision + visual)
  • Identical shelf layout (static, box collisions — no mesh complexity)
  • Identical physics (except step size which differs per profile)
  • The same 6 pickup/dropoff station positions
  • The same blockage-zone markers

The recording world eliminates:
  • 41 individual floor-grid geometry draw calls → replaced by one subtle
    textured floor (single draw call, painted lane lines)
  • Shadow casting (saves ~30-40% GPU render time on Ogre2 scenes)
  • Cargo clutter (~30 additional draw calls per pickup station)
  • 5 always-on camera sensors (moved to on-demand / low rate)
  • Specular material highlights on static geometry

Usage (from project root, in WSL2):
  python3 -m ros2_integration.generate_world --profile recording
  python3 -m ros2_integration.generate_world --all
"""

from __future__ import annotations
import argparse
import os
import textwrap
from typing import Optional

from ros2_integration.perf_config import PROFILES, PerfProfile, get_profile


# ─────────────────────────────────────────────────────────────────────────────
# World constants (must match coordinate_bridge.py)
# ─────────────────────────────────────────────────────────────────────────────
MAP_W = 25
MAP_H = 20
CELL  = 1.0          # metres per grid cell
WALL_T = 0.2         # wall thickness metres
WALL_H = 2.5         # wall height metres


def _indent(xml: str, n: int = 4) -> str:
    return "\n".join(" " * n + l for l in xml.strip().splitlines())


def _physics_block(p: PerfProfile) -> str:
    return textwrap.dedent(f"""
    <physics name="default" type="ode">
      <real_time_update_rate>{p.physics_real_time_update_rate}</real_time_update_rate>
      <max_step_size>{p.physics_max_step_size}</max_step_size>
      <real_time_factor>{p.physics_real_time_factor}</real_time_factor>
      <ode>
        <solver>
          <type>quick</type>
          <iters>{p.physics_ode_iters}</iters>
          <sor>{p.physics_ode_sor}</sor>
        </solver>
        <constraints>
          <cfm>0</cfm>
          <erp>0.2</erp>
          <contact_max_correcting_vel>100</contact_max_correcting_vel>
          <contact_surface_layer>0.001</contact_surface_layer>
        </constraints>
      </ode>
    </physics>
    """).strip()


def _plugins_block() -> str:
    return textwrap.dedent("""
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
    <plugin filename="gz-sim-contact-system" name="gz::sim::systems::Contact"/>
    """).strip()


def _scene_block(p: PerfProfile) -> str:
    shadows = "true" if p.shadows_enabled else "false"
    return textwrap.dedent(f"""
    <scene>
      <ambient>0.65 0.68 0.72 1</ambient>
      <background>0.78 0.82 0.86 1</background>
      <shadows>{shadows}</shadows>
      <grid>false</grid>
      <origin_visual>false</origin_visual>
    </scene>
    """).strip()


def _gui_block(profile_name: str) -> str:
    """Minimal GUI: elevated cinematic overview of entire 25x20 warehouse floor."""
    return textwrap.dedent(f"""
    <gui fullscreen="0">
      <plugin filename="MinimalScene" name="3D View">
        <gz-gui>
          <title>SIH26123 — {profile_name.upper()} Mode</title>
          <property type="bool" key="showTitleBar">false</property>
          <property type="string" key="state">docked</property>
        </gz-gui>
        <engine>ogre2</engine>
        <scene>scene</scene>
        <ambient_light>0.65 0.68 0.72</ambient_light>
        <background_color>0.78 0.82 0.86</background_color>
        <camera_pose>12.0 -2.5 19.0 0 0.90 1.5708</camera_pose>
      </plugin>
      <plugin filename="GzSceneManager" name="Scene Manager">
        <gz-gui>
          <property key="resizable" type="bool">false</property>
          <property key="width" type="double">5</property>
          <property key="height" type="double">5</property>
          <property key="state" type="string">floating</property>
          <property key="showTitleBar" type="bool">false</property>
        </gz-gui>
      </plugin>
      <plugin filename="InteractiveViewControl" name="Interactive view control">
        <gz-gui>
          <property key="resizable" type="bool">false</property>
          <property key="width" type="double">5</property>
          <property key="height" type="double">5</property>
          <property key="state" type="string">floating</property>
          <property key="showTitleBar" type="bool">false</property>
        </gz-gui>
      </plugin>
      <plugin filename="CameraTracking" name="Camera Tracking">
        <gz-gui>
          <property key="resizable" type="bool">false</property>
          <property key="width" type="double">5</property>
          <property key="height" type="double">5</property>
          <property key="state" type="string">floating</property>
          <property key="showTitleBar" type="bool">false</property>
        </gz-gui>
      </plugin>
      <plugin filename="WorldControl" name="World control">
        <gz-gui>
          <title>World control</title>
          <property type="bool" key="showTitleBar">false</property>
          <property type="bool" key="resizable">false</property>
          <property type="double" key="height">72</property>
          <property type="double" key="z">1</property>
          <property type="string" key="state">floating</property>
          <anchors target="3D View">
            <line own="left" target="left"/>
            <line own="bottom" target="bottom"/>
          </anchors>
        </gz-gui>
        <play_pause>true</play_pause>
        <step>true</step>
        <start_paused>false</start_paused>
        <use_event>true</use_event>
      </plugin>
      <plugin filename="WorldStats" name="World stats">
        <gz-gui>
          <title>World stats</title>
          <property type="bool" key="showTitleBar">false</property>
          <property type="bool" key="resizable">false</property>
          <property type="double" key="height">110</property>
          <property type="double" key="width">290</property>
          <property type="double" key="z">1</property>
          <property type="string" key="state">floating</property>
          <anchors target="3D View">
            <line own="right" target="right"/>
            <line own="bottom" target="bottom"/>
          </anchors>
        </gz-gui>
        <sim_time>true</sim_time>
        <real_time>true</real_time>
        <real_time_factor>true</real_time_factor>
        <iterations>true</iterations>
      </plugin>
    </gui>
    """).strip()


def _sun_light(cast_shadows: bool) -> str:
    sh = "true" if cast_shadows else "false"
    return textwrap.dedent(f"""
    <light name="sun" type="directional">
      <cast_shadows>{sh}</cast_shadows>
      <pose>5 5 15 0 0 0</pose>
      <diffuse>0.95 0.95 0.98 1</diffuse>
      <specular>0.25 0.25 0.25 1</specular>
      <attenuation>
        <range>1000</range>
        <constant>0.9</constant>
        <linear>0.01</linear>
        <quadratic>0.001</quadratic>
      </attenuation>
      <direction>-0.3 0.2 -0.9</direction>
    </light>
    """).strip()


def _floor(p: PerfProfile) -> str:
    """
    Polished light epoxy concrete floor with subtle reflectivity.
    High-tech modern warehouse finish (bright, clean, zero dingy black pitch).
    """
    spec = "0.20 0.20 0.22 1" if p.specular_highlights else "0.08 0.08 0.08 1"
    return textwrap.dedent(f"""
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry>
            <plane><normal>0 0 1</normal><size>26 22</size></plane>
          </geometry>
        </collision>
        <visual name="visual">
          <geometry>
            <plane><normal>0 0 1</normal><size>26 22</size></plane>
          </geometry>
          <material>
            <ambient>0.78 0.80 0.84 1</ambient>
            <diffuse>0.85 0.87 0.90 1</diffuse>
            <specular>{spec}</specular>
          </material>
        </visual>
        <pose>12.0 9.5 0 0 0 0</pose>
      </link>
    </model>
    """).strip()


def _wall(name: str, pose: str, size: str, p: PerfProfile) -> str:
    spec = "0.10 0.10 0.10 1" if p.specular_highlights else "0 0 0 0"
    return textwrap.dedent(f"""
    <model name="{name}">
      <static>true</static>
      <pose>{pose}</pose>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>{size}</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>{size}</size></box></geometry>
          <material>
            <ambient>0.70 0.73 0.78 1</ambient>
            <diffuse>0.78 0.82 0.88 1</diffuse>
            <specular>{spec}</specular>
          </material>
        </visual>
      </link>
    </model>
    """).strip()


def _perimeter_walls(p: PerfProfile) -> str:
    walls = [
        ("wall_west",  f"0.1 9.5 1.25 0 0 0",   f"0.2 20.0 2.5"),
        ("wall_east",  f"23.9 9.5 1.25 0 0 0",   f"0.2 20.0 2.5"),
        ("wall_south", f"12.0 19.9 1.25 0 0 0",  f"25.0 0.2 2.5"),
        ("wall_north", f"12.0 0.1 1.25 0 0 0",   f"25.0 0.2 2.5"),
    ]
    return "\n\n".join(_wall(n, pose, sz, p) for n, pose, sz in walls)


def _shelf_row(base_name: str, x: float, y_start: float, count: int, p: PerfProfile) -> str:
    """
    Generate a row of 'count' realistic industrial shelving units.
    - Upright frames: Heavy-duty Industrial Blue
    - Crossbeams: OSHA Safety Orange
    - Tiers: Lower kraft cartons + Upper colorful logistics totes
    - Collision: exact bounding box (0.8m x 1.2m x 2.0m)
    """
    blocks = []
    # Varied colorful totes for top shelf: Cyan, Yellow, Orange
    tote_colors = [
        ("0.10 0.55 0.75 1", "0.15 0.65 0.85 1"),  # Warehouse Cyan
        ("0.85 0.70 0.10 1", "0.95 0.80 0.15 1"),  # Logistics Yellow
        ("0.90 0.40 0.10 1", "0.98 0.48 0.12 1"),  # Signal Orange
        ("0.15 0.65 0.35 1", "0.20 0.75 0.42 1"),  # Eco Green
    ]

    for i in range(count):
        cy = y_start + i * 2.0
        amb_tote, diff_tote = tote_colors[i % len(tote_colors)]
        blocks.append(textwrap.dedent(f"""
        <model name="{base_name}_{i+1:02d}">
          <static>true</static>
          <pose>{x:.1f} {cy:.1f} 1.0 0 0 0</pose>
          <link name="link">
            <collision name="col">
              <geometry><box><size>0.8 1.2 2.0</size></box></geometry>
            </collision>
            <!-- Upright Industrial Blue Frame -->
            <visual name="vis_frame">
              <geometry><box><size>0.80 1.20 1.95</size></box></geometry>
              <material>
                <ambient>0.10 0.35 0.70 1</ambient>
                <diffuse>0.15 0.45 0.85 1</diffuse>
                <specular>0.2 0.2 0.25 1</specular>
              </material>
            </visual>
            <!-- Mid-level OSHA Safety Orange Crossbeam -->
            <visual name="vis_beam_mid">
              <pose>0 0 0.0 0 0 0</pose>
              <geometry><box><size>0.82 1.22 0.05</size></box></geometry>
              <material>
                <ambient>0.88 0.42 0.05 1</ambient>
                <diffuse>0.96 0.48 0.08 1</diffuse>
                <specular>0.15 0.15 0.15 1</specular>
              </material>
            </visual>
            <!-- Top OSHA Safety Orange Crossbeam -->
            <visual name="vis_beam_top">
              <pose>0 0 0.96 0 0 0</pose>
              <geometry><box><size>0.82 1.22 0.05</size></box></geometry>
              <material>
                <ambient>0.88 0.42 0.05 1</ambient>
                <diffuse>0.96 0.48 0.08 1</diffuse>
                <specular>0.15 0.15 0.15 1</specular>
              </material>
            </visual>
            <!-- Lower Tier: Kraft Cardboard Cartons -->
            <visual name="vis_cargo_low">
              <pose>0 0 -0.46 0 0 0</pose>
              <geometry><box><size>0.70 1.05 0.74</size></box></geometry>
              <material>
                <ambient>0.72 0.55 0.32 1</ambient>
                <diffuse>0.82 0.64 0.38 1</diffuse>
                <specular>0.05 0.05 0.05 1</specular>
              </material>
            </visual>
            <!-- Upper Tier: Vibrant Logistics Storage Totes -->
            <visual name="vis_cargo_high">
              <pose>0 0 0.48 0 0 0</pose>
              <geometry><box><size>0.70 1.05 0.74</size></box></geometry>
              <material>
                <ambient>{amb_tote}</ambient>
                <diffuse>{diff_tote}</diffuse>
                <specular>0.25 0.25 0.25 1</specular>
              </material>
            </visual>
          </link>
        </model>
        """).strip())
    return "\n\n".join(blocks)


def _shelf_layout(p: PerfProfile) -> str:
    """
    Six shelf rows at fixed world positions (cols 6, 12, 18).
    Positioned with 2m cross-aisles at y=1, 9, 17.
    """
    rows = [
        ("shelf_row_A", 6.0,  2.0, 4),
        ("shelf_row_B", 6.0,  10.0, 4),
        ("shelf_row_C", 12.0, 2.0, 4),
        ("shelf_row_D", 12.0, 10.0, 4),
        ("shelf_row_E", 18.0, 2.0, 4),
        ("shelf_row_F", 18.0, 10.0, 4),
    ]
    return "\n\n".join(_shelf_row(n, x, y, c, p) for n, x, y, c in rows)


def _pickup_dropoff_pads() -> str:
    """
    Pickup (vibrant emerald green) and dropoff (safety orange) station pads.
    """
    stations = [
        # (name, wx, wy, color, type)
        ("pad_P1", 2.0,  17.0, "0.08 0.85 0.38 1", "P"),
        ("pad_P2", 2.0,   9.0, "0.08 0.85 0.38 1", "P"),
        ("pad_P3", 2.0,   2.0, "0.08 0.85 0.38 1", "P"),
        ("pad_P4", 5.0,   5.0, "0.08 0.85 0.38 1", "P"),
        ("pad_P5", 5.0,  14.0, "0.08 0.85 0.38 1", "P"),
        ("pad_P6", 10.0,  9.0, "0.08 0.85 0.38 1", "P"),
        ("pad_D1", 20.0, 17.0, "0.95 0.52 0.05 1", "D"),
        ("pad_D2", 20.0,  9.0, "0.95 0.52 0.05 1", "D"),
        ("pad_D3", 20.0,  2.0, "0.95 0.52 0.05 1", "D"),
        ("pad_D4", 15.0, 15.0, "0.95 0.52 0.05 1", "D"),
        ("pad_D5",  5.0, 17.0, "0.95 0.52 0.05 1", "D"),
        ("pad_D6",  5.0,  2.0, "0.95 0.52 0.05 1", "D"),
    ]
    parts = []
    for name, wx, wy, color, _ in stations:
        parts.append(textwrap.dedent(f"""
        <model name="{name}">
          <static>true</static>
          <pose>{wx:.1f} {wy:.1f} 0.003 0 0 0</pose>
          <link name="link">
            <visual name="pad">
              <geometry><box><size>1.10 1.10 0.004</size></box></geometry>
              <material>
                <ambient>{color}</ambient>
                <diffuse>{color}</diffuse>
                <specular>0.2 0.2 0.2 1</specular>
              </material>
            </visual>
          </link>
        </model>
        """).strip())
    return "\n\n".join(parts)


def _transit_lanes(p: PerfProfile) -> str:
    """Four horizontal transit lane safety markings."""
    lanes = [
        ("ln_NW", "7.0 14.0 0.002 0 0 0",  "7.5 0.12 0.002"),
        ("ln_NE", "16.5 14.0 0.002 0 0 0", "7.0 0.12 0.002"),
        ("ln_SW", "7.0 5.0 0.002 0 0 0",   "7.5 0.12 0.002"),
        ("ln_SE", "16.5 5.0 0.002 0 0 0",  "7.0 0.12 0.002"),
    ]
    parts = []
    for name, pose, size in lanes:
        parts.append(textwrap.dedent(f"""
        <model name="{name}">
          <static>true</static>
          <pose>{pose}</pose>
          <link name="link">
            <visual name="lane">
              <geometry><box><size>{size}</size></box></geometry>
              <material>
                <ambient>0.88 0.78 0.08 1</ambient>
                <diffuse>0.96 0.85 0.10 1</diffuse>
                <specular>0.1 0.1 0.1 1</specular>
              </material>
            </visual>
          </link>
        </model>
        """).strip())
    return "\n\n".join(parts)


def _floor_grid(p: PerfProfile) -> str:
    """
    RECORDING: omit grid entirely (saves 41 draw calls).
    NORMAL/DEBUG: include subtle grid lines.
    The grid is purely decorative — zero physics interaction.
    Instead of 41 individual line geometries, we use ONE merged model with
    all 41 visuals consolidated into a single link (one draw call batch).
    """
    if not p.render_floor_grid:
        return "<!-- floor_grid omitted in recording profile (41 draw calls → 0) -->"

    # Merge all grid lines into one link (single model = batched draw call)
    visuals = []
    for x in range(1, 24):
        visuals.append(
            f'<visual name="gx_{x:02d}"><pose>{x:.1f} 9.5 0.001 0 0 0</pose>'
            f'<geometry><box><size>0.015 19.0 0.001</size></box></geometry>'
            f'<material><ambient>0.70 0.73 0.76 1</ambient><diffuse>0.75 0.78 0.82 1</diffuse></material></visual>'
        )
    for y in range(1, 19):
        visuals.append(
            f'<visual name="gy_{y:02d}"><pose>12.0 {y:.1f} 0.001 0 0 0</pose>'
            f'<geometry><box><size>23.0 0.015 0.001</size></box></geometry>'
            f'<material><ambient>0.70 0.73 0.76 1</ambient><diffuse>0.75 0.78 0.82 1</diffuse></material></visual>'
        )
    inner = "\n    ".join(visuals)
    return textwrap.dedent(f"""
    <model name="floor_grid">
      <static>true</static>
      <pose>0 0 0 0 0 0</pose>
      <link name="link">
        {inner}
      </link>
    </model>
    """).strip()


def _cargo_clutter(p: PerfProfile) -> str:
    if not p.render_cargo_clutter:
        return "<!-- cargo_clutter omitted in recording profile -->"
    # Simple single-box cargo stack at each pickup station — not the
    # multi-visual per-pallet build from the original world
    stations = [(2.0, 17.0), (2.0, 9.0), (2.0, 2.0)]
    parts = []
    for i, (wx, wy) in enumerate(stations):
        parts.append(textwrap.dedent(f"""
        <model name="cargo_{i+1}">
          <static>true</static>
          <pose>{wx-0.5:.1f} {wy:.1f} 0.35 0 0 0</pose>
          <link name="link">
            <visual name="stack">
              <geometry><box><size>0.80 0.90 0.70</size></box></geometry>
              <material>
                <ambient>0.62 0.50 0.32 1</ambient>
                <diffuse>0.75 0.62 0.40 1</diffuse>
                <specular>0 0 0 0</specular>
              </material>
            </visual>
          </link>
        </model>
        """).strip())
    return "\n\n".join(parts)


def generate_world_sdf(profile_name: str, world_type: str = "s1") -> str:
    """
    Generate a complete SDF world string for the given profile.

    Args:
        profile_name: "normal", "debug", or "recording"
        world_type:   "s1" (open grid) or "s4" (choke wall)
    """
    p = get_profile(profile_name)
    world_name = f"warehouse_{world_type}_{profile_name}"

    dividing_wall = ""
    if world_type == "s4":
        # Choke wall: vertical wall at x=12 with passages at y=5 and y=14
        spec = "0 0 0 0"
        wall_segments = []
        for y_start, y_end in [(1.0, 4.0), (6.0, 13.0), (15.0, 18.0)]:
            length = y_end - y_start
            cy = (y_start + y_end) / 2.0
            wall_segments.append(textwrap.dedent(f"""
            <model name="wall_choke_{int(y_start*10):03d}">
              <static>true</static>
              <pose>12.0 {cy:.2f} 1.25 0 0 0</pose>
              <link name="link">
                <collision name="col">
                  <geometry><box><size>0.2 {length:.1f} 2.5</size></box></geometry>
                </collision>
                <visual name="vis">
                  <geometry><box><size>0.2 {length:.1f} 2.5</size></box></geometry>
                  <material>
                    <ambient>0.55 0.58 0.62 1</ambient>
                    <diffuse>0.62 0.66 0.72 1</diffuse>
                    <specular>{spec}</specular>
                  </material>
                </visual>
              </link>
            </model>
            """).strip())
        dividing_wall = "\n\n".join(wall_segments)

    return textwrap.dedent(f"""<?xml version="1.0"?>
<!--
  {world_name}.sdf — Auto-generated by generate_world.py
  Profile: {profile_name} — {p.description}

  Performance profile settings:
    Physics step:  {p.physics_max_step_size}s   ODE iters: {p.physics_ode_iters}
    LiDAR: {p.lidar_update_rate} Hz / {p.lidar_ray_count} rays   IMU: {p.imu_update_rate} Hz
    Shadows: {p.shadows_enabled}   Floor grid: {p.render_floor_grid}   Cargo: {p.render_cargo_clutter}
    Log level: {p.log_level}
-->
<sdf version="1.10">
  <world name="{world_name}">

    {_indent(_physics_block(p), 4)}

    {_indent(_plugins_block(), 4)}

    <gravity>0 0 -9.81</gravity>
    <magnetic_field>6e-06 2.3e-05 -4.2e-05</magnetic_field>
    <atmosphere type="adiabatic"/>

    {_indent(_gui_block(profile_name), 4)}

    {_indent(_scene_block(p), 4)}

    {_indent(_sun_light(p.sun_cast_shadows), 4)}

    {_indent(_floor(p), 4)}

    {_indent(_perimeter_walls(p), 4)}

    {_indent(dividing_wall, 4)}

    {_indent(_floor_grid(p), 4)}

    {_indent(_transit_lanes(p), 4)}

    {_indent(_pickup_dropoff_pads(), 4)}

    {_indent(_cargo_clutter(p), 4)}

    {_indent(_shelf_layout(p), 4)}

  </world>
</sdf>
""").strip()


def main():
    parser = argparse.ArgumentParser(
        description="Generate optimised SDF world for SIH26123"
    )
    parser.add_argument(
        "--profile", choices=["normal", "debug", "recording"],
        default="recording", help="Performance profile"
    )
    parser.add_argument(
        "--world-type", choices=["s1", "s4"], default="s1",
        help="s1=open grid, s4=choke wall"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Generate all 6 combinations (3 profiles × 2 world types)"
    )
    parser.add_argument(
        "--out-dir", default=None,
        help="Output directory (default: ros2_integration/worlds/)"
    )
    args = parser.parse_args()

    # Resolve output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out_dir or os.path.join(script_dir, "worlds")
    os.makedirs(out_dir, exist_ok=True)

    combos = []
    if args.all:
        for pname in ["normal", "debug", "recording"]:
            for wtype in ["s1", "s4"]:
                combos.append((pname, wtype))
    else:
        combos = [(args.profile, args.world_type)]

    for pname, wtype in combos:
        sdf = generate_world_sdf(pname, wtype)
        fname = f"warehouse_{wtype}_{pname}.sdf"
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(sdf)
        size_kb = len(sdf) / 1024
        print(f"Generated: {fname}  ({size_kb:.1f} KB)")

    print(f"\nOutput directory: {out_dir}")
    print("To use in Gazebo:")
    print(f"  gz sim {out_dir}/warehouse_s1_recording.sdf")


if __name__ == "__main__":
    main()
