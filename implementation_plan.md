# Implementation Plan: Edge-AI Based Distributed Fleet Coordination for AMRs in Smart Warehouses (SIH26123)

A comprehensive, production-grade, modular Python framework for decentralized multi-robot coordination, task allocation, congestion estimation, collision-free multi-agent path planning, safety supervision, execution abstraction, and reproducible benchmark evaluation for SIH 2026.

---

## 1. System Architecture

```
                    TASK STREAM
                         │
                         ▼
                   TASK MANAGER (Lifecycle / Generators)
                         │
                         ▼
              FLEET TASK ALLOCATION (Marginal Cost / Fleet Congestion)
                         │
                         ▼
                CONGESTION + ETA (Dynamic Heatmap & Delay Estimation)
                         │
                         ▼
              ADAPTIVE COORDINATION (Local / Neighbor / Cluster Modes)
                         │
                         ▼
                 DECENTRALIZED MAPF (PIBT / Time-Space Reservation / A*)
                         │
                         ▼
                 TRAJECTORY GEN (Waypoints / Velocities / Headings)
                         │
                         ▼
                 SAFETY SUPERVISOR (Hard Invariants & Fallbacks)
                         │
                         ▼
                     EXECUTION (Executor / Motion Model / Action)
                         │
                         ▼
                       ROBOTS
                    ↙          ↘
               SENSORS         P2P NETWORK
                    ↘          ↙
                   LOCAL WORLD MODEL
                         │
                         ▼
                   DECISION LOOP

      ┌────────────────────────────────────────────────────────┐
      │ Event Bus • Metrics Engine • Resource Monitor          │
      │ Replay System • Benchmark Runner • Statistical Reports │
      └────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Invariants & Additions

### A. Strict 16-Step Simulation Tick Contract
Every simulation tick **MUST** execute strictly in this order to guarantee zero future-information leakage:
1. **Advance simulation clock** ($t \leftarrow t + \Delta t$)
2. **Apply external events** (blockage spawns, robot hardware faults, user injections)
3. **Update ground-truth world** (physical obstacles, dynamic hazards)
4. **Generate sensor observations** (apply sensor noise/dropout based on ground truth)
5. **Deliver network messages** whose simulated latency has elapsed
6. **Update each robot's local belief/world model** (integrate fresh sensor sweeps and delivered P2P packets; update information age)
7. **Update task/robot state machines**
8. **Estimate congestion / ETA** (evaluated using local/shared belief)
9. **Allocate / reallocate tasks** (fleet-aware auction/marginal scoring)
10. **Detect conflicts / deadlocks** (wait-for graph analysis)
11. **Plan / replan paths** (A* / PIBT / Reservation)
12. **Generate trajectory / action**
13. **Safety supervisor validation** (hard invariant checking & fallback assignment)
14. **Execute only approved actions** (discrete or continuous motion model update)
15. **Update metrics and logging**
16. **Record replay state frame**

### B. Mathematical & Architectural Decentralization Isolation
- Robots have **zero reference** to the simulator's global ground-truth state, global task list, or other robots' true coordinates.
- Each robot operates exclusively on its instance of `LocalWorldModel`.
- A runtime assertion checks and raises `DecentralizationViolationError` if any planning or allocation function queries non-local world state.

### C. Dedicated Execution Layer (`execution/`)
Bridging planning/safety to physical and simulated robots for seamless future migration to ROS 2 (`cmd_vel` / `FollowJointTrajectoryAction`):
- `execution/action.py`: Action representations (`MOVE`, `WAIT`, `ROTATE`, `PICK`, `DROP`, `CHARGE`, `ESTOP`).
- `execution/motion_model.py`: Kinematic models (Differential Drive & Omnidirectional, acceleration bounds, turning limits).
- `execution/executor.py`: Action dispatcher and trajectory follower.

### D. Explicit Planner Outcome Hierarchy & Graceful Degradation
Planner returns a typed result `PlannerResult` with explicit status codes:
- `SUCCESS`: Full collision-free path found to goal.
- `PARTIAL_PLAN`: Safe sub-path found reaching horizon $H$.
- `NO_PATH`: No feasible path under current reservations.
- `TIMEOUT`: Planning time budget ($T_{\max}$) exceeded.
- `INVALID_PLAN`: Plan failed validation invariants.
- `STALE_STATE`: Local world model data too stale to plan safely.

**Graceful Degradation Escalation**:
$$\text{Planner Failure} \longrightarrow \text{Local Repair} \longrightarrow \text{Alternative Planner} \longrightarrow \text{WAIT} \longrightarrow \text{Safety Fallback}$$

### E. Detailed Robot Geometry Model
`RobotGeometry` dataclass:
- `footprint`: Polygon / geometric shape
- `radius`: Bounding circle radius ($r_{\text{robot}}$)
- `length`: Length in meters
- `width`: Width in meters
- `safety_margin`: Extra buffer distance ($\delta_{\text{safe}}$)
- `max_velocity`: Linear velocity cap ($v_{\max}$)
- `max_acceleration`: Linear acceleration cap ($a_{\max}$)
- `turning_radius`: Minimum turning radius / rotational velocity ($\omega_{\max}$)

### F. Calibrated Safety Authority
The **Safety Supervisor** has absolute final authority over actuator commands and rejects any candidate action that violates safety invariants.
- The discrete simulator guarantees zero collisions under the validated discrete model.
- Continuous-motion safety is verified through geometric sweep lookahead and runtime bounding-box overlap checks.

### G. Standardized Scenario Ladder ($S_0$ to $S_9$)
- **$S_0$ — Normal Operation**: Standard warehouse traffic, 6 AMRs, nominal task arrival.
- **$S_1$ — High Congestion**: High task frequency causing dense intersection traffic.
- **$S_2$ — Communication Latency**: Severe network delays ($100\text{ms} - 500\text{ms}$).
- **$S_3$ — Packet Loss**: High packet loss rate ($10\% - 40\%$) and burst drops.
- **$S_4$ — Aisle Blockage**: Sudden blockage of central corridor requiring dynamic fleet rerouting.
- **$S_5$ — Robot Failure**: Robot motor/battery failure mid-task requiring peer reclamation.
- **$S_6$ — Task Demand Surge**: Burst arrival of 20+ priority tasks in a single zone.
- **$S_7$ — Communication Degradation + Blockage**: Degraded network alongside blocked aisles.
- **$S_8$ — Failure + High Congestion**: Robot failure inside a critical choke point during peak load.
- **$S_9$ — Full Combined Disturbance**: Packet loss + latency + blocked aisles + robot failure + high task surge.

### H. Benchmark Reproducibility Manifest
Every experiment run automatically produces `manifest.json` containing:
- `experiment_id`, `git_commit`, `config_version`, `random_seed`
- `warehouse_layout`, `robot_count`, `task_count`, `algorithm_stack`
- `network_conditions`, `sensor_conditions`, `simulation_parameters`
- `timestamp`, `software_version`, `hardware_profile`

### I. Research Positioning on Adaptive Coordination
Adaptive coordination (`LOCAL`, `NEIGHBOR`, `CLUSTER`) is implemented as an integrated system policy. We empirically evaluate how dynamic coordination intensity optimizes the trade-off between task completion time, communication bandwidth, edge compute, and resilience.

---

## 3. Directory & File Plan

```
AMR-Fleet/
├── main.py
├── README.md
├── requirements.txt
├── pyproject.toml
│
├── config/
│   ├── default.yaml
│   ├── benchmark.yaml
│   └── demo.yaml
│
├── simulator/
│   ├── __init__.py
│   ├── clock.py
│   ├── warehouse.py
│   ├── robot.py
│   ├── task.py
│   ├── obstacle.py
│   ├── sensors.py
│   ├── world.py
│   └── simulation.py
│
├── world_model/
│   ├── __init__.py
│   ├── local_world.py
│   ├── belief_state.py
│   └── information_age.py
│
├── planning/
│   ├── __init__.py
│   ├── astar.py
│   ├── reservation.py
│   ├── multi_agent.py
│   ├── pibt.py
│   ├── conflict.py
│   ├── deadlock.py
│   ├── replanning.py
│   └── trajectory.py
│
├── execution/
│   ├── __init__.py
│   ├── action.py
│   ├── motion_model.py
│   └── executor.py
│
├── coordination/
│   ├── __init__.py
│   ├── allocator.py
│   ├── congestion.py
│   ├── eta.py
│   ├── priority.py
│   ├── coordinator.py
│   └── adaptive_coordination.py
│
├── network/
│   ├── __init__.py
│   ├── communication.py
│   ├── message.py
│   ├── topology.py
│   └── network_conditions.py
│
├── safety/
│   ├── __init__.py
│   ├── supervisor.py
│   ├── collision_checker.py
│   ├── invariants.py
│   └── fallback.py
│
├── resilience/
│   ├── __init__.py
│   ├── blockage.py
│   ├── failure.py
│   ├── recovery.py
│   └── charging.py
│
├── benchmark/
│   ├── __init__.py
│   ├── runner.py
│   ├── scenarios.py
│   ├── baselines.py
│   ├── ablation.py
│   ├── statistics.py
│   └── reports.py
│
├── events/
│   ├── __init__.py
│   ├── event.py
│   └── event_bus.py
│
├── metrics/
│   ├── __init__.py
│   ├── metrics.py
│   └── resource_monitor.py
│
├── registry/
│   ├── __init__.py
│   ├── planners.py
│   ├── allocators.py
│   └── scenarios.py
│
├── replay/
│   ├── __init__.py
│   ├── recorder.py
│   └── player.py
│
├── ui/
│   ├── __init__.py
│   └── dashboard.py
│
├── tests/
│   ├── __init__.py
│   ├── test_clock.py
│   ├── test_astar.py
│   ├── test_collision.py
│   ├── test_pibt.py
│   ├── test_allocation.py
│   ├── test_network.py
│   ├── test_deadlock.py
│   ├── test_failure.py
│   ├── test_safety.py
│   ├── test_execution.py
│   └── test_scenarios.py
│
├── experiments/
└── docs/
    ├── ARCHITECTURE.md
    ├── ALGORITHMS.md
    ├── BENCHMARKING.md
    ├── DEPENDENCIES.md
    ├── RESEARCH.md
    └── ROS_MIGRATION.md
