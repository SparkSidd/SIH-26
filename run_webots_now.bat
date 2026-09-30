@echo off
echo.
echo ===================================================================
echo   SIH26123 - Webots GUI Launcher
echo   This window MUST stay open while Webots is running.
echo ===================================================================
echo.
wsl -d Ubuntu-24.04 bash -c "cd /mnt/c/Users/thega/PROJECTS/SIH*26 && bash scripts/launch_gui_simulator.sh webots simulation/webots/worlds/warehouse_fleet.wbt"
echo.
echo Webots exited.
pause
