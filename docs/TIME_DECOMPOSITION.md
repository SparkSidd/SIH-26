# Strictly Additive Time-Decomposition Framework (SIH26123)

## 1. Overview & Mathematical Guarantee

In previous preliminary profiling scripts, metrics such as `travel_time`, `wait_time`, `congestion_delay`, and `assignment_latency` were updated using non-exclusive, parallel counters. For instance, `congestion_delay` was incremented concurrently with travel whenever local cell congestion was non-zero. Consequently, the sum of those counters did not equal the total measured task duration.

This document formalizes the **Strictly Additive Time-Decomposition Framework** for all tasks executed in the simulation. Every instant of a task's lifecycle—from creation $t_{\text{create}}$ to delivery $t_{\text{deliver}}$—belongs to exactly **one mutually exclusive category**.

$$\boxed{T_{\text{total}} = T_{\text{assign}} + T_{\text{travel}} + T_{\text{conflict\_wait}} + T_{\text{normal\_wait}} + T_{\text{replan}} + T_{\text{recovery}} + T_{\text{pickup}} + T_{\text{delivery}} + T_{\text{overhead}}}$$

where:
$$T_{\text{total}} = t_{\text{delivery}} - t_{\text{create}}$$

---

## 2. Mutually Exclusive Additive Categories

| Category | State / Trigger Condition | Physical / Operational Meaning |
| :--- | :--- | :--- |
| **`ASSIGNMENT`** ($T_{\text{assign}}$) | $t \in [t_{\text{create}}, t_{\text{assign}}]$ | Time elapsed in the task queue awaiting an eligible, healthy AMR to be allocated. |
| **`TRAVEL`** ($T_{\text{travel}}$) | $v_{\text{robot}} > 0$ while active | Time spent physically in motion between cells (heading to pickup or dropoff). |
| **`CONFLICT_WAIT`** ($T_{\text{conflict\_wait}}$) | $v=0$, reason: Yielding, Deadlock, or Peer Contention | Time spent stationary specifically due to multi-agent right-of-way resolution, yielding to higher-priority AMRs, or PIBT push chain delays. |
| **`NORMAL_WAIT`** ($T_{\text{normal\_wait}}$) | $v=0$, reason: Nominal wait / Hold | Time spent waiting when not in direct conflict with an active peer (e.g. holding for clearance). |
| **`REPLANNING`** ($T_{\text{replan}}$) | `RobotState.REPLANNING` | Time spent executing an on-the-fly Space-Time A* detour around an unexpected obstruction. |
| **`RECOVERY`** ($T_{\text{recovery}}$) | `RobotState.BLOCKED` or Failure handling | Time spent in failure backoff or awaiting station/aisle clearance after an external disturbance. |
| **`PICKUP`** ($T_{\text{pickup}}$) | Reached pickup station ($1\text{ tick}$) | Transfer interval at the inbound pickup station to load payload. |
| **`DELIVERY`** ($T_{\text{delivery}}$) | Reached dropoff station ($1\text{ tick}$) | Transfer interval at the outbound dropoff station to unload payload. |
| **`EXECUTION_OVERHEAD`** ($T_{\text{overhead}}$) | Remainder residual ($\le \Delta t$) | Discrete clock quantization and state transition residual ($\sum_i T_i + T_{\text{overhead}} \equiv T_{\text{total}}$). |

---

## 3. Non-Additive Diagnostic Telemetry

Independent of the additive time budget, the simulator records non-additive telemetry signals for root-cause bottleneck analysis:

- **`congestion_exposure`**: Time integral of corridor congestion along the AMR's occupied cells:
  $$\text{Exposure} = \sum_{t=t_{\text{assign}}}^{t_{\text{deliver}}} \text{Congestion}(p_{\text{robot}}(t)) \cdot \Delta t$$
- **`bottleneck_visits`**: Number of times the AMR crossed an identified shared bottleneck cell (e.g., $x=12, y \in \{5, 15\}$).
- **`conflicts_experienced`**: Count of discrete yielding or conflict resolution events encountered by the AMR during the task.
- **`replans_count`**: Count of Space-Time A* rerouting events triggered for the task.
- **`stops_count`**: Number of transitions from moving ($v > 0$) to stationary ($v = 0$).
- **`distance_traveled`**: Total grid distance traversed in meters (grid cells $\times 1.0\text{ m}$).
- **`turns_count`**: Number of 90-degree heading changes along the route.

---

## 4. Verification Protocol

During any diagnostic or benchmark run, the profiler validates:
$$\left| T_{\text{total}} - \sum_{k \in \text{Categories}} T_k \right| < 10^{-5}\text{ s}$$
Any violation raises an immediate assertion error in diagnostic mode.
