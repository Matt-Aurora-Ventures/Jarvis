"""Secure wallet keystore for encrypted private key storage.

CRITICAL SECURITY: Never store wallet passwords in environment variables!
Use this encrypted keystore instead.

Usage:
    from core.wallet.keystore import WalletKeystore
    
    # Initialize keystore with master password (from user input, not env)
    keystore = WalletKeystore(master_password="user-provided-password")
    
    # Store wallet (one-time setup)
    keystore.store_wallet("jarvis_main", private_key_bytes, salt)
    
    # Load wallet (runtime)
    private_key = keystore.load_wallet("jarvis_main")
"""

import os
import json
import logging
import hashlib
from typing import Optional, Dict
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64

logger = logging.getLogger(__name__)


class WalletKeystore:
    """Encrypted storage for wallet private keys.
    
    Uses PBKDF2 + Fernet encryption to protect keys at rest.
    Master password should NEVER be stored - only provided at runtime.
    """
    
    DEFAULT_KEYSTORE_PATH = Path.home() / ".jarvis" / "wallets.enc"
    
    def __init__(self, master_password: str, keystore_path: Optional[Path] = None):
        """Initialize keystore with master password.
        
        Args:
            master_password: Master password for encryption (user-provided)
            keystore_path: Optional custom keystore location
        """
        self.keystore_path = keystore_path or self.DEFAULT_KEYSTORE_PATH
        self.keystore_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Derive encryption key from master password
        self._fernet = self._derive_key(master_password)
    
    def _derive_key(self, password: str) -> Fernet:
        """Derive Fernet key from password using PBKDF2.
        
        Args:
            password: Master password
            
        Returns:
            Fernet cipher instance
        """
        # Use fixed salt for key derivation (stored with encrypted data)
        # In production, consider storing salt separately
        salt = b"jarvis_wallet_keystore_v1"  
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def store_wallet(
        self,
        wallet_name: str,
        private_key_data: bytes,
        metadata: Optional[Dict] = None
    ):
        """Store encrypted wallet private key.
        
        Args:
            wallet_name: Unique wallet identifier
            private_key_data: Raw private key bytes
            metadata: Optional wallet metadata (public key, address, etc.)
        """
        # Load existing keystore
        wallets = self._load_keystore()
        
        # Encrypt private key
        encrypted_key = self._fernet.encrypt(private_key_data)
        
        # Store with metadata
        wallets[wallet_name] = {
            "encrypted_key": encrypted_key.decode(),
            "metadata": metadata or {},
        }
        
        # Save keystore
        self._save_keystore(wallets)
        logger.info(f"Wallet '{wallet_name}' stored securely in keystore")
    
    def load_wallet(self, wallet_name: str) -> bytes:
        """Load and decrypt wallet private key.
        
        Args:
            wallet_name: Wallet identifier
            
        Returns:
            Decrypted private key bytes
            
        Raises:
            KeyError: If wallet not found
            ValueError: If decryption fails (wrong password)
        """
        wallets = self._load_keystore()
        
        if wallet_name not in wallets:
            available = list(wallets.keys())
            raise KeyError(
                f"Wallet '{wallet_name}' not found in keystore.\n"
                f"Available wallets: {available}"
            )
        
        wallet_data = wallets[wallet_name]
        encrypted_key = wallet_data["encrypted_key"].encode()
        
        try:
            private_key = self._fernet.decrypt(encrypted_key)
            return private_key
        except Exception as e:
            raise ValueError(
                f"Failed to decrypt wallet '{wallet_name}'. "
                "Incorrect master password?"
            ) from e
    
    def list_wallets(self) -> list:
        """List all wallet names in keystore.
        
        Returns:
            List of wallet names
        """
        wallets = self._load_keystore()
        return list(wallets.keys())
    
    def get_metadata(self, wallet_name: str) -> Dict:
        """Get wallet metadata without decrypting key.
        
        Args:
            wallet_name: Wallet identifier
            
        Returns:
            Wallet metadata dict
        """
        wallets = self._load_keystore()
        if wallet_name not in wallets:
            raise KeyError(f"Wallet '{wallet_name}' not found")
        return wallets[wallet_name]["metadata"]
    
    def remove_wallet(self, wallet_name: str):
        """Remove wallet from keystore.
        
        Args:
            wallet_name: Wallet identifier
        """
        wallets = self._load_keystore()
        if wallet_name in wallets:
            del wallets[wallet_name]
            self._save_keystore(wallets)
            logger.info(f"Wallet '{wallet_name}' removed from keystore")
        else:
            logger.warning(f"Wallet '{wallet_name}' not found in keystore")
    
    def _load_keystore(self) -> Dict:
        """Load keystore from disk.
        
        Returns:
            Dict of wallet data
        """
        if not self.keystore_path.exists():
            return {}
        
        try:
            with open(self.keystore_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load keystore: {e}")
            return {}
    
    def _save_keystore(self, wallets: Dict):
        """Save keystore to disk.
        
        Args:
            wallets: Wallet data dict
        """
        with open(self.keystore_path, 'w') as f:
            json.dump(wallets, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(self.keystore_path, 0o600)


# Convenience function for migration
def migrate_env_wallet_to_keystore(
    wallet_name: str,
    env_var_name: str,
    master_password: str
):
    """One-time migration helper to move wallet from env to keystore.
    
    WARNING: This is for migration only. After migrating, remove the
    env var from .env file permanently.
    
    Args:
        wallet_name: Name for wallet in keystore
        env_var_name: Environment variable containing password/key
        master_password: Master password for keystore
        
    Example:
        # One-time migration
        migrate_env_wallet_to_keystore(
            "jarvis_main",
            "JARVIS_WALLET_PASSWORD",  # OLD - will be removed
            "secure-master-password"    # NEW - user provides
        )
    """
    import warnings
    warnings.warn(
        "migrate_env_wallet_to_keystore is for one-time migration only. "
        "Remove env vars after migration!",
        DeprecationWarning,
        stacklevel=2
    )
    
    wallet_password = os.getenv(env_var_name)
    if not wallet_password:
        raise ValueError(f"Environment variable {env_var_name} not found")
    
    # For Solana wallets, the password might need to be converted to private key
    # This is a placeholder - actual implementation depends on wallet format
    private_key_bytes = wallet_password.encode()  # Simplified
    
    keystore = WalletKeystore(master_password)
    keystore.store_wallet(
        wallet_name,
        private_key_bytes,
        metadata={
            "migrated_from": env_var_name,
            "wallet_type": "solana"
        }
    )
    
    print(f"✅ Wallet '{wallet_name}' migrated to encrypted keystore")
    print(f"⚠️  IMPORTANT: Remove {env_var_name} from .env file NOW")
