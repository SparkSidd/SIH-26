#!/usr/bin/env bash
# =============================================================================
# run_as_user.sh — To be executed INSIDE the Ubuntu 24.04 WSL2 terminal
#                  by user "siddharth"
#
# SIH26123 — ROS 2 Jazzy + Gazebo Harmonic Full Installer
#
# HOW TO RUN:
#   1. Open Ubuntu 24.04 (from Start Menu or Windows Terminal)
#   2. You should see:  siddharth@hostname:~$
#   3. Copy and paste this single command:
#
#      bash /mnt/c/Users/thega/PROJECTS/SIH\'26/docs/install_ros_gazebo.sh
#
#   OR if the apostrophe causes issues, use:
#
#      cd ~ && bash install_ros_gazebo.sh
#
#      (The file was copied there already by the Antigravity agent)
#
# EXPECTED TIME: 20-45 minutes
# DISK REQUIRED: ~6 GB (you have 955 GB free)
#
# The script will install:
#   - ROS 2 Jazzy (ros-jazzy-desktop)
#   - Gazebo Harmonic (gz-harmonic)
#   - ros_gz_bridge packages
#   - Python colcon build tools
#   - Workspace setup at ~/sih_ros_ws/
# =============================================================================

echo "This file is a README — run the commands above directly."
