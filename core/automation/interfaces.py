"""
Abstract interfaces for the automation system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Credential:
    """Secure credential container."""
    username: str
    password: str
    otp_secret: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowserSession:
    """Browser session state for persistence."""
    cookies: List[Dict[str, Any]]
    local_storage: Dict[str, str]
    session_storage: Dict[str, str]
    user_agent: str
    created_at: datetime
    last_used: datetime
    domain: str = ''


@dataclass
class OAuthToken:
    """OAuth token container with metadata."""
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime
    scopes: List[str]
    account_id: str
    provider: str
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at


class CredentialProvider(ABC):
    """Abstract credential provider interface."""
    
    @abstractmethod
    async def get_credential(self, service: str, account: str) -> Optional[Credential]:
        pass
    
    @abstractmethod
    async def store_credential(self, service: str, account: str, credential: Credential) -> bool:
        pass
    
    @abstractmethod
    async def list_accounts(self, service: str) -> List[str]:
        pass


class BrowserAutomator(ABC):
    """Abstract browser automation interface."""
    
    @abstractmethod
    async def connect(self, debug_port: int = 9222) -> bool:
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        pass
    
    @abstractmethod
    async def navigate(self, url: str) -> bool:
        pass
    
    @abstractmethod
    async def screenshot(self, path: str) -> bool:
        pass
    
    @abstractmethod
    async def save_session(self, name: str) -> BrowserSession:
        pass
    
    @abstractmethod
    async def restore_session(self, session: BrowserSession) -> bool:
        pass
    
    @abstractmethod
    async def execute_script(self, script: str) -> Any:
        pass


class OAuthManager(ABC):
    """Abstract OAuth token manager."""
    
    @abstractmethod
    async def get_token(self, account_id: str) -> Optional[OAuthToken]:
        pass
    
    @abstractmethod
    async def refresh_token(self, account_id: str) -> Optional[OAuthToken]:
        pass
    
    @abstractmethod
    async def store_token(self, token: OAuthToken) -> bool:
        pass
    
    @abstractmethod
    async def list_accounts(self) -> List[str]:
        pass
