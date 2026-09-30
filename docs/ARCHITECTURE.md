# System Architecture: Edge-First Distributed AMR Fleet Coordination (SIH26123)

## 1. Architectural Philosophy & Core Pipeline

The core architectural contribution of this framework is a **decentralized, peer-to-peer intelligence stack** engineered specifically for edge execution on Autonomous Mobile Robots (AMRs) in smart warehouses.

```
                    WAREHOUSE TASK SOURCE
                              │
                              ▼
           TASK ALLOCATION (Hungarian + Fleet-Aware Cost Model)
                              │
                              ▼
      DISTRIBUTED OWNERSHIP LAYER (Claim / ACK / Commit Protocol)
                              │
                              ▼
           LOCAL WORLD MODEL & P2P WIRELESS GOSSIP MESH
                              │
                              ▼
          CONGESTION ESTIMATION & DYNAMIC HOTSPOT INDEX
                              │
                              ▼
             EVENT-DRIVEN REPLANNING (11 Discrete Triggers)
                              │
                              ▼
            MOTION COORDINATION (PIBT Priority Inheritance)
                              │
                              ▼
              PATH PLANNING (Space-Time A* Fallback)
                              │
                              ▼
        SPACE-TIME RESERVATION TABLE (Time-Indexed Corridors)
                              │
                              ▼
        DETERMINISTIC SAFETY SUPERVISOR (Non-Bypassable Veto Gate)
                              │
                              ▼
                   SIMULATED ROBOT EXECUTION
                              │
                              ▼
             TELEMETRY & INTERACTIVE DIGITAL TWIN
```

---

## 2. Component Responsibility Matrix

| Subsystem Component | Algorithmic Mechanism | Safety Criticality | Edge Execution Responsibility |
|---|---|---|---|
| **Task Allocation** | Hungarian algorithm (Kuhn-Munkres) with fleet ETA cost model | Non-Critical | Evaluates distance, turn penalty ($0.4\text{s}$), congestion ($0.3$), and workload balance ($3.0$) |
| **Task Ownership Layer** | Distributed Claim / ACK / Commit Protocol (`coordination/task_ownership.py`) | Operational Critical | Prevents duplicate task ownership via versioned epochs and timeout reclaims |
| **Local World Model** | Decentralized belief state with exponential age decay | Operational Critical | Fuses on-board perception with 1-hop P2P heartbeats; dead-reckons missing peer updates |
| **Congestion Estimation** | Normalized Congestion Index ($0$–$100$ exponential saturation) | Advisory | Detects bottleneck saturation and biases A* edge costs to route around crowds |
| **Event-Driven Replanning**| `EventDrivenReplanner` with 11 discrete trigger types (`planning/replanning.py`) | Operational Critical | Initiates replanning only on state changes; prevents reroute spam via hash cooldown |
| **Motion Coordination** | Priority Inheritance Behavioral Tree (`coordination/pibt.py`) | Operational Critical | Resolves pairwise and group conflicts in $\mathcal{O}(V)$ time per AMR |
| **Path Planning** | Space-Time A* $(x, y, t)$ Planner (`planning/spacetime_astar.py`) | Operational Critical | Computes 3D $(x,y,\text{time})$ conflict-free trajectories avoiding occupied cells |
| **Reservation Table** | Time-Indexed Space-Time Table (`planning/reservation.py`) | Safety Critical | Registers spatio-temporal cell claims and validates future availability horizon |
| **Safety Supervisor** | Deterministic Invariant Verifier (`safety/supervisor.py`) | **Strictly Safety Critical** | Non-bypassable runtime gate vetoing any action with vertex or edge-swap conflicts |
| **Learned Priority Guidance**| Optional PyTorch Neural Adapter (`learning/model_adapter.py`) | **Non-Critical (Optional)** | Advisory priority suggestions; deterministically falls back to heuristic if disabled |

---

## 3. Distributed Task Ownership Layer (Claim / ACK / Commit)

To guarantee that no two AMRs execute the same task during wireless jitter or network partitions, task ownership is coordinated via an explicit, versioned distributed protocol:

```
  UNASSIGNED ──► PROPOSED ──► CLAIMED ──► ACKED ──► COMMITTED ──► EXECUTING ──► COMPLETED
                                 │                      │
                           (ACK Timeout)         (Robot Failure)
                                 │                      │
                                 ▼                      ▼
                             RELEASED               RECLAIMED
```

