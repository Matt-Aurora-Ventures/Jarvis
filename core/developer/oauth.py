"""
OAuth 2.0 Provider

OAuth implementation for third-party application authorization.

Prompts #61-64: Developer OAuth
"""

import asyncio
import hashlib
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import json
import base64

logger = logging.getLogger(__name__)


class OAuthScope(str, Enum):
    """OAuth permission scopes"""
    PROFILE_READ = "profile:read"
    PORTFOLIO_READ = "portfolio:read"
    PORTFOLIO_WRITE = "portfolio:write"
    TRADES_READ = "trades:read"
    TRADES_EXECUTE = "trades:execute"
    SIGNALS_READ = "signals:read"
    ALERTS_READ = "alerts:read"
    ALERTS_WRITE = "alerts:write"
    STAKING_READ = "staking:read"
    OFFLINE_ACCESS = "offline_access"  # For refresh tokens


SCOPE_DESCRIPTIONS = {
    OAuthScope.PROFILE_READ: "Read your profile information",
    OAuthScope.PORTFOLIO_READ: "View your portfolio and positions",
    OAuthScope.PORTFOLIO_WRITE: "Modify your portfolio settings",
    OAuthScope.TRADES_READ: "View your trading history",
    OAuthScope.TRADES_EXECUTE: "Execute trades on your behalf",
    OAuthScope.SIGNALS_READ: "Access trading signals",
    OAuthScope.ALERTS_READ: "View your alerts",
    OAuthScope.ALERTS_WRITE: "Create and manage alerts",
    OAuthScope.STAKING_READ: "View your staking info",
    OAuthScope.OFFLINE_ACCESS: "Maintain access when you're not using the app",
}


@dataclass
class OAuthClient:
    """An OAuth client application"""
    client_id: str
    client_secret_hash: str
    name: str
    description: str
    redirect_uris: List[str]
    owner_id: str
    allowed_scopes: List[OAuthScope]
    is_public: bool = False     # Public clients don't have secrets
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "name": self.name,
            "description": self.description,
            "redirect_uris": self.redirect_uris,
            "allowed_scopes": [s.value for s in self.allowed_scopes],
            "is_public": self.is_public,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class AuthorizationCode:
    """An authorization code for code flow"""
    code: str
    client_id: str
    user_id: str
    redirect_uri: str
    scopes: List[OAuthScope]
    code_challenge: Optional[str] = None  # PKCE
    code_challenge_method: Optional[str] = None
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(minutes=10)
    )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


@dataclass
class OAuthToken:
    """An OAuth access/refresh token"""
    token_id: str
    client_id: str
    user_id: str
    access_token: str
    token_type: str = "Bearer"
    scopes: List[OAuthScope] = field(default_factory=list)
    refresh_token: Optional[str] = None
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=1)
    )
    refresh_expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    revoked: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired

    def to_response(self) -> Dict[str, Any]:
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": int((self.expires_at - datetime.utcnow()).total_seconds()),
            "scope": " ".join(s.value for s in self.scopes),
            "refresh_token": self.refresh_token
        }


