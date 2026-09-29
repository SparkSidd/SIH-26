# SIH 2026 (SIH26123) — Video Demo Presentation Guide & Walkthrough
**Project**: AETHER — Edge-AI Distributed Autonomous Mobile Robot (AMR) Fleet Coordination  
**Theme**: Smart Automation / Robotics & Industrial IoT  
**Target Duration**: 3:00 Minutes  

---

## 1. Split-Screen Recording Setup (High Production Value)

For the most impressive submission video, judges love seeing **Cyber-Physical Verification** (the 3D simulation alongside the real-time Digital Twin):

```
+------------------------------------+------------------------------------+
|                                    |                                    |
|      GAZEBO 3D SIMULATION          |    AETHER DIGITAL TWIN CONTROL     |
|      (Physics Engine)              |    (Edge-AI Mission Control)       |
|                                    |                                    |
|  - 6 Differential-Drive AMRs       |  - Real-time P2P Mesh Telemetry    |
|  - Realistic Warehouse Aisles      |  - 0-Collision & Invariant HUD     |
|  - LiDAR Obstacle Detection        |  - Dynamic Hazard Injection        |
|                                    |  - 5-Stage Guided Evaluation Tour  |
|                                    |                                    |
+------------------------------------+------------------------------------+
|  [Win + Left Arrow]                |  [Win + Right Arrow]               |
+------------------------------------+------------------------------------+
```

### Quick Launch Instructions
1. **Gazebo is already running** in the background with the 6 AMRs. Snap its window to the **left half** (`Win + Left Arrow`).
2. Double-click [`run_video_demo.bat`](file:///c:/Users/thega/PROJECTS/SIH'26/run_video_demo.bat) in the project folder:
   - This starts the AETHER Mission Control server on port 8000.
   - Automatically opens your browser at `http://localhost:8000`.
3. Snap your browser window to the **right half** (`Win + Right Arrow`).
4. Press `Win + Alt + R` (Windows Game Bar) or use OBS to start recording!

---

## 2. Minute-by-Minute Video Script & Voiceover Guide

### ⏱️ [0:00 - 0:35] Introduction & Cyber-Physical Architecture
- **Action**: Both Gazebo and the Digital Twin are visible side-by-side. 
- **Voiceover**:
  > *"Respected judges, we are presenting our Edge-AI Distributed AMR Fleet Management system for Problem Statement **SIH26123**.  
  > In high-density modern warehouses, centralized dispatchers suffer from single-point bottlenecks and deadlocks when communication drops.  
  > On the left, we have our 6-AMR fleet running in the Gazebo physics simulation with differential drive dynamics and LiDAR.  
  > On the right is our AETHER Digital Twin Mission Control, streaming real-time telemetry from our decentralized edge coordination stack."*

---

### ⏱️ [0:35 - 1:15] Stage 1 & 2: Nominal Fleet Flow & Conflict Resolution
- **Action**: In the Digital Twin top bar, click **`⚡ SIH DEMO TOUR`** (or click **`Nominal Fleet`**).
- **Voiceover**:
  > *"Watch how all 6 AMRs operate completely decentralized. Each robot computes its own trajectories locally using our optimized PIBT (Priority-Inheritance Backtracking) algorithm in under **0.07 milliseconds**.  
  > When two robots approach an intersection—like AMR-01 and AMR-04 here—they negotiate right-of-way via peer-to-peer gossip without stopping or deadlocking.  
  > Across 200 empirical runs, our Wait-For-Graph cycle breaker mathematically guarantees **zero deadlocks** and **zero collisions**."*

---

### ⏱️ [1:15 - 2:05] Stage 3: Dynamic Hazard & Corridor Blockage Detour
- **Action**: In the Disruption Lab (left panel), click **`⛔ Block Aisle`** (or click **`Stage 3 Aisle Detour`**).
- **Visual**: A bright red hazard stripe appears in the central aisle on the digital twin with the alert banner `⛔ BLOCKED AISLE — DETOUR ACTIVE`.
- **Voiceover**:
  > *"Now, let's inject a real-world disturbance: an unexpected spill or fallen pallet blocking the central corridor.  
  > Notice the immediate reaction: the approaching AMRs detect the blockage via simulated LiDAR, update their local spatial world model, and broadcast the hazard across the P2P mesh.  
  > Instead of halting the fleet in a traffic jam, our algorithm dynamically reroutes the AMRs around adjacent aisles in real time, maintaining smooth throughput with zero human intervention."*

---

### ⏱️ [2:05 - 2:40] Stage 4: Hardware Fault & Peer Recovery
- **Action**: Click **`💥 Fail AMR`** (targeting R2) or click **`Stage 4 Robot Recovery`**.
- **Visual**: AMR-02 turns red with `⚠️ MOTOR STALL: REALLOCATING TASK`.
- **Voiceover**:
  > *"Next, we simulate a severe hardware failure—a sudden motor stall on AMR-02.  
  > The local world model detects the lack of progress within 100 milliseconds. The peer fleet coordinator immediately reclaims AMR-02's pending delivery order, reallocates it to the nearest operational robot, and updates navigation reservations so peer robots treat the disabled chassis as a static obstacle."*
- **Action**: Click **`🔧 Recover AMR`** to show smooth restoration.

---

### ⏱️ [2:40 - 3:00] Stage 5: Verified Benchmark Proof & Closing
- **Action**: Click **`📊 SCORECARD`** in the top bar.
- **Visual**: The 200-Run Scientific Benchmark modal pops up, displaying the verified metrics table.
- **Voiceover**:
  > *"To ensure rigorous engineering validation, we conducted an empirical 200-run benchmark across 10 stress scenarios:  
  > - **0 collisions** across all scenarios.  
  > - **+31.2% throughput speedup** over traditional stop-and-wait dispatchers.  
  > - **0.07 ms edge decision latency**.  
  > Our solution is fully compatible with ROS 2 Jazzy, Gazebo Sim, and real industrial AMRs. Thank you!"*

---

## 3. Quick Reference: Interactive Buttons During Video
| Button | Location | Visual Effect |
| :--- | :--- | :--- |
| **`⚡ SIH DEMO TOUR`** | Top Right Header | Launches the 5-stage automated tour with live on-screen judge insights |
| **`⛔ Block Aisle`** | Left Panel (Disruption Lab) | Injects blockage at (7, 10) & triggers dynamic detour |
| **`🧹 Clear All Blockages`** | Left Panel (Disruption Lab) | Restores aisles to nominal free flow |
| **`💥 Fail AMR`** | Left Panel (Disruption Lab) | Simulates motor stall on selected robot |
| **`🔧 Recover AMR`** | Left Panel (Disruption Lab) | Restores stalled robot to operational IDLE |
| **`📦 Demand Surge`** | Left Panel (Disruption Lab) | Bursts 5 new high-priority delivery orders |
| **`📊 SCORECARD`** | Top Right Header | Pops up the verified 200-run empirical metrics scorecard |
