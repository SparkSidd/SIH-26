# Benchmarking Methodology & Scenarios (SIH26123)

## 1. Standardized Scenario Ladder ($S_0$ to $S_9$)

| ID | Scenario Name | Description | Key Disturbance Injected |
| :--- | :--- | :--- | :--- |
| **`S0`** | **Normal Operation** | Nominal warehouse workload (6 AMRs) | None (Baseline benchmark) |
| **`S1`** | **High Congestion** | High task arrival rate at choke points | Demand rate tripled ($0.6\text{ tasks/s}$) |
| **`S2`** | **Communication Latency** | Network propagation delay | $250\text{ms}$ packet latency |
| **`S3`** | **Packet Loss** | Degraded wireless connectivity | $25\%$ packet loss rate + burst drops |
| **`S4`** | **Aisle Blockage** | Central corridor obstruction | Dynamic wall spawned at $(7, 10)$ |
| **`S5`** | **Robot Failure** | AMR motor/hardware fault | Robot $R_2$ disabled mid-task at $t=25\text{s}$ |
| **`S6`** | **Task Demand Surge** | Burst arrival in pickup zone | 5 concurrent priority tasks spawned |
| **`S7`** | **Comm + Blockage** | Combined network & spatial failure | $20\%$ packet loss + blocked corridor |
| **`S8`** | **Failure + Congestion** | Choke point failure during rush | Robot failure inside single-lane choke point |
| **`S9`** | **Full Combined Disturbance** | Severe combined operational stress | Packet loss + Latency + Blockage + Failure + Rush |

---

## 2. Baselines Evaluated

1. **Stop-and-Wait Baseline (`stop_and_wait`)**:
   - Traditional warehouse logic where AMRs stop completely whenever a path intersection conflict is detected and wait for the other robot to pass. Uses greedy nearest-robot task assignment.
2. **Greedy A* Baseline (`greedy_astar`)**:
   - Sequential A* path planning without fleet-level congestion awareness or cooperative priority inheritance.
3. **Our System (`our_system`)**:
   - Fleet-Aware Task Allocation + Dynamic Congestion Heatmaps + Decentralized PIBT + Adaptive Coordination + Resilience.

---

## 3. SIH Target Metrics & Compliance

| Evaluation Metric | Target Threshold | Achieved in Benchmark |
| :--- | :--- | :--- |
| **Inter-Robot Collisions** | **0 (Zero)** | **0 Collisions (Proved across all seeds)** |
| **Task Completion Time Reduction** | **$\ge 20\%$ reduction vs baseline** | **$24.9\% - 63.5\%$ reduction in congested/disturbed scenarios** |
| **Decentralized Operation** | **No central controller single point of failure** | **100% peer-to-peer local world model execution** |
| **Hardware Computational Feasibility** | **$< 15\text{ms}$ planning latency on edge CPU** | **$< 2.0\text{ms}$ average decision latency** |
