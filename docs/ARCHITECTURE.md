# System Architecture: Edge-AI Distributed AMR Fleet Coordination (SIH26123)

## 1. Architectural Philosophy

The core architectural contribution of this framework is a **decentralized, peer-to-peer intelligence stack** designed specifically for edge computation on Autonomous Mobile Robots (AMRs) in smart warehouses.

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
```

---

## 2. The Strict 16-Step Simulation Tick Contract

To prevent accidental information leakage between the future ground truth and on-board robot planning, every simulation step executes in this strict deterministic order:

1. **Advance simulation clock** ($t \leftarrow t + \Delta t$)
2. **Apply external disturbance events** (aisle blockages, hardware motor faults)
3. **Update ground-truth world** (physical map obstacles)
4. **Generate sensor observations** (per-robot LiDAR sweeps with range limits & noise)
5. **Deliver network messages** whose simulated latency has elapsed
6. **Update local belief/world model** (absorb sensor sweeps and delivered P2P packets; decay information age)
7. **Update task/robot state machines** (advance pick/drop lifecycles)
8. **Estimate congestion / ETA** (evaluated using local/shared belief)
9. **Allocate / reallocate tasks** (fleet-aware auction/marginal scoring)
10. **Detect conflicts / deadlocks** (directed Wait-For Graph cycle detection)
11. **Plan / replan paths** (PIBT / Space-Time A*)
12. **Generate trajectory / action**
13. **Safety supervisor validation** (hard invariant checking & fallback assignment)
14. **Execute only approved actions** (via `ActionExecutor` and `MotionModel`)
15. **Update metrics and resource profiling** (CPU %, RAM, latencies)
16. **Record replay state frame**

---

## 3. Decentralization Guarantee

- **Ground Truth Isolation**: AMRs have zero direct pointer access to the `SimulatorWorld` ground truth.
- **Local Beliefs**: Every AMR maintains an independent `LocalWorldModel` populated solely by on-board sensors and received P2P wireless packets.
- **Information Age**: Every piece of peer data is timestamped and categorized into `FRESH`, `RECENT`, `STALE`, and `UNKNOWN`. Confidence exponentially decays over time ($t_{1/2} = 1.0\text{s}$).

---

## 4. Safety Architecture

The **Safety Supervisor** is the supreme authority over AMR actuator commands. The planner never directly controls physical motors.

```
Planner Candidate Action ──► [ SAFETY SUPERVISOR ] ──► Approved Action / Fallback
                                   │
                                   ├── Verification: Vertex Invariant (No overlap)
                                   ├── Verification: Edge Invariant (No swap)
                                   ├── Verification: Immobility of Failed AMRs
                                   └── Verification: Blocked Cell Rejection
```
