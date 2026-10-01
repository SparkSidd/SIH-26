# Canonical SIH26123 Fleet Benchmark Summary

**Generated At**: 2026-09-30T23:51:42.808233+00:00  
**Source Commit**: `a2b975aff65fc985dc91791936a76f1ec377603b`  
**Experiment Design**: 100 Paired Experiments (200 Total System Executions)  
**Verification Standard**: 10 Scenarios $\times$ 10 Paired Seeds across Baseline (Stop-and-Wait) and Proposed (Decentralized Fleet System)

---

## 1. Verified Headline Outcomes

| Metric Dimension | Baseline | Proposed System | Canonical Result | Verification Status |
|---|---|---|---|---|
| **Mean Task Completion Time** | **8.8 s** | **6.61 s** | **+24.89% reduction** | **PASS (Target $\ge 20\%$ Exceeded)** |
| **Inter-Robot Collisions** | 0 | **0** | **0 collisions observed** | **VERIFIED (Runtime Invariants)** |
| **Inter-Robot Deadlocks** | 0 | **0** | **0 deadlocks observed** | **VERIFIED (WFG Cycle Breaking)** |
| **Edge Decision Latency** | — | Mean: **2.17 ms**, P95: **1.23 ms** | Single-core CPU profile | **VERIFIED (<5% core load)** |
| **Process Memory Footprint** | — | Core: **54.0 MB**, Digital Twin: **238.7 MB** | Process measurement taxonomy | **VERIFIED** |
| **Automated Test Suite** | — | **121/121 PASS (100%)** | Automated pytest execution | **100% PASS** |

---

## 2. Complete 10-Scenario Breakdown

| Scenario ID | Name & Disturbance | Baseline Time | Proposed Time | Time Cut | Throughput Gain | Collisions |
|---|---|---|---|---|---|---|
| `S0_NORMAL` | Nominal Warehouse Poisson Stream | 9.17 s | **6.36 s** | **+30.64%** | +20.33% | **0** |
| `S1_HIGH_CONGESTION` | Choke-Point Bottleneck | 8.27 s | **6.71 s** | **+18.86%** | +11.24% | **0** |
| `S2_COMM_LATENCY` | 250ms Wireless Transport Latency | 8.73 s | **6.36 s** | **+27.15%** | +25.38% | **0** |
| `S3_PACKET_LOSS` | 25% Random Mesh Packet Drop | 8.88 s | **6.36 s** | **+28.38%** | +20.87% | **0** |
| `S4_AISLE_BLOCKAGE` | Dynamic Obstacle / Aisle Blockage | 8.5 s | **6.44 s** | **+24.24%** | +25.38% | **0** |
| `S5_ROBOT_FAILURE` | Robot Motor Failure & Peer Reclaim | 9.04 s | **6.47 s** | **+28.43%** | +13.7% | **0** |
| `S6_TASK_SURGE` | Burst Task Generation Surge | 9.91 s | **7.55 s** | **+23.81%** | +27.63% | **0** |
| `S7_COMM_AND_BLOCKAGE` | Packet Loss + Corridor Blockage | 8.72 s | **6.36 s** | **+27.06%** | +20.01% | **0** |
| `S8_FAILURE_AND_CONGESTION` | Choke-Point + Robot Hardware Stall | 8.1 s | **6.6 s** | **+18.52%** | +6.34% | **0** |
| `S9_FULL_COMBINED_DISTURBANCE` | Full Multi-Disturbance Matrix | 8.71 s | **6.88 s** | **+21.01%** | +3.45% | **0** |

---

## 3. Scientific Honesty & Traceability Notice
1. **Safety**: State *"0 inter-robot collisions observed across 200 benchmark executions under deterministic safety supervision"*. Do not claim mathematical formal proof without Coq/Isabelle mechanical proofs.
2. **Planning State Space**: State *"Space-Time A* searching (x, y, t)"*. Do not use misleading 4D marketing jargon.
3. **Bandwidth**: The measured simulated P2P transmission difference is -0.56%. Do NOT claim a 93% benchmark reduction.
4. **Physical Deployment**: Clarify that validation was performed across the interactive Digital Twin and two independent ROS 2-based robotics simulation platforms (Gazebo Harmonic and Webots R2023b).
5. **Raw Run Telemetry**: Every individual run is recorded in `results/canonical/raw_runs.jsonl`.
