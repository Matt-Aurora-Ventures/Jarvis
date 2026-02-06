"""
Computer Automation System for Jarvis.

Provides comprehensive automation capabilities:
- Browser automation via Chromium CDP
- Password manager integration (1Password/Bitwarden)
- Google OAuth multi-account management
- LinkedIn automation
- X (Twitter) multi-account management
- Windows automation (PyAutoGUI, Task Scheduler, Services)
"""

from core.automation.interfaces import (
    Credential,
    BrowserSession,
    OAuthToken,
    CredentialProvider,
    BrowserAutomator,
    OAuthManager,
)

__all__ = [
    "Credential",
    "BrowserSession", 
    "OAuthToken",
    "CredentialProvider",
    "BrowserAutomator",
    "OAuthManager",
]
