@echo off
REM ============================================================================
REM JARVIS Docker Startup Script (Windows)
REM ============================================================================
REM Usage:
REM   docker-start.bat              - Start core services
REM   docker-start.bat --monitoring - Include Prometheus + Grafana
REM   docker-start.bat --ollama     - Include local Ollama LLM
REM   docker-start.bat --all        - Start everything
REM   docker-start.bat --stop       - Stop all services
REM   docker-start.bat --logs       - Follow logs
REM ============================================================================

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set COMPOSE_FILE=%PROJECT_DIR%\docker-compose.bots.yml
set PROFILES=

REM Parse arguments
:parse_args
if "%~1"=="" goto :main
if "%~1"=="--monitoring" (
    set PROFILES=!PROFILES! --profile monitoring
    shift
    goto :parse_args
)
if "%~1"=="--ollama" (
    set PROFILES=!PROFILES! --profile with-ollama
    shift
    goto :parse_args
)
if "%~1"=="--all" (
    set PROFILES=--profile monitoring --profile with-ollama
    shift
    goto :parse_args
)
if "%~1"=="--stop" (
    echo Stopping JARVIS services...
    docker-compose -f "%COMPOSE_FILE%" %PROFILES% down
    echo Services stopped.
    goto :eof
)
if "%~1"=="--logs" (
    docker-compose -f "%COMPOSE_FILE%" logs -f supervisor
    goto :eof
)
if "%~1"=="--status" (
    docker-compose -f "%COMPOSE_FILE%" ps
    goto :eof
)
if "%~1"=="--restart" (
    echo Restarting supervisor...
    docker-compose -f "%COMPOSE_FILE%" restart supervisor
    echo Supervisor restarted.
    goto :eof
)
if "%~1"=="--health" (
    echo Checking health...
    curl -s http://localhost:8080/health
    goto :eof
)
if "%~1"=="-h" goto :help
if "%~1"=="--help" goto :help

echo Unknown option: %~1
goto :eof

:help
echo JARVIS Docker Startup Script
echo.
echo Usage: %~nx0 [OPTIONS]
echo.
echo Options:
echo   --monitoring    Include Prometheus + Grafana
echo   --ollama        Include local Ollama LLM
echo   --all           Start all services
echo   --stop          Stop all services
echo   --logs          Follow supervisor logs
echo   --status        Show service status
echo   --restart       Restart supervisor
echo   --health        Check health endpoint
echo   -h, --help      Show this help
goto :eof

:main
REM Load Claude OAuth token automatically when not explicitly set
if "%ANTHROPIC_AUTH_TOKEN%"=="" (
    if exist "%USERPROFILE%\.claude\.credentials.json" (
        for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue';$p=Join-Path $env:USERPROFILE '.claude\\.credentials.json';if(Test-Path $p){$j=Get-Content $p -Raw | ConvertFrom-Json;$t=[string]$j.claudeAiOauth.accessToken;if(-not [string]::IsNullOrWhiteSpace($t)){Write-Output $t.Trim()}}"`) do (
            set "ANTHROPIC_AUTH_TOKEN=%%T"
        )
        if not "%ANTHROPIC_AUTH_TOKEN%"=="" (
            echo Loaded ANTHROPIC_AUTH_TOKEN from %%USERPROFILE%%\.claude\.credentials.json
        )
    )
)

REM Check for .env file
if not exist "%PROJECT_DIR%\.env" (
    echo Warning: .env file not found.
    echo Copy .env.docker.example to .env and configure your credentials.
    echo.
    echo Example: copy .env.docker.example .env
    goto :eof
)

REM Check for secrets directory
if not exist "%PROJECT_DIR%\secrets" (
    echo Warning: secrets directory not found.
    echo Creating secrets directory...
    mkdir "%PROJECT_DIR%\secrets"
)

REM Create necessary directories
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"
if not exist "%PROJECT_DIR%\data" mkdir "%PROJECT_DIR%\data"

REM Build and start services
echo ============================================
echo    JARVIS Bot System - Docker Deployment
echo ============================================
echo.
echo Compose file: %COMPOSE_FILE%
if "%PROFILES%"=="" (
    echo Profiles: (core only)
) else (
    echo Profiles: %PROFILES%
)
echo.

REM Pull latest images
echo Pulling latest images...
docker-compose -f "%COMPOSE_FILE%" %PROFILES% pull --quiet

REM Build custom images
echo Building JARVIS supervisor image...
docker-compose -f "%COMPOSE_FILE%" %PROFILES% build --quiet supervisor

REM Start services
echo Starting services...
docker-compose -f "%COMPOSE_FILE%" %PROFILES% up -d

REM Wait for health check
echo.
echo Waiting for health check...
set ATTEMPTS=0
:health_loop
if %ATTEMPTS% geq 30 goto :health_done
curl -sf http://localhost:8080/health >nul 2>&1
if %errorlevel%==0 (
    echo Health check passed!
    goto :health_done
)
set /a ATTEMPTS+=1
timeout /t 2 /nobreak >nul
echo|set /p=.
goto :health_loop
:health_done
echo.

REM Show status
echo.
echo Services started:
docker-compose -f "%COMPOSE_FILE%" ps

echo.
echo ============================================
echo Health endpoint: http://localhost:8080/health
echo ============================================
echo.
echo To view logs: docker-compose -f docker-compose.bots.yml logs -f supervisor
echo To stop: %~nx0 --stop

:eof
endlocal
