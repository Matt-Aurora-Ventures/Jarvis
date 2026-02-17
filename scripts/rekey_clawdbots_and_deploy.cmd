@echo off
setlocal

REM Rekey missing ClawdBots via BotFather (waits out cooldowns), then deploy tokens to VPS.
REM Safe: scripts avoid printing tokens to stdout.

cd /d "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis" || exit /b 1

REM Only create missing ClawdBots here. Keep the already-working Jarvis/buy/treasury/public bot tokens unchanged.
call ".venv\Scripts\python.exe" "scripts\telegram_rekey_bots.py" ^
  --mode full ^
  --wait ^
  --group-title "kr8tiv" ^
  --session-name "tdesktop_jarvis_debug_mybots" ^
  --preserve-existing ^
  --skip-env "TELEGRAM_BOT_TOKEN,TELEGRAM_BUY_BOT_TOKEN,TREASURY_BOT_TOKEN,PUBLIC_BOT_TELEGRAM_TOKEN,X_BOT_TELEGRAM_TOKEN"

REM Deploy rekey bundles:
REM - KVM8 (jarvis-vps): merges secrets/rekey_jarvis_updates.env into /etc/jarvis/jarvis.env and restarts jarvis-supervisor
REM - KVM4 (76.13.106.100): patches ClawdBot config JSONs and restarts containers
call ".venv\Scripts\python.exe" "scripts\auto_deploy_after_rekey.py"

endlocal

