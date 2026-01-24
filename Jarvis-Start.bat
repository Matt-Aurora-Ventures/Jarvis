@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PS_SCRIPT=%SCRIPT_DIR%scripts\jarvis-startup.ps1

if not exist "%PS_SCRIPT%" (
  echo Jarvis startup script not found: %PS_SCRIPT%
  pause
  exit /b 1
)

echo Starting Jarvis auto-start loop...
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File "%PS_SCRIPT%"
echo Jarvis startup launched. Logs: %SCRIPT_DIR%logs\startup\jarvis-startup-latest.log
endlocal
