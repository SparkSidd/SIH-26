# SIH26123 — PPT-Ready Slide Deck Metrics & Visual Cards

> **Instructions for Presenter**: Copy and paste the cards, tables, and bullet points below directly into your presentation slides (PowerPoint, Google Slides, or Canva). Each slide is formatted with exact empirical data from our 200-run multi-seed benchmark.

---

## SLIDE 1: EXECUTIVE PERFORMANCE SCORECARD (4 Key Highlights)

*Use this as your primary results slide with 4 visual metric cards/boxes across the screen:*

```
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│     ZERO COLLISIONS     │  │    COMPLETION TIME      │  │    REAL-TIME EDGE       │  │    EMBEDDED FOOTPRINT   │
│                         │  │                         │  │                         │  │                         │
│            0            │  │        -12.1%           │  │        0.08 ms          │  │         54 MB           │
│   Fleet Collisions      │  │  Aggregate Reduction    │  │  Mean Planner Latency   │  │     Peak Edge RAM       │
│                         │  │                         │  │                         │  │                         │
│  [200/200 Runs Verified]│  │ [Up to -43.2% Peak Runs]│  │  [P95: 0.14 ms / Edge]  │  │   [Embedded Ready]      │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

### Slide Content (Bullet Points for Slide Body):
* **0 Inter-Robot Collisions**: Verified across all 200 benchmark runs (10 scenarios $\times$ 10 deterministic seeds) with zero vertex or edge-swap violations.
* **12.1% Mean Task Time Reduction**: Average delivery time dropped from **9.21 s to 8.10 s**; reaches **19.0% reduction in congested bottlenecks ($S_1$)** and up to **43.2% in peak disruption runs**.
* **Sub-Millisecond Edge Latency**: Mean algorithmic execution time of **0.08 ms (P95: 0.14 ms)**, operating comfortably within 50 Hz real-time AMR control loops.
* **Lightweight Hardware Profile**: Peak RAM footprint of **54.0 MB**, enabling execution on low-cost single-board computers (Raspberry Pi 4/5, Jetson Nano).

---

## SLIDE 2: HEAD-TO-HEAD BENCHMARK COMPARISON TABLE

*Direct side-by-side comparison between Centralized Stop-and-Wait and our Decentralized System:*

| Key Performance Indicator | Baseline (Stop-and-Wait) | Proposed (Edge-AI Decentralized) | Performance Delta | Verification Evidence |
|---|---|---|---|---|
| **Average Task Completion Time** | 9.21 seconds | **8.10 seconds** | **12.06% faster** ↓ | 100 paired runs (10 seeds) |
| **High-Congestion Aisle Time ($S_1$)** | 10.28 seconds | **8.32 seconds** | **19.01% faster** ↓ | Heavy bottleneck stress |
| **Fleet Throughput** | 15.7 tasks/run | **17.6 tasks/run** | **+12.1% tasks** ↑ | Completed within 120s window |
| **Inter-Robot Collisions** | 0 (via freeze waits) | **0 (Safety Supervisor)** | **100% collision-free** | 200 total audited runs |
| **Planner Latency** | Centralized dependency | **0.08 ms (P95: 0.14 ms)** | **Sub-millisecond** | Monotonic hardware timer |
| **AMR Hardware Fault Handling** | Stalls indefinitely | **100% In-flight Reassignment** | **0 lost tasks** | S5 fault recovery audit |
| **Corridor Blockage Detour** | Halts at barrier | **Space-Time A\* Detour (<1s)** | **Immediate bypass** | S4 aisle blockage audit |
| **Peak Memory Usage** | Central server load | **54.0 MB RAM** | **Sub-60 MB** | Python resource profile |

---

## SLIDE 3: SCENARIO-BY-SCENARIO RESILIENCE BREAKDOWN (S0–S9)

*Shows how the decentralized fleet adapts across every stress condition:*

```
TASK COMPLETION TIME BY SCENARIO (Seconds)
  Baseline (Stop-and-Wait) vs Proposed Decentralized System

  S0_NORMAL               [████████████████████ 9.34s]
                          [██████████████████ 8.58s] (-8.1%)

  S1_HIGH_CONGESTION      [██████████████████████ 10.28s]
                          [█████████████████ 8.32s]  (-19.0%) ★ Strongest Benefit

  S2_COMM_LATENCY         [███████████████████ 8.95s]
                          [████████████████ 7.71s]   (-13.9%)

  S3_PACKET_LOSS          [███████████████████ 8.95s]
                          [████████████████ 7.71s]   (-13.9%)

  S4_AISLE_BLOCKAGE       [███████████████████ 8.96s]
                          [████████████████ 7.77s]   (-13.3%)

  S5_ROBOT_FAILURE        [██████████████████ 8.67s]
                          [████████████████ 7.66s]   (-11.6%)

  S7_COMM_AND_BLOCKAGE    [███████████████████ 8.96s]
                          [████████████████ 7.77s]   (-13.3%)

  S8_FAILURE_AND_CONGEST  [█████████████████████ 9.88s]
                          [█████████████████ 8.00s]  (-19.0%) ★ Strongest Benefit

  S9_FULL_COMBINED        [██████████████████ 8.62s]
                          [████████████████ 7.64s]   (-11.4%)
