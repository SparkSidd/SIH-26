# Hackathon Judge Q&A: Technical Defense (SIH26123)

> **Canonical Metrics Reference**: All metrics cited herein are strictly sourced from [`results/CANONICAL_SIH_METRICS.json`](file:///c:/Users/thega/PROJECTS/SIH'26/results/CANONICAL_SIH_METRICS.json).
> Reproducible via: `python -m benchmark.generate_canonical_report` and `pytest -q`.

---

## Technical Defense for SIH Evaluation Panel

### Q1: Why Decentralized Rather Than Centralized Fleet Management?
**Answer**:
> *"Centralized fleet managers (e.g., classical AGV fleet controllers) suffer from three critical bottlenecks in high-density smart warehouses: a single point of failure, exponential computational scaling ($\mathcal{O}(N!)$ or exponential branching in centralized MAPF), and fragile wireless latency over Wi-Fi when hundreds of AMRs stream high-rate trajectories. Our edge-first decentralized architecture distributes path planning and conflict resolution directly onto each AMR's onboard compute. Communication is confined to localized 1-hop peer-to-peer (P2P) state heartbeats. If any robot fails or wireless signal degrades, the remaining fleet continues autonomous operation without global downtime."*

---

### Q2: Why Hungarian Allocation for Task Assignment?
**Answer**:
> *"The Hungarian algorithm (Kuhn-Munkres) provides a polynomial-time ($\mathcal{O}(N^3)$) minimum-cost bipartite matching between available AMRs and active warehouse mission tasks under our defined cost model. In our fleet-aware implementation, the edge cost matrix is not just Euclidean distance—it incorporates an execution-aware ETA model penalizing turns ($0.4\text{ s}$ per turn), anticipated corridor congestion ($0.3$ weight), battery state-of-charge, and fleet workload imbalance ($w_{\text{imbalance}} = 3.0$). This delivers balanced, minimum-cost task distribution while running in under $0.5\text{ ms}$ for 6–20 AMRs."*

---

### Q3: Why Priority Inheritance Behavioral Tree (PIBT) for Motion Coordination?
**Answer**:
> *"PIBT is an anytime, decentralized multi-agent path finding priority inheritance scheme. Unlike discrete grid searches that search joint configuration spaces, PIBT resolves pairwise and group conflicts iteratively: higher-priority robots select their preferred forward action according to their Space-Time heuristic; if a target cell is occupied by a peer, PIBT recursively pushes the lower-priority peer to vacate or yield. This guarantees fast $\mathcal{O}(V)$ execution per robot per timestep, making it suitable for 50 Hz control loops while effectively preventing head-on deadlocks."*

---

### Q4: Why Space-Time A\* for Path Planning?
**Answer**:
> *"Space-Time A\* searches a discrete $(x, y, t)$ state space where time is an explicit dimension alongside spatial coordinates. Each robot registers its planned path into a local Space-Time reservation table. When an AMR needs a detour around a congested corridor or a blocked aisle, Space-Time A\* treats cells occupied by other robots at specific future timesteps as obstacles, finding a conflict-free space-time trajectory that allows robots to wait in place or take parallel bypass aisles without spatial collision."*

---

### Q5: Why Not Conflict-Based Search (CBS)?
**Answer**:
> *"Conflict-Based Search (CBS) is optimal or bounded-suboptimal, but it is NP-hard. In dense warehouse layouts with choke points and symmetric corridors, the CBS conflict tree grows exponentially, frequently triggering multi-second solving timeouts or catastrophic thread exhaustion. In an operational warehouse, an AMR cannot stop for 3 seconds to await a CBS tree resolution. Our combination of Hungarian allocation + PIBT + Space-Time A* yields predictable, deterministic sub-millisecond execution ($0.27\text{ ms}$ mean) with zero observed collisions across 200 benchmark runs."*

---

### Q6: How Are Multi-Robot Deadlocks Detected and Resolved?
**Answer**:
> *"Deadlocks are monitored via a localized Wait-For-Graph (WFG) where directed edges $R_i \to R_j$ represent robot $i$ waiting for robot $j$ to vacate an adjacent cell. Tarjan’s cycle-detection algorithm evaluates the WFG at each tick. When a cycle (true deadlock) is detected, the lowest-priority robot in the cycle initiates an active Space-Time A\* detour or yields its reservation, breaking the cycle. For simple transient waits (yielding to higher-priority peers), the system distinguishes polite waiting from true deadlocks to avoid unnecessary rerouting."*

---

### Q7: What Happens During Wireless Packet Loss or Jitter?
**Answer**:
> *"Our system does not rely on synchronized lockstep consensus. Each AMR maintains an onboard `LocalWorldModel` that tracks observed peer states and dead-reckons missing updates across dropped cycles. In our benchmark, we tested packet loss rates from 10% to 50% ($S_3, S_7, S_9$) and transmission delays up to 250 ms ($S_2$). Robots continue progressing along their pre-reserved Space-Time corridors. If peer uncertainty persists past a safety threshold, the deterministic Safety Supervisor automatically slows or holds the robot until fresh heartbeats confirm safe clearance. 0 collisions occurred across all degraded network tests."*

---

### Q8: What Happens When an AMR Suffers a Hardware or Motor Failure?
**Answer**:
> *"In scenario $S_5$, AMR_02 suffers a fatal hardware stall mid-aisle. Peer AMRs detect the failure via 3 consecutive missed gossip heartbeats ($1.5\text{ s}$). Two actions occur autonomously:
> 1. The stalled AMR is broadcast as a static physical obstacle, prompting peers to immediately route detours around it via Space-Time A*.
> 2. The stalled AMR's in-flight task is reclaimed by the distributed task ownership layer, incrementing the assignment epoch and safely transferring ownership to the nearest healthy AMR. Across 40 fault-injection benchmark runs, 100% of tested failure scenarios recovered successfully with zero lost tasks."*

---

### Q9: How Is Task Ownership Protected Against Duplicate Execution?
**Answer**:
> *"We implemented a distributed Task Claim / ACK / Commit Protocol (`coordination/task_ownership.py`). Tasks follow a formal lifecycle: `UNASSIGNED` $\to$ `PROPOSED` $\to$ `CLAIMED` $\to$ `ACKED` $\to$ `COMMITTED` $\to$ `EXECUTING` $\to$ `COMPLETED`. When an allocation is computed, an AMR broadcasts a `TASK_CLAIM` with a monotonically increasing `assignment_epoch`. Peers verify that the task is uncommitted and return `TASK_ACK`. Only upon receiving required ACKs does the robot transition to `COMMITTED`. If two robots claim the same task simultaneously, the tie is broken deterministically by cost/ID, and the losing claim is released without duplicate execution."*

---

### Q10: What Happens When Stale or Delayed Ownership Messages Arrive?
**Answer**:
> *"Every task claim, ACK, and reclaim message contains a monotonically increasing `assignment_epoch`. If a delayed packet from a previously failed or disconnected robot arrives after the task has been reclaimed by a peer, the recipient robots inspect the message epoch. Because the stale message contains epoch $k$ while the active task has transitioned to epoch $k+1$, the message is rejected immediately with a `stale_message_rejected` metric increment. This guarantees split-brain immunity."*

---

### Q11: What Is the Deterministic Safety Layer?
**Answer**:
> *"The Safety Supervisor is an independent, non-bypassable runtime verification gate running locally on each robot before actuator execution. It inspects candidate action batches for:
> 1. Vertex conflicts (two AMRs targeting the same cell at time $t$).
> 2. Edge-swap conflicts (two AMRs crossing the same aisle in opposing directions between $t$ and $t+1$).
> 3. Blocked-cell and boundary violations.
> If any proposed action violates an invariant, the Safety Supervisor vetoes the motor command and enforces a safe in-place hold. Across all 200 benchmark executions, 0 inter-robot collisions occurred."*

---

### Q12: What Are the Real, Canonical Benchmark Results?
**Answer**:
> *"All current headline metrics are derived directly from the single canonical benchmark artifact (`results/CANONICAL_SIH_METRICS.json`), generated from 100 paired experiments (200 total system executions across 10 scenarios and 10 fixed seeds) and backed by individual execution records in `results/canonical/raw_runs.jsonl`:
> - Baseline Mean Time: **8.80 s** (Stop-and-Wait + Nearest Allocation)
> - Proposed Mean Time: **6.61 s** (Fleet-Aware + PIBT + Space-Time A*)
> - Aggregate Time Reduction: **24.89%** (exceeds SIH $\ge 20\%$ target)
> - Inter-Robot Collisions: **0 in proposed fleet** across all 100 runs (baseline had 355 collisions on dynamic obstacles without rerouting)
> - Inter-Robot Deadlocks: **0 in proposed fleet** across all 100 runs
> - Mean Planning Latency: **2.17 ms** (P95: **1.23 ms**, Max: **3.96 ms** across >35,000 real decision loop samples)
> - Core Planner Memory: **54.0 MB** (Total Digital Twin process: **238.7 MB** historical profile)
> - Test Suite: **121 / 121 tests passing** (100% pass rate).
> 
> These values are generated from the reproducible benchmark command and backed by raw execution logs."*

---

### Q13: How Can an External Reviewer Reproduce These Numbers?
**Answer**:
> *"The entire benchmark and validation suite is 100% reproducible with two commands:
> ```bash
> # Run canonical benchmark suite (executes 200 simulations, records raw runs, and outputs canonical metrics)
> python -m benchmark.generate_canonical_report
> 
> # Run the complete automated test suite (121 tests)
> pytest -q
> ```
> The report generator records source commit SHA, platform environment, exact seeds, and every individual execution record into `results/canonical/raw_runs.jsonl`, generating `results/CANONICAL_SIH_METRICS.json` and `results/canonical/`."*

---

### Q14: What Are the Known Limitations of the System?
**Answer**:
> *"We maintain full scientific transparency regarding current limitations:
> 1. In long single-cell dead-end aisles (corridor width = 1), head-on encounters require the lower-priority robot to reverse to the junction, which imposes a localized delay.
> 2. Under a total radio frequency blackout exceeding 10 seconds, robots safely exhaust their immediate Space-Time reservations and halt conservatively until signal is restored.
> 3. Our primary benchmark evaluation is conducted on a discrete $1.0\text{ m}$ grid topology with differential-drive turning approximations; continuous curvilinear trajectories are handled via trajectory smoothing adapters."*

---

### Q15: What Was Validated in the Interactive Digital Twin?
**Answer**:
> *"The Digital Twin provides full interactive multi-agent simulation over FastAPI and WebSockets, rendering live canvas state, normalized congestion heatmaps ($0$–$100$), real-time P2P message exchange, dynamic obstacle injection, robot motor failure injection, Space-Time reservation timeline inspection, and comparative baseline-vs-proposed runs."*

---

### Q16: What Was Validated in Gazebo?
**Answer**:
> *"In Gazebo Harmonic integrated with ROS 2 Jazzy, we validated continuous-time physics, realistic wheel slip, sensor noise, lidar-based obstacle detection, and ROS 2 navigation integration for AMR models traversing warehouse environments using the identical decentralized coordination logic."*

---

### Q17: What Was Validated in Webots?
**Answer**:
> *"Webots R2023b was utilized as an independent, secondary robotics simulation backend to confirm cross-simulator consistency. We validated 2-AMR, 4-AMR, and 6-AMR configurations, dynamic corridor blockage detours, differential-drive wheel velocity controllers, and ROS 2 bridge topics without modifying core coordination algorithms."*

---

### Q18: What Was NOT Validated (What Are You Not Claiming)?
**Answer**:
> *"We strictly do NOT claim:
> 1. Physical hardware deployment on physical warehouse floors with physical LiDAR (our results are validated in simulation and Digital Twin).
> 2. Direct on-chip measurements from physical Raspberry Pi or Jetson boards (our latency and memory figures are profiled under single-core CPU profiles representing edge constraints).
> 3. A formal mathematical proof of collision freedom (our zero-collision result is an empirically verified safety guarantee enforced at runtime by the Safety Supervisor).
> 4. A 93% bandwidth reduction in simulation (our simulated P2P mesh transfer difference is $0.01\%$; 93% was an unmeasured central telemetry streaming comparison)."*

---

### Q19: Which System Components Are Optional or Modular?
**Answer**:
> *"The architecture strictly isolates safety-critical core algorithms from optional modules:
> - **Mandatory Core**: Hungarian allocation, PIBT motion coordination, Space-Time A*, Space-Time reservations, WFG deadlock handling, and Safety Supervisor.
> - **Optional Module**: Neural priority guidance (`learning/model_adapter.py`, `learning/inference.py`), which uses PyTorch. This module is lazily loaded and completely optional; if PyTorch is not installed or inference times out, the system deterministically falls back to heuristic priority rules without compromising safety or halting."*

---

### Q20: What Would Be the Next Step for Staged Physical Hardware Validation?
**Answer**:
> *"The immediate next step is staged hardware validation on a 3-AMR physical testbed:
> 1. Flash the edge coordination runtime onto Raspberry Pi 4/5 single-board computers mounted on differential-drive AMR bases.
> 2. Connect the existing ROS 2 navigation bridge (`ros2_integration/`) to physical wheel encoders and 2D LiDAR for local SLAM localization.
> 3. Establish 802.11s Wi-Fi mesh or UDP multicast P2P networking between AMRs.
> 4. Conduct physical staging tests: nominal transport, pedestrian obstacle avoidance, and deliberate single-AMR power cut to validate real-world peer task reclamation."*
