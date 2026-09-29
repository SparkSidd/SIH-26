# Gazebo Physical Validation Methodology
**Project**: SIH26123 — Edge-AI Distributed Fleet Coordination  
**Purpose**: Describe how physical validation evidence is collected and interpreted

---

## Validation Layers

This project uses three completely independent validation layers. They MUST NOT be conflated.

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Python Deterministic Benchmark             │
│  ─────────────────────────────────────────────────  │
│  200 runs × 6 robots × S0 scenario                  │
│  Frozen coordinator (CHECKPOINT_FINAL_PRE_GAZEBO)   │
│  Result: 26.18% aggregate task-time reduction       │
│  Status: FROZEN — do not re-run or overwrite        │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Layer 2: ROS/SIL Integration Tests                  │
│  ─────────────────────────────────────────────────  │
│  102 tests: 77 original + 25 ROS adapter tests      │
│  Uses mock_ros stubs (no actual ROS runtime)        │
│  Result: 102/102 passing                            │
│  Status: LOCKED — tests must not be weakened        │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Layer 3: Gazebo Harmonic Physical Validation        │
│  ─────────────────────────────────────────────────  │
│  Real physics: ODE, diff-drive, LiDAR, IMU          │
│  Real ROS 2 Jazzy + ros_gz_bridge                   │
│  Results: measured and reported separately          │
│  Purpose: Confirm physical execution feasibility    │
└─────────────────────────────────────────────────────┘
```

---

## Gate System

Gates are executed sequentially. A failed gate stops further progress.

| Gate | Description | Pass Criterion |
|---|---|---|
| **G1** | Ubuntu 24.04 + WSL2 | `VERSION_ID=24.04`, arch=x86_64, WSL VERSION=2 |
| **G2** | ROS 2 Jazzy | `ROS_DISTRO=jazzy`, `ros2 --version` succeeds |
| **G3** | Gazebo Harmonic | `gz sim --version` returns 8.x.x |
| **G4** | ros_gz_bridge | `ros2 pkg list` shows ros_gz_bridge, ros_gz_sim |
| **G5** | Single AMR spawn | Robot appears in Gazebo, no SDF errors |
| **G6** | cmd_vel | cmd_vel → bridge → robot motion in Gazebo |
| **G7** | Odometry | odom x/y/yaw change matches motion |
| **G8** | LiDAR + IMU | Scan ranges populated, IMU values plausible |
| **G9** | Single robot task | Full pickup→travel→dropoff lifecycle |
| **G10** | Two-robot interaction | Separation maintained, no contacts |
| **G11** | Six-robot fleet | All 6 robots operate concurrently |
| **G12** | S1 scenario | High-congestion six-robot run |
| **G13** | S4 scenario | Blockage with choke wall |
| **G14** | S5 scenario | Robot failure + recovery |
| **G15** | S8 scenario | Failure + congestion combined |
| **G16** | Baseline vs proposed | Matched comparison of policies |
| **G17** | Final report | All docs complete |

---

## Metric Definitions

### Task Metrics
- **makespan**: wall-clock time from first task start to last task completion
- **throughput**: tasks completed per unit simulation time
- **waiting_time**: time a robot spends idle with a task assigned
- **travel_distance**: total path length traversed by all robots

### Physical Safety Metrics
- **contact_events**: actual Gazebo physics contact detections (robot-to-robot)
- **wall_contacts**: robot-to-wall contact events
- **min_separation**: minimum inter-robot Euclidean distance observed
- **near_miss_count**: events where separation < 0.6 m (1 × robot width)

### Navigation Metrics
- **path_deviation**: |planned_path − actual_trajectory| integrated over time
- **position_error**: |intended_position − actual_position| at waypoints
- **heading_error**: |intended_yaw − actual_yaw| at waypoints
- **stopping_distance**: distance traveled after cmd_vel=0 issued

### Coordination Metrics
- **belief_age**: age of P2P belief messages when received
- **replan_count**: number of path replans triggered
- **conflict_wait**: time spent in conflict-resolution waiting

---

## Claim Validity Policy

> [!IMPORTANT]
> The following distinguishes valid from invalid claims about this project.

### VALID CLAIMS

```
✅ "26.18% aggregate task-completion-time reduction was established 
   across the frozen deterministic 200-run Python benchmark."

