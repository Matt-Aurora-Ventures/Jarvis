@echo off
cd /d "c:\Users\lucid\Desktop\Jarvis"
python -m pytest services/investments/tests/ -v --tb=short > test_results.txt 2>&1
echo EXIT_CODE=%ERRORLEVEL% >> test_results.txt
echo.
echo === Tests complete. Results saved to test_results.txt ===
echo You can close this window now.
timeout /t 5
