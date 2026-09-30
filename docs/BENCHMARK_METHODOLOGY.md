# SIH26123 Rigorous Benchmark Methodology & Reproducibility Guide

**Project**: Decentralized AMR Fleet Coordination for Smart Warehouses  
**Submission**: Smart India Hackathon 2026 (Problem Statement: SIH26123)  
**Canonical Dataset Reference**: `results/CANONICAL_SIH_METRICS.json`  

---

## 1. Experimental Objectives & Core Hypothesis

The benchmark evaluates the hypothesis that a **decentralized, edge-native coordination architecture** (synthesizing Hungarian allocation, Priority Inheritance with Backtracking [PIBT], Space-Time A*, and a deterministic Safety Supervisor) reduces average mission task completion time by $\ge 20\%$ relative to traditional Stop-and-Wait baselines, while observing zero inter-robot collisions and zero unhandled deadlocks under realistic warehouse disturbances.

---

## 2. Experimental Controls & Fairness Guarantees

Every comparison in the benchmark suite executes under strict paired-sample isolation:

1. **Warehouse Environment**:
   - Discrete grid layout: $30 \times 20$ cells ($1.0\text{ m}$ per grid cell).
   - Industrial heavy-corridor warehouse layout with designated pickup bays, dropoff stations, and charging kiosks.
2. **Fleet Kinematics**:
   - 6 active AMRs with identical differential-drive kinematic profiles.
   - Maximum linear speed: $1.5\text{ m/s}$; Maximum rotational velocity: $2.0\text{ rad/s}$.
   - Safety bounding radius: $0.45\text{ m}$.
3. **Identical Task Streams & Seeds**:
   - 10 deterministic pseudo-random seeds: `[42, 101, 202, 303, 404, 505, 606, 707, 808, 909]`.
   - For every seed, both the baseline and proposed systems receive the exact same task arrivals, pickup locations, dropoff targets, and injected disturbances.
4. **Execution Scale & Pairing**:
   - **$100\text{ Paired Experiments}$** = $10\text{ Scenarios} \times 10\text{ Seeds}$.
   - **$200\text{ Total Simulation Executions}$** = $100\text{ Baseline Executions} + 100\text{ Proposed Executions}$.
   - Simulations run for a fixed duration of $350$ steps per execution ($0.1\text{ s}$ per discrete clock tick).

---

## 3. System Configurations Under Test

### Baseline System (Centralized Stop-and-Wait)
- **Task Allocation**: Greedy nearest-robot assignment (Manhattan distance).
- **Motion Strategy**: Uncoordinated A* shortest path search.
- **Conflict Resolution**: Stop-and-Wait (when two robots contest an edge or vertex, both robots halt or wait until clear, with no priority inheritance or lateral detour routing).

### Proposed System (Decentralized Fleet Coordination)
- **Task Allocation**: Hungarian bipartite minimum-cost matching factoring distance, spatial congestion index, and battery reserves.
- **Task Ownership**: Distributed Claim/ACK/Commit protocol with monotonic assignment epochs (`coordination/task_ownership.py`).
- **Local MAPF**: Priority Inheritance with Backtracking (PIBT) with traffic flow alignment (`planning/pibt.py`).
- **Path Repair**: Event-driven Space-Time A* dynamic detour rerouting (`planning/replanning.py`).
- **Deadlock Handling**: Tarjan strongly connected components cycle detection over the Wait-For Graph (WFG) with automated lateral yielding.
- **Safety**: Authoritative runtime safety supervisor gating all motor commands at the actuator boundary (`safety/supervisor.py`).

---

## 4. Scenario Taxonomy (S0 – S9)

