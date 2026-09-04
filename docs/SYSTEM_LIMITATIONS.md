# System Limitations & Boundary Conditions (SIH26123)

## 1. Scope & Honest Technical Boundaries
In accordance with professional engineering integrity, this document explicitly details the operational assumptions, failure boundaries, and environmental constraints of the Edge-AI Distributed Fleet Coordination system.

---

## 2. Structural & Environmental Boundaries

### 2.1 Single-Width Dead-End Corridors
- **Condition**: A corridor segment with width $= 1\text{ cell}$ that terminates in a dead end.
- **Behavior**: If a higher-priority robot enters the dead end to deliver a task while a lower-priority robot is already inside, PIBT priority inheritance forces the lower-priority robot to reverse step-by-step out of the corridor to the nearest junction.
- **Limitation**: While safe and collision-free, this reversal increases waiting time and temporary congestion at the corridor entrance.
- **Mitigation**: Warehouse layout topology should enforce one-way traffic rules or designated turnout bays for single-width dead ends.

### 2.2 Discrete Grid Abstraction
- **Condition**: Spatial coordinates are represented as discrete $1.0\text{ m} \times 1.0\text{ m}$ grid cells.
- **Behavior**: Real-world AMRs operate in continuous $\mathbb{R}^2$ or $\text{SE}(2)$ space. Continuous swept bounding circles ($r = 0.4\text{ m}$) are verified at discrete increments.
- **Limitation**: Sub-grid trajectory deviations caused by wheel slip or mechanical drift are assumed to be compensated by low-level onboard PID/Pure Pursuit trajectory tracking controllers.

---

## 3. Communication & Network Boundaries

### 3.1 Sustained RF Blackout (> 10 Seconds)
- **Condition**: Complete loss of wireless communication across all peer-to-peer radio channels exceeding 10 seconds.
- **Behavior**: AMRs continue movement along their currently reserved Space-Time trajectory (up to $5\text{ steps}$ / $5.0\text{ s}$). Once the reservation horizon is exhausted and no peer heartbeats are received, the onboard Safety Supervisor transitions the AMR to a controlled deceleration STOP.
- **Limitation**: The system does not attempt blind unsynchronized traversal into unverified cross-aisles without radio confirmation.

### 3.2 High Packet Drop (> 60%) Under High Fleet Density
- **Condition**: Sustained packet loss exceeding 60% in a congested bottleneck with $> 4\text{ AMRs}$ within 2 meters.
- **Behavior**: Missing peer intentions lead to conservative yielding, resulting in higher average wait times as robots fail to confirm mutual right-of-way. Safety is strictly preserved (0 collisions), but task throughput temporarily degrades.

---

## 4. Algorithmic Scalability Boundaries

### 4.1 PIBT Completeness Under Extreme Clutter
- **Condition**: PIBT is an anytime greedy multi-agent path finding heuristic. In dense mazes with multiple interlocking cyclic dependencies, PIBT can occasionally oscillate if priorities are static.
- **Mitigation Implemented**: Dynamic priority escalation and the Wait-For-Graph cycle detector break oscillation within $\le 2\text{ timesteps}$ by forcing active Space-Time A\* waypoint detours.

### 4.2 Embedded Memory Footprint
- **Current Footprint**: 53.0 MB mean RAM, 54.0 MB peak RAM.
- **Boundary**: Suitable for micro-Linux edge devices (Raspberry Pi 4/5, Jetson Nano, industrial x86/ARM SBCs). Not suitable for bare-metal microcontrollers without dynamic memory (e.g., 32 KB RAM STM32/ESP32).
