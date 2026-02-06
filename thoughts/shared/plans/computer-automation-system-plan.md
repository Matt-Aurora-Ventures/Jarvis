# Feature Plan: Complete Computer Automation System
Created: 2026-01-31 20:45 PST
Author: architect-agent

## Overview

Enable AI to fully automate and control the computer when offline, including browser automation via Chromium CDP, password manager integration (1Password/Bitwarden CLI), Google account OAuth persistence, LinkedIn automation, X (Twitter) multi-account management, and Windows automation with PyAutoGUI and Task Scheduler.

## Requirements

- [ ] Browser Automation: Connect to existing Chrome via CDP, save/restore cookies, headless operation, screenshots
- [ ] Password Manager: 1Password CLI integration, Bitwarden fallback, secure credential retrieval, auto-fill
- [ ] Google Accounts: OAuth 2.0 persistence, multi-account management, Gmail/Drive/YouTube API access
- [ ] LinkedIn: API integration, cookie persistence, post automation, connection management
- [ ] X Multi-Account: Manage all user accounts, OAuth per account, posting/replying, account switching
- [ ] Windows Automation: PyAutoGUI, Task Scheduler, Windows Services, Wake-on-LAN

## Design

### Architecture Diagram



### Data Flow

1. Credential Request: Task -> CredentialManager -> 1Password/Bitwarden -> Return Credential
2. Browser Session: Task -> CDP Manager -> Chrome -> Session Store -> Execute -> Save
3. OAuth Token: API Request -> OAuthManager -> Check/Refresh -> Return valid token

## Dependencies

| Dependency | Type | Reason |
|------------|------|--------|
| playwright | External | Browser automation with CDP support |
| aiohttp | External | Async HTTP for API calls |
| pyotp | External | OTP generation for 2FA |
| google-auth | External | Google OAuth library |
| tweepy | Internal | Already used for X API |
| pyautogui | External | Windows GUI automation |
| wakeonlan | External | Wake-on-LAN packets |

## Implementation Phases

### Phase 1: Foundation - Credential & Browser Infrastructure
**Files to create:**
- core/automation/__init__.py - Module init
- core/automation/interfaces.py - Abstract interfaces
- core/automation/credential_manager.py - 1Password/Bitwarden integration
- core/automation/browser_cdp.py - CDP connection and control
- core/automation/session_store.py - Cookie/session persistence

**Estimated effort:** Medium (3-4 hours)

### Phase 2: Google Account Automation
**Files to create:**
- core/automation/google_oauth.py - Multi-account OAuth manager
- core/automation/google_services.py - Gmail/Drive/YouTube clients

**Estimated effort:** Medium (2-3 hours)

### Phase 3: X (Twitter) Multi-Account Management
**Files to create:**
- core/automation/x_multi_account.py - Multi-account manager
- bots/twitter/account_switcher.py - Account switching logic

**Estimated effort:** Medium (2-3 hours)

### Phase 4: LinkedIn Automation
**Files to create:**
- core/automation/linkedin_client.py - LinkedIn API client
- core/automation/linkedin_session.py - Cookie-based session

**Estimated effort:** Medium (2-3 hours)

### Phase 5: Windows Automation
**Files to create:**
- core/automation/windows_service.py - Windows service wrapper
- core/automation/gui_automation.py - PyAutoGUI wrapper
- core/automation/task_scheduler.py - Task Scheduler integration
- core/automation/wake_on_lan.py - WoL functionality
- scripts/windows/jarvis-service-installer.ps1 - Service installer

**Estimated effort:** Medium (2-3 hours)

### Phase 6: Orchestrator Integration
**Files to create:**
- core/automation/orchestrator.py - Central automation controller
- core/automation/task_queue.py - Persistent task queue

**Estimated effort:** Small (1-2 hours)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 1Password CLI not installed | High | Fallback to Bitwarden, clear error |
| Chrome not running with debug port | High | Auto-launch Chrome with --remote-debugging-port |
| OAuth tokens expire during offline | Medium | Queue actions, retry on wake |
| LinkedIn rate limits | Medium | Exponential backoff, action queuing |

## Success Criteria

1. AI can retrieve any credential without user input
2. Browser sessions persist across restarts
3. All social accounts accessible 24/7
4. Windows automation works when user logged out
5. VPS can wake local computer and trigger tasks
