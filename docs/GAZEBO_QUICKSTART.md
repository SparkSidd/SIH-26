# SIH26123 — Gazebo Harmonic Quickstart Guide
**Purpose**: Get from a fresh Ubuntu 24.04 WSL2 terminal to a running 6-AMR Gazebo simulation in the minimum number of steps.

---

## Prerequisites

Before this guide, the following must be done on **Windows** (Administrator PowerShell):

```powershell
wsl --install -d Ubuntu-24.04
# → Reboot when prompted
# → Create Linux username + password when Ubuntu opens
```

---

## Step 1: Run the install script

Open the Ubuntu 24.04 terminal and run:

```bash
bash /mnt/c/Users/thega/PROJECTS/SIH\'26/docs/install_ros_gazebo.sh
```

This takes **20–45 minutes** on first run. It installs:
- ROS 2 Jazzy
- Gazebo Harmonic
- ros_gz_bridge
- Creates `~/sih_ros_ws/`

---

## Step 2: Run smoke test

```bash
bash /mnt/c/Users/thega/PROJECTS/SIH\'26/docs/gazebo_smoke_test.sh
```

Expected: `ALL GATES PASSED`

---

## Step 3: Single-AMR smoke test (Gate 9)

In **two terminals**:

**Terminal 1** (launch):
```bash
source ~/.bashrc
ros2 launch ros2_integration single_amr.launch.py
```

**Terminal 2** (verify odom):
```bash
source ~/.bashrc
ros2 topic echo /R01/odom | head -20
```

**Terminal 3** (send manual cmd_vel):
```bash
source ~/.bashrc
# Drive forward
ros2 topic pub /R01/cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.5, y: 0, z: 0}, angular: {x: 0, y: 0, z: 0}}'
# Stop
ros2 topic pub /R01/cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.0, y: 0, z: 0}, angular: {x: 0, y: 0, z: 0}}'
```

---

## Step 4: Full 6-AMR fleet (Gate 11+)

```bash
source ~/.bashrc

# S1 — Open warehouse, 6 robots
ros2 launch ros2_integration amr_fleet.launch.py scenario:=S1

# S4 — Choke-point, 6 robots
ros2 launch ros2_integration amr_fleet.launch.py scenario:=S4

# S5 — Deadlock recovery
ros2 launch ros2_integration amr_fleet.launch.py scenario:=S5

# S8 — Haven retreat, congestion
ros2 launch ros2_integration amr_fleet.launch.py scenario:=S8
```

---

## Step 5: Check topic health

```bash
ros2 topic list           # Should show /R01/odom, /R01/scan, etc.
ros2 topic hz /R01/odom   # Should be ~30 Hz
ros2 topic hz /R01/scan   # Should be ~10 Hz
ros2 node list            # Should show /R01/amr_node etc.
```

---

## Step 6: View results

Results are saved automatically to:
```
/mnt/c/Users/thega/PROJECTS/SIH'26/results/gazebo/
```

---

## Useful Commands

```bash
# Check if Gazebo is running
gz topic -l

# Check Gazebo simulation time
gz topic -e -t /clock

# List robot entities
gz service -s /world/warehouse_s1/state

# Kill all ROS nodes
pkill -f ros2

# Kill Gazebo
pkill -f gz
```

---

## WSL2 Graphics Setup (if Gazebo GUI fails)

If the Gazebo GUI doesn't render, the WSL2 GPU driver may need updating:

```bash
# Check display
echo $DISPLAY  # Should be :0 or similar

# Install Mesa for software rendering fallback
sudo apt-get install -y mesa-utils libgl1-mesa-glx

# Test
glxgears  # Should show spinning gears

# If still no display, use headless mode
export GZ_HEADLESS=1
gz sim -r warehouse_s1.sdf --headless-rendering
```

---

## Checkpoint Reminder

```
CHECKPOINT_FINAL_PRE_GAZEBO (FROZEN):
  26.18% task-completion-time reduction
  77/77 original tests
  25/25 ROS/SIL tests
  102/102 total

Gazebo validation is SEPARATE from the benchmark.
Do NOT report Gazebo results as the 26.18% result.
```
