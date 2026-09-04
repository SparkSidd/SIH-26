# Hackathon Judge Q&A: Technical Defense (SIH26123)

## Preparation for Uncomfortable & In-Depth Technical Questions

### Q1: "Your prompt mentions a 20% reduction target, but your aggregate reduction is 12.06%. Why did you fail to hit 20%?"
**Answer**:
> *"That is an accurate observation, and we intentionally refuse to manufacture numbers to falsely claim a blanket pass. Across 200 paired multi-seed runs, our aggregate reduction is 12.06% because in uncongested nominal conditions ($S_0$), AMRs travel on direct Manhattan paths where physical kinematics—not coordination—bound completion time. However, in congested and high-conflict scenarios ($S_1$ and $S_8$), where multi-agent coordination actually matters, our system achieves a 19.01% and 18.99% reduction, with individual peak disruption runs achieving up to 43.20% reduction. We report raw, unfiltered empirical facts rather than cherry-picked best seeds."*

---

### Q2: "How do you formally guarantee zero collisions in a decentralized system?"
**Answer**:
> *"We clarify that we do NOT claim a formal mathematical theorem proof. Rather, we empirically verified zero inter-robot collisions across all 200 benchmark runs and continuous live stress tests. This is achieved through a multi-tiered defense: first, decentralized Space-Time reservations and PIBT priority inheritance; second, an invariant-checking Safety Supervisor running locally on each robot that evaluates one-step-ahead action batches for vertex and edge-swap conflicts before motor commands are committed. If any conflict is detected, lower-priority robots are forced to yield to their current cell with priority cascade resolution."*

---

### Q3: "Previous prototypes claimed a 93% bandwidth reduction. Why does your benchmark show -1.1%?"
**Answer**:
> *"In our simulated peer-to-peer mesh, both baseline and proposed robots exchange compact 1-hop periodic state heartbeats (~18 KB/s). The previously cited '93% reduction' was an architectural comparison between centralized cloud telemetry streaming (where every robot streams full high-frequency sensor bags and map states to a central server, requiring ~184 KB/s) versus local edge P2P mesh exchanges. To maintain strict scientific integrity in our PPT, we do not claim a 93% simulation bandwidth reduction; we report the true measured P2P mesh volume (~18.6 KB/s) and characterize the bandwidth advantage as an architectural elimination of central server bandwidth bottlenecks."*

---

### Q4: "How do you detect and resolve deadlocks peer-to-peer?"
**Answer**:
> *"We maintain a dynamic Wait-For-Graph (WFG) where directed edges $R_i \to R_j$ represent robot $i$ waiting for robot $j$ to vacate an adjacent cell. Tarjan's cycle-detection algorithm evaluates the WFG at each timestep. When a cycle is detected, the lowest-priority robot in the cycle initiates an active Space-Time A\* detour, temporarily treating the blocking agent's position as an obstacle and computing an alternate waypoint through a parallel aisle."*

---

### Q5: "What happens when wireless communication is completely lost or packets drop?"
**Answer**:
> *"Our system does not rely on lockstep distributed consensus. Each AMR maintains a local world model that tracks observed peer positions and extrapolates trajectories using dead-reckoning. Under 20% to 50% packet loss (tested in $S_3, S_7, S_9$), robots continue forward progression using their onboard Space-Time reservations. If peer state uncertainty exceeds a safety clearance threshold ($< 2.0\text{ m}$), the Safety Supervisor conservatively slows down or yields until fresh heartbeats confirm clear passage. We observed zero collisions even under 50% packet drop."*

---

### Q6: "Why use PIBT rather than centralized MAPF solvers like CBS (Conflict-Based Search)?"
**Answer**:
> *"Conflict-Based Search (CBS) is NP-hard. While it guarantees bounded suboptimality, its worst-case solving time grows exponentially with robot density, frequently causing multi-second planning timeouts in warehouse bottlenecks. In contrast, PIBT is an anytime, iterative algorithm that operates in $\mathcal{O}(V)$ time per robot. Our benchmarks demonstrate a mean planning latency of 0.08 ms and a P95 of 0.14 ms, making it suitable for real-time edge microcontrollers operating at 50 Hz control loops."*

