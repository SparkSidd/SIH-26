# Empirical Benchmark Results & Metrics Audit (SIH26123)

## 1. Executive Summary & Verification Headline
Across a rigorous multi-seed benchmark comprising **200 full simulation runs** (10 scenarios $\times$ 10 paired random seeds $\times$ 2 complete systems) plus 23 ablation trials:

- **Collision Safety**: **0 inter-robot collisions across all 200 benchmark runs** under the validated simulation and safety model.
- **Task Completion Time**:
  - Baseline Mean: **9.21 s**
  - Proposed Mean: **8.10 s**
  - Aggregate Reduction: **12.06%**
  - Peak Seed Reduction: **43.20%**
  - High-Congestion ($S_1$) Reduction: **19.01%**
  - Compound Failure + Congestion ($S_8$) Reduction: **18.99%**
- **SIH Performance Target Evaluation ( $\ge 20\%$ )**:
  - **Overall Status**: **SUB-TARGET (12.06% Aggregate)**.
  - **Context**: The proposed decentralized system excels under high interaction density ($S_1: 19.01\%$, $S_8: 18.99\%$, individual runs up to $43.2\%$). In uncongested nominal conditions ($S_0$), the headroom for path optimization is naturally bounded by direct Manhattan distances.
- **Edge Compute Latency**:
  - Mean Planner Latency: **0.08 ms**
  - P95 Planner Latency: **0.14 ms**
  - Maximum Latency: **0.82 ms** (100% sub-millisecond real-time edge execution).
- **Edge Memory Footprint**:
  - Mean RAM: **53.0 MB**
  - Peak RAM: **54.0 MB** (fits comfortably within 512 MB embedded edge boards such as Raspberry Pi / Jetson Nano).

---

## 2. Complete Scenario-by-Scenario Benchmark Summary (10 Seeds Paired)

| Scenario | Baseline Mean Time (s) | Proposed Mean Time (s) | Time Reduction (%) | Baseline Tasks Completed | Proposed Tasks Completed | Throughput Gain (%) | Collisions (All Runs) | Mean P95 Latency (ms) | Target Status |
|---|---|---|---|---|---|---|---|---|---|
| **S0_NORMAL** | 9.34 | 8.58 | **8.08%** | 12.2 | 13.8 | **+13.1%** | 0 | 0.09 | SUB-TARGET |
| **S1_HIGH_CONGESTION** | 10.28 | 8.32 | **19.01%** | 22.9 | 26.3 | **+14.9%** | 0 | 0.10 | SUB-TARGET |
| **S2_COMM_LATENCY** | 8.95 | 7.71 | **13.85%** | 13.6 | 14.9 | **+9.6%** | 0 | 0.09 | SUB-TARGET |
| **S3_PACKET_LOSS** | 8.95 | 7.71 | **13.85%** | 13.6 | 14.9 | **+9.6%** | 0 | 0.08 | SUB-TARGET |
| **S4_AISLE_BLOCKAGE** | 8.96 | 7.77 | **13.28%** | 13.6 | 14.8 | **+8.8%** | 0 | 0.08 | SUB-TARGET |
| **S5_ROBOT_FAILURE** | 8.67 | 7.66 | **11.58%** | 13.6 | 14.5 | **+6.6%** | 0 | 0.10 | SUB-TARGET |
| **S6_TASK_SURGE** | 9.55 | 9.86 | **-3.26%** | 11.9 | 13.8 | **+16.0%** | 0 | 0.09 | SUB-TARGET |
| **S7_COMM_AND_BLOCKAGE** | 8.96 | 7.77 | **13.28%** | 13.6 | 14.8 | **+8.8%** | 0 | 0.08 | SUB-TARGET |
| **S8_FAILURE_AND_CONGESTION** | 9.88 | 8.00 | **18.99%** | 20.3 | 21.2 | **+4.4%** | 0 | 0.10 | SUB-TARGET |
| **S9_FULL_COMBINED_DISTURBANCE** | 8.62 | 7.64 | **11.35%** | 21.8 | 24.1 | **+10.6%** | 0 | 0.10 | SUB-TARGET |
| **OVERALL AGGREGATE** | **9.21** | **8.10** | **12.06%** | **15.7** | **17.6** | **+12.1%** | **0** | **0.14 (Peak P95)** | **SUB-TARGET** |

---

## 3. Statistical Distribution (Paired Difference Analysis)

- **Mean Reduction**: $10.36\%$
- **Median Reduction**: $12.92\%$
- **Sample Standard Deviation**: $16.11\%$
- **Minimum Observed Reduction**: $-42.36\%$ (Scenario $S_6$ surge where proposed processed more tasks simultaneously, causing longer per-task queuing)
- **Maximum Observed Reduction**: $+43.20\%$ (Scenario $S_1$, Seed 808 during heavy bottleneck conflict)
- **95% Confidence Interval**: $[7.20\%, 13.52\%]$

---

## 4. Feature-Specific Metrics

### 4.1 Blockage Recovery Metric ($S_4$)
- **Obstacle Injection**: $t = 15.0\text{ s}$
- **Detection & Reroute Latency**: $\le 1\text{ step}$ ($1.0\text{ s}$)
- **Space-Time A\* Detour Generation**: $< 0.5\text{ ms}$
- **Movement Resumption**: Immediate at next timestep
- **Task Completion After Detour**: $100\%$ tasks reached destination

### 4.2 Hardware Failure Recovery ($S_5$)
- **Fault Injection**: AMR_02 motor fault at $t = 20.0\text{ s}$
- **Peer Heartbeat Timeout Detection**: 3 missing cycles ($1.5\text{ s}$)
- **In-Flight Task Reclaim**: $100\%$ orphaned tasks reclaimed
- **Reassignment to Healthy Peer**: Completed in next scheduling cycle ($1.0\text{ s}$)
- **Task Loss**: $0.0\%$ (all assigned payloads safely delivered by surviving fleet)

### 4.3 Network Degradation Robustness ($S_2, S_3, S_7, S_9$)
- **Latency Tested**: Up to $150\text{ ms}$ + $50\text{ ms}$ jitter
- **Packet Loss Tested**: Up to $50\%$ drop rate
- **Safety Invariant Violations**: $0$
- **Deadlock Occurrences**: $0$
- **Mechanisms**: Decentralized local world model extrapolates dead-reckoned peer trajectories; fallback safety buffer prevents premature entry.

---

## 5. System Ablation Studies

| Ablation Configuration | Scenario Evaluated | Completion Time (s) | Tasks Completed | Collision Violations | Key Finding |
|---|---|---|---|---|---|
| **Full Proposed System** | $S_1$ (Congestion) | **8.32 s** | **26.3** | **0** | Adaptive coordination + congestion routing maximizes flow |
| **Fixed LOCAL Coordination Only** | $S_1$ (Congestion) | 9.15 s | 23.4 | 0 | Fixed local fails to negotiate multi-agent bottlenecks early |
| **Ablation Delta (Adaptive Mode)** | $S_1$ | **+9.1% speedup** | **+12.4% tasks** | — | Adaptive system-level coordination policy is strictly superior |
| **Full System (Congestion-Aware)** | $S_1$ (Congestion) | **8.32 s** | **26.3** | **0** | Distributes AMRs across alternate parallel aisles |
| **Without Congestion Component** | $S_1$ (Congestion) | 8.84 s | 24.1 | 0 | AMRs crowd primary corridor, increasing local wait cycles |
| **Ablation Delta (Congestion Weights)**| $S_1$ | **+5.9% speedup** | **+9.1% tasks** | — | Congestion penalty prevents self-induced bottleneck stalls |
