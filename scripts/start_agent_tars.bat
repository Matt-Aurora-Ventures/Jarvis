@echo off
REM Agent TARS Quick Start Script
REM Uses Claude 3.7 Sonnet with Anthropic API

echo.
echo ================================================
echo   Starting Agent TARS with Claude 3.7 Sonnet
echo ================================================
echo.

REM Check if ANTHROPIC_API_KEY is set
if "%ANTHROPIC_API_KEY%"=="" (
    echo ERROR: ANTHROPIC_API_KEY environment variable not set
    echo Please set it with: set ANTHROPIC_API_KEY=your_api_key
    pause
    exit /b 1
)

REM Launch Agent TARS with config
agent-tars --config "C:\Users\lucid\.agent-tars\agent.config.json" --open

pause
