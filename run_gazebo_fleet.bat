@echo off
REM run_gazebo_fleet.bat - Launch Gazebo Live Simulation with 6 robots fleet via WSL2
echo ========================================================
echo   SIH26123 - LAUNCHING GAZEBO LIVE SIMULATION (6 FLEET)
echo ========================================================
wsl -d Ubuntu-24.04 -- bash -c "cd '/mnt/c/Users/thega/PROJECTS/SIH'\''26' && bash run_live_fleet.sh"
pause
