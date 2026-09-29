@echo off
REM ========================================================
REM   SIH 2026 (SIH26123) - VIDEO RECORDING LAUNCHER
REM   Sets up Digital Twin + Gazebo side-by-side demo
REM ========================================================
title SIH26123 - Video Recording Demo Launcher
cls
echo ======================================================================
echo   SIH 2026 (SIH26123) - CYBER-PHYSICAL AMR FLEET VIDEO DEMO
echo   Edge-AI Distributed Autonomous Mobile Robot Coordination
echo ======================================================================
echo.
echo   RECORDING SETUP STEPS:
echo   ------------------------------------------------------------------
echo   1. Gazebo 3D Simulation is already running in background!
echo      - Snap Gazebo to the LEFT half of your screen: [Win + Left Arrow]
echo.
echo   2. Browser with Digital Twin will open at http://localhost:8000
echo      - Snap Browser to the RIGHT half of screen:   [Win + Right Arrow]
echo.
echo   3. In the Digital Twin, click the top button:
echo      - [ SIH DEMO TOUR ] to auto-run through all 5 competition stages
echo      - Or click [ SCORECARD ] to show the 200-run verified metrics!
echo.
echo   4. Start your screen recording:
echo      - Windows Game Bar: [Win + Alt + R]
echo      - Or OBS Studio
echo.
echo ======================================================================
echo   Starting Mission Control Server on port 8000...
echo ======================================================================
echo.
start "" http://localhost:8000
python -m uvicorn web.server:app --host 0.0.0.0 --port 8000
pause
