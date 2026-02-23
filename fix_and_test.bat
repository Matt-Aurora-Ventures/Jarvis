@echo off
echo ============================================
echo  Jarvis - Kill stale processes + run tests
echo ============================================
echo.

echo [1/3] Killing stale node/python zombie processes...
taskkill /f /im "node.exe" /t 2>nul
taskkill /f /im "python.exe" /t 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] Running investment service tests...
cd /d "c:\Users\lucid\Desktop\Jarvis"
python -m pytest services/investments/tests/ -v --tb=short 2>&1

echo.
echo [3/3] Quick bash sanity check...
echo Bash is alive!

echo.
echo ============================================
echo  DONE - Results above. Press any key to close.
echo ============================================
pause
