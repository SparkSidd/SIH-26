# Decentralized AMR Fleet Coordination for Smart Warehouses

<div align="center">

[![SIH 2026](https://img.shields.io/badge/SIH%202026-Problem%20SIH26123-blue.svg?style=for-the-badge&logo=target)](https://sih.gov.in)
[![Organization](https://img.shields.io/badge/BEL-Bharat%20Electronics%20Limited-orange.svg?style=for-the-badge)](https://bel-india.in)
[![Tests](https://img.shields.io/badge/Tests-121%2F121%20PASS%20(100%25)-emerald.svg?style=for-the-badge&logo=checkmarx)](results/test_manifest.json)
[![Safety Invariants](https://img.shields.io/badge/Collisions-0%20(VERIFIED)-brightgreen.svg?style=for-the-badge&logo=shield)](results/CANONICAL_SIH_METRICS.json)
[![Time Reduction](https://img.shields.io/badge/Task%20Time%20Cut-%2B24.89%25-cyan.svg?style=for-the-badge&logo=speedtest)](results/CANONICAL_SIH_METRICS.json)
[![License](https://img.shields.io/badge/License-MIT-purple.svg?style=for-the-badge)](LICENSE)

**A safety-first, edge-oriented multi-robot coordination system for industrial smart warehouses.**  
*Bipartite Hungarian Task Allocation · Distributed Claim/ACK/Commit · Peer-to-Peer PIBT Negotiation · Space-Time A\* Search · Wait-For Graph Deadlock Recovery · Deterministic Safety Supervision*

[Interactive Digital Twin](#-interactive-digital-twin--web-control-center) • [Canonical Verified Results](#-canonical-verified-results) • [System Architecture](#-system-architecture) • [Algorithmic Foundations](#-algorithmic-foundations) • [Robotics Simulation Validation](#-robotics-simulation-validation-gazebo--webots) • [Quick Start](#-quick-start)

</div>

---

## 📌 Problem Context & Executive Summary

In high-throughput smart warehouses, central dispatchers suffer from catastrophic bottlenecks when wireless latency fluctuates or robot counts scale. A single wireless drop can stall operations, and naive stop-and-wait conflict policies lead to cascading corridor deadlocks.

**SIH26123** introduces a fully decentralized, edge-native fleet coordination framework that eliminates single points of failure. By synthesizing **bipartite Hungarian matching**, an explicit **distributed Claim/ACK/Commit task ownership layer**, **Priority Inheritance with Backtracking (PIBT)**, **Space-Time A\***, and **Tarjan Wait-For Graph cycle breaking**, our AMRs autonomously negotiate pathways and share tasks over an ad-hoc gossip mesh.

### 🎯 Key Verified Outcomes (Canonical Benchmark)

*Canonical benchmark generated from 100 paired experiments / 200 total executions.* Traceable via: [Raw Runs (`results/canonical/raw_runs.jsonl`)](results/canonical/raw_runs.jsonl) • [Benchmark Manifest (`results/canonical/benchmark_manifest.json`)](results/canonical/benchmark_manifest.json) • [Canonical JSON (`results/CANONICAL_SIH_METRICS.json`)](results/CANONICAL_SIH_METRICS.json) • [Test Manifest (`results/test_manifest.json`)](results/test_manifest.json).

* **+24.89% Aggregate Task Time Reduction**: Baseline mean $8.80\text{ s}$ reduced to $6.61\text{ s}$ across **100 paired experiments** (**200 total system executions**: $10\text{ scenarios} \times 10\text{ paired seeds} \times 2\text{ systems}$).
* **0 Inter-Robot Collisions Observed**: Zero vertex overlaps, zero edge swaps, and zero blocked-cell violations observed across all 100 proposed runs under deterministic runtime safety supervision. Baseline experienced 355 collisions when encountering dynamic obstacles without rerouting.
* **0 Deadlocks in Validated Scenarios**: Tarjan-based Wait-For Graph (WFG) cycle detection proactively detours lowest-priority AMRs.
* **Predictable Edge Execution Latency**: Mean algorithmic planning latency of **$2.17\text{ ms}$** (P95: **$1.23\text{ ms}$**) across >35,000 live decision loop samples on single-core CPU execution.
* **100% Automated Test Suite Pass Rate**: **121 / 121 unit, integration, benchmark integrity, and safety tests passing** (`python -m pytest -q`).
* **Self-Healing Fault Resilience**: 40/40 (100.0%) recovery rate across hardware stalls, dynamic aisle blockages, and packet-loss disruptions.
* **Multi-Simulator Verification**: Validated across an interactive Digital Twin and two independent ROS 2-based robotics simulation platforms (Gazebo Harmonic and Webots R2023b).

---

## 📊 Canonical Verified Results

All quantitative claims are strictly synchronized with the canonical machine-readable benchmark artifact: [`results/CANONICAL_SIH_METRICS.json`](results/CANONICAL_SIH_METRICS.json).

### Baseline vs. Proposed Fleet Performance

$$\text{Task Time Reduction} = \left(\frac{T_{\text{baseline}} - T_{\text{proposed}}}{T_{\text{baseline}}}\right) \times 100 = \left(\frac{8.80\text{ s} - 6.61\text{ s}}{8.80\text{ s}}\right) \times 100 = \mathbf{24.89\%}$$

```text
Baseline (Stop-and-Wait + Nearest)   ████████████████████  8.80 s Mean
Proposed (Fleet-Aware + PIBT + A*)   ███████████████        6.61 s Mean (-24.89%)
```

### 10-Scenario Stress & Disturbance Audit Matrix

Every scenario was evaluated across the identical set of 10 pseudorandom seeds: `[42, 101, 202, 303, 404, 505, 606, 707, 808, 909]`.

| Scenario ID | Operational Profile / Injected Disturbance | Baseline Time | Proposed Time | Time Cut | Throughput Gain | Collisions | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`S0_NORMAL`** | Nominal Poisson task stream ($\lambda=0.2$) | $9.17\text{ s}$ | **$6.36\text{ s}$** | **$+30.64\%$** | $+20.33\%$ | **0** | Verified |
| **`S1_HIGH_CONGESTION`**| Choke-point bottleneck layout ($\lambda=0.6$) | $8.27\text{ s}$ | **$6.71\text{ s}$** | **$+18.86\%$** | $+11.24\%$ | **0** | Verified |
| **`S2_COMM_LATENCY`** | $250\text{ ms}$ P2P wireless transport delay | $8.73\text{ s}$ | **$6.36\text{ s}$** | **$+27.15\%$** | $+25.38\%$ | **0** | Verified |
| **`S3_PACKET_LOSS`** | $25\%$ random RF packet loss on mesh | $8.88\text{ s}$ | **$6.36\text{ s}$** | **$+28.38\%$** | $+20.87\%$ | **0** | Verified |
| **`S4_AISLE_BLOCKAGE`**| Dynamic obstacle at cell $(7, 10)$ at $t=20\text{s}$ | $8.50\text{ s}$ | **$6.44\text{ s}$** | **$+24.24\%$** | $+25.38\%$ | **0** | Detour Verified |
| **`S5_ROBOT_FAILURE`** | Catastrophic motor stall of AMR R2 at $t=25\text{s}$ | $9.04\text{ s}$ | **$6.47\text{ s}$** | **$+28.43\%$** | $+13.70\%$ | **0** | Peer Reclaimed |
| **`S6_TASK_SURGE`** | Bursts of 3–5 concurrent urgent orders | $9.91\text{ s}$ | **$7.55\text{ s}$** | **$+23.81\%$** | $+27.63\%$ | **0** | Verified |
| **`S7_COMM_AND_BLOCKAGE`**| Combined $20\%$ packet drop + aisle blockage | $8.72\text{ s}$ | **$6.36\text{ s}$** | **$+27.06\%$** | $+20.01\%$ | **0** | Verified |
| **`S8_FAILURE_CONGESTION`**| Choke-point layout + AMR R3 hardware stall | $8.10\text{ s}$ | **$6.60\text{ s}$** | **$+18.52\%$** | $+6.34\%$ | **0** | Acyclic |
| **`S9_FULL_DISTURBANCE`**| Combined latency + loss + blockage + stall | $8.71\text{ s}$ | **$6.88\text{ s}$** | **$+21.01\%$** | $+3.45\%$ | **0** | Resilient |
| **OVERALL AGGREGATE** | **100 Paired Experiments (200 Executions)** | **$8.80\text{ s}$** | **$6.61\text{ s}$** | **$+24.89\%$** | **$+17.43\%$** | **0** | **PASS** |

### Plan vs. Execution Telemetry

| Metric Dimension | Planned Model | Actual Executed | Efficiency / Overhead | Explanatory Rationale |
|---|---|---|---|---|
| **Mean Path Length** | 27.3 cells | 29.0 cells | **94.1% path efficiency** | 1.7 cell divergence due to dynamic yield steps and local detour nudges |
| **Mean Makespan** | 5.52 s | 6.61 s | **83.5% temporal efficiency** | Overhead from transient deceleration, mesh delay, and priority yield states |
| **Conflict Waiting Steps** | 0.0 steps (nominal) | 1.1 steps | — | Temporary cooperative yield delays while clearing high-priority peers |
| **Safety Interventions** | 0 | 0 | **100% nominal safety** | Runtime Safety Supervisor verified all reservations; 0 emergency stops needed |

---

## 🏛️ System Architecture

The coordination architecture operates as an asynchronous, edge-first multi-robot mesh structured into a 3-tier hierarchy:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        3-TIER COORDINATION MODEL                       │
├────────────────────────────────────────────────────────────────────────┤
│ TIER 1: LOCAL     │ Autonomous onboard kinematic trajectory execution. │
│                   │ Deterministic safety supervisor veto gate.         │
├───────────────────┼────────────────────────────────────────────────────┤
│ TIER 2: NEIGHBOR  │ 1-hop peer intent broadcast via P2P gossip mesh.   │
│                   │ Decentralized conflict negotiation via PIBT.       │
├───────────────────┼────────────────────────────────────────────────────┤
│ TIER 3: CLUSTER   │ Dynamic multi-agent cluster formation at bottlenecks.│
│                   │ Wait-For Graph cycle breaking & task reallocation.  │
└────────────────────────────────────────────────────────────────────────┘
```

### End-to-End Decision Flow

```
TASK SOURCE ──► FLEET ALLOCATION ──► CLAIM/ACK/COMMIT ──► LOCAL WORLD MODEL
                     │                     │
                     ▼                     ▼
              CONGESTION INDEX ──► EVENT REPLANNER ──► PIBT & SPACE-TIME A*
                                                            │
                                                            ▼
                                                   RESERVATION TABLE
                                                            │
                                                            ▼
                                                    SAFETY SUPERVISOR ──► EXECUTION
```

### Core Architecture Enhancements
1. **Distributed Task Claim / ACK / Commit**: Enforces versioned task ownership epochs to reject stale messages and prevent duplicate payload deliveries.
2. **Time-Indexed Reservation Timeline**: Temporal cell reservation tracking with automated expired pruning and dynamic obstacle invalidation.
3. **Event-Driven Replanning Triggers**: 11 discrete trigger types (`TASK_COMPLETION`, `DYNAMIC_BLOCKAGE`, `ROBOT_FAILURE`, `DEADLOCK_DETECTED`, etc.) with hash-based cooldown backoff to suppress reroute spam.
4. **Authoritative Safety Supervisor**: Non-bypassable runtime verification gate enforcing zero vertex conflicts, zero edge swaps, and zero boundary violations.

---

## 🧮 Algorithmic Foundations

Our framework synthesizes proven mathematical algorithms from multi-agent path finding and combinatorial optimization:

### 1. Hungarian Bipartite Task Allocation (Kuhn-Munkres)
Solves the minimum-cost matching problem in polynomial time $\mathcal{O}(N^3)$ over bipartite graph $G = (R \cup T, E)$ under our defined fleet cost model:
$$C_{ij} = w_{\text{dist}} \cdot (d_{\text{pickup}} + d_{\text{delivery}}) + w_{\text{turn}} \cdot N_{\text{turns}} + w_{\text{cong}} \cdot \text{Congestion}(P) + w_{\text{bal}} \cdot \text{Imbalance}$$
*Reference: Kuhn, H. W. (1955). The Hungarian Method for the Assignment Problem. Naval Research Logistics Quarterly.*

### 2. Priority Inheritance with Backtracking (PIBT)
When robot $R_i$ requires a cell occupied or reserved by $R_j$:
* If $\text{Priority}(R_i) > \text{Priority}(R_j)$, $R_j$ inherits priority from $R_i$ and recursively attempts to clear its position.
* If no valid alternative exists, the algorithm backtracks, preserving collision avoidance in discrete time.
*Reference: Okumura, K., et al. (2022). Priority Inheritance with Backtracking for Iterative MAPF. Artificial Intelligence Journal.*

### 3. Space-Time A\* Search
Searches state space $(x, y, t)$ against a rolling reservation horizon, enforcing:
$$f(n, t) = g(n, t) + h(n), \quad \forall (n, t) \notin \mathcal{R}_{\text{reserved}}$$
*Reference: Silver, D. (2005). Cooperative Pathfinding. AIIDE.*

### 4. Wait-For Graph (WFG) Cycle Resolution
Constructs directed dependency graph $G = (V, E)$ where edge $R_i \to R_j$ denotes $R_i$ waiting for a space reserved by $R_j$. Cycles are detected in $\mathcal{O}(V + E)$ using Tarjan's strongly connected components algorithm; the lowest-priority AMR executes a lateral detour.
*Reference: Tarjan, R. (1972). Depth-First Search and Linear Graph Algorithms. SIAM Journal on Computing.*

---

## 🎮 Interactive Digital Twin & Web Control Center

The project includes a host-ready, full-screen **Industrial Web Control Center**:

* **Live 60 FPS Digital Twin Canvas**: Real-time fleet trajectory visualization, dynamic obstacle markers, Space-Time reservation footprints, and P2P communication links.
* **Authoritative Safety Panel**: Real-time breakdown of vertex conflicts, edge conflicts, and safety interventions.
* **Live Hungarian Matrix**: Dynamic table showing live composite costs between AMRs and active tasks with Kuhn-Munkres optimal matches highlighted.
* **Pre-Demo Automated Self-Check (`/api/self_check`)**: 10-subsystem verification modal dynamically loading canonical benchmark truth before evaluations.
* **Evidence Drawer & Data Provenance**: Clickable metadata modals disclosing mathematical formulas, raw values, sample sizes, and source files for every claim.
* **Disturbance Injection Panel**: Live interactive tools to block aisles, drop RF packets, increase latency, trigger hardware motor stalls, or burst task demand.

---

## 🤖 Robotics Simulation Validation (Gazebo & Webots)

The coordination stack has been validated across an interactive Digital Twin and two independent ROS 2-based robotics simulation environments:

1. **Interactive Digital Twin**: High-throughput multi-scenario verification and interactive disturbance testing.
2. **Gazebo Harmonic + ROS 2 Jazzy**: Continuous-time physics, realistic wheel slip, sensor noise, and ROS 2 navigation action bridges.
3. **Webots R2023b + ROS 2 Jazzy**: Independent secondary simulator validation confirming cross-simulator consistency across 2, 4, and 6 AMR configurations.

```bash
# Launch 6-AMR physical warehouse simulation in Gazebo
ros2 launch ros2_integration live_demo.launch.py
```

### 🛡️ Technical Credibility & Scientific Honesty Notice
* **Simulation Scope**: Physical hardware validation on real warehouse floors remains a next-stage development milestone. All reported metrics reflect rigorous robotics simulation validation.
* **Sensor Scope**: Dynamic obstacles injected during benchmark scenarios are evaluated against simulated perception models.

---

## 🚀 Quick Start

### Prerequisites
* Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13)
* Git

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/SparkSidd/SIH-26.git
cd SIH-26

# Install core and web dependencies
pip install -r requirements.txt
```

### 2. Launch the Web Digital Twin & Control Center
```bash
# Start FastAPI / WebSocket server on port 8080
python -m uvicorn web.server:app --host 0.0.0.0 --port 8080
```
Open your browser at: **`http://localhost:8080/`**

### 3. Run the Automated Test Suite (116 Tests)
```bash
python -m pytest tests/ -q
```

### 4. Run Canonical Benchmark Suite & Reproduce Metrics
```bash
# Execute canonical benchmark suite across all scenarios
python -m benchmark.generate_canonical_report
```

---

## 📁 Repository Map

```text
SIH'26/
├── .github/workflows/ci.yml       # GitHub Actions CI testing matrix
├── config/                        # Externalized YAML configuration files
│   ├── default.yaml               # Fleet size, warehouse dimensions, velocity limits
│   └── benchmark.yaml             # Multi-seed scenario evaluation parameters
├── coordination/                  # PIBT, Hungarian allocator, distributed task ownership
│   └── task_ownership.py          # Claim / ACK / Commit lifecycle protocol
├── core/                          # Mathematical abstractions, vectors, and discrete coordinates
├── docs/                          # Verified architectural and benchmark reports
│   ├── ARCHITECTURE.md            # Comprehensive system architecture & pipeline
│   ├── BENCHMARK_METHODOLOGY.md   # Reproducible benchmark protocols & equations
│   ├── DESIGN_INSPIRATIONS.md     # Attribution of design patterns (ACE, MRWS, etc.)
│   ├── ENGINEERING_OPTIMIZATION_REPORT.md # Engineering optimization report
│   ├── JUDGE_QA.md                # 20-question technical defense for judges
│   ├── REPOSITORY_AUDIT.md        # Pre-edit repository audit matrix
│   └── RESULTS.md                 # Empirical benchmark results & metrics audit
├── events/                        # Asynchronous event bus and telemetry dispatchers
├── execution/                     # Differential drive motion models and actuator controllers
├── metrics/                       # Telemetry, plan-vs-execution metrics, battery tracking
├── planning/                      # Decentralized MAPF: PIBT, Space-Time A*, Event Replanning
│   ├── reservation.py             # Time-indexed Space-Time reservation timeline
│   └── replanning.py              # EventDrivenReplanner with 11 discrete triggers
├── resilience/                    # Fault detection, dynamic rerouting, peer task reclaim
├── results/                       # Canonical benchmark artifacts
│   ├── CANONICAL_SIH_METRICS.json # Single canonical source of numerical truth
│   ├── test_manifest.json         # Automated test suite manifest (116 tests)
│   └── canonical/                 # CSV, JSON, and Markdown summaries
├── ros2_integration/              # ROS 2 nodes, SDF models, and Gazebo launch files
├── safety/                        # Deterministic safety supervisor and invariant assertions
├── simulator/                     # 16-step synchronous simulation loop and world state
├── tests/                         # 116 automated regression, unit, and scenario tests
│   └── test_audit_hardening.py    # Unit & integration tests for audit features
├── web/                           # FastAPI REST endpoints, WebSocket streaming, serializers
│   ├── static/                    # Cybernetic Industrial UI: Canvas renderer, modals, tabs
│   └── server.py                  # Dynamic canonical data endpoints, self-check API
├── LICENSE                        # MIT License
├── pyproject.toml                 # Package metadata and tool configurations
├── README.md                      # Primary project documentation and benchmark guide
└── requirements.txt               # Pinned dependencies
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
Developed with pride for <strong>Smart India Hackathon 2026</strong> · Problem Statement <strong>SIH26123</strong>
<br>
<em>Bharat Electronics Limited (BEL) & Ministry of Electronics and Information Technology (MeitY)</em>
</div>
