@echo off
REM run_gazebo_two.bat - Launch Gazebo Live Simulation with 2 robots via WSL2
echo ========================================================
echo   SIH26123 - LAUNCHING GAZEBO LIVE SIMULATION (2 ROBOTS)
echo ========================================================
wsl -d Ubuntu-24.04 -- bash -c "cd '/mnt/c/Users/thega/PROJECTS/SIH'\''26' && bash run_live_two.sh"
pause
