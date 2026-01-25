@echo off
REM KR8TIV Token Metadata Setup (Windows)
REM This script guides you through updating token metadata

setlocal enabledelayedexpansion

set MINT=7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
set CONTRACT=U1zc8QpnrQ3HBJUBrWFYWbQTLzNsCpPgZNegWXdBAGS

echo ============================================================
echo            KR8TIV Token Metadata Setup
echo ============================================================
echo.
echo Mint:     %MINT%
echo Contract: %CONTRACT%
echo.

REM Check for metaboss
where metaboss >nul 2>nul
if %errorlevel% neq 0 (
    echo [X] metaboss not found
    echo.
    echo Please install metaboss first:
    echo   1. Install Rust: https://rustup.rs/
    echo   2. Run: cargo install metaboss
    echo.
    pause
    exit /b 1
)

echo [OK] metaboss found
echo.

REM Get keypair
set /p KEYPAIR_PATH="Path to your keypair JSON file: "

if not exist "%KEYPAIR_PATH%" (
    echo [X] Keypair file not found: %KEYPAIR_PATH%
    pause
    exit /b 1
)

echo [OK] Keypair found
echo.

echo ============================================================
echo.
echo MANUAL STEPS REQUIRED:
echo.
echo 1. Upload your logo image to NFT.Storage or Arweave
echo    - NFT.Storage (free): https://nft.storage
echo    - Arweave: Use metaboss upload arweave --file logo.png
echo.
echo 2. Create metadata.json with your token details
echo.
echo 3. Upload metadata.json to permanent storage
echo.
echo 4. Run the update command:
echo.
echo    metaboss update uri ^
echo      --keypair "%KEYPAIR_PATH%" ^
echo      --account %MINT% ^
echo      --new-uri YOUR_METADATA_URL
echo.
echo 5. (Optional) Freeze metadata:
echo.
echo    metaboss update immutable ^
echo      --keypair "%KEYPAIR_PATH%" ^
echo      --account %MINT%
echo.
echo ============================================================
echo.
echo For full automation, use Git Bash or WSL to run:
echo   bash scripts/setup_kr8tiv_metadata.sh
echo.
echo Or see the guide:
echo   scripts/TOKEN_METADATA_GUIDE.md
echo.

pause