class OAuthProvider:
    """
    OAuth 2.0 authorization server.

    Supports:
    - Authorization Code flow
    - Authorization Code with PKCE
    - Client Credentials flow
    - Refresh token rotation
    """

    ACCESS_TOKEN_LIFETIME = timedelta(hours=1)
    REFRESH_TOKEN_LIFETIME = timedelta(days=30)
    AUTH_CODE_LIFETIME = timedelta(minutes=10)

    def __init__(self, storage_path: str = "data/oauth.json"):
        self.storage_path = storage_path
        self._clients: Dict[str, OAuthClient] = {}
        self._auth_codes: Dict[str, AuthorizationCode] = {}
        self._tokens: Dict[str, OAuthToken] = {}
        self._token_lookup: Dict[str, str] = {}  # access_token -> token_id
        self._load()

    def _load(self):
        """Load data from storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r") as f:
                    data = json.load(f)

                for item in data.get("clients", []):
                    client = OAuthClient(
                        client_id=item["client_id"],
                        client_secret_hash=item["client_secret_hash"],
                        name=item["name"],
                        description=item.get("description", ""),
                        redirect_uris=item["redirect_uris"],
                        owner_id=item["owner_id"],
                        allowed_scopes=[
                            OAuthScope(s) for s in item.get("allowed_scopes", [])
                        ],
                        is_public=item.get("is_public", False),
                        is_active=item.get("is_active", True),
                        created_at=datetime.fromisoformat(item["created_at"])
                    )
                    self._clients[client.client_id] = client

                for item in data.get("tokens", []):
                    token = OAuthToken(
                        token_id=item["token_id"],
                        client_id=item["client_id"],
                        user_id=item["user_id"],
                        access_token=item["access_token"],
                        scopes=[OAuthScope(s) for s in item.get("scopes", [])],
                        refresh_token=item.get("refresh_token"),
                        expires_at=datetime.fromisoformat(item["expires_at"]),
                        revoked=item.get("revoked", False)
                    )
                    if token.is_valid:
                        self._tokens[token.token_id] = token
                        self._token_lookup[token.access_token] = token.token_id
        except Exception as e:
            logger.error(f"Failed to load OAuth data: {e}")

    def _save(self):
        """Save data to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                "clients": [
                    {
                        "client_id": c.client_id,
                        "client_secret_hash": c.client_secret_hash,
                        "name": c.name,
                        "description": c.description,
                        "redirect_uris": c.redirect_uris,
                        "owner_id": c.owner_id,
                        "allowed_scopes": [s.value for s in c.allowed_scopes],
                        "is_public": c.is_public,
                        "is_active": c.is_active,
                        "created_at": c.created_at.isoformat()
                    }
                    for c in self._clients.values()
                ],
                "tokens": [
                    {
                        "token_id": t.token_id,
                        "client_id": t.client_id,
                        "user_id": t.user_id,
                        "access_token": t.access_token,
                        "scopes": [s.value for s in t.scopes],
                        "refresh_token": t.refresh_token,
                        "expires_at": t.expires_at.isoformat(),
                        "revoked": t.revoked
                    }
                    for t in self._tokens.values()
                    if t.is_valid
                ]
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save OAuth data: {e}")

    @staticmethod
    def _hash_secret(secret: str) -> str:
        """Hash a client secret"""
        return hashlib.sha256(secret.encode()).hexdigest()

    @staticmethod
    def _generate_token() -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def _generate_code() -> str:
        """Generate authorization code"""
        return secrets.token_urlsafe(48)

    # =========================================================================
    # CLIENT MANAGEMENT
    # =========================================================================

    async def register_client(
        self,
        owner_id: str,
        name: str,
        description: str,
        redirect_uris: List[str],
        allowed_scopes: Optional[List[OAuthScope]] = None,
        is_public: bool = False
    ) -> Dict[str, str]:
        """Register a new OAuth client"""
        client_id = f"cli_{secrets.token_hex(12)}"
        client_secret = self._generate_token()

        client = OAuthClient(
            client_id=client_id,
            client_secret_hash=self._hash_secret(client_secret),
            name=name,
            description=description,
            redirect_uris=redirect_uris,
            owner_id=owner_id,
            allowed_scopes=allowed_scopes or list(OAuthScope),
            is_public=is_public
        )

        self._clients[client_id] = client
        self._save()

        logger.info(f"Registered OAuth client: {client_id}")

        result = {"client_id": client_id}
        if not is_public:
            result["client_secret"] = client_secret
        return result

    async def get_client(self, client_id: str) -> Optional[OAuthClient]:
        """Get a client by ID"""
        return self._clients.get(client_id)

    async def verify_client(
        self,
        client_id: str,
        client_secret: Optional[str] = None
    ) -> Optional[OAuthClient]:
        """Verify client credentials"""
        client = self._clients.get(client_id)
        if not client or not client.is_active:
            return None

        if client.is_public:
            return client

        if not client_secret:
            return None

        if self._hash_secret(client_secret) != client.client_secret_hash:
            return None

        return client

    # =========================================================================
    # AUTHORIZATION CODE FLOW
    # =========================================================================

    async def create_authorization_code(
        self,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        scopes: List[OAuthScope],
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None
    ) -> Optional[str]:
        """Create an authorization code"""
        client = self._clients.get(client_id)
        if not client or not client.is_active:
            return None

        # Validate redirect URI
        if redirect_uri not in client.redirect_uris:
            return None

        # Validate scopes
        for scope in scopes:
            if scope not in client.allowed_scopes:
                return None

        code = self._generate_code()

        auth_code = AuthorizationCode(
            code=code,
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method
        )

        self._auth_codes[code] = auth_code
        return code

    async def exchange_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> Optional[OAuthToken]:
        """Exchange authorization code for tokens"""
        auth_code = self._auth_codes.get(code)
        if not auth_code:
            return None

        # Validate
        if auth_code.is_expired:
            del self._auth_codes[code]
            return None

        if auth_code.client_id != client_id:
            return None

        if auth_code.redirect_uri != redirect_uri:
            return None

        # Verify PKCE if used
        if auth_code.code_challenge:
            if not code_verifier:
                return None

            if auth_code.code_challenge_method == "S256":
                expected = base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                ).decode().rstrip("=")
            else:
                expected = code_verifier

            if expected != auth_code.code_challenge:
                return None

        # Create token
        token = await self._create_token(
            client_id=client_id,
            user_id=auth_code.user_id,
            scopes=auth_code.scopes
        )

        # Consume code
        del self._auth_codes[code]

        return token

    async def _create_token(
        self,
        client_id: str,
        user_id: str,
        scopes: List[OAuthScope]
    ) -> OAuthToken:
        """Create access and refresh tokens"""
        token_id = f"tok_{secrets.token_hex(8)}"
        access_token = self._generate_token()
        refresh_token = None

        if OAuthScope.OFFLINE_ACCESS in scopes:
            refresh_token = self._generate_token()

        token = OAuthToken(
            token_id=token_id,
            client_id=client_id,
            user_id=user_id,
            access_token=access_token,
            scopes=scopes,
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + self.ACCESS_TOKEN_LIFETIME,
            refresh_expires_at=(
                datetime.utcnow() + self.REFRESH_TOKEN_LIFETIME
                if refresh_token else None
            )
        )

        self._tokens[token_id] = token
        self._token_lookup[access_token] = token_id
        self._save()

        return token

    # =========================================================================
    # TOKEN VALIDATION
    # =========================================================================

    async def validate_token(
        self,
        access_token: str,
        required_scopes: Optional[List[OAuthScope]] = None
    ) -> Optional[OAuthToken]:
        """Validate an access token"""
        token_id = self._token_lookup.get(access_token)
        if not token_id:
            return None

        token = self._tokens.get(token_id)
        if not token or not token.is_valid:
            return None

        # Check scopes
        if required_scopes:
            for scope in required_scopes:
                if scope not in token.scopes:
                    return None

        return token

    async def refresh_tokens(
        self,
        refresh_token: str,
        client_id: str
    ) -> Optional[OAuthToken]:
        """Refresh access token using refresh token"""
        # Find token with this refresh token
        token = None
        for t in self._tokens.values():
            if t.refresh_token == refresh_token and t.client_id == client_id:
                token = t
                break

        if not token:
            return None

        if token.revoked:
            return None

        if token.refresh_expires_at and datetime.utcnow() > token.refresh_expires_at:
            return None

        # Revoke old token
        token.revoked = True
        if token.access_token in self._token_lookup:
            del self._token_lookup[token.access_token]

        # Create new token
        new_token = await self._create_token(
            client_id=token.client_id,
            user_id=token.user_id,
            scopes=token.scopes
        )

        return new_token

    async def revoke_token(self, access_token: str):
        """Revoke an access token"""
        token_id = self._token_lookup.get(access_token)
        if token_id and token_id in self._tokens:
            self._tokens[token_id].revoked = True
            del self._token_lookup[access_token]
            self._save()

    async def revoke_all_tokens(self, user_id: str, client_id: Optional[str] = None):
        """Revoke all tokens for a user"""
        for token in self._tokens.values():
            if token.user_id == user_id:
                if client_id is None or token.client_id == client_id:
                    token.revoked = True
                    if token.access_token in self._token_lookup:
                        del self._token_lookup[token.access_token]
        self._save()


# Testing
if __name__ == "__main__":
    async def test():
        provider = OAuthProvider("data/test_oauth.json")

        # Register client
        result = await provider.register_client(
            owner_id="test_user",
            name="Test App",
            description="A test application",
            redirect_uris=["http://localhost:3000/callback"],
            allowed_scopes=[
                OAuthScope.PROFILE_READ,
                OAuthScope.PORTFOLIO_READ,
                OAuthScope.OFFLINE_ACCESS
            ]
        )
        print(f"Registered client: {result}")

        # Create auth code
        code = await provider.create_authorization_code(
            client_id=result["client_id"],
            user_id="user_123",
            redirect_uri="http://localhost:3000/callback",
            scopes=[OAuthScope.PROFILE_READ, OAuthScope.PORTFOLIO_READ]
        )
        print(f"Auth code: {code}")

        # Exchange for tokens
        token = await provider.exchange_code(
            code=code,
            client_id=result["client_id"],
            redirect_uri="http://localhost:3000/callback"
        )
        if token:
            print(f"Token response: {token.to_response()}")

            # Validate token
            validated = await provider.validate_token(token.access_token)
            print(f"Validated: {validated is not None}")

    asyncio.run(test())
