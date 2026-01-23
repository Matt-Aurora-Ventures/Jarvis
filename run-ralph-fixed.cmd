@echo off
REM Ralph-TUI Execution Script with Windows Fix
REM This script handles the sessions.lock file issue

echo.
echo ================================
echo Ralph-TUI Demo Bot Execution
echo ================================
echo.

cd /d "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"

REM Create ralph-tui config directory if it doesn't exist
if not exist "%USERPROFILE%\.config\ralph-tui" mkdir "%USERPROFILE%\.config\ralph-tui"

REM Always recreate the lock file (ralph-tui deletes it during cleanup)
echo Creating session files...
echo [] > "%USERPROFILE%\.config\ralph-tui\sessions.json"
type nul > "%USERPROFILE%\.config\ralph-tui\sessions.lock"

REM Give the filesystem a moment to sync
timeout /t 1 /nobreak >nul

echo.
echo Starting Ralph-TUI...
echo PRD: prd-demo-bot.json
echo User Stories: 33
echo Max Iterations: 10
echo.

REM Run ralph-tui with --force to skip stale session prompt
ralph-tui run --prd prd-demo-bot.json --iterations 10 --force

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo Ralph-TUI encountered an error
    echo ========================================
    echo.
    echo This appears to be a ralph-tui Windows compatibility issue.
    echo The PRD is ready - you may want to try:
    echo   1. Implementing the user stories manually
    echo   2. Using WSL/Linux environment for ralph-tui
    echo   3. Checking ralph-tui GitHub issues for Windows support
    echo.
)

pause