### Protocol Mechanics:
1. **Assignment Epochs**: Every task maintains a monotonically increasing `assignment_epoch`. Any peer receiving a claim with an outdated epoch immediately rejects it.
2. **Claim & Acknowledgement**: An AMR broadcasting a `TASK_CLAIM` must collect positive `TASK_ACK` responses from peers in its local communication cluster before transitioning to `COMMITTED`.
3. **Automated Reclaim**: If an executing AMR suffers a hardware failure (detected via missed heartbeats), healthy peers trigger a `TASK_RECLAIM` with an epoch bump, transferring ownership without duplicate execution.

---

## 4. Space-Time Reservation System & Timeline

The reservation table records temporal occupancy as a mapping of $(x, y, t) \to \text{robot\_id}$:

- **Time-Indexed Horizon**: Tracks reservations up to a configurable horizon ($H = 20\text{ steps}$).
- **Timeline Inspection**: The `/api/reservations` endpoint provides live telemetry distinguishing:
  - *Active Reservation*: Current cell occupancy at tick $t$.
  - *Future Reservation*: Planned corridor reservation at $t + k$.
  - *Expired Reservation*: Historical timestamps automatically pruned via `prune_expired()`.
  - *Invalidated Cells*: Blocked corridors immediately released via `invalidate_cell(x, y)` during dynamic obstacle injection.

---

## 5. Event-Driven Replanning Triggers

Rather than continuously polling expensive graph searches on idle robots, replanning is governed by an event-driven architecture with 11 explicit triggers:

1. `TASK_COMPLETION`: AMR successfully delivered payload; requires next waypoint.
2. `NEW_URGENT_TASK`: High-priority surge task injected into the warehouse.
3. `TASK_OWNERSHIP_TIMEOUT`: Stalled peer claim released.
4. `ROBOT_FAILURE`: Peer AMR suffered hardware stall.
5. `BATTERY_THRESHOLD`: AMR reached low-state-of-charge ($< 20\%$) and must route to charger.
6. `DYNAMIC_BLOCKAGE`: Sensor or peer detected physical aisle obstruction.
7. `RESERVATION_INVALIDATED`: Target corridor invalidated by another agent.
8. `COMMUNICATION_TOPOLOGY_CHANGE`: Peer joined or dropped from local wireless mesh.
9. `DEADLOCK_DETECTED`: Wait-For-Graph identified cyclic wait.
10. `PATH_DEVIATION`: AMR position diverged from planned trajectory.
11. `HEARTBEAT_TIMEOUT`: Missing P2P heartbeats for $> 1.5\text{ s}$.

*Reroute Deduplication*: Scene state hashing `(start_pos, goal_pos, blocked_hash)` combined with an exponential backoff cooldown prevents reroute thrashing on stopped or waiting robots.

---

## 6. The Deterministic Safety Supervisor Invariant Guarantee

The **Safety Supervisor** is architecturally isolated from the planner and has sole authority over motor actuation commands:

```
Candidate Motion Vector ──► [ SAFETY SUPERVISOR ] ──► Motor Actuator Execution
                                    │
                                    ├── Check 1: Vertex Invariant (No two AMRs share cell at t)
                                    ├── Check 2: Edge Invariant (No two AMRs swap cells t -> t+1)
                                    ├── Check 3: Obstacle Invariant (Cell not occupied by static/dynamic wall)
                                    └── Check 4: Boundary Invariant (Cell within warehouse dimensions)
                                    │
                                    └── IF VIOLATED ──► Forced In-Place Halt & Priority Yield
```

Because the Safety Supervisor executes on deterministic boolean logic without external network dependencies, **0 inter-robot collisions were observed across all 200 validated benchmark executions**.

---

## 7. Parallel Background & Observability Systems

Operating asynchronously alongside the high-rate control loop:
- **P2P Gossip Mesh**: Simulates decentralized wireless broadcasts with configurable latency (up to $500\text{ ms}$) and packet loss (up to $50\%$).
- **Interactive Digital Twin**: FastAPI backend streaming live simulation state over WebSockets at 10 Hz to an HTML5 Canvas interface.
- **Robot Inspector Panel**: Exposes real-time AMR diagnostics: kinematic velocity, SOC, explicit wait reasons, assignment epoch, and current reservation footprint.
- **Evidence Drawer & Metric Sync**: Automatically ingests `results/CANONICAL_SIH_METRICS.json` to guarantee that all UI dashboards display empirically verified data.
