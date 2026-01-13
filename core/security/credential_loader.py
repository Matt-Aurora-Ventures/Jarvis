"""
Unified Credential Loader for X/Telegram Bots.

Centralizes credential loading to prevent credential mismatches.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger("jarvis.security.credentials")


@dataclass
class XCredentials:
    """X (Twitter) API credentials."""
    oauth2_client_id: str = ""
    oauth2_client_secret: str = ""
    oauth2_access_token: str = ""
    oauth2_refresh_token: str = ""
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    expected_username: str = "jarvis_lifeos"
    xai_api_key: str = ""
    
    def is_complete(self) -> bool:
        return bool(self.oauth2_access_token or self.api_key)
    
    def can_upload_media(self) -> bool:
        return all([self.api_key, self.api_secret, self.access_token, self.access_token_secret])


@dataclass
class TelegramCredentials:
    """Telegram bot credentials."""
    bot_token: str = ""
    admin_ids: List[str] = field(default_factory=list)
    admin_chat_id: str = ""
    buy_bot_token: str = ""
    
    def is_complete(self) -> bool:
        return bool(self.bot_token)


@dataclass
class BotCredentials:
    """All bot credentials."""
    x: XCredentials = field(default_factory=XCredentials)
    telegram: TelegramCredentials = field(default_factory=TelegramCredentials)


class CredentialLoader:
    """Unified credential loader for all bots."""
    
    ENV_FILES = [".env", "tg_bot/.env", "bots/twitter/.env"]
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._credentials: Optional[BotCredentials] = None
        self._validated = False
    
    def load(self) -> BotCredentials:
        if self._credentials:
            return self._credentials
        
        creds = BotCredentials()
        for env_file in reversed(self.ENV_FILES):
            env_path = self.project_root / env_file
            if env_path.exists():
                self._load_env_file(env_path, creds)
        self._load_from_environment(creds)
        self._credentials = creds
        return creds
    
    def _load_env_file(self, path: Path, creds: BotCredentials):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    self._set_credential(key.strip(), value.strip().strip('"'), creds)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    
    def _load_from_environment(self, creds: BotCredentials):
        mappings = {
            "X_OAUTH2_ACCESS_TOKEN": ("x", "oauth2_access_token"),
            "X_API_KEY": ("x", "api_key"),
            "X_EXPECTED_USERNAME": ("x", "expected_username"),
            "XAI_API_KEY": ("x", "xai_api_key"),
            "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
            "TELEGRAM_ADMIN_CHAT_ID": ("telegram", "admin_chat_id"),
        }
        for env_key, (section, attr) in mappings.items():
            if value := os.getenv(env_key):
                setattr(getattr(creds, section), attr, value)
    
    def _set_credential(self, key: str, value: str, creds: BotCredentials):
        key = key.upper()
        if "OAUTH2_ACCESS" in key:
            creds.x.oauth2_access_token = value
        elif "API_KEY" in key and "XAI" not in key:
            creds.x.api_key = value
        elif "EXPECTED_USERNAME" in key:
            creds.x.expected_username = value
        elif "XAI_API_KEY" in key:
            creds.x.xai_api_key = value
        elif "TELEGRAM" in key and "TOKEN" in key and "BUY" not in key:
            creds.telegram.bot_token = value
        elif "ADMIN_CHAT_ID" in key:
            creds.telegram.admin_chat_id = value

    async def validate_x_account(self) -> tuple:
        """Validate X credentials match expected account."""
        creds = self.load()
        if not creds.x.expected_username:
            return False, "X_EXPECTED_USERNAME not set"
        if not creds.x.oauth2_access_token:
            return False, "No OAuth2 token"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.twitter.com/2/users/me",
                    headers={"Authorization": f"Bearer {creds.x.oauth2_access_token}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        username = data.get("data", {}).get("username", "")
                        if username.lower() != creds.x.expected_username.lower():
                            return False, f"Account mismatch: @{username} != @{creds.x.expected_username}"
                        self._validated = True
                        return True, f"Validated: @{username}"
                    return False, f"API error: {resp.status}"
        except Exception as e:
            return False, str(e)


_loader: Optional[CredentialLoader] = None

def get_credential_loader() -> CredentialLoader:
    global _loader
    if _loader is None:
        _loader = CredentialLoader()
    return _loader
