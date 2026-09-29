@echo off
REM ======================================================================
REM   SIH26123 — GAZEBO + ROS 2 PHYSICAL FLEET COORDINATION LAUNCHER
REM   Smart Warehouse Multi-AMR Decentralized Planning & Verification
REM ======================================================================
title SIH26123 - Gazebo Multi-AMR Fleet Simulation

set SCENARIO=%1
if "%SCENARIO%"=="" set SCENARIO=LIVE_DEMO

echo ======================================================================
echo   SIH 2026 (SIH26123) - GAZEBO ROBOTICS SIMULATION & VALIDATION
echo ======================================================================
echo   Scenario Selected: %SCENARIO%
echo   Algorithms:        Hungarian Allocation + PIBT + Space-Time A*
echo   Safety Guarantee:  0 Collisions, 0 Deadlocks, Invariant Enforcement
echo   Fleet Size:        6 Industrial AMRs (R01 - R06)
echo ======================================================================
echo.
echo   Launching via WSL2 (Ubuntu-24.04 with ROS 2 Jazzy + Gazebo Harmonic)...
echo.

wsl -d Ubuntu-24.04 -- bash -c "cd '/mnt/c/Users/thega/PROJECTS/SIH'\''26' && bash run_live_fleet.sh %SCENARIO% proposed false"

pause
