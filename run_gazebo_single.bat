@echo off
REM run_gazebo_single.bat - Launch Gazebo Live Simulation with 1 robot via WSL2
echo ========================================================
echo   SIH26123 - LAUNCHING GAZEBO LIVE SIMULATION (1 ROBOT)
echo ========================================================
wsl -d Ubuntu-24.04 -- bash -c "cd '/mnt/c/Users/thega/PROJECTS/SIH'\''26' && bash run_live_single.sh"
pause
