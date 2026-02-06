# Jarvis Automation Setup Guide

**Status**: ✅ Infrastructure 100% Built
**Created**: 2026-01-31

---

## 🎯 Summary

Jarvis has a **complete automation infrastructure** already implemented:

| Component | Status | Implementation |
|-----------|--------|----------------|
| Browser CDP | ✅ Complete | `core/automation/browser_cdp.py` |
| X Multi-Account | ✅ Complete | `core/automation/x_multi_account.py` |
| Google OAuth | ✅ Complete | `core/automation/google_oauth.py` |
| LinkedIn | ✅ Complete | `core/automation/linkedin_client.py` |
| Password Managers | ✅ Complete | `core/automation/credential_manager.py` |
| Orchestrator | ✅ Complete | `core/automation/orchestrator.py` |
| GUI Automation | ✅ Complete | `core/automation/gui_automation.py` |
| Task Scheduler | ✅ Complete | `core/automation/task_scheduler.py` |
| Wake-on-LAN | ✅ Complete | `core/automation/wake_on_lan.py` |

**All code is production-ready. We just need to initialize the accounts.**

---

## 📋 Setup Checklist

### 1. Password Manager Integration

**Supported**: 1Password or Bitwarden CLI

#### 1Password Setup:
```bash
# Download CLI: https://developer.1password.com/docs/cli/get-started/
# Install and sign in:
op signin

# Verify:
op --version
```

#### Bitwarden Setup:
```bash
# Download CLI: https://bitwarden.com/help/cli/
# Install and login:
bw login

# Unlock vault:
export BW_SESSION=$(bw unlock --raw)

# Verify:
bw --version
```

**Jarvis will auto-detect which CLI is available and use it.**

---

### 2. Browser Automation Setup

**Launch Chrome with debugging enabled:**

```bash
# Windows:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=%USERPROFILE%\.chrome-automation

# Or use Jarvis helper:
python -c "import asyncio; from core.automation.browser_cdp import launch_chrome_with_debugging; asyncio.run(launch_chrome_with_debugging())"
```

**This enables:**
- Cookie persistence
- Session save/restore
- Headless automation
- Screenshot capture

---

### 3. X (Twitter) Multi-Account Setup

**Add accounts via Python:**

```python
import asyncio
from core.automation.x_multi_account import get_x_manager

async def setup():
    mgr = get_x_manager()

    # Add @Jarvis_lifeos
    await mgr.add_account(
        account_id='jarvis_lifeos',
        username='Jarvis_lifeos',
        client_id='YOUR_CLIENT_ID',  # From Twitter Developer Portal
        client_secret='YOUR_CLIENT_SECRET'
    )

    # Add more accounts as needed...

asyncio.run(setup())
```

**OAuth Flow** (first-time only):
1. Visit https://developer.twitter.com/en/portal/projects-and-apps
2. Create OAuth 2.0 app
3. Get client_id and client_secret
4. Run setup script
5. Tokens auto-refresh after that

**Accounts stored in**: `secrets/x_accounts.json`

---

### 4. Google OAuth Setup

**Get credentials**:
1. Visit https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID
3. Download `credentials.json`
4. Save to `secrets/google_credentials.json`

**Add accounts**:
```python
import asyncio
from core.automation.google_oauth import get_google_manager

async def setup():
    mgr = get_google_manager()
    # First time: Will open browser for OAuth flow
    # Tokens auto-save and auto-refresh
    token = await mgr.get_token('your@gmail.com')

asyncio.run(setup())
```

**Scopes supported**:
- Gmail (read/send)
- Drive
- Calendar
- YouTube

**Accounts stored in**: `secrets/google_accounts.json`

---

### 5. LinkedIn Setup

**Cookie-based authentication** (no API key needed):

```python
import asyncio
from core.automation.browser_cdp import ChromeCDPClient
from core.automation.linkedin_client import LinkedInClient

async def setup():
    browser = ChromeCDPClient()
    await browser.connect(9222)

    linkedin = LinkedInClient()
    # Opens LinkedIn login page
    # Wait for manual login
    # Auto-saves session cookies
    await linkedin.login_via_browser(browser)

    await browser.disconnect()

asyncio.run(setup())
```

**After first login, session persists** - no re-login needed.

**Session stored in**: `data/browser_sessions/linkedin.json`

---

## 🚀 Quick Start - All-in-One

**Test the entire automation system:**

