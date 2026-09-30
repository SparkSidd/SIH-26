# Empirical Benchmark Results & Metrics Audit (SIH26123)

> **Canonical Artifact Reference**: All metrics in this document are strictly synchronized with [`results/CANONICAL_SIH_METRICS.json`](file:///c:/Users/thega/PROJECTS/SIH'26/results/CANONICAL_SIH_METRICS.json).
> Generated via reproducible suite: `python -m benchmark.generate_canonical_report`

---

## 1. Executive Summary & Canonical Verification Headline

Across a validated multi-scenario benchmark comprising **100 paired experiments** (**200 total system executions**: 10 scenarios $\times$ 10 paired random seeds $\times$ 2 complete systems):

- **Collision Safety**: **0 inter-robot collisions observed across all 200 benchmark executions** under deterministic runtime safety supervision.
- **Task Completion Time**:
  - Baseline Mean: **8.70 s** (Stop-and-Wait + Greedy Nearest Allocation)
  - Proposed Mean: **6.42 s** (Decentralized Hungarian Fleet-Aware + PIBT + Space-Time A*)
  - Aggregate Reduction: **26.18%**
  - Mean Per-Seed Reduction: **24.24%** (Median: **23.79%**, Std: **13.56%**)
  - 95% Confidence Interval: $[21.58\%, 26.90\%]$
  - Peak Scenario Reduction ($S_0$): **33.10%**
  - Minimum Scenario Reduction ($S_8$): **15.31%**
- **SIH Performance Target Evaluation ($\ge 20\%$)**:
  - **Overall Status**: **PASS (26.18% Aggregate Reduction Exceeds SIH Goal)**.
- **Planner Latency Taxonomy (Single-Core Edge Profile)**:
  - Mean Planner Latency: **0.27 ms**
  - P95 Planner Latency: **1.25 ms**
  - Maximum Planner Latency: **4.10 ms**
  - *Measurement Scope*: Algorithmic decision loop (PIBT step + Space-Time A* reservation query) running on a single CPU thread (<5% core load).
- **Process Memory Taxonomy**:
  - Core Planner & Coordination Runtime: **54.0 MB** (measured isolated memory footprint)
  - Complete Digital Twin Process: **238.7 MB** (FastAPI backend + WebSocket buffers + in-memory state tracking)
  - Peak Total Process Memory: **240.7 MB**
- **Simulated Communication Profile**:
  - P2P Gossip Mesh Transfer: **18,562.4 bytes/sec** (Baseline: 18,564.6 bytes/sec)
  - Measured Bandwidth Difference: **0.01%**
  - *Clarification on Historical 93% Claim*: The legacy 93% figure was an unmeasured architectural back-of-the-envelope comparison to continuous central telemetry streaming. Real simulated mesh bandwidth difference is 0.01% with 0 central server dependency.
- **Automated Test Validation**:
  - **116 / 116 tests passing** (100% pass rate in `tests/test_audit_hardening.py` and suite).

---

## 2. Complete Scenario-by-Scenario Benchmark Summary (10 Seeds Paired)

Every scenario was evaluated across the identical set of 10 pseudorandom seeds: `[42, 101, 202, 303, 404, 505, 606, 707, 808, 909]`.

| Scenario ID | Scenario Name & Disturbance Profile | Baseline Mean (s) | Proposed Mean (s) | Time Reduction (%) | Derived Throughput Gain (%) | Collisions Observed | Deadlocks Observed | SIH Target ($\ge 20\%$) |
|---|---|---|---|---|---|---|---|---|
| **S0_NORMAL** | Nominal Poisson task stream ($\lambda=0.2$) | 9.20 | 6.15 | **33.10%** | +21.14% | 0 | 0 | **PASS** |
| **S1_HIGH_CONGESTION** | Choke-point bottleneck layout ($\lambda=0.6$) | 8.47 | 6.73 | **20.50%** | +19.74% | 0 | 0 | **PASS** |
| **S2_COMM_LATENCY** | 250 ms simulated P2P wireless transport delay | 8.55 | 6.10 | **28.67%** | +23.88% | 0 | 0 | **PASS** |
| **S3_PACKET_LOSS** | 25% random RF packet drop + dead-reckoning hold | 8.55 | 6.10 | **28.67%** | +23.88% | 0 | 0 | **PASS** |
| **S4_AISLE_BLOCKAGE** | Dynamic aisle blockage at cell (7, 10) at $t=20$ s | 8.54 | 6.13 | **28.21%** | +23.13% | 0 | 0 | **PASS** |
| **S5_ROBOT_FAILURE** | AMR_02 motor failure at $t=25$ s with peer mission reclaim | 8.52 | 6.12 | **28.12%** | +22.22% | 0 | 0 | **PASS** |
| **S6_TASK_SURGE** | Sudden arrival burst of 3–5 concurrent urgent tasks | 9.66 | 7.06 | **26.87%** | +31.93% | 0 | 0 | **PASS** |
| **S7_COMM_AND_BLOCKAGE** | Combined 20% packet drop + corridor obstacle | 8.54 | 6.13 | **28.21%** | +23.13% | 0 | 0 | **PASS** |
| **S8_FAILURE_AND_CONGESTION** | Choke-point bottleneck + AMR hardware stall | 8.25 | 6.99 | **15.31%** | -3.40% | 0 | 0 | Sub-Target* |
| **S9_FULL_COMBINED** | Multi-disturbance matrix (latency + loss + blockage + stall) | 8.72 | 6.70 | **23.19%** | +5.60% | 0 | 0 | **PASS** |
| **OVERALL AGGREGATE** | **100 Paired Experiments (200 Executions)** | **8.70** | **6.42** | **26.18%** | **+18.12%** | **0** | **0** | **PASS** |

*\*Note on $S_8$*: In extreme compound failure scenarios within a physical choke point, the surviving robots must yield and reroute around the stalled agent through single-width alternate aisles. Even under this severe physical constraint, the proposed coordination achieves a 15.31% reduction over the baseline without deadlock.

---

## 3. Plan vs. Execution Metrics

Borrowing rigorous experimental methodologies from multi-robot execution analysis, we separate discrete planned path properties from continuous executed trajectories:

| Metric Dimension | Planned Model | Actual Executed | Efficiency / Overhead | Explanatory Rationale |
|---|---|---|---|---|
| **Mean Path Length** | 18.4 cells | 19.8 cells | **92.9% path efficiency** | 1.4 cell divergence due to dynamic yield steps and local detour nudges |
| **Mean Makespan** | 6.12 s | 6.42 s | **95.3% temporal efficiency** | 0.30 s overhead from transient deceleration and priority yield states |
| **Conflict Waiting Steps** | 0.0 steps (nominal) | 1.1 steps | — | Temporary cooperative yield delays while clearing high-priority peers |
| **Safety Interventions** | 0 | 0 | **100% nominal safety** | Runtime Safety Supervisor verified all reservations; 0 emergency stops needed |
| **Task Reclaims** | 0 | 10 (across $S_5, S_8$) | **100% reclaim success** | Orphaned tasks from stalled AMRs reclaimed via distributed epoch bump |

---

## 4. Resilience & Fault Recovery Audit

Across all 40 fault-injection experiments ($S_4, S_5, S_7, S_8$ across 10 random seeds):
- **Recovery Success Rate**: **40 / 40 tested scenarios recovered successfully (100%)** without unhandled deadlocks.
- **Heartbeat Timeout Detection Latency**: 3 missed gossip cycles ($1.5\text{ s}$).
- **Mean Task Reassignment Latency**: $0.45\text{ s}$ via distributed Claim/ACK/Commit epoch bump.
- **Dynamic Obstacle Detour Overhead**: $4.2\text{ steps}$ average detour around blocked aisles ($S_4, S_7$).
- **Payload Loss**: $0$ tasks dropped or double-executed.

---

## 5. System Ablation Studies

To verify that each algorithmic subsystem contributes meaningfully to the overall performance, controlled ablations were conducted on the benchmark:

| Ablation Configuration | Changes Applied | Completion Time (s) | Relative Delta | Collision Rate | Mechanistic Finding |
|---|---|---|---|---|---|
| **Full Proposed System** | All modules active | **6.42 s** | **Reference (0%)** | **0** | Full integration of Hungarian + PIBT + Space-Time A* + Reservations |
| **Without Congestion Penalty** | Static Manhattan distance routing | 7.15 s | **+11.37% slower** | 0 | AMRs crowd primary arterial aisles; higher wait times at intersections |
| **Without Adaptive Coordination** | Fixed low-priority local yielding | 7.38 s | **+14.95% slower** | 0 | Fails to proactively yield to AMRs carrying urgent surge payloads |
| **Without Claim/ACK Protocol** | Greedy immediate ownership | 6.82 s | **+6.23% slower** | 0 | Reassignment races during packet loss cause transient duplicate claims |
| **Without Fault Reclaim Engine** | Disabled peer heartbeat reclaim | $\infty$ ($S_5, S_8$ fail) | **Failure** | 0 | Stalled AMR task remains orphaned indefinitely |

---

## 6. Scalability Analysis (Stress Benchmark)

Evaluated under increasing AMR density on the $30 \times 20$ warehouse topology:

| Fleet Size (AMRs) | Mean Planning Latency (ms) | P95 Planning Latency (ms) | Inter-Robot Collisions | Deadlock Rate | Memory Footprint (MB) |
|---|---|---|---|---|---|
| **6 AMRs (Canonical)** | 0.27 ms | 1.25 ms | 0 | 0% | 54.0 MB |
| **10 AMRs** | 0.42 ms | 1.88 ms | 0 | 0% | 57.2 MB |
| **20 AMRs** | 1.15 ms | 4.20 ms | 0 | 0% | 66.8 MB |
| **40 AMRs** | 3.80 ms | 12.40 ms | 0 | 0% | 88.5 MB |
| **50 AMRs (Stress)** | 6.90 ms | 21.50 ms | 0 | 0.2% (transient) | 104.2 MB |

*Conclusion*: The decentralized coordination core scales gracefully, maintaining sub-5 ms average planning latency up to 40 AMRs on a standard CPU thread.

---

## 7. Provenance & Reproducibility

To re-run and verify the canonical metrics from source:
```bash
# 1. Run the canonical benchmark suite & generate artifacts
python -m benchmark.generate_canonical_report

# 2. Run the automated test suite (116 tests)
pytest -q
```
*Generated Artifacts*:
- `results/CANONICAL_SIH_METRICS.json`
- `results/canonical/canonical_metrics.csv`
- `results/canonical/scenario_metrics.csv`
- `results/canonical/benchmark_summary.md`
- `results/test_manifest.json`
