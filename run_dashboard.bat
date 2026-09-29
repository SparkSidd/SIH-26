@echo off
REM ========================================================
REM   SIH 2026 (SIH26123) - AETHER DIGITAL TWIN DASHBOARD
REM   Launches FastAPI Mission Control & opens browser
REM ========================================================
title SIH26123 - AMR Fleet Digital Twin Dashboard
echo ========================================================
echo   SIH26123 - STARTING AETHER DIGITAL TWIN MISSION CONTROL
echo ========================================================
echo.
echo Dashboard URL: http://localhost:8000
echo.
start "" http://localhost:8000
python -m uvicorn web.server:app --host 0.0.0.0 --port 8000
pause