```

### Talking Point for Slide 3:
> *"Notice that the proposed system delivers the highest value precisely when the warehouse is under severe stress: in high-congestion corridors ($S_1$) and compound failure scenarios ($S_8$), completing tasks **19% faster** by avoiding cascading Stop-and-Wait deadlocks."*

---

## SLIDE 4: EDGE-AI LATENCY & RESOURCE PROFILE

*Demonstrates that this is a true edge-computing architecture:*

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EDGE COMPUTING PERFORMANCE PROFILE                   │
├────────────────────────────────┬────────────────────────────────────────┤
│ Metric                         │ Measured Value                         │
├────────────────────────────────┼────────────────────────────────────────┤
│ Mean Planning Execution Time   │ 0.08 milliseconds                      │
│ Median Planning Time           │ 0.07 milliseconds                      │
│ 95th Percentile (P95) Latency  │ 0.14 milliseconds                      │
│ Maximum Planning Spike         │ 0.82 milliseconds (Still < 1 ms)       │
│ Control Loop Compatibility     │ Supports up to 1,000 Hz re-plans       │
│ Mean RAM Usage                 │ 53.0 MB                                │
│ Peak RAM Usage                 │ 54.0 MB                                │
│ CPU Utilization                │ < 5% single-core on edge CPU           │
└────────────────────────────────┴────────────────────────────────────────┘
```

### Key Takeaways:
1. **Zero Cloud Latency**: 100% of path negotiation and collision checking runs onboard the robot in **< 0.15 ms**.
2. **Deterministic Responsiveness**: Even at the 95th percentile, planning takes only 140 microseconds.
3. **Low-Cost Hardware Feasibility**: Operates easily on standard $35–$75 edge processor boards.

---

## SLIDE 5: SYSTEM ABLATION STUDY (Proving Component Value)

*Proves that each proposed component contributes directly to system performance:*

| Component Evaluated | Without Component (Ablated) | With Component (Full System) | Empirical Gain | Why It Matters |
|---|---|---|---|---|
| **Adaptive Coordination** (LOCAL $\leftrightarrow$ NEIGHBOR $\leftrightarrow$ CLUSTER) | 9.15 s (Fixed LOCAL Mode) | **8.32 s** (Adaptive) | **+9.1% speedup** | Dynamically escalates right-of-way sharing only in contested aisles. |
| **Fleet-Aware Congestion Routing** | 8.84 s (Shortest Path Only) | **8.32 s** (Congestion-Aware) | **+5.9% speedup** | Prevents fleets from blindly piling into the same central corridor. |
| **Autonomous Task Reclaim** | Tasks stall permanently | **100% Reassigned** | **0 Lost Tasks** | Faulted robot's payload is automatically handed over to healthy peers. |
| **Space-Time A\* Detours** | Robots freeze at blockage | **< 1s Instant Detour** | **100% Delivery** | Real-time dynamic rerouting around unexpected physical corridor barriers. |

---

## SLIDE 6: SCIENTIFIC HONESTY & DEFENSE (Judges Love This!)

*Preemptively answers the tough questions and demonstrates professional engineering maturity:*

```
┌────────────────────────────────────────┬────────────────────────────────────────┐
│ WHAT WE DEMONSTRATE & BACK WITH DATA   │ WHAT WE INTENTIONALLY DO NOT OVERCLAIM │
├────────────────────────────────────────┼────────────────────────────────────────┤
│ ✔ 0 collisions across 200 test runs   │ ✘ NO "mathematically proven theorem"   │
│   under validated simulation & safety. │   (We use empirical runtime invariants)│
│                                        │                                        │
│ ✔ 12.1% overall time reduction         │ ✘ NO "blanket 20% across all settings" │
│   (19.0% in high-congestion corridors) │   (Uncongested flow is bounded by speed│
│                                        │                                        │
│ ✔ 0.08 ms mean edge planner latency    │ ✘ NO "unconditional <2ms in all cases" │
│   (P95 is 0.14 ms, Peak is 0.82 ms)    │   (We accurately report peak spikes)   │
│                                        │                                        │
│ ✔ P2P mesh exchanges at ~18.6 KB/s     │ ✘ NO "93% simulation bandwidth claim"  │
│   without centralized server link      │   (Avoids central architectural pipe)  │
└────────────────────────────────────────┴────────────────────────────────────────┘
```
