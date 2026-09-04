# SIH 2026 Benchmark Methodology & Experimental Rigor

### 1. Controlled Experimental Isolation
Every paired comparison executes under strictly identical:
- **Layout**: 30x20 industrial heavy-corridor warehouse grid
- **Robot Count**: 6 active AMRs with identical kinematic models (max speed 1.5 m/s, bounding radius 0.45m)
- **Task Generation**: Identical Poisson task stream, arrival seeds, pickup/dropoff stations
- **Seeds**: 10 deterministic seeds `[42, 101, 202, 303, 404, 505, 606, 707, 808, 909]`
- **Timestep**: 0.1s simulation clock tick contract

### 2. Evaluated Systems
1. **Baseline**: Stop-and-Wait with uncoordinated A* shortest paths and nearest-robot task allocation.
2. **Proposed System**: Decentralized Fleet Coordination with Fleet-Aware Task Allocation (ETA + Congestion), Priority Inheritance Backtracking (PIBT), Space-Time A* dynamic detour recovery, Adaptive Coordination (LOCAL/NEIGHBOR/CLUSTER), and Deterministic Safety Supervisor.

### 3. Metric Calculations
- **Completion Time Reduction**: `((Baseline_Time - Proposed_Time) / Baseline_Time) * 100` calculated on unrounded float values.
- **Collisions**: Verified continuously at every simulation tick for:
  - Vertex Conflict (two robots in identical cell)
  - Edge Swap Conflict (robots crossing along same edge)
  - Obstacle Conflict (robot entering blocked cell or wall)
