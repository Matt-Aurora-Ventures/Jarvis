@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo  Starting canonical Jarvis Sniper UI...
echo  Open http://127.0.0.1:3001 in your browser
echo  Press Ctrl+C to stop
echo.
echo  [Policy] web/trading_web.py and jarvis-web-terminal are prototype-only surfaces.
echo  [Policy] Production UI is jarvis-sniper only.
echo.

where npm >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] npm not found in PATH.
  echo  Install Node.js 20+ and ensure `npm` is available in this shell.
  echo.
  pause
  exit /b 1
)

if not exist logs mkdir logs
set "LOG_FILE=logs\\jarvis_sniper_dev.log"

echo  Writing runtime log to %LOG_FILE%
echo.

npm --prefix jarvis-sniper run dev 1>"%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo  [ERROR] Jarvis Sniper UI exited with code %EXIT_CODE%.
  echo  Check %LOG_FILE% for details.
  echo.
)

pause
exit /b %EXIT_CODE%
