#!/usr/bin/env bash
# gate1_verify.sh — GATE 1 Verification Script
# Run: bash /mnt/c/Users/thega/PROJECTS/SIH\'26/docs/gate1_verify.sh

set -euo pipefail

PROJECT_PATH="/mnt/c/Users/thega/PROJECTS/SIH'26"

echo "============================================================"
echo " GATE 1: Ubuntu + WSL2 Environment Verification"
echo " $(date)"
echo "============================================================"
echo ""

echo "=== OS Release ==="
cat /etc/os-release
echo ""

echo "=== Architecture ==="
uname -m
echo ""

echo "=== Python ==="
python3 --version
echo ""

echo "=== Git ==="
git --version
echo ""

echo "=== Disk ==="
df -h /
echo ""

echo "=== RAM ==="
free -h
echo ""

echo "=== Network ==="
ping -c 2 archive.ubuntu.com 2>&1 | tail -4
echo ""

echo "=== Project Path ==="
if [ -d "$PROJECT_PATH" ]; then
    echo "[OK] Project accessible at $PROJECT_PATH"
    ls "$PROJECT_PATH" | head -10
else
    echo "[FAIL] Project NOT found at $PROJECT_PATH"
    exit 1
fi
echo ""

echo "=== ROS 2 Jazzy (if installed) ==="
if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
    echo "ROS_DISTRO=$ROS_DISTRO"
    ros2 --version 2>&1 || true
else
    echo "[NOT YET] ROS 2 Jazzy not installed"
fi
echo ""

echo "=== Gazebo Harmonic (if installed) ==="
if command -v gz &>/dev/null; then
    gz sim --version 2>&1 || true
else
    echo "[NOT YET] Gazebo Harmonic not installed"
fi
echo ""

echo "============================================================"
echo " GATE 1 COMPLETE"
echo "============================================================"
