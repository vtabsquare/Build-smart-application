@echo off
setlocal
title BuildSmart 360 Deployment Application Launcher
cd /d "%~dp0"

echo Launching BuildSmart 360 Deployment Application...
if exist "..\BuildSmart_Deployer\run_deployer.py" (
    cd "..\BuildSmart_Deployer"
    call "Start-Deployment-App.cmd"
) else (
    echo Error: BuildSmart_Deployer folder not found in parent directory.
    pause
)