```

---

## 4. Phased Execution Roadmap

### Step 1: Foundation & Event Architecture (Phase 0)
- Build configurations, event bus, clock with deterministic tick order, warehouse grid layouts, robot model with geometry, and task lifecycle models.

### Step 2: World Modeling, Sensors, Network, Execution & Safety (Phases 1, 2, 3)
- Decentralized belief tracking and information age.
- P2P network simulation with packet loss, latency, and topology models.
- Execution engine (`action.py`, `motion_model.py`, `executor.py`).
- Deterministic Safety Supervisor with runtime invariants and emergency fallbacks.

### Step 3: Multi-Agent Planning & Coordination (Phases 4, 5)
- Space-Time A*, Reservation Table, PIBT algorithm, Conflict & Deadlock detection.
- Congestion heatmaps, ETA estimators, dynamic priority aging, and Fleet-Aware Allocator.
- Adaptive Coordination escalation engine (`LOCAL`, `NEIGHBOR`, `CLUSTER`).

### Step 4: Resilience & Simulation Integration (Phase 6)
- Blocked aisle rerouting, robot failure recovery, battery return-to-charger.
- Complete 16-step orchestrator loop in `simulator/simulation.py`.

### Step 5: Benchmarking, Baselines, Scenarios $S_0-S_9$ & Metrics (Phase 7)
- Stop-and-Wait Baseline & Greedy A* Baseline.
- Scenario generators $S_0$ through $S_9$.
- Statistical analysis, ablation runner, resource monitor, replay engine.

### Step 6: Pygame Dashboard, CLI & Demo Mode (Phase 8)
- Real-time visual dashboard with side-by-side baseline vs. fleet metrics and 6-phase demo sequence.
- Full CLI (`main.py --demo`, `--headless`, `--benchmark`, `--replay`).

### Step 7: Pytest Suite & Documentation (Phase 9)
- Exhaustive unit and integration tests.
- Complete documentation suite in `docs/` and `README.md`.

---

## 5. Verification Plan

### Automated Pytest Suite
```powershell
pytest tests/ -v
```
All unit tests for clock ordering, A*, PIBT, conflict detection, safety supervisor, allocation, network degradation, failure recovery, and execution models must pass with 100% success.

### Headless Benchmark Validation
```powershell
python main.py --benchmark --seeds 10 --headless
```
Verify zero collisions ($0$) and $\ge 20\%$ task completion time reduction over the Stop-and-Wait baseline.

### Visual Demo Run
```powershell
python main.py --demo
```
Verify smooth real-time execution across the 6-phase demo sequence.
