# Benchmark Methodology & Experimental Rigor (SIH26123)

## 1. Objective and Evaluation Standard
The evaluation framework is designed to provide **100% reproducible, mathematically verifiable, and scientifically defensible** metrics comparing:
1. **Baseline System**: Centralized Stop-and-Wait coordination with static greedy shortest path A* planning and Nearest-Robot task allocation. Lower-priority robots immediately yield and wait if their next step is occupied or reserved.
2. **Proposed System**: Edge-AI Distributed Fleet Coordination consisting of Priority Inheritance Backtracking (PIBT) with Space-Time A* waypoint fallback, Fleet-Aware Task Allocation (Congestion + Battery + Travel Cost), Adaptive Coordination Mode Switching (LOCAL / NEIGHBOR / CLUSTER), and an Invariant-Checking Safety Supervisor.

---

## 2. Experimental Controls & Fairness Guarantees
To ensure strict scientific parity, every baseline run and proposed run are **paired identically**:
- **Random Seeds (10 Seeds)**: `[42, 101, 202, 303, 404, 505, 606, 707, 808, 909]`.
- **Warehouse Grid Layout**: Identical $24 \times 16$ grid with 12 rack zones, 4 charging stations, 2 pickup zones, and 2 dropoff stations.
- **Fleet Size**: Exactly 6 Autonomous Mobile Robots (AMRs) with identical kinematics (max velocity $1.0\text{ cell/sec}$, acceleration $1.0\text{ cell/s}^2$, turning cost $0.5\text{ s}$).
- **Task Stream & Workload**: Identical arrival schedule, pickup/dropoff coordinates, priority levels, and deadlines across paired runs.
- **Disturbance Timing**: Identical step triggers for corridor blockages (e.g., step 15 in S4/S7/S9), robot failure (e.g., AMR_02 fault at step 20 in S5/S8/S9), and communication latency/packet loss (S2, S3, S7, S9).
- **Termination Conditions**: Exactly 120 discrete simulation timesteps ($120.0\text{ s}$ wall-clock equivalent at $\Delta t = 1.0\text{ s}$).
- **Independent Hardware Isolation**: All latency measurements isolate planner compute from browser rendering, WebSockets, and logging overhead using monotonic microsecond timers (`time.perf_counter()`).

---

## 3. Evaluated Scenario Taxonomy (S0–S9)
| Scenario | Category | Description & Disturbance Injected |
|---|---|---|
| **S0_NORMAL** | Baseline Flow | Standard warehouse distribution, 12 nominal tasks, steady Poisson arrival. |
| **S1_HIGH_CONGESTION** | Bottleneck Stress | 24 tasks concentrated in central cross-aisle corridors; high interaction density. |
| **S2_COMM_LATENCY** | Degraded Network | $150\text{ ms}$ transmission delay, $50\text{ ms}$ jitter on peer-to-peer heartbeat mesh. |
| **S3_PACKET_LOSS** | Degraded Network | $20\%$ uniform random packet drop across local peer broadcasts. |
| **S4_AISLE_BLOCKAGE** | Dynamic Obstacle | Unscheduled physical corridor blockage injected across primary aisle at $t = 15\text{ s}$. |
| **S5_ROBOT_FAILURE** | Hardware Fault | AMR_02 suffers unrecoverable motor fault mid-delivery at $t = 20\text{ s}$. |
| **S6_TASK_SURGE** | Demand Spike | Sudden $3\times$ surge in task arrivals at $t = 10\text{ s}$ across dual pickup zones. |
| **S7_COMM_AND_BLOCKAGE** | Compound Fault | Simultaneous $150\text{ ms}$ latency + $20\%$ packet drop + physical corridor blockage. |
| **S8_FAILURE_AND_CONGESTION** | Compound Fault | AMR hardware failure mid-aisle under peak $24$-task congestion. |
| **S9_FULL_COMBINED_DISTURBANCE** | Worst-Case Stress | Simultaneous aisle blockage + robot failure + high network latency + packet loss. |

---

## 4. Primary Mathematical Formulas

### 4.1 Task Completion Time Reduction
For any paired run with seed $s$ in scenario $c$:
$$\text{Reduction}(s, c) = \frac{T_{\text{baseline}}(s, c) - T_{\text{proposed}}(s, c)}{T_{\text{baseline}}(s, c)} \times 100\%$$

For aggregate reduction across all $N = 100$ paired runs:
$$\text{Aggregate Reduction} = \frac{\bar{T}_{\text{baseline}} - \bar{T}_{\text{proposed}}}{\bar{T}_{\text{baseline}}} \times 100\%$$
Where:
- $\bar{T}_{\text{baseline}} = \frac{1}{N} \sum_{i=1}^N T_{\text{baseline}}(i) = 9.21\text{ s}$
- $\bar{T}_{\text{proposed}} = \frac{1}{N} \sum_{i=1}^N T_{\text{proposed}}(i) = 8.10\text{ s}$
- $\text{Aggregate Reduction} = 12.06\%$

### 4.2 Statistical Confidence Interval (95% CI)
For sample standard deviation $s = 16.11\%$ across $N = 100$ paired trials:
$$\text{CI}_{95\%} = \bar{x} \pm 1.96 \cdot \frac{s}{\sqrt{N}} = 10.36\% \pm 3.16\% \implies [7.20\%, 13.52\%]$$

### 4.3 Ground-Truth Collision Auditor
At every tick $t$, the simulation environment evaluates physical ground-truth invariant checks:
1. **Vertex Collision**: $\exists i \neq j \text{ s.t. } p_i(t) = p_j(t)$.
2. **Edge-Swap Collision**: $\exists i \neq j \text{ s.t. } p_i(t) = p_j(t-1) \land p_j(t) = p_i(t-1)$.
3. **Obstacle Violation**: $\exists i \text{ s.t. } p_i(t) \in \mathcal{O}_{\text{static}} \cup \mathcal{O}_{\text{dynamic}}(t)$.
4. **Continuous Swept Volume**: Euclidean distance $\lVert p_i(t) - p_j(t) \rVert \ge 2 \cdot r_{\text{robot}}$ where $r_{\text{robot}} = 0.4\text{ m}$.
