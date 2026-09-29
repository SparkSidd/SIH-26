# Gazebo Environment Audit
**Project**: SIH26123 — Edge-AI Distributed Fleet Coordination  
**Audit Date**: 2026-09-12  
**Auditor**: Automated (Antigravity agent)

---

## Host Environment

| Property | Value |
|---|---|
| **OS** | Windows 11 Home Single Language |
| **Windows Version** | 25H2 |
| **Build Number** | 26200 |
| **CPU** | 12th Gen Intel Core i5-12500H |
| **CPU Cores** | 12 physical / 16 logical |
| **Total RAM** | 16,078 MB (~15.7 GB) |
| **Available RAM** | ~2,686 MB (at audit time) |
| **Disk (C:) Total** | ~476 GB (512,110,190,592 bytes) |
| **Disk (C:) Used** | 329.7 GB |
| **Disk (C:) Free** | **145.7 GB** ✓ sufficient |

---

## Virtualization Status

| Property | Value |
|---|---|
| **Hypervisor Present** | `False` (WSL2 not yet active) |
| **VirtualizationFirmwareEnabled** | `True` ✓ |
| **VMMonitorModeExtensions** | `True` ✓ |
| **Hyper-V Requirements (systeminfo)** | VM Monitor Mode Extensions: Yes |
| **BIOS** | American Megatrends X1502ZA.308, 2022-12-23 |

**Conclusion**: Hardware virtualization is fully supported and enabled in firmware.
WSL2 will work once the Windows features are enabled.

---

## WSL2 Status

| Property | Value |
|---|---|
| **WSL installed** | **NO** |
| **WSL2 feature enabled** | Unknown (requires Admin elevation to query via DISM) |
| **VirtualMachinePlatform** | Unknown (requires Admin elevation) |
| **Ubuntu installed** | No |
| **wsl --status** | "The Windows Subsystem for Linux is not installed" |

**Root cause of `wsl --install` failure**: The current PowerShell session is **not elevated (not Administrator)**. The `wsl --install` command requires Administrator privileges to enable Windows optional features.

---

## WSL2 Installation Requirements

- ✅ Windows 11 (build 26200) — fully supports WSL2 and `wsl --install`
- ✅ Hardware virtualization enabled in BIOS
- ✅ 145.7 GB free disk space (requirement: ≥20 GB)
- ✅ 15.7 GB RAM (requirement: ≥8 GB)
- ⚠️ **Administrator session required** to run `wsl --install`

---

## Installation Path (per validated gates)

```
GATE 0: WSL2 installed          → PENDING (needs Admin PowerShell)
GATE 1: Ubuntu 24.04 running    → PENDING
GATE 2: ROS 2 Jazzy working     → PENDING
GATE 3: Gazebo Harmonic working → PENDING
GATE 4: ros_gz_bridge working   → PENDING
...
```

---

## BLOCKER: Requires Administrator PowerShell

The agent's current PowerShell session is **non-elevated**.

`wsl --install` cannot proceed without elevation. This is a Windows security boundary — it cannot be circumvented by the agent.

### Required Action (Manual)

The user must run the following command in an **Administrator PowerShell**:

```powershell
wsl --install -d Ubuntu-24.04
```

This single command:
1. Enables `Microsoft-Windows-Subsystem-Linux` Windows feature
2. Enables `VirtualMachinePlatform` Windows feature  
3. Downloads and installs the WSL2 Linux kernel
4. Downloads and installs Ubuntu 24.04 LTS

**Estimated time**: 5–15 minutes (depends on internet speed)

**After the command completes**, a reboot is typically required.

After reboot, Ubuntu 24.04 will open automatically and ask to create a Linux username + password. Then the agent can continue from inside WSL2.

---

## Strategy: Structured Scripted Installation

Rather than manual step-by-step commands, all post-WSL2 installation steps
(ROS 2 Jazzy, Gazebo Harmonic, ros_gz_bridge, workspace setup) are packaged
as a single script the user runs once inside Ubuntu:

```
docs/install_ros_gazebo.sh
```

The agent will prepare this script now so it is ready immediately after
the user completes the WSL2 + Ubuntu step.

---

## Disk Space Estimate

| Component | Size |
|---|---|
| WSL2 Linux kernel | ~100 MB |
| Ubuntu 24.04 base | ~1.5 GB |
| ROS 2 Jazzy desktop-full | ~2.5 GB |
| Gazebo Harmonic + ros_gz | ~1.5 GB |
| Python deps + workspace | ~500 MB |
| **Total estimate** | **~6 GB** |

Available: **145.7 GB** — more than sufficient.

---

## Summary

| Check | Status |
|---|---|
| Windows 11 compatible | ✅ |
| Hardware virtualization | ✅ |
| RAM sufficient | ✅ |
| Disk sufficient | ✅ |
| WSL2 installed | ❌ (needs Admin PowerShell) |
| Ubuntu 24.04 | ❌ (needs WSL2 first) |
| ROS 2 Jazzy | ❌ (needs Ubuntu) |
| Gazebo Harmonic | ❌ (needs ROS 2) |

**Next action**: User runs `wsl --install -d Ubuntu-24.04` in Administrator PowerShell, then reboots.