✅ "ROS 2 integration passed 102/102 software/SIL tests."

✅ "Gazebo Harmonic physical-execution validation demonstrated [X]
   task completion with [Y] physical contacts across [Z] runs."
```

### INVALID CLAIMS

```
❌ "Gazebo proved the 26.18% result."
   (Gazebo results are separate from the benchmark)

❌ "0 physical collisions guaranteed."
   (Gazebo shows observed data only; no physical guarantee)

❌ "Real robot performance is identical to simulation."
   (Simulation limitations apply; see SYSTEM_LIMITATIONS.md)

❌ "The benchmark was obtained from Gazebo runs."
   (The benchmark is from the frozen Python deterministic system)
```

---

## Data Storage Convention

All Gazebo validation data stored under `results/gazebo/`.

### Per-run directory structure:
```
results/gazebo/
├── S0_nominal_proposed/
│   ├── run_001/
│   │   ├── run_manifest.json      # config, seed, versions
│   │   ├── task_metrics.csv       # per-task timing
│   │   ├── robot_states.csv       # per-robot position/velocity log
│   │   ├── planner_metrics.csv    # planning latency
│   │   ├── collision_metrics.csv  # contacts + separations
│   │   └── network_metrics.csv    # belief age, loss rate
│   └── run_002/
│       └── ...
├── S0_nominal_baseline/
├── S1_congestion/
├── S4_blockage/
├── S5_failure/
└── S8_combined/
```

### `run_manifest.json` schema:
```json
{
  "run_id": "S1_proposed_001",
  "scenario": "S1",
  "policy": "proposed",
  "seed": 42,
  "robot_count": 6,
  "timestamp": "ISO8601",
  "software": {
    "ros_distro": "jazzy",
    "gazebo_version": "8.x.x",
    "ros_gz_bridge": "x.y.z",
    "python": "3.12.x",
    "coordinator_checkpoint": "CHECKPOINT_FINAL_PRE_GAZEBO"
  },
  "physics": {
    "step_size_ms": 1,
    "real_time_factor": 1.0,
    "world": "warehouse_s1.sdf"
  },
  "network": {
    "latency_ms": 0,
    "jitter_ms": 0,
    "loss_pct": 0
  }
}
```

---

## Trajectory Validation Protocol

For each significant run, compare planned vs actual trajectory:

1. **Record planned waypoints** from the coordinator's path output
2. **Record actual positions** from `/robot_id/odom` at 10 Hz
3. **Compute deviation** at each planned waypoint:
   - `d_pos = sqrt((x_plan - x_actual)² + (y_plan - y_actual)²)`
   - `d_yaw = |yaw_plan - yaw_actual|` (wrapped to [0, π])
4. **Report**:
   - Mean position error
   - Max position error  
   - Stopping distance overshoot
   - Heading error at targets

---

## WSLg / Headless Policy

Gazebo GUI via WSLg is **preferred** for validation because:
- Visual inspection catches SDF/plugin errors immediately
- Interactive debugging of spawn, motion, sensor rays

If WSLg fails (rendering errors, display issues):
1. Diagnose: `echo $DISPLAY`, `echo $WAYLAND_DISPLAY`
2. Try: `gz sim -r world.sdf --headless-rendering`
3. For batch runs (Gates 12–16): headless is acceptable
4. Document which runs used headless and why

**Physical simulation accuracy is not affected by rendering mode.**

---

*Last updated: 2026-09-12*  
*Author: Antigravity (SIH26123)*
