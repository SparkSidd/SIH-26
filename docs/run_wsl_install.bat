@echo off
REM run_wsl_install.bat
REM Wrapper to call WSL scripts without PowerShell apostrophe issues
REM Run from: C:\Users\thega\PROJECTS\SIH'26\docs\
wsl -d Ubuntu-24.04 bash -c "bash '/mnt/c/Users/thega/PROJECTS/SIH'"'"'26/docs/install_ros_gazebo.sh' 2>&1 | tee ~/sih26123_install.log"
