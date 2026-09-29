#!/usr/bin/env bash
# =============================================================================
# install_ros_gazebo.sh
# SIH26123 — Full ROS 2 Jazzy + Gazebo Harmonic installation script
# Run ONCE inside Ubuntu 24.04 WSL2 after first login.
#
# Usage:
#   chmod +x /mnt/c/Users/thega/PROJECTS/SIH\'26/docs/install_ros_gazebo.sh
#   bash /mnt/c/Users/thega/PROJECTS/SIH\'26/docs/install_ros_gazebo.sh
#
# Estimated time: 20-45 minutes (depending on internet speed)
# Disk required:  ~6 GB
# =============================================================================
set -eo pipefail

LOG_FILE="$HOME/sih26123_install.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================"
echo " SIH26123 ROS 2 + Gazebo Harmonic Install"
echo " Started: $(date)"
echo "============================================================"

# ── Helper ───────────────────────────────────────────────────────────────────
check_cmd() {
    command -v "$1" &>/dev/null && echo "[OK] $1 found" || echo "[MISSING] $1"
}

# ── 0. Verify Ubuntu 24.04 ───────────────────────────────────────────────────
echo ""
echo "=== STEP 0: Verify Ubuntu version ==="
. /etc/os-release
echo "Distro: $NAME $VERSION_ID"
if [[ "$VERSION_ID" != "24.04" ]]; then
    echo "ERROR: Expected Ubuntu 24.04, got $VERSION_ID. Abort."
    exit 1
fi
echo "[GATE 1] Ubuntu 24.04 confirmed."

export DEBIAN_FRONTEND=noninteractive

# ── 1. System update ─────────────────────────────────────────────────────────
echo ""
echo "=== STEP 1: System update ==="
sudo apt-get update -q
sudo apt-get install -y -q curl gnupg2 lsb-release software-properties-common git build-essential
sudo add-apt-repository -y universe
sudo apt-get update -q
sudo apt-get install -y -q \
    python3-pip python3-numpy python3-scipy python3-yaml \
    python3-colcon-common-extensions

# ── 2. Locale ────────────────────────────────────────────────────────────────
echo ""
echo "=== STEP 2: Locale setup ==="
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
echo "[OK] Locale set to en_US.UTF-8"

# ── 3. ROS 2 Jazzy ───────────────────────────────────────────────────────────
echo ""
echo "=== STEP 3: Install ROS 2 Jazzy ==="

# Add ROS 2 apt key
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc \
  | sudo gpg --dearmor --yes -o /usr/share/keyrings/ros-archive-keyring.gpg

# Add ROS 2 repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt-get update -q
sudo apt-get install -y -q ros-jazzy-desktop

echo "[GATE 2] ROS 2 Jazzy installed."

# Verify
source /opt/ros/jazzy/setup.bash
echo "ROS_DISTRO=$ROS_DISTRO"
echo "ROS 2 ready."

# ── 4. Gazebo Harmonic ───────────────────────────────────────────────────────
echo ""
echo "=== STEP 4: Install Gazebo Harmonic ==="

# Add OSRF Gazebo apt key
sudo curl -sSL https://packages.osrfoundation.org/gazebo.gpg \
  | sudo gpg --dearmor --yes -o /usr/share/keyrings/gazebo-archive-keyring.gpg

# Add Gazebo repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gazebo-archive-keyring.gpg] \
  http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

sudo apt-get update -q
sudo apt-get install -y -q gz-harmonic

echo "[GATE 3] Gazebo Harmonic installed."

# Verify
gz sim --version

# ── 5. ROS-Gazebo bridge packages ─────────────────────────────────────────────
echo ""
echo "=== STEP 5: Install ros_gz packages ==="
sudo apt-get install -y -q \
    ros-jazzy-ros-gz \
    ros-jazzy-ros-gz-bridge \
    ros-jazzy-ros-gz-sim \
    ros-jazzy-ros-gz-image \
    ros-jazzy-ros-gz-interfaces

echo "[GATE 4] ros_gz packages installed."

# ── 6. Python dependencies ────────────────────────────────────────────────────
echo ""
echo "=== STEP 6: Python dependencies ==="
sudo apt-get install -y -q python3-numpy python3-scipy python3-yaml python3-pytest \
    python3-psutil python3-matplotlib python3-pandas
pip3 install --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu

# ── 7. ROS workspace setup ────────────────────────────────────────────────────
echo ""
echo "=== STEP 7: ROS 2 workspace setup ==="

WORKSPACE="$HOME/sih_ros_ws"
PROJECT_PATH="/mnt/c/Users/thega/PROJECTS/SIH'26"

mkdir -p "$WORKSPACE/src"

# Symlink the project directory into the workspace
if [ ! -e "$WORKSPACE/src/ros2_integration" ]; then
    ln -s "$PROJECT_PATH/ros2_integration" "$WORKSPACE/src/ros2_integration"
    echo "[OK] Symlinked ros2_integration into workspace"
fi

# Set up PYTHONPATH so the frozen coordinator is importable from WSL
PYTHONPATH_LINE="export PYTHONPATH=\"$PROJECT_PATH:\$PYTHONPATH\""
if ! grep -qF "$PYTHONPATH_LINE" "$HOME/.bashrc"; then
    echo "$PYTHONPATH_LINE" >> "$HOME/.bashrc"
    echo "[OK] Added project to PYTHONPATH in .bashrc"
fi

# Source ROS 2 automatically
ROS_SOURCE_LINE="source /opt/ros/jazzy/setup.bash"
if ! grep -qF "$ROS_SOURCE_LINE" "$HOME/.bashrc"; then
    echo "$ROS_SOURCE_LINE" >> "$HOME/.bashrc"
    echo "[OK] Added ROS 2 source to .bashrc"
fi

# ── 8. Build the workspace ────────────────────────────────────────────────────
echo ""
echo "=== STEP 8: Build ROS 2 workspace ==="
source /opt/ros/jazzy/setup.bash
export PYTHONPATH="$PROJECT_PATH:${PYTHONPATH:-}"

cd "$WORKSPACE"
colcon build --symlink-install --packages-select ros2_integration \
    --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 || {
    echo "[WARN] colcon build had issues — check above. Continuing with smoke tests."
}

# Source the workspace
WORKSPACE_SOURCE="source $WORKSPACE/install/setup.bash"
if ! grep -qF "$WORKSPACE_SOURCE" "$HOME/.bashrc"; then
    echo "$WORKSPACE_SOURCE" >> "$HOME/.bashrc"
fi
source "$WORKSPACE/install/setup.bash" 2>/dev/null || true

# ── 9. Smoke tests ────────────────────────────────────────────────────────────
echo ""
echo "=== STEP 9: Smoke tests ==="

echo "--- ROS 2 ---"
ros2 pkg list | grep -E "ros_gz|geometry_msgs|nav_msgs|sensor_msgs" | head -20

echo ""
echo "--- Gazebo Harmonic ---"
gz sim --version

echo ""
echo "--- Python project import ---"
cd "$PROJECT_PATH"
python3 -c "from coordination.coordinator import FleetCoordinator; print('[OK] FleetCoordinator importable')"
python3 -c "from ros2_integration.amr_node import AMRNode; print('[OK] AMRNode importable')"

echo ""
echo "============================================================"
echo " INSTALLATION COMPLETE"
echo " Log: $LOG_FILE"
echo " Next step: Run smoke test script"
echo "   bash $PROJECT_PATH/docs/gazebo_smoke_test.sh"
echo "============================================================"
echo " Finished: $(date)"
