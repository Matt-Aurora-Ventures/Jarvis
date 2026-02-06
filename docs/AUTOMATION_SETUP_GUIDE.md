# Computer Automation Setup Guide

Complete guide to setting up AI-powered computer automation.

## Prerequisites

1. Python 3.10+ with pip
2. Google Chrome installed
3. 1Password CLI or Bitwarden CLI (for credential management)
4. Windows 10/11 (for Windows automation features)

## Quick Start

### 1. Install Dependencies

pip install pyautogui aiohttp playwright wakeonlan

### 2. Setup Chrome for Remote Debugging

Run: scripts/windows/setup-chrome-debugging.ps1

Or launch Chrome manually with:
chrome.exe --remote-debugging-port=9222 --user-data-dir=%USERPROFILE%/.chrome-automation

### 3. Install Password Manager CLI

1Password: Download from https://1password.com/downloads/command-line/
Bitwarden: npm install -g @bitwarden/cli

### 4. Configure Google OAuth

1. Create project in Google Cloud Console
2. Enable Gmail, Drive, Calendar, YouTube APIs
3. Create OAuth credentials (Desktop app)
4. Save to secrets/google_credentials.json

### 5. Configure X (Twitter) Accounts

Create secrets/x_accounts.json with your account configs.

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Orchestrator | core/automation/orchestrator.py | Central controller |
| Credential Manager | core/automation/credential_manager.py | 1Password/Bitwarden |
| Browser CDP | core/automation/browser_cdp.py | Chrome automation |
| Google OAuth | core/automation/google_oauth.py | Multi-account Google |
| X Multi-Account | core/automation/x_multi_account.py | Twitter accounts |
| LinkedIn | core/automation/linkedin_client.py | LinkedIn automation |
| GUI Automation | core/automation/gui_automation.py | PyAutoGUI wrapper |
| Wake-on-LAN | core/automation/wake_on_lan.py | Remote wake |
| Task Scheduler | core/automation/task_scheduler.py | Windows tasks |

## Usage Example

from core.automation.orchestrator import get_orchestrator
import asyncio

async def main():
    orch = get_orchestrator()
    await orch.initialize()
    
    await orch.navigate("https://example.com")
    await orch.screenshot("/tmp/page.png")
    
    cred = await orch.get_credential("google", "email@gmail.com")
    await orch.x_post("jarvis_lifeos", "Hello from automation\!")
    
    await orch.shutdown()

asyncio.run(main())

## Windows Service

Install as service (runs at boot):
scripts/windows/jarvis-service-installer.ps1 -Install
scripts/windows/jarvis-service-installer.ps1 -Start

## Security Notes

- Credentials stored in password managers, not config files
- OAuth tokens persisted encrypted in secrets/
- Browser sessions contain sensitive cookies
- Windows service runs with elevated privileges
