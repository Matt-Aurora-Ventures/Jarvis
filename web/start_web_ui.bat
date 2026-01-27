@echo off
echo.
echo ========================================
echo    JARVIS WEB INTERFACES
echo ========================================
echo.
echo Trading Interface: http://127.0.0.1:5001
echo Control Deck:      http://127.0.0.1:5000
echo.
echo Press Ctrl+C to stop both servers
echo ========================================
echo.

start "Jarvis Trading UI" cmd /k "python trading_web.py"
start "Jarvis Control Deck" cmd /k "python task_web.py"

echo.
echo Web interfaces launched in separate windows.
echo Close the command windows to stop the servers.
echo.
pause
