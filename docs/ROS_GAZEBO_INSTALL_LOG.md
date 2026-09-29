# ROS 2 + Gazebo Harmonic Installation Log
**Project**: SIH26123 — Edge-AI Distributed Fleet Coordination  
**Target**: WSL2 → Ubuntu 24.04 → ROS 2 Jazzy → Gazebo Harmonic  
**Log Created**: 2026-09-12

---

## GATE 1: Environment Verification

**Date/Time**: 2026-09-12T02:26 IST  
**Status**: ✅ PASSED

### Observed Values (Actual — Not Assumed)

| Property | Observed Value |
|---|---|
| **OS** | Ubuntu 24.04.4 LTS (Noble Numbat) |
| **VERSION_ID** | 24.04 |
| **Architecture** | x86_64 |
| **Python** | Python 3.12.3 |
| **git** | git version 2.43.0 |
| **WSL Version** | 2 (Ubuntu-24.04 Running, Version 2) |
| **Total RAM** | 7.6 GiB |
| **Available RAM** | 7.1 GiB |
| **Disk (/)** | 1007G total, 1.3G used, **955G free** |
| **Network** | archive.ubuntu.com: 2/2 packets received, 0% loss, ~290ms RTT |

### Windows Host
| Property | Value |
|---|---|
| **Host OS** | Windows 11 |
| **WSL Distribution** | Ubuntu-24.04 |
| **WSL Version** | 2 |
| **Project on Windows** | `C:\Users\thega\PROJECTS\SIH'26` |
| **Project in WSL** | `/mnt/c/Users/thega/PROJECTS/SIH'26` |

### Gate 1 Conclusion
- Ubuntu 24.04 ✅
- x86_64 ✅
- WSL2 ✅
- RAM: 7.6 GiB ✅ (sufficient for 1–6 robot Gazebo)
- Disk: 955 GB ✅ (far more than 6 GB required)
- Network: 0% packet loss ✅ (safe to install packages)

---

## GATE 2: ROS 2 Jazzy Installation

**Status**: 🔄 IN PROGRESS

### Installation Script
Script used: `docs/install_ros_gazebo.sh`  
Log file: `~/sih26123_install.log` (inside WSL2)

### Expected Packages
- `ros-jazzy-desktop`
- `python3-colcon-common-extensions`
- `python3-pip`
- Build tools: `curl gnupg2 lsb-release git build-essential`

> **Update this section after install completes with actual version strings from:**
> ```
> ros2 --version
> echo $ROS_DISTRO
> ```

---

## GATE 3: Gazebo Harmonic Installation

**Status**: ⏳ PENDING (after Gate 2)

### Expected Version
Gazebo Harmonic 8.x.x (gz-harmonic package)

> **Update this section after install with:**
> ```
> gz sim --version
> ```

---

## GATE 4: ros_gz Bridge Installation

**Status**: ⏳ PENDING (after Gate 3)

### Expected Packages
- `ros-jazzy-ros-gz`
- `ros-jazzy-ros-gz-bridge`
- `ros-jazzy-ros-gz-sim`
- `ros-jazzy-ros-gz-image`
- `ros-jazzy-ros-gz-sensor-bridges`

> **Update with:**
> ```
> ros2 pkg list | grep ros_gz
> ```

---

## Workspace Strategy

**Source location**: `/mnt/c/Users/thega/PROJECTS/SIH'26` (Windows filesystem, accessed via WSL mnt)

**ROS workspace**: `~/sih_ros_ws/` (Linux home, inside WSL)

**Strategy**: 
- `ros2_integration/` is **symlinked** from `/mnt/c/.../SIH'26/ros2_integration` into `~/sih_ros_ws/src/ros2_integration`
- The frozen Python coordination stack is added to `PYTHONPATH` pointing at the Windows filesystem
- No copies of the project are made; the symlink keeps a single source of truth
- `colcon build --symlink-install` is used so changes in the source are immediately reflected

**PYTHONPATH addition to .bashrc**:
```bash
export PYTHONPATH="/mnt/c/Users/thega/PROJECTS/SIH'26:$PYTHONPATH"
```

---

## Known Issues / Resolutions

| Issue | Resolution |
|---|---|
| PowerShell apostrophe in path `SIH'26` | Use bash heredoc pattern for all WSL calls; paths work fine inside WSL bash |
| GPU/WSLg rendering (unknown) | To be diagnosed at Gate 3 — will test headless if GUI fails |

---

## Installation Command History

```bash
# GATE 1: Verified manually via WSL2 commands (2026-09-12)
# Results: All checks passed — see table above

# GATE 2: Install ROS 2 Jazzy (to be run)
# bash /mnt/c/Users/thega/PROJECTS/SIH'26/docs/install_ros_gazebo.sh

# GATE 3-4: Handled by same install script (Steps 4-5)
```

---

*This document is updated after each gate completes.*  
*Last updated: 2026-09-12 — Gate 1 PASSED, waiting for Gate 2.*