| Scenario ID | Operational Disturbance Profile | Description & Injection Parameters |
| :--- | :--- | :--- |
| **`S0_NORMAL`** | Nominal Poisson Task Stream | Baseline warehouse operations with task arrival rate $\lambda = 0.2$ tasks/sec. |
| **`S1_HIGH_CONGESTION`** | Choke-Point Bottleneck | Heavy task arrival stream ($\lambda = 0.6$ tasks/sec) converging on central warehouse aisles. |
| **`S2_COMM_LATENCY`** | High Wireless Latency | $250\text{ ms}$ fixed transport delay injected across all P2P gossip mesh broadcasts. |
| **`S3_PACKET_LOSS`** | Severe Packet Drop Rate | $25\%$ uniform random wireless packet loss across the peer communication mesh. |
| **`S4_AISLE_BLOCKAGE`** | Dynamic Corridor Blockage | Obstacle injected at cell $(7, 10)$ at $t = 20.0\text{s}$, blocking primary transit artery. |
| **`S5_ROBOT_FAILURE`** | Catastrophic Motor Stall | AMR R02 suffers a hardware stall at $t = 25.0\text{s}$; active task reclaimed by healthy peer. |
| **`S6_TASK_SURGE`** | Burst Task Arrivals | Arrival bursts of 3–5 concurrent urgent orders injected simultaneously at peak timesteps. |
| **`S7_COMM_AND_BLOCKAGE`** | Compound Loss & Obstacle | Simultaneous $20\%$ packet drop rate and aisle blockage at cell $(12, 10)$. |
| **`S8_FAILURE_AND_CONGESTION`** | Choke-Point + Hardware Stall | Choke-point layout with AMR R03 failing in the narrow bottleneck corridor. |
| **`S9_FULL_DISTURBANCE`** | Combined Multi-Disturbance Matrix | Simultaneous communication latency ($200\text{ms}$), packet loss ($25\%$), blockage, and motor failure. |

---

## 5. Mathematical Formulations & Metric Definitions

### 1. Task Completion Time Reduction (%)
Calculated across paired seeds and aggregate scenario averages:
$$\text{Reduction (\%)} = \left(\frac{T_{\text{baseline}} - T_{\text{proposed}}}{T_{\text{baseline}}}\right) \times 100$$
- $T_{\text{baseline}}$: Mean task completion duration (seconds) under Stop-and-Wait.
- $T_{\text{proposed}}$: Mean task completion duration (seconds) under our decentralized coordination.

### 2. Collision Classification & Observation
Evaluated at every simulation step:
- **Vertex Conflict**: $\exists i \neq j : \mathbf{p}_i(t) = \mathbf{p}_j(t)$ (two robots occupying the exact same cell).
- **Edge Swap Conflict**: $\exists i \neq j : \mathbf{p}_i(t) = \mathbf{p}_j(t+1) \land \mathbf{p}_j(t) = \mathbf{p}_i(t+1)$ (two robots traversing the same corridor in opposing directions).
- **Obstacle Conflict**: $\exists i : \mathbf{p}_i(t) \in \mathcal{B}_{\text{blocked}}$ (robot entering a blocked cell).
- *Scientific standard*: Reported as **observed empirical collisions** (0 across all 200 executions), rather than claiming unproven mathematical formal proofs.

### 3. Deadlock Classification
A true deadlock is defined as a cyclic waiting condition in the directed dependency graph:
$$G = (V, E), \quad (R_i, R_j) \in E \iff R_i \text{ is waiting for a cell reserved by } R_j$$
Cycles are detected via Tarjan's SCC algorithm. Transient yields or yielding to a moving agent are **not** counted as deadlocks.

### 4. Latency Taxonomy
- **Algorithmic Planning Latency**: Wall-clock time required for PIBT and Space-Time A* decision routines (measured via `time.perf_counter()`).
- **Simulation Step Latency**: Total time per discrete step including physics integration, network delay simulation, and metric serialization.
- **Web Telemetry Latency**: WebSocket serialization and transport duration.

### 5. Memory Taxonomy
- **Core Planner Memory**: Resident set size (RSS) of the standalone Python coordination runtime without GUI dependencies ($\approx 54.0\text{ MB}$).
- **Total Digital Twin Process Memory**: Full process memory including Uvicorn, FastAPI, WebSocket streaming buffers, and history caches ($\approx 238.7\text{ MB}$).

---

## 6. How to Reproduce the Benchmark

To regenerate the complete canonical benchmark suite from scratch:

```bash
# 1. Run the canonical report generator
python -m benchmark.generate_canonical_report

# 2. Run the 116-test regression suite
python -m pytest -q

# 3. Inspect generated canonical files
cat results/CANONICAL_SIH_METRICS.json
cat results/canonical/benchmark_summary.md
```
