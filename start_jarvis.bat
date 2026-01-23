@echo off
REM JARVIS Quick Start - Windows
REM Starts the unified JARVIS daemon with all components

echo =======================================
echo   JARVIS - Your Personal AI Assistant
echo =======================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

REM Change to script directory
cd /d "%~dp0"

REM Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Start JARVIS daemon
echo Starting JARVIS daemon...
echo.
python jarvis_daemon.py %*

pause
