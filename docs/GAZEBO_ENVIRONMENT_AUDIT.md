# Gazebo Environment Audit
**Project**: SIH26123 — Edge-AI Distributed Fleet Coordination for AMRs  
**Date**: 2026-09-12  
**Status**: BLOCKER IDENTIFIED → ALTERNATIVE PATH SELECTED

---

## 1. Host System

| Property | Value |
|---|---|
| OS | Windows 10 Home Single Language (Version 2009 / 21H2) |
| Architecture | 64-bit |
| CPU | 12th Gen Intel Core i5-12500H |
| Python | 3.13.4 |
| Virtualization in Firmware | ✅ Yes |
| Hyper-V (VBS) | ❌ Not enabled |
| WSL2 | ❌ Not installed |
| ROS 2 (native Windows) | ❌ Not found |
| Gazebo Harmonic | ❌ Not found |
| `rclpy` pip package | ❌ Not found |

---

## 2. Blocker Analysis

### 2.1 WSL2 Not Installed

```
wsl --list --verbose
ERROR: The Windows Subsystem for Linux is not installed.
```

WSL2 is the **primary path** for running ROS 2 Jazzy + Gazebo Harmonic on Windows 10.
Without it, the original plan (install Ubuntu 24.04 on WSL2 → install ROS 2 Jazzy →
install Gazebo Harmonic → run gz sim) **cannot execute as written**.

### 2.2 Windows 10 Home — Hyper-V Limitation

Windows 10 Home does not support full Hyper-V. While virtualization is enabled in
firmware and WSL2 uses its own virtualisation platform (distinct from Hyper-V Pro),
enabling WSL2 on Home **does require admin/BIOS changes** and a store installation.
This is a one-time setup action that requires user consent, not an automated step.

### 2.3 ROS 2 Native Windows — Not Viable

ROS 2 Jazzy has official Windows binary releases but:
- Only supports Windows 10/11 **Pro or Enterprise** for Gazebo Harmonic GPU rendering.
- Gazebo Harmonic has **no official Windows installer** as of its stable release.
- `rclpy` would need to be built from source on Windows against Visual Studio 2022.

### 2.4 Docker Desktop — Not Verified

Docker Desktop with Linux containers could theoretically run a ROS 2 + headless
Gazebo container. Not currently installed. Would require WSL2 backend anyway.

---

## 3. Viable Paths Forward

| Path | Viability | Effort | Notes |
|---|---|---|---|
| **A. Enable WSL2 + Install ROS 2 + Gazebo** | ✅ Best | High (one-time) | Requires admin; ~3-5 GB download |
| **B. Docker Desktop (Linux containers)** | ✅ Good | Medium | Requires WSL2 as backend anyway |
| **C. ROS 2 Native Windows build** | ⚠️ Partial | Very High | No Gazebo Harmonic support |
| **D. Gazebo standalone web sim (gz-web / WebAssembly)** | ⚠️ Limited | Medium | No ROS bridge |
| **E. Hardware-in-loop on Linux machine** | ✅ Good | External | Requires separate device |
| **F. Gazebo-absent validation (Software-in-Loop)** | ✅ Pragmatic | Low | Use existing Python sim as SIL |

---

## 4. Selected Strategy: Software-in-the-Loop (SIL) + WSL2 Setup Guide

Given the constraints of the current environment, we adopt a **two-track approach**:

### Track 1 — Immediate (SIL Validation, no Gazebo required)
Implement the **full ROS 2 adapter layer** in Python using mock ROS interfaces:
- `AMRNode` class with correct ROS 2 API signatures (rclpy-compatible)
- `cmd_vel`, `odom`, `scan`, `imu` topic handling with type stubs
- Integration harness that drives the frozen coordination stack through the adapter
- Validates that the adapter architecture is correct before real ROS 2 deployment

This produces **real, testable, ROS-2-compatible code** that runs in the existing
Python environment without WSL2 or rclpy installed.

### Track 2 — Deferred (WSL2 + Gazebo Harmonic, user-triggered)
Provide a step-by-step WSL2 + ROS 2 Jazzy + Gazebo Harmonic installation guide
(`docs/WSL2_SETUP_GUIDE.md`) so that once the user enables WSL2, the same adapter
code drops in and runs against real Gazebo with zero changes.

---

## 5. What the SIL Track Produces

1. **`ros2_integration/amr_node.py`** — Full `AMRNode(rclpy.Node)` class with:
   - `/robot_id/cmd_vel` publisher (Twist)
   - `/robot_id/odom` subscriber (Odometry)
   - `/robot_id/scan` subscriber (LaserScan)
   - P2P belief sync topic
   - Coordination stack integration (frozen PIBT + FleetAware allocator)

2. **`ros2_integration/fleet_launcher.py`** — Launch 1–6 AMR nodes, run a scenario,
   collect timing and safety metrics, report pass/fail.

3. **`ros2_integration/mock_ros/`** — Thin Python stubs for `rclpy`, `geometry_msgs`,
   `nav_msgs`, `sensor_msgs` that match the real ROS 2 API surface exactly. When
   `rclpy` is not installed, the stubs transparently substitute, making the code
   testable on Windows without WSL2.

4. **`ros2_integration/launch/`** — ROS 2 launch files (`.py` format) ready to use
   directly in a real ROS 2 Jazzy workspace.

5. **`tests/test_ros2_adapter.py`** — Integration tests for the adapter layer covering:
   - Single AMR node lifecycle
   - cmd_vel dispatch correctness
   - Odom feedback loop
   - 6-AMR fleet coordination parity with deterministic Python sim

6. **`docs/WSL2_SETUP_GUIDE.md`** — Step-by-step guide to enable WSL2, install
   Ubuntu 24.04, ROS 2 Jazzy, and Gazebo Harmonic.

---

## 6. Scenario Parity Targets

The following scenarios from the frozen benchmark must be matched in the adapter layer:

| Scenario | AMRs | Key Validation |
|---|---|---|
| S1 | 4 | Basic navigation, no choke-points |
| S4 | 6 | Choke-point avoidance |
| S5 | 6 | Deadlock recovery |
| S8 | 6 | Haven retreat under congestion |

Pass criteria (SIL): all 4 scenarios complete with 0 collisions, 0 deadlocks,
task completion rate = 100%.

---

## 7. Next Actions

- [ ] Create `ros2_integration/` directory structure
- [ ] Implement `mock_ros/` stubs (rclpy, message types)
- [ ] Implement `AMRNode` adapter
- [ ] Implement `fleet_launcher.py`
- [ ] Implement ROS 2 launch files
- [ ] Write `tests/test_ros2_adapter.py`
- [ ] Write `docs/WSL2_SETUP_GUIDE.md`
- [ ] Run adapter tests and confirm parity with Python sim
- [ ] Write `docs/GAZEBO_INTEGRATION_REPORT.md`