```python
import asyncio
from core.automation.orchestrator import get_orchestrator

async def test_all():
    orch = get_orchestrator()

    # Initialize (connects browser, loads all managers)
    await orch.initialize(debug_port=9222)

    # Test X accounts
    x_accounts = await orch.list_x_accounts()
    print(f'✅ X accounts: {x_accounts}')

    # Test Google accounts
    google_accounts = await orch.list_google_accounts()
    print(f'✅ Google accounts: {google_accounts}')

    # Test browser
    await orch.navigate('https://google.com')
    await orch.screenshot('test_screenshot.png')
    print(f'✅ Browser working')

    # Test LinkedIn
    if await orch.linkedin_post("Test post from Jarvis automation"):
        print(f'✅ LinkedIn posting working')

    # Test credentials
    cred = await orch.get_credential('github', 'kr8tiv')
    if cred:
        print(f'✅ Password manager working: {cred.username}')

    await orch.shutdown()

# Run:
asyncio.run(test_all())
```

---

## 📂 File Structure

```
Jarvis/
├── core/automation/
│   ├── orchestrator.py          # Central controller
│   ├── browser_cdp.py           # Chrome automation
│   ├── x_multi_account.py       # X/Twitter manager
│   ├── google_oauth.py          # Google OAuth manager
│   ├── linkedin_client.py       # LinkedIn automation
│   ├── credential_manager.py    # 1Password/Bitwarden
│   ├── gui_automation.py        # Windows GUI automation
│   ├── task_scheduler.py        # Windows Task Scheduler
│   └── wake_on_lan.py           # Remote PC wake
│
├── secrets/                     # Git-ignored credentials
│   ├── x_accounts.json          # X OAuth tokens
│   ├── google_accounts.json     # Google OAuth tokens
│   ├── google_credentials.json  # OAuth client credentials
│   └── bot_tokens_DEPLOY_ONLY.txt
│
└── data/browser_sessions/       # Saved browser sessions
    ├── linkedin.json
    ├── twitter.json
    └── google.json
```

---

## 🔧 Advanced Usage

### Post to X from any account:
```python
await orch.x_post('jarvis_lifeos', 'GM, frens! ☀️')
```

### Automate Gmail:
```python
token = await orch.google_get_token('your@gmail.com')
# Use token with Gmail API
```

### Save/restore browser sessions:
```python
# Save current session
await orch.save_browser_session('github_logged_in')

# Restore later
await orch.restore_browser_session('github_logged_in')
```

### Windows GUI automation:
```python
# Click at coordinates
await orch.click_screen(100, 200)

# Type text
await orch.type_text('Hello World')

# Screenshot
screenshot_bytes = await orch.take_screenshot()
```

---

## 🎯 Integration with Jarvis Bots

**Add automation to Telegram bot commands:**

```python
from core.automation.orchestrator import get_orchestrator

# In your bot handler:
async def handle_post_to_x(update, context):
    orch = get_orchestrator()
    await orch.initialize()

    text = ' '.join(context.args)
    success = await orch.x_post('jarvis_lifeos', text)

    if success:
        await update.message.reply_text('✅ Posted to X!')
    else:
        await update.message.reply_text('❌ Post failed')
```

---

## 🔐 Security Notes

- All credentials stored in `secrets/` (git-ignored)
- OAuth tokens auto-refresh before expiry
- Browser sessions encrypted at rest
- Password manager requires CLI unlock
- No plaintext passwords in code

---

## ✅ Next Steps

1. **Install password manager CLI** (1Password or Bitwarden)
2. **Launch Chrome with debugging** (`--remote-debugging-port=9222`)
3. **Add X accounts** (via Python script above)
4. **Add Google accounts** (OAuth flow once)
5. **Login to LinkedIn** (manual once, persists forever)
6. **Run test script** to verify everything works

**After setup, all automation is code-driven and fully autonomous.**

---

## 🤖 Ralph Wiggum Loop Integration

The automation orchestrator is designed for continuous autonomous operation:

```python
async def autonomous_loop():
    orch = get_orchestrator()
    await orch.initialize()

    while True:
        # Post to X every hour
        await orch.x_post('jarvis_lifeos', generate_tweet())

        # Check Gmail every 10 minutes
        await check_gmail(orch)

        # Update LinkedIn weekly
        await post_linkedin_update(orch)

        await asyncio.sleep(600)  # 10 minutes
```

**This is the future of Jarvis: fully autonomous multi-platform presence.**