---

### Q7: "How is task allocation decentralized if tasks arrive dynamically?"
**Answer**:
> *"Task allocation uses a fleet-aware cost function evaluated locally. Rather than assigning purely based on Euclidean distance, our cost metric integrates three factors: $C = w_1 \cdot \text{TravelDistance} + w_2 \cdot \text{AisleCongestionPenalty} + w_3 \cdot \text{BatteryState}$. In our ablation study, disabling the congestion penalty increased bottleneck waiting time by 28%, proving that congestion-aware allocation actively prevents fleets from crowding into identical corridors."*

---

### Q8: "What happens if a robot carrying a payload breaks down in the middle of a corridor?"
**Answer**:
> *"In scenario $S_5$, AMR_02 suffers a fatal hardware fault mid-aisle. The fleet detects the failure via three missed heartbeats (1.5 s). Two autonomous mechanisms trigger: first, the failed robot is broadcast as a static physical obstacle so peer AMRs immediately detour around it; second, the orphaned task is reclaimed by the decentralized allocation protocol and reassigned to the nearest available healthy AMR. Our recovery rate is 100% with zero lost tasks."*

---

### Q9: "Can this system run on actual robot hardware?"
**Answer**:
> *"Yes. The entire coordination stack is written in standard Python with zero heavy GUI or cloud dependencies. Its peak RAM consumption is 54 MB, and single-step planning requires 0.14 ms on a single core. It is directly deployable on embedded edge computers like the Raspberry Pi 4/5 or NVIDIA Jetson Nano running ROS2 (Robot Operating System), communicating over standard UDP/DDS multicast."*

---

### Q10: "How do you handle turning radius and kinematic constraints?"
**Answer**:
> *"Our robot model enforces differential-drive kinematics with a maximum linear velocity of $1.0\text{ cell/s}$, maximum acceleration of $1.0\text{ cell/s}^2$, and a discrete turning time penalty of $0.5\text{ s}$ per 90-degree heading change. The continuous collision supervisor verifies swept bounding circles ($r = 0.4\text{ m}$) to ensure safe inter-robot clearance during rotational transitions."*

---

### Q11: "Why do you have three coordination modes (LOCAL, NEIGHBOR, CLUSTER)?"
**Answer**:
> *"Dynamic mode escalation minimizes communication overhead during free flow while providing maximum coordination during bottlenecks. When AMRs are isolated, they operate in LOCAL mode with zero peer negotiation. When interaction density increases or waiting steps occur, they escalate to NEIGHBOR mode (sharing 1-hop intent). If multi-robot deadlocks or corridor blockages occur, they escalate to CLUSTER mode to coordinate multi-agent priority swaps."*

---

### Q12: "How is your benchmark reproducible by an external reviewer?"
**Answer**:
> *"Anyone can clone our repository and execute:
> ```bash
> python main.py --benchmark --seeds 10 --headless
> ```
> This executes all 10 scenarios across the 10 fixed random seeds in headless mode, logging raw timestamps, coordinates, and latency samples into CSV and JSON files in `results/ppt_metrics/`. The numbers in our PPT match the exact outputs generated by this command."*

---

### Q13: "What are the fundamental limits or failure modes of this system?"
**Answer**:
> *"The system has two defined physical limitations: first, in a dead-end corridor narrower than two cells, if a higher-priority robot meets a lower-priority robot head-on, the lower-priority robot must reverse all the way to the corridor junction, which increases waiting time; second, under 100% complete RF blackout lasting longer than 10 seconds, AMRs conservatively halt once they exhaust their immediate reservation window to uphold safety."*
