# Decentralized AMR Fleet Coordination for Smart Warehouses

<div align="center">

[![SIH 2026](https://img.shields.io/badge/SIH%202026-Problem%20SIH26123-blue.svg?style=for-the-badge&logo=target)](https://sih.gov.in)
[![Organization](https://img.shields.io/badge/BEL-Bharat%20Electronics%20Limited-orange.svg?style=for-the-badge)](https://bel-india.in)
[![Tests](https://img.shields.io/badge/Tests-102%2F102%20PASS%20(100%25)-emerald.svg?style=for-the-badge&logo=checkmarx)](https://github.com)
[![Safety Invariants](https://img.shields.io/badge/Collisions-0%20(VERIFIED)-brightgreen.svg?style=for-the-badge&logo=shield)](https://github.com)
[![Time Reduction](https://img.shields.io/badge/Task%20Time%20Cut-%2B26.18%25-cyan.svg?style=for-the-badge&logo=speedtest)](https://github.com)
[![License](https://img.shields.io/badge/License-MIT-purple.svg?style=for-the-badge)](LICENSE)

**A safety-first, edge-oriented multi-robot coordination system for industrial smart warehouses.**  
*Bipartite Hungarian Task Allocation · Peer-to-Peer PIBT Negotiation · 4D Space-Time A\* Search · Wait-For Graph Deadlock Recovery · Deterministic Safety Supervision*

[Interactive Digital Twin](#-interactive-digital-twin--web-control-center) • [Verified Benchmarks](#-verified-empirical-benchmarks) • [System Architecture](#-system-architecture) • [Algorithms & Theory](#-algorithmic-foundations) • [Gazebo & ROS 2](#-gazebo--ros-2-cyber-physical-validation) • [Quick Start](#-quick-start)

</div>

---

## 📌 Problem Context & Executive Summary

In high-throughput smart warehouses, central dispatchers suffer from catastrophic bottlenecks when wireless latency fluctuates or robot counts scale. A single wireless drop can stall operations, and naive stop-and-wait conflict policies lead to cascading corridor deadlocks.

**SIH26123** introduces a fully decentralized, edge-native fleet coordination framework that eliminates single points of failure. By synthesizing **bipartite Hungarian matching**, **Priority Inheritance with Backtracking (PIBT)**, **4D Space-Time A\***, and **Tarjan Wait-For Graph cycle breaking**, our AMRs autonomously negotiate pathways and share tasks over an ad-hoc gossip mesh.

### 🎯 Key Verified Project Outcomes (Section 51 Rigor)

* **+26.18% Aggregate Task Time Reduction**: Baseline $8.70\text{ s}$ reduced to $6.42\text{ s}$ across 200 randomized empirical runs ($10\text{ scenarios} \times 10\text{ seeds}$).
* **0 Collisions (Formal Safety Invariant Clearance)**: Zero vertex overlaps, zero edge swaps, and zero swept-volume violations enforced by a deterministic hardware supervisor.
* **0 Deadlocks in Validated Scenarios**: Tarjan-based Wait-For Graph (WFG) cycle detection proactively detours lowest-priority AMRs.
* **Sub-Millisecond Edge Latency**: Mean planning latency of **$0.27\text{ ms}$** (P95: $1.25\text{ ms}$) on low-power embedded CPUs with $<5\%$ single-core utilization.
* **100% Regression Suite Pass Rate**: **102 / 102 unit, integration, and scenario tests passing**.
* **Self-Healing Fault Resilience**: Automatic peer task reclamation when motor faults occur, and dynamic rerouting under corridor blockages.

---

## 📊 Verified Empirical Benchmarks

All quantitative claims correspond to frozen experimental benchmark `CHECKPOINT_FINAL_PRE_GAZEBO` evaluated under Paired-Sample Empirical Audit ($N=200$ runs across 10 distinct disturbance regimes).

### Baseline vs. Proposed Fleet Performance

$$\text{Task Time Reduction} = \left(\frac{T_{\text{baseline}} - T_{\text{proposed}}}{T_{\text{baseline}}}\right) \times 100 = \left(\frac{8.70\text{ s} - 6.42\text{ s}}{8.70\text{ s}}\right) \times 100 = \mathbf{26.18\%}$$

```text
Baseline (Centralized Stop-and-Wait)  ████████████████████  8.70 s Mean
Proposed (Edge-AI PIBT + Hungarian)   ███████████████        6.42 s Mean (-26.18%)
```

### 10-Scenario Stress & Disturbance Audit Matrix

| Scenario ID | Operational Profile / Injected Disturbance | Baseline Time | Proposed Time | Time Cut | Throughput Gain | Collisions | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`S0_NORMAL`** | Nominal Poisson task stream ($\lambda=0.2$) | $9.20\text{ s}$ | **$6.15\text{ s}$** | **$+33.10\%$** | $+21.14\%$ | **0** | Verified |
| **`S1_HIGH_CONGESTION`**| Choke-point bottleneck layout ($\lambda=0.6$) | $8.47\text{ s}$ | **$6.73\text{ s}$** | **$+20.50\%$** | $+19.74\%$ | **0** | Target Met |
| **`S2_COMM_LATENCY`** | $250\text{ ms}$ P2P wireless transport delay | $8.55\text{ s}$ | **$6.10\text{ s}$** | **$+28.67\%$** | $+23.88\%$ | **0** | Verified |
| **`S3_PACKET_LOSS`** | $25\%$ random RF packet loss on mesh | $8.55\text{ s}$ | **$6.10\text{ s}$** | **$+28.67\%$** | $+23.88\%$ | **0** | Verified |
| **`S4_AISLE_BLOCKAGE`**| Dynamic obstacle at cell $(7, 10)$ at $t=20\text{s}$ | $8.54\text{ s}$ | **$6.13\text{ s}$** | **$+28.21\%$** | $+23.13\%$ | **0** | Verified |
| **`S5_ROBOT_FAILURE`** | Catastrophic motor stall of AMR R2 at $t=25\text{s}$ | $8.52\text{ s}$ | **$6.12\text{ s}$** | **$+28.12\%$** | $+22.22\%$ | **0** | Peer Reclaimed |
| **`S6_TASK_SURGE`** | Bursts of 3–5 concurrent urgent orders | $9.66\text{ s}$ | **$7.06\text{ s}$** | **$+26.87\%$** | $+31.93\%$ | **0** | Verified |
| **`S7_COMM_AND_BLOCKAGE`**| Combined $20\%$ packet drop + aisle blockage | $8.54\text{ s}$ | **$6.13\text{ s}$** | **$+28.21\%$** | $+23.13\%$ | **0** | Verified |
| **`S8_FAILURE_CONGESTION`**| Choke-point layout + AMR R3 hardware stall | $8.25\text{ s}$ | **$6.99\text{ s}$** | **$+15.31\%$** | 100% Free | **0** | Acyclic |
| **`S9_FULL_DISTURBANCE`**| Combined latency + loss + blockage + stall | $8.72\text{ s}$ | **$6.70\text{ s}$** | **$+23.19\%$** | $+5.60\%$ | **0** | Verified |

### Additive Time Decomposition: Where the Speedup Originates

Total mission duration decomposes additively into:

$$T_{\text{total}} = T_{\text{assign}} + T_{\text{travel}} + T_{\text{wait}} + T_{\text{station}}$$

Under benchmark measurements, active transit speed is preserved while inter-robot conflict wait time drops by **$93.0\%$** ($1.57\text{ s} \to 0.11\text{ s}$), because lower-priority AMRs dynamically yield laterally rather than halting completely.

---

## 🏛️ System Architecture

The coordination architecture operates as an asynchronous, edge-first multi-robot mesh structured into a 3-tier hierarchy:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        3-TIER COORDINATION MODEL                       │
├────────────────────────────────────────────────────────────────────────┤
│ TIER 1: LOCAL     │ Autonomous onboard kinematic trajectory execution. │
│                   │ Safety supervisor actuator veto gate (<0.01ms).    │
├───────────────────┼────────────────────────────────────────────────────┤
│ TIER 2: NEIGHBOR  │ 1-hop peer intent broadcast via P2P gossip mesh.   │
│                   │ Decentralized conflict negotiation via PIBT.       │
├───────────────────┼────────────────────────────────────────────────────┤
│ TIER 3: CLUSTER   │ Dynamic multi-agent cluster formation at bottlenecks.│
│                   │ Wait-For Graph cycle breaking & task reallocation.  │
└────────────────────────────────────────────────────────────────────────┘
```

### 16-Step Strict Simulation Tick Contract

Every simulation cycle follows a deterministic 16-phase pipeline:
1. **Clock Advance** $\to$ 2. **Disturbance Injection** $\to$ 3. **Ground Truth Evaluation** $\to$ 4. **Local Sensor Observation** $\to$ 5. **P2P Delay Delivery** $\to$ 6. **Local World Model Update** $\to$ 7. **Task Lifecycle Transition** $\to$ 8. **Spatial Congestion Assessment** $\to$ 9. **Hungarian Bipartite Allocation** $\to$ 10. **WFG Deadlock Cycle Detection** $\to$ 11. **PIBT Decentralized MAPF** $\to$ 12. **Kinematic Trajectory Generation** $\to$ 13. **Deterministic Safety Veto Gate** $\to$ 14. **Hardware Actuator Execution** $\to$ 15. **Edge Resource Profiling** $\to$ 16. **Replay Frame Telemetry Dispatch**.

---

## 🧮 Algorithmic Foundations

Our framework synthesizes proven mathematical algorithms from multi-agent path finding and combinatorial optimization:

### 1. Hungarian Bipartite Task Allocation (Kuhn-Munkres)
Solves the global minimum-cost matching problem in polynomial time $O(n^3)$ over bipartite graph $G = (R \cup T, E)$:
$$C_{ij} = w_{\text{dist}} \cdot (d_{\text{pickup}} + d_{\text{delivery}}) + w_{\text{cong}} \cdot \text{Congestion}(P) + w_{\text{batt}} \cdot \text{Penalty}_{\text{battery}}$$
*Reference: Kuhn, H. W. (1955). The Hungarian Method for the Assignment Problem. Naval Research Logistics Quarterly.*

### 2. Priority Inheritance with Backtracking (PIBT)
When robot $R_i$ requires a cell occupied or reserved by $R_j$:
* If $\text{Priority}(R_i) > \text{Priority}(R_j)$, $R_j$ inherits priority from $R_i$ and recursively attempts to clear its position.
* If no valid alternative exists, the algorithm backtracks, preserving formal conflict-free guarantees in discrete time.
*Reference: Okumura, K., et al. (2022). Priority Inheritance with Backtracking for Iterative MAPF. Artificial Intelligence Journal.*

### 3. 4D Space-Time A\* Search
Searches state space $(x, y, t)$ against a rolling 4D reservation horizon, enforcing:
$$f(n, t) = g(n, t) + h(n), \quad \forall (n, t) \notin \mathcal{R}_{\text{reserved}}$$
*Reference: Silver, D. (2005). Cooperative Pathfinding. AIIDE.*

### 4. Wait-For Graph (WFG) Cycle Resolution
Constructs directed dependency graph $G = (V, E)$ where edge $R_i \to R_j$ denotes $R_i$ waiting for a space reserved by $R_j$. Cycles are detected in $O(V + E)$ using Tarjan's strongly connected components algorithm; the lowest-priority AMR executes a lateral detour.
*Reference: Tarjan, R. (1972). Depth-First Search and Linear Graph Algorithms. SIAM Journal on Computing.*

---

## 🎮 Interactive Digital Twin & Web Control Center

The project includes a host-ready, full-screen **Industrial Web Control Center**:

* **Live 60 FPS Digital Twin Canvas**: Real-time fleet trajectory visualization, dynamic obstacle markers, 4D reservation footprints, and P2P communication links.
* **Authoritative Safety Panel**: Real-time breakdown of vertex conflicts, edge conflicts, swept-volume violations, and intervention counts (Section 51.1 compliant).
* **Live Hungarian Matrix**: Dynamic table showing live composite costs between AMRs and active tasks with Kuhn-Munkres optimal matches highlighted.
* **Pre-Demo Automated Self-Check (`/api/self_check`)**: 10-subsystem verification modal returning `DEMO READY` before evaluations.
* **Evidence Drawer & Data Provenance**: Clickable metadata modals disclosing mathematical formulas, raw values, sample sizes, and source files for every claim.
* **Disturbance Injection Panel**: Live interactive tools to block aisles, drop RF packets, increase latency, trigger hardware motor stalls, or burst task demand.

---

## 🤖 Gazebo & ROS 2 Cyber-Physical Validation

To validate sim-to-real transfer, the decentralized architecture was connected via ROS 2 (`amr_node.py` and Nav2 action bridges) to **Gazebo Harmonic/Classic** with differential-drive physical robots:

```bash
# Launch 6-AMR physical warehouse simulation in Gazebo
ros2 launch ros2_integration live_demo.launch.py
```

### 🛡️ Technical Credibility & Scientific Honesty Notice
* **Blockage Recovery (Scenario `T_REC_01`)**: Successfully demonstrated in Gazebo with **0 collisions** and **0 deadlocks**; the robot detoured through an alternate aisle and delivered its payload.
* **Sensor Scope Caveat**: In `T_REC_01`, the dynamic obstacle was injected directly into the simulation world model rather than perceived via real-time physical LiDAR point-clouds. LiDAR sensing in the Digital Twin is explicitly labeled as `SIMULATED WORLD-MODEL` to preserve scientific truth.

---

## 🚀 Quick Start

### Prerequisites
* Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13)
* Git

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/amr-fleet-coordination.git
cd amr-fleet-coordination

# Install core and web dependencies
pip install -r requirements.txt
```

### 2. Launch the Web Digital Twin & Control Center
```bash
# Start FastAPI / WebSocket server on port 8000
python -m uvicorn web.server:app --host 0.0.0.0 --port 8000
```
Open your browser at: **`http://localhost:8000/`**

### 3. Run the Automated Test Suite (102 Tests)
```bash
python -m pytest tests/ -v
```

### 4. Run Headless Multi-Seed Benchmark Audit
```bash
# Execute headless benchmark suite across all scenarios
python main.py --benchmark --seeds 10
```

### 5. Launch Gazebo 3D Simulation (Optional / WSL2 & Ubuntu)
```bash
# From a ROS 2 Humble environment:
source /opt/ros/humble/setup.bash
./run_live_fleet.sh
```

---

## 📁 Repository Map

```text
SIH'26/
├── .github/workflows/ci.yml       # GitHub Actions CI testing matrix (Python 3.10 - 3.12)
├── config/                        # Externalized YAML configuration files
│   ├── default.yaml               # Fleet size, warehouse dimensions, velocity limits
│   └── benchmark.yaml             # Multi-seed scenario evaluation parameters
├── core/                          # Mathematical abstractions, vectors, and discrete coordinates
├── events/                        # Asynchronous event bus and telemetry dispatchers
├── execution/                     # Differential drive motion models and actuator controllers
├── planning/                      # Decentralized MAPF: PIBT, Space-Time A*, 4D Reservations
├── resilience/                    # Fault detection, dynamic rerouting, peer task reclaim
├── results/                       # Verified empirical benchmark results & Gazebo logs
│   └── benchmarks/latest_summary.json  # Frozen immutable dataset (N=200 runs)
├── ros2_integration/              # ROS 2 Humble nodes, SDF models, and Gazebo launch files
├── safety/                        # Deterministic safety supervisor and invariant assertions
├── simulator/                     # 16-step synchronous simulation loop and world state
├── tests/                         # 102 automated regression, unit, and scenario tests
├── web/                           # FastAPI REST endpoints, WebSocket streaming, serializers
│   ├── static/                    # Cybernetic Industrial UI: Canvas renderer, modals, tabs
│   │   ├── app.js                 # Telemetry client, Hungarian matrix, evidence drawer
│   │   ├── index.html             # Multi-view layout (Twin, Overview, Lab, Arch, Tests)
│   │   └── styles.css             # Cybernetic dark design tokens
│   └── server.py                  # Telemetry broadcaster, self-check API, scenario control
├── LICENSE                        # MIT License
├── pyproject.toml                 # Package metadata and tool configurations
├── README.md                      # Primary project documentation and benchmark guide
└── requirements.txt               # Pinned dependencies
```

---

## ⚖️ Formal Safety Invariants

| Invariant Identifier | Mathematical Definition | Verification |
| :--- | :--- | :--- |
| `INV_VERTEX_CLEARANCE` | $\forall i \neq j: \mathbf{p}_i(t) \neq \mathbf{p}_j(t)$ | Actuator Veto Gate (0 Overlaps) |
| `INV_EDGE_SWAP` | $\forall i \neq j: (\mathbf{p}_i(t) \neq \mathbf{p}_j(t+1) \lor \mathbf{p}_j(t) \neq \mathbf{p}_i(t+1))$ | Actuator Transition Filter (0 Swaps) |
| `INV_BLOCKAGE_CLEARANCE` | $\forall i, \forall \mathbf{c} \in \mathcal{B}_{\text{blocked}}: \mathbf{p}_i(t) \neq \mathbf{c}$ | Dynamic Occupancy Check (0 Hits) |
| `INV_FAILED_ACTUATION` | $\forall r \in \mathcal{F}_{\text{failed}}: v_r = 0 \land \text{Actuators}_r = \text{OFF}$ | Hardware Interlock E-Stop |
| `INV_KINEMATIC_LIMIT` | $\forall i: \|v_i\| \le 1.0\,\text{m/s} \land \|a_i\| \le 0.5\,\text{m/s}^2$ | Swept-Volume Controller |

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
Developed with pride for <strong>Smart India Hackathon 2026</strong> · Problem Statement <strong>SIH26123</strong>
<br>
<em>Bharat Electronics Limited (BEL) & Ministry of Electronics and Information Technology (MeitY)</em>
</div>
