@echo off
setlocal
cd /d "%~dp0"
title SIH26123 - Webots Multi-AMR Fleet Simulation Launcher
cls
echo ======================================================================
echo   SIH 2026 (SIH26123) - WEBOTS MULTI-AMR ROBOTICS SIMULATION
echo   Decentralized AMR Fleet Coordination for Smart Warehouses
echo ======================================================================
echo   Algorithms: Hungarian Allocation + PIBT + Space-Time A* + MotionModel
echo   Fleet Size: 6 Industrial AMRs (R01 - R06)
echo   Safety:     0 Collisions, 0 Deadlocks, Dynamic Detour Detour
echo ======================================================================
echo.
echo   SELECT AN EXECUTION OPTION:
echo   [1] Launch Webots 3D Graphical Window (Native Desktop View) [DEFAULT]
echo   [2] Open Webots Interactive HTML5 Player (Browser View)
echo   [3] Run Official SIH-WEBOTS-REC-01 Recording Scenario (Paced 90-150s)
echo   [4] Run 6-AMR Scenario C (Dynamic Blockage Replanning)
echo   [5] Run 6-AMR Scenario A (Nominal Flow)
echo   [6] Run Milestone POC-01 / POC-02 Validations
echo   [7] Clean / Kill All Webots Background Processes
echo.
set "opt="
set /p opt="Enter choice [1-7, default 1]: "
if "%opt%"=="" set opt=1
set opt=%opt: =%
set opt=%opt:~0,1%

if "%opt%"=="1" goto opt1
if "%opt%"=="2" goto opt2
if "%opt%"=="3" goto opt3
if "%opt%"=="4" goto opt4
if "%opt%"=="5" goto opt5
if "%opt%"=="6" goto opt6
if "%opt%"=="7" goto opt7

echo.
echo Invalid option selected: %opt%
goto done

:opt1
echo.
echo [LAUNCHING] Cleaning previous instances and opening Webots 3D...
wsl -d Ubuntu-24.04 bash -c "pkill -9 -f webots || true" >nul 2>&1
timeout /t 1 /nobreak >nul
wsl -d Ubuntu-24.04 bash simulation/webots/scripts/launch_webots_gui.sh
goto done

:opt2
echo.
echo [LAUNCHING] Opening Webots Interactive Visualizer in default browser...
start "" "%~dp0simulation\webots\webots_visualizer.html"
goto done

:opt3
echo.
echo [RUNNING] Official SIH-WEBOTS-REC-01 Paced Video Scenario...
wsl -d Ubuntu-24.04 bash -c "python3 simulation/webots/scripts/run_webots_recording.py --paced --dt 0.05"
goto done

:opt4
echo.
echo [RUNNING] 6-AMR Scenario C (Dynamic Blockage Replanning)...
wsl -d Ubuntu-24.04 bash -c "python3 simulation/webots/scripts/run_webots_fleet.py --scenario SCENARIO_C"
goto done

:opt5
echo.
echo [RUNNING] 6-AMR Scenario A (Nominal Flow)...
wsl -d Ubuntu-24.04 bash -c "python3 simulation/webots/scripts/run_webots_fleet.py --scenario SCENARIO_A"
goto done

:opt6
echo.
echo [RUNNING] Milestone Validations (POC-01: 2 AMRs, POC-02: 4 AMRs)...
wsl -d Ubuntu-24.04 bash -c "python3 simulation/webots/scripts/run_poc01.py && python3 simulation/webots/scripts/run_poc02.py"
goto done

:opt7
echo.
echo [CLEANING] Terminating all Webots processes...
wsl -d Ubuntu-24.04 bash -c "pkill -9 -f webots || true"
echo All Webots processes cleaned.
goto done

:done
echo.
echo ======================================================================
echo   Session finished. Press any key to close this window.
echo ======================================================================
pause >nul
