# Architectural Design Inspirations & Academic Citations

**Project**: Decentralized AMR Fleet Coordination for Smart Warehouses (SIH26123)  
**Team**: Boom Baam  

This document provides transparent, judge-safe attribution for the design patterns, architectural paradigms, and algorithmic inspirations adapted in our system. All algorithms and components in this repository were independently designed and implemented from first principles to address the decentralized warehouse multi-agent path finding (MAPF) requirements of problem statement **SIH26123**.

---

## 1. Architectural Concept Provenance

| Adopted Concept | Academic / System Inspiration | Our Implementation | Why It Helps |
| :--- | :--- | :--- | :--- |
| **Distributed Task Ownership Protocol** | ACE-style consensus & contract net protocols | `coordination/task_ownership.py` (`TaskOwnershipProtocol`) | Prevents duplicate task ownership across peers via monotonic assignment epochs, handles stale network messages, and automates peer reclaim upon hardware failure without replacing Hungarian allocation. |
| **Time-Indexed Reservation Timeline** | Space-Time Reservation Tables (Silver 2005, MAPF-LIB) | `planning/reservation.py` (`SpaceTimeReservationTable`) & `/api/reservations` | Makes rolling space-time $(x, y, t)$ occupancy visually inspectable in the Digital Twin, enables dynamic invalidation on corridor blockage, and prunes expired state. |
| **Plan vs. Execution Metric Separation** | MultiRobotBattle experimental evaluation paradigm | `metrics/metrics.py` (`FleetMetrics`) | Distinguishes theoretical planner expectations (planned path length, planned makespan) from physical simulation outcomes (actual wait time, reroutes, clearance, and safety gating). |
| **Event-Driven Replanning Triggers** | Lazy Conflict-Based Adaptation (LCBA) | `planning/replanning.py` (`EventDrivenReplanner`) | Eliminates blind periodic replanning loops by triggering Space-Time A* only upon specific operational events (blockage, hardware stall, task completion, deadlock) with cooldown deduplication. |
| **Robot Inspector & Fault Lab** | Multi-Robot Warehouse System (MRWS) observability patterns | Web Digital Twin Robot Inspector panel & Disturbance Injection API | Provides deep single-robot operational visibility (SOC, task epoch, local belief age, last veto reason) and controllable disturbance injection for live evaluation. |
| **Pluggable Baseline / Ablation Suite** | warefleet & standard MAPF benchmark suites | `benchmark/baselines.py`, `benchmark/sih_metrics_audit.py` | Allows fair, paired comparative evaluation against standardized Stop-and-Wait and greedy baselines, as well as controlled ablation of congestion, adaptive, and reservation components. |
| **Decentralized Multi-Agent Negotiation** | Priority Inheritance with Backtracking (PIBT, Okumura et al. 2022) | `planning/pibt.py` | Provides sub-millisecond, anytime one-step right-of-way resolution without centralized combinatorial explosion. |
| **Bipartite Minimum-Cost Assignment** | Kuhn-Munkres Hungarian Algorithm (Kuhn 1955) | `coordination/allocator.py` (`HungarianAllocator`) | Solves global minimum-cost matching in polynomial time $\mathcal{O}(n^3)$ over composite cost (Manhattan transit + congestion + battery penalty). |
| **Deadlock Cycle Resolution** | Strongly Connected Components (Tarjan 1972) on Wait-For Graphs | `planning/deadlock.py` | Breaks multi-robot ring and head-on deadlocks in $\mathcal{O}(V + E)$ by identifying cyclic waiting dependencies and commanding lateral yields to the lowest-priority agent. |

---

## 2. Core Scientific Differentiation

Our production coordination architecture remains centered around our own unified pipeline:
$$\text{Task Stream} \to \text{Hungarian Assignment} \to \text{Ownership Protocol (Claim/ACK/Commit)} \to \text{PIBT Negotiation} \to \text{Space-Time A* Detour} \to \text{Safety Supervisor}$$

- **No external source code has been copied**: All patterns are clean-room Python implementations tailored specifically to our 16-phase simulation tick and ROS 2 Jazzy integration.
- **Hungarian matching is preserved**: The Claim/ACK/Commit layer acts as an ownership enforcement and fault-recovery shield rather than an auction replacement.
- **Authoritative Safety Supervision**: Academic MAPF algorithms operate under discrete assumptions; our system enforces a deterministic, zero-overhead safety supervisor gate at the actuator boundary.
