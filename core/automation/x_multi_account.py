"""
X (Twitter) Multi-Account Manager.
Manages multiple X accounts with OAuth persistence.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.automation.interfaces import OAuthManager, OAuthToken

logger = logging.getLogger(__name__)

ACCOUNTS_FILE = Path(__file__).parent.parent.parent / 'secrets' / 'x_accounts.json'


class XMultiAccountManager(OAuthManager):
    """Manage multiple X accounts with OAuth 2.0."""
    
    def __init__(self):
        self._accounts: Dict[str, Dict] = {}
        self._current_account: Optional[str] = None
        self._load_accounts()
    
    def _load_accounts(self):
        if ACCOUNTS_FILE.exists():
            try:
                self._accounts = json.loads(ACCOUNTS_FILE.read_text())
                logger.info(f'Loaded {len(self._accounts)} X accounts')
            except Exception as e:
                logger.error(f'Failed to load accounts: {e}')
    
    def _save_accounts(self):
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACCOUNTS_FILE.write_text(json.dumps(self._accounts, indent=2))
    
    async def add_account(self, account_id: str, username: str, 
                          client_id: str, client_secret: str) -> bool:
        """Add a new X account configuration."""
        self._accounts[account_id] = {
            'username': username,
            'client_id': client_id,
            'client_secret': client_secret,
            'oauth_token': None,
            'added_at': datetime.utcnow().isoformat()
        }
        self._save_accounts()
        logger.info(f'Added X account: @{username}')
        return True
    
    async def get_token(self, account_id: str) -> Optional[OAuthToken]:
        if account_id not in self._accounts:
            return None
        
        acct = self._accounts[account_id]
        token_data = acct.get('oauth_token')
        
        if not token_data:
            logger.warning(f'No token for account {account_id}')
            return None
        
        token = OAuthToken(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_at=datetime.fromisoformat(token_data['expires_at']),
            scopes=token_data.get('scopes', []),
            account_id=account_id,
            provider='x'
        )
        
        if token.needs_refresh:
            return await self.refresh_token(account_id)
        
        return token
    
    async def refresh_token(self, account_id: str) -> Optional[OAuthToken]:
        if account_id not in self._accounts:
            return None
        
        acct = self._accounts[account_id]
        token_data = acct.get('oauth_token')
        
        if not token_data or not token_data.get('refresh_token'):
            logger.error(f'No refresh token for {account_id}')
            return None
        
        try:
            import aiohttp
            import base64
            
            credentials = base64.b64encode(
                f"{acct['client_id']}:{acct['client_secret']}".encode()
            ).decode()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.twitter.com/2/oauth2/token',
                    headers={
                        'Authorization': f'Basic {credentials}',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data={
                        'grant_type': 'refresh_token',
                        'refresh_token': token_data['refresh_token']
                    }
                ) as resp:
                    if resp.status != 200:
                        logger.error(f'Token refresh failed: {await resp.text()}')
                        return None
                    
                    result = await resp.json()
                    
                    new_token = {
                        'access_token': result['access_token'],
                        'refresh_token': result.get('refresh_token', token_data['refresh_token']),
                        'expires_at': (datetime.utcnow() + timedelta(seconds=result.get('expires_in', 7200))).isoformat(),
                        'scopes': result.get('scope', '').split()
                    }
                    
                    self._accounts[account_id]['oauth_token'] = new_token
                    self._save_accounts()
                    
                    return OAuthToken(
                        access_token=new_token['access_token'],
                        refresh_token=new_token['refresh_token'],
                        expires_at=datetime.fromisoformat(new_token['expires_at']),
                        scopes=new_token['scopes'],
                        account_id=account_id,
                        provider='x'
                    )
        except Exception as e:
            logger.error(f'Token refresh error: {e}')
            return None
    
    async def store_token(self, token: OAuthToken) -> bool:
        if token.account_id not in self._accounts:
            return False
        
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
    
    def get_username(self, account_id: str) -> Optional[str]:
        if account_id in self._accounts:
            return self._accounts[account_id].get('username')
        return None
    
    async def switch_account(self, account_id: str) -> bool:
        if account_id not in self._accounts:
            return False
        self._current_account = account_id
        logger.info(f'Switched to X account: @{self.get_username(account_id)}')
        return True


# Singleton
_x_manager: Optional[XMultiAccountManager] = None

def get_x_manager() -> XMultiAccountManager:
    global _x_manager
    if _x_manager is None:
        _x_manager = XMultiAccountManager()
    return _x_manager
