@echo off
REM Ralph-TUI Execution Script
REM Run this in CMD outside of Claude Code

echo.
echo ================================
echo Ralph-TUI Demo Bot Execution
echo ================================
echo.

cd /d "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"

echo Cleaning up stale sessions...
del "%USERPROFILE%\.config\ralph-tui\sessions.*" /F /Q 2>nul
del "%USERPROFILE%\.config\ralph-tui\*.lock" /F /Q 2>nul

if not exist "%USERPROFILE%\.config\ralph-tui" mkdir "%USERPROFILE%\.config\ralph-tui"
echo [] > "%USERPROFILE%\.config\ralph-tui\sessions.json"
type nul > "%USERPROFILE%\.config\ralph-tui\sessions.lock"

echo.
echo Starting Ralph-TUI...
echo PRD: prd-demo-bot.json
echo User Stories: 33
echo Max Iterations: 10
echo.

ralph-tui run --prd prd-demo-bot.json --iterations 10

echo.
echo Execution complete!
pause
