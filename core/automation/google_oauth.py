"""
Google OAuth Multi-Account Manager.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.automation.interfaces import OAuthManager, OAuthToken

logger = logging.getLogger(__name__)

GOOGLE_ACCOUNTS_FILE = Path(__file__).parent.parent.parent / 'secrets' / 'google_accounts.json'
GOOGLE_CREDENTIALS_FILE = Path(__file__).parent.parent.parent / 'secrets' / 'google_credentials.json'

SCOPES = {
    'gmail': ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send'],
    'drive': ['https://www.googleapis.com/auth/drive'],
    'calendar': ['https://www.googleapis.com/auth/calendar'],
    'youtube': ['https://www.googleapis.com/auth/youtube.readonly'],
}


class GoogleOAuthManager(OAuthManager):
    def __init__(self):
        self._accounts: Dict[str, Dict] = {}
        self._credentials: Optional[Dict] = None
        self._load_config()
    
    def _load_config(self):
        if GOOGLE_ACCOUNTS_FILE.exists():
            try:
                self._accounts = json.loads(GOOGLE_ACCOUNTS_FILE.read_text())
            except Exception:
                pass
        if GOOGLE_CREDENTIALS_FILE.exists():
            try:
                self._credentials = json.loads(GOOGLE_CREDENTIALS_FILE.read_text())
            except Exception:
                pass
    
    def _save_accounts(self):
        GOOGLE_ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        GOOGLE_ACCOUNTS_FILE.write_text(json.dumps(self._accounts, indent=2))

    async def get_token(self, account_id: str) -> Optional[OAuthToken]:
        if account_id not in self._accounts:
            return None
        token_data = self._accounts[account_id].get('oauth_token')
        if not token_data:
            return None
        token = OAuthToken(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_at=datetime.fromisoformat(token_data['expires_at']),
            scopes=token_data.get('scopes', []),
            account_id=account_id,
            provider='google'
        )
        if token.needs_refresh:
            return await self.refresh_token(account_id)
        return token
    
    async def refresh_token(self, account_id: str) -> Optional[OAuthToken]:
        if account_id not in self._accounts:
            return None
        token_data = self._accounts[account_id].get('oauth_token')
        if not token_data or not token_data.get('refresh_token'):
            return None
        creds = self._credentials.get('installed', self._credentials.get('web', {}))
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://oauth2.googleapis.com/token',
                    data={
                        'client_id': creds['client_id'],
                        'client_secret': creds['client_secret'],
                        'refresh_token': token_data['refresh_token'],
                        'grant_type': 'refresh_token'
                    }
                ) as resp:
                    if resp.status != 200:
                        return None
                    result = await resp.json()
                    new_token = {
                        'access_token': result['access_token'],
                        'refresh_token': token_data['refresh_token'],
                        'expires_at': (datetime.utcnow() + timedelta(seconds=result.get('expires_in', 3600))).isoformat(),
                        'scopes': result.get('scope', '').split() or token_data.get('scopes', [])
                    }
                    self._accounts[account_id]['oauth_token'] = new_token
                    self._save_accounts()
                    return OAuthToken(
                        access_token=new_token['access_token'],
                        refresh_token=new_token['refresh_token'],
                        expires_at=datetime.fromisoformat(new_token['expires_at']),
                        scopes=new_token['scopes'],
                        account_id=account_id,
                        provider='google'
                    )
        except Exception as e:
            logger.error(f'Token refresh error: {e}')
            return None
    
    async def store_token(self, token: OAuthToken) -> bool:
        if token.account_id not in self._accounts:
            self._accounts[token.account_id] = {'email': token.account_id}
        self._accounts[token.account_id]['oauth_token'] = {
            'access_token': token.access_token,
            'refresh_token': token.refresh_token,
            'expires_at': token.expires_at.isoformat(),
            'scopes': token.scopes
        }
        self._save_accounts()
        return True
    
    async def list_accounts(self) -> List[str]:
        return list(self._accounts.keys())
    
    async def revoke_token(self, account_id: str) -> bool:
        if account_id in self._accounts:
            self._accounts[account_id]['oauth_token'] = None
            self._save_accounts()
            return True
        return False


_google_manager: Optional[GoogleOAuthManager] = None

def get_google_manager() -> GoogleOAuthManager:
    global _google_manager
    if _google_manager is None:
        _google_manager = GoogleOAuthManager()
    return _google_manager
