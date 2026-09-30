# Canonical Verified Benchmark Report: SIH26123

**Dataset Checkpoint**: `CANONICAL_VERIFIED_CHECKPOINT`  
**Git Commit SHA**: `572659382f62619a28776b0e080841b0e544ff81`  
**Generated At**: `2026-09-30T23:21:23.227549+00:00`  
**Evaluation Scope**: 100 Paired Experiments (10 Scenarios × 10 Deterministic Seeds) = **200 Total Simulation Executions**  

---

## 1. Headline Empirical Results

| Metric | Baseline (Stop-and-Wait) | Proposed (Decentralized Fleet) | Improvement / Result | Target / Status |
| :--- | :--- | :--- | :--- | :--- |
| **Mean Task Completion Time** | **8.70 s** | **6.42 s** | **+26.18% Time Cut** | Target $\ge 20\%$ (**PASS**) |
| **Inter-Robot Collisions** | 0 | **0** | **0 Collisions Observed** | Safety Invariant Enforced |
| **Deadlock Events** | 0 | **0** | **0 Deadlocks Observed** | Tarjan WFG Cycle Breaking |
| **Edge Decision Latency** | — | Mean: **0.27 ms**, P95: **1.25 ms** | Sub-2ms Tail Planning | Real-Time 50 Hz Feasible |
| **Memory Footprint** | — | Core: **54.0 MB** / Twin: **238.7 MB** | Embedded-ready (<512 MB) | Lightweight Edge Profile |
| **Regression Test Suite** | — | **116/116 PASS (100%)** | 100% Pass Rate | Zero Regressions |

$$\text{Aggregate Reduction} = \left(\frac{8.70\text{ s} - 6.42\text{ s}}{8.70\text{ s}}\right) \times 100 = \mathbf{26.18\%}$$

---

## 2. 10-Scenario Breakdown Matrix

| Scenario ID | Operational Disturbance Profile | Baseline Time | Proposed Time | Time Cut | Throughput Gain (Derived) | Collisions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `S0_NORMAL` | Nominal Warehouse Poisson Stream | 9.20 s | **6.15 s** | **+33.10%** | +21.14% | **0** |
| `S1_HIGH_CONGESTION` | Choke-Point Bottleneck | 8.47 s | **6.73 s** | **+20.50%** | +19.74% | **0** |
| `S2_COMM_LATENCY` | 250ms Wireless Transport Latency | 8.55 s | **6.10 s** | **+28.67%** | +23.88% | **0** |
| `S3_PACKET_LOSS` | 25% Random Mesh Packet Drop | 8.55 s | **6.10 s** | **+28.67%** | +23.88% | **0** |
| `S4_AISLE_BLOCKAGE` | Dynamic Obstacle / Aisle Blockage | 8.54 s | **6.13 s** | **+28.21%** | +23.13% | **0** |
| `S5_ROBOT_FAILURE` | Robot Motor Failure & Peer Reclaim | 8.52 s | **6.12 s** | **+28.12%** | +22.22% | **0** |
| `S6_TASK_SURGE` | Burst Task Generation Surge | 9.66 s | **7.06 s** | **+26.87%** | +31.93% | **0** |
| `S7_COMM_AND_BLOCKAGE` | Packet Loss + Corridor Blockage | 8.54 s | **6.13 s** | **+28.21%** | +23.13% | **0** |
| `S8_FAILURE_AND_CONGESTION` | Choke-Point + Robot Hardware Stall | 8.25 s | **6.99 s** | **+15.31%** | +-3.40% | **0** |
| `S9_FULL_COMBINED_DISTURBANCE` | Full Multi-Disturbance Matrix | 8.72 s | **6.70 s** | **+23.19%** | +5.60% | **0** |

---

## 3. Scientific Defensibility & Terminology Guidelines

1. **Safety**: State *"0 inter-robot collisions observed across 200 benchmark executions under deterministic safety supervision"*. Do not claim mathematical formal proof without Coq/Isabelle mechanical proofs.
2. **Latency**: State *"Mean planning latency: 0.27 ms; P95: 1.25 ms"*. Do not claim unconditional sub-millisecond P95 because P95 is 1.25 ms.
3. **Bandwidth**: The measured simulated P2P transmission difference is 0.01%. Do NOT claim a 93% benchmark reduction.
4. **Planning Dimension**: The state space is $(x, y, t)$ across discrete reservation intervals. Terminology is **Space-Time A\***.
5. **Allocation Optimality**: The Hungarian allocator achieves **minimum-cost bipartite assignment under the defined fleet cost model** (distance + congestion + battery).
