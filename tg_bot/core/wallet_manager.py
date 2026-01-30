"""
User Wallet Manager for Jarvis Trading Bot.

Each user gets their own wallet for trading (not treasury).
Wallets are stored encrypted in Redis per user.
Treasury only collects success fees.
"""

import os
import json
import base64
import hashlib
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore

logger = logging.getLogger(__name__)

# Encryption key derived from environment secret + user_id
WALLET_ENCRYPTION_SECRET = os.getenv("WALLET_ENCRYPTION_SECRET", "jarvis-wallet-secret-2026")


@dataclass
class UserWallet:
    """User wallet data."""
    user_id: int
    public_key: str
    encrypted_private_key: str  # Never exposed except via /wallet export in DM
    created_at: str


class WalletManager:
    """
    Manages user wallets with encryption.
    
    Storage: Redis hash "jarvis:user_wallets:{user_id}"
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        
    def _get_encryption_key(self, user_id: int) -> bytes:
        """Derive unique encryption key per user."""
        salt = f"jarvis-user-{user_id}".encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(WALLET_ENCRYPTION_SECRET.encode())
        return base64.urlsafe_b64encode(key)
    
    def _encrypt(self, data: str, user_id: int) -> str:
        """Encrypt data with user-specific key."""
        f = Fernet(self._get_encryption_key(user_id))
        return f.encrypt(data.encode()).decode()
    
    def _decrypt(self, encrypted_data: str, user_id: int) -> str:
        """Decrypt data with user-specific key."""
        f = Fernet(self._get_encryption_key(user_id))
        return f.decrypt(encrypted_data.encode()).decode()
    
    def _redis_key(self, user_id: int) -> str:
        return f"jarvis:user_wallet:{user_id}"
    
    async def get_wallet(self, user_id: int) -> Optional[UserWallet]:
        """Get user's wallet if exists."""
        try:
            data = await self.redis.hgetall(self._redis_key(user_id))
            if not data:
                return None
            return UserWallet(
                user_id=user_id,
                public_key=data.get("public_key", ""),
                encrypted_private_key=data.get("encrypted_private_key", ""),
                created_at=data.get("created_at", ""),
            )
        except Exception as e:
            logger.error(f"Error getting wallet for user {user_id}: {e}")
            return None
    
    async def create_wallet(self, user_id: int) -> Tuple[UserWallet, str]:
        """
        Create new wallet for user.
        Returns (wallet, private_key_base58) - private key shown once on creation.
        """
        from datetime import datetime, timezone
        
        # Generate new keypair
        keypair = Keypair()
        public_key = str(keypair.pubkey())
        private_key_bytes = bytes(keypair)
        private_key_b58 = base64.b58encode(private_key_bytes).decode() if hasattr(base64, 'b58encode') else keypair.to_base58_string()
        
        # Actually use solders' built-in base58 encoding
        try:
            # Get the secret key bytes (64 bytes: 32 secret + 32 public)
            private_key_b58 = str(keypair)
        except:
            # Fallback
            import base58
            private_key_b58 = base58.b58encode(private_key_bytes).decode()
        
        # Encrypt private key
        encrypted_pk = self._encrypt(private_key_b58, user_id)
        
        wallet = UserWallet(
            user_id=user_id,
            public_key=public_key,
            encrypted_private_key=encrypted_pk,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Store in Redis
        await self.redis.hset(
            self._redis_key(user_id),
            mapping={
                "public_key": wallet.public_key,
                "encrypted_private_key": wallet.encrypted_private_key,
                "created_at": wallet.created_at,
            }
        )
        
        logger.info(f"Created new wallet for user {user_id}: {public_key}")
        return wallet, private_key_b58
    
    async def import_wallet(self, user_id: int, private_key_b58: str) -> Optional[UserWallet]:
        """
        Import existing wallet from private key.
        Returns wallet if successful, None if invalid key.
        """
        from datetime import datetime, timezone
        
        try:
            # Parse private key
            keypair = Keypair.from_base58_string(private_key_b58.strip())
            public_key = str(keypair.pubkey())
            
            # Encrypt private key
            encrypted_pk = self._encrypt(private_key_b58.strip(), user_id)
            
            wallet = UserWallet(
                user_id=user_id,
                public_key=public_key,
                encrypted_private_key=encrypted_pk,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            
            # Store in Redis
            await self.redis.hset(
                self._redis_key(user_id),
                mapping={
                    "public_key": wallet.public_key,
                    "encrypted_private_key": wallet.encrypted_private_key,
                    "created_at": wallet.created_at,
                }
            )
            
            logger.info(f"Imported wallet for user {user_id}: {public_key}")
            return wallet
            
        except Exception as e:
            logger.error(f"Failed to import wallet for user {user_id}: {e}")
            return None
    
    async def export_private_key(self, user_id: int) -> Optional[str]:
        """
        Export private key (ONLY for DM, never in groups).
        Returns base58 private key or None if no wallet.
        """
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return None
        
        try:
            return self._decrypt(wallet.encrypted_private_key, user_id)
        except Exception as e:
            logger.error(f"Failed to decrypt wallet for user {user_id}: {e}")
            return None
    
    async def get_keypair(self, user_id: int) -> Optional[Keypair]:
        """
        Get Keypair object for signing transactions.
        Used internally for trading operations.
        """
        private_key = await self.export_private_key(user_id)
        if not private_key:
            return None
        
        try:
            return Keypair.from_base58_string(private_key)
        except Exception as e:
            logger.error(f"Failed to create keypair for user {user_id}: {e}")
            return None
    
    async def get_balance_sol(self, user_id: int) -> Optional[float]:
        """Get wallet SOL balance from RPC."""
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return None
        
        try:
            from solana.rpc.async_api import AsyncClient
            
            rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
            async with AsyncClient(rpc_url) as client:
                pubkey = Pubkey.from_string(wallet.public_key)
                response = await client.get_balance(pubkey)
                if response.value is not None:
                    return response.value / 1e9  # lamports to SOL
        except Exception as e:
            logger.error(f"Failed to get balance for user {user_id}: {e}")
        
        return None
    
    async def delete_wallet(self, user_id: int) -> bool:
        """Delete user's wallet (careful - irreversible if not exported!)."""
        try:
            await self.redis.delete(self._redis_key(user_id))
            logger.info(f"Deleted wallet for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete wallet for user {user_id}: {e}")
            return False


# Singleton instance
_wallet_manager: Optional[WalletManager] = None


def get_wallet_manager() -> WalletManager:
    """Get or create wallet manager singleton."""
    global _wallet_manager
    if _wallet_manager is None:
        import redis.asyncio as redis
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        _wallet_manager = WalletManager(redis_client)
    return _wallet_manager


async def init_wallet_manager(redis_client) -> WalletManager:
    """Initialize wallet manager with existing Redis client."""
    global _wallet_manager
    _wallet_manager = WalletManager(redis_client)
    return _wallet_manager
