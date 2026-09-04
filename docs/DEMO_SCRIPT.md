# SIH26123 Judge Demonstration Script & Live Telemetry Walkthrough

## Overview
This document guides the live 5-minute presentation for the SIH evaluators. The demonstration utilizes the built-in **Digital Twin Web Dashboard** (`http://localhost:8080`) with the dedicated **Judge Presentation Mode**.

---

## 1. Preparation Checklist (T-minus 2 Minutes)
1. Verify web server is active:
   ```bash
   python main.py --web --port 8080
   ```
2. Open browser at `http://localhost:8080`.
3. Press `P` on keyboard or click **"PRESENTATION MODE"** in the top bar to display the live judge presentation telemetry modal.
4. Set simulation speed to `1x` or `2x`.

---

## 2. 5-Minute Stage-by-Stage Pitch & Actions

### Minute 1: The Problem & Architecture (Nominal Flow)
- **Visual**: Default Scenario $S_0$ running. AMRs 0–5 picking up and delivering payloads smoothly.
- **Narrative**:
  > *"Respected Judges, centralized warehouse fleet managers suffer from single-point-of-failure bottlenecks and exponential planning latency when scaling. We present an Edge-AI Decentralized Fleet Coordination System running on 6 AMRs. Notice the bottom telemetry: each robot runs local PIBT planning in under 0.15 milliseconds with zero centralized orchestration."*
- **UI Highlight**: Point out **Fleet Mode: LOCAL**, **P95 Latency: < 0.2 ms**, and the 2.5D visual rack grid.

### Minute 2: Congestion & Dynamic Priority Inheritance ($S_1$)
- **Action**: Select **"S1_HIGH_CONGESTION"** from the Scenario dropdown, or click **"Inject Bottleneck"**.
- **Narrative**:
  > *"When 24 tasks concentrate in the central corridor, traditional Stop-and-Wait algorithms cause cascading freezes. Watch our adaptive coordination escalate from LOCAL to NEIGHBOR mode. Robots negotiate right-of-way peer-to-peer using Priority Inheritance Backtracking. Notice that higher-priority loaded robots retain smooth flow while unloaded robots yield without stalling the aisle."*
- **UI Highlight**: Show the yellow/red corridor heatmap overlay and the Wait-For-Graph (WFG) tab remaining cycle-free.

### Minute 3: Real-Time Dynamic Corridor Blockage & Rerouting ($S_4$)
- **Action**: Click any corridor cell on the canvas to place a physical blockage barrier, or load scenario **$S_4$**.
- **Narrative**:
  > *"In real factories, a dropped pallet or forklift suddenly blocks an aisle. Watch AMR_01 encounter this blockage. Within one timestep, it detects the unreachable waypoint, marks the cell, and executes a Space-Time A* detour through the adjacent aisle. Notice it does not blindly stop or cause a gridlock behind it."*
- **UI Highlight**: Show the blinking red blockage indicator, the yellow waypoint detour path line, and the on-canvas alert notification.

### Minute 4: AMR Hardware Failure & In-Flight Task Reclaim ($S_5$)
- **Action**: Click on AMR_02 to inject a motor failure, or load scenario **$S_5$**.
- **Narrative**:
  > *"Now observe hardware failure resilience. AMR_02 is halted mid-transit. The peer mesh observes three missing heartbeats. Its in-flight task is immediately reclaimed by our decentralized auction supervisor and reassigned to AMR_04. The payload is successfully delivered with zero human intervention and zero deadlocks."*
- **UI Highlight**: AMR_02 turns red (FAULTED), its task is re-assigned, and AMR_04 transitions to pick up the orphaned load.

### Minute 5: Empirical Rigor & PPT Defense
- **Action**: Open the **"BASELINE VS PROPOSED"** tab at the bottom drawer.
- **Narrative**:
  > *"We validated this system across 200 fresh multi-seed simulation runs across 10 distinct disturbance scenarios. Our system achieves zero inter-robot collisions, a 12.1% overall reduction in task completion time—reaching 19.0% in congested corridors and up to 43.2% in peak disruption runs—all while consuming under 54 MB of edge RAM. Every single metric you see is fully reproducible via our automated benchmark suite."*
