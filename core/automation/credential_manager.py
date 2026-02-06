"""
Credential Manager - 1Password and Bitwarden CLI integration.
Provides secure credential retrieval without user interaction.
"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from core.automation.interfaces import Credential, CredentialProvider

logger = logging.getLogger(__name__)


class OnePasswordProvider(CredentialProvider):
    """1Password CLI credential provider."""
    
    def __init__(self, vault: str = 'Personal'):
        self.vault = vault
        self._session_token: Optional[str] = None
        self._check_cli()
    
    def _check_cli(self) -> bool:
        try:
            result = subprocess.run(['op', '--version'], capture_output=True, text=True, timeout=5)
            logger.info(f'1Password CLI version: {result.stdout.strip()}')
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning('1Password CLI (op) not found')
            return False
    
    async def _run_op(self, args: List[str]) -> Optional[str]:
        try:
            cmd = ['op'] + args + ['--format', 'json']
            env = os.environ.copy()
            if self._session_token:
                env['OP_SESSION'] = self._session_token
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
            )
            stdout, stderr = await proc.communicate()
            return stdout.decode() if proc.returncode == 0 else None
        except Exception as e:
            logger.error(f'1Password CLI error: {e}')
            return None
    
    async def get_credential(self, service: str, account: str) -> Optional[Credential]:
        result = await self._run_op(['item', 'get', f'{service} {account}', '--vault', self.vault])
        if not result:
            return None
        
        try:
            item = json.loads(result)
            username = password = otp_secret = None
            for field in item.get('fields', []):
                if field.get('id') == 'username':
                    username = field.get('value')
                elif field.get('id') == 'password':
                    password = field.get('value')
                elif field.get('type') == 'otp':
                    otp_secret = field.get('totp', {}).get('secret')
            
            if username and password:
                return Credential(username=username, password=password, otp_secret=otp_secret)
        except json.JSONDecodeError:
            pass
        return None
    
    async def store_credential(self, service: str, account: str, credential: Credential) -> bool:
        args = ['item', 'create', '--category', 'login', '--title', f'{service} - {account}',
                '--vault', self.vault, f'username={credential.username}', f'password={credential.password}']
        return await self._run_op(args) is not None
    
    async def list_accounts(self, service: str) -> List[str]:
        result = await self._run_op(['item', 'list', '--vault', self.vault, '--tags', service])
        if not result:
            return []
        try:
            return [item.get('title', '') for item in json.loads(result)]
        except json.JSONDecodeError:
            return []


class BitwardenProvider(CredentialProvider):
    """Bitwarden CLI credential provider."""
    
    def __init__(self):
        self._session_key: Optional[str] = None
        self._check_cli()
    
    def _check_cli(self) -> bool:
        try:
            result = subprocess.run(['bw', '--version'], capture_output=True, text=True, timeout=5)
            logger.info(f'Bitwarden CLI version: {result.stdout.strip()}')
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning('Bitwarden CLI (bw) not found')
            return False
    
    async def _run_bw(self, args: List[str]) -> Optional[str]:
        try:
            cmd = ['bw'] + args
            env = os.environ.copy()
            if self._session_key:
                env['BW_SESSION'] = self._session_key
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
            )
            stdout, stderr = await proc.communicate()
            return stdout.decode() if proc.returncode == 0 else None
        except Exception as e:
            logger.error(f'Bitwarden CLI error: {e}')
            return None
    
    async def get_credential(self, service: str, account: str) -> Optional[Credential]:
        await self._run_bw(['sync'])
        result = await self._run_bw(['list', 'items', '--search', f'{service} {account}'])
        if not result:
            return None
        
        try:
            items = json.loads(result)
            for item in items:
                login = item.get('login', {})
                if login.get('username') and login.get('password'):
                    return Credential(
                        username=login['username'],
                        password=login['password'],
                        otp_secret=login.get('totp')
                    )
        except json.JSONDecodeError:
            pass
        return None
    
    async def store_credential(self, service: str, account: str, credential: Credential) -> bool:
        item = {'type': 1, 'name': f'{service} - {account}',
                'login': {'username': credential.username, 'password': credential.password}}
        if credential.otp_secret:
            item['login']['totp'] = credential.otp_secret
        # Note: Actual implementation needs base64 encoding
        return False  # Placeholder
    
    async def list_accounts(self, service: str) -> List[str]:
        result = await self._run_bw(['list', 'items', '--search', service])
        if not result:
            return []
        try:
            return [item.get('name', '') for item in json.loads(result)]
        except json.JSONDecodeError:
            return []


class CredentialManager:
    """Unified credential manager with fallback providers."""
    
    def __init__(self):
        self.providers: List[CredentialProvider] = []
        self._init_providers()
    
    def _init_providers(self):
        # Try 1Password first
        try:
            self.providers.append(OnePasswordProvider())
            logger.info('1Password provider initialized')
        except Exception as e:
            logger.warning(f'Could not init 1Password: {e}')
        
        # Bitwarden fallback
        try:
            self.providers.append(BitwardenProvider())
            logger.info('Bitwarden provider initialized')
        except Exception as e:
            logger.warning(f'Could not init Bitwarden: {e}')
    
    async def get_credential(self, service: str, account: str) -> Optional[Credential]:
        for provider in self.providers:
            try:
                cred = await provider.get_credential(service, account)
                if cred:
                    logger.info(f'Found credential for {service}/{account}')
                    return cred
            except Exception as e:
                logger.warning(f'Provider failed: {e}')
        return None
    
    async def list_all_accounts(self, service: str) -> List[str]:
        accounts = set()
        for provider in self.providers:
            try:
                accounts.update(await provider.list_accounts(service))
            except Exception:
                pass
        return list(accounts)


# Singleton
_credential_manager: Optional[CredentialManager] = None

def get_credential_manager() -> CredentialManager:
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager
