# Diagnostic Parity & Benchmark Reconciliation Report (SIH26123)

## 1. Executive Summary

This investigation resolves the apparent discrepancy between the historical benchmark numbers cited in `docs/RESULTS.md` ($S_1: 10.28\text{ s} \to 8.32\text{ s} = +19.01\%$, $S_8: 9.88\text{ s} \to 8.00\text{ s} = +18.99\%$) and the recent single-seed ($42$) diagnostic runs ($S_1: 7.50\text{ s} \to 10.73\text{ s}$, $S_8: 7.18\text{ s} \to 11.88\text{ s}$).

### Key Parity Verification
Under controlled, identical execution ($N=350$ steps, 6 AMRs, discrete grid $\Delta t=0.1\text{ s}$, seed 42):
- **Official Auditor (`SIHMetricsAuditor`) vs. Direct Simulation (`BaselineRunner.get_simulation`)**:
  - **$S_0$**: Auditor = $6.96\text{ s}$ / $6.17\text{ s}$ vs. Direct = $6.96\text{ s}$ / $6.17\text{ s}$ (**Exact Match**)
  - **$S_1$**: Auditor = $7.50\text{ s}$ / $10.73\text{ s}$ vs. Direct = $7.50\text{ s}$ / $10.73\text{ s}$ (**Exact Match**)
  - **$S_6$**: Auditor = $9.16\text{ s}$ / $7.39\text{ s}$ vs. Direct = $9.16\text{ s}$ / $7.39\text{ s}$ (**Exact Match**)
  - **$S_8$**: Auditor = $7.18\text{ s}$ / $11.88\text{ s}$ vs. Direct = $7.18\text{ s}$ / $11.88\text{ s}$ (**Exact Match**)

There is **zero discrepancy** between the official auditor mechanism and the direct simulation harness.

---

## 2. Root Cause of the Discrepancy

Two distinct factors created the apparent contradiction:

### Factor A: Multi-Seed Scenario Means vs. Single-Seed 42 Outcomes
- The values in `docs/RESULTS.md` ($10.28\text{ s}$ and $8.32\text{ s}$) were **10-seed paired arithmetic means** across seeds `[42, 101, 202, 303, 404, 505, 606, 707, 808, 909]`.
- In contrast, the diagnostic profiler was executed exclusively on **Seed 42**.

### Factor B: Codebase Drift Post-Commit `25df37f`
- In commit `25df37f` (which produced the initial $12.06\%$ aggregate report), PIBT and A* operated without hardcoded directional bias.
- Subsequent experimental commits and working-tree modifications introduced `preferred_directions` into `coordination/coordinator.py`, `planning/pibt.py`, and `planning/astar.py`:
  - Corridors $y \in (3, 7, 11, 15)$ were assigned Eastbound $(+1, 0)$.
  - Corridors $y \in (5, 9, 13, 17)$ were assigned Westbound $(-1, 0)$.
- In `choke_point` layouts ($S_1$ and $S_8$), the dividing wall at $x=12$ has **only two single-cell passages**: $y=5$ and $y=15$.
- Because $y=15$ was forced Eastbound and $y=5$ was forced Westbound, returning empty robots or outbound AMRs heading to pick up packages were penalized or forced into extreme detours whenever moving against the assigned direction, causing severe queuing at the two single cells.
- Furthermore, `_generate_manhattan_path` in `FleetAwareTaskAllocator` generated rectilinear paths straight through the dividing wall at $x=12$, skewing ETAs and ignoring the choke bottleneck.

---

## 3. Configuration & Metric Definitions

Both runners are now strictly verified to share identical specifications:

| Parameter | Official Benchmark Runner | Diagnostic Runner | Status |
| :--- | :--- | :--- | :--- |
| **Grid Geometry** | 25 × 20 grid (`layout_type`) | 25 × 20 grid (`layout_type`) | Identical |
| **Fleet Size** | 6 AMRs ($v_{\text{nom}} = 1.0\text{ m/s}$) | 6 AMRs ($v_{\text{nom}} = 1.0\text{ m/s}$) | Identical |
| **Simulation Step** | $\Delta t = 0.1\text{ s}$, 350 steps ($35.0\text{ s}$ sim time) | $\Delta t = 0.1\text{ s}$, 350 steps ($35.0\text{ s}$ sim time) | Identical |
| **Task Metric** | `t.total_completion_duration` = $t_{\text{delivery}} - t_{\text{creation}}$ | `t.total_completion_duration` = $t_{\text{delivery}} - t_{\text{creation}}$ | Identical |
| **Averaging** | $\frac{1}{N}\sum_{i=1}^N \text{duration}_i$ over completed tasks | $\frac{1}{N}\sum_{i=1}^N \text{duration}_i$ over completed tasks | Identical |

---

## 4. Corrected Diagnostic Procedure

1. **Dual Verification**: Whenever reporting diagnostic results, report both the **single-seed diagnostic breakdown** and the **10-seed paired scenario mean**.
2. **True Additive Decomposition**: The profiler must separate exclusive state intervals (Assignment, Travel, Conflict Wait, Normal Wait, Replanning, Station Handover) from non-additive telemetry (Congestion Index, Message Count, WFG cycle count).
3. **Reference Anchoring**: Every experiment must explicitly state its baseline git commit checkpoint (anchored to `25df37f` or the frozen baseline).
