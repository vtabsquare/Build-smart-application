@echo off
setlocal
if not exist "%~dp0.env" (
    echo Could not find .env next to this file.
    echo Copy .env.example to .env and try again.
    pause
    exit /b 1
)
start "" notepad.exe "%~dp0.env"
