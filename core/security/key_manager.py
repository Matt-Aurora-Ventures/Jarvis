"""
Persistent Key Management for Jarvis Treasury.

Hardwired key discovery and loading to prevent keys from being "lost".
This module provides a single source of truth for all key-related operations.
"""

import os
import json
import base64
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Project root detection
def _find_project_root() -> Path:
    """Find the Jarvis project root directory."""
    # Start from this file's location
    current = Path(__file__).resolve()
    
    # Walk up until we find key markers
    for parent in [current] + list(current.parents):
        if (parent / "tg_bot").exists() or (parent / "bots").exists():
            return parent
        if (parent / ".git").exists():
            return parent
    
    # Fallback to cwd
    return Path.cwd()


PROJECT_ROOT = _find_project_root()


@dataclass
class KeyConfig:
    """Configuration for a key location."""
    path: Path
    encrypted: bool
    encryption_type: str  # 'nacl', 'fernet', 'none'
    description: str


# HARDWIRED KEY LOCATIONS - Add new key locations here
KEY_LOCATIONS = {
    "treasury_primary": KeyConfig(
        path=PROJECT_ROOT / "data" / "treasury_keypair.json",
        encrypted=True,
        encryption_type="nacl",
        description="Primary treasury keypair (NaCl encrypted)"
    ),
    "treasury_backup": KeyConfig(
        path=PROJECT_ROOT / "bots" / "treasury" / ".wallets" / "treasury.key",
        encrypted=True,
        encryption_type="fernet",
        description="Backup treasury key (Fernet encrypted)"
    ),
    "secure_wallet_dir": KeyConfig(
        path=PROJECT_ROOT / "bots" / "treasury" / ".wallets",
        encrypted=True,
        encryption_type="fernet",
        description="SecureWallet directory"
    ),
}

# Environment variable names for passwords
PASSWORD_ENV_VARS = [
    "JARVIS_WALLET_PASSWORD",
    "TREASURY_WALLET_PASSWORD",
    "WALLET_PASSWORD",
]

# Environment variable names for key paths
KEY_PATH_ENV_VARS = [
    "TREASURY_WALLET_PATH",
    "TREASURY_KEYPAIR_PATH",
    "JARVIS_KEYPAIR_PATH",
]


class KeyManager:
    """
    Centralized key management with automatic discovery.
    
    Usage:
        km = KeyManager()
        keypair = km.load_treasury_keypair()
    """
    
    _instance: Optional["KeyManager"] = None
    
    def __new__(cls):
        """Singleton pattern for consistent state."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._password: Optional[str] = None
        self._cached_keypairs: Dict[str, Any] = {}
        self._initialized = True
        
        # Auto-load password from environment
        self._load_password()
    
    def _load_password(self):
        """Load password from environment or .env files."""
        # Check environment variables first
        for env_var in PASSWORD_ENV_VARS:
            if os.environ.get(env_var):
                self._password = os.environ[env_var]
                logger.debug(f"Password loaded from {env_var}")
                return
        
        # Check .env files
        env_files = [
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / "tg_bot" / ".env",
            PROJECT_ROOT / "bots" / "treasury" / ".env",
        ]
        
        for env_file in env_files:
            if env_file.exists():
                try:
                    for line in env_file.read_text().splitlines():
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        if key in PASSWORD_ENV_VARS and value:
                            self._password = value
                            os.environ[key] = value  # Also set in env
                            logger.debug(f"Password loaded from {env_file}")
                            return
                except Exception as e:
                    logger.warning(f"Failed to read {env_file}: {e}")
        
        logger.warning("No wallet password found in environment or .env files")
    
    def _find_keypair_path(self) -> Optional[Path]:
        """Find the keypair file using hardwired locations and env vars."""
        # Check environment variable paths first
        for env_var in KEY_PATH_ENV_VARS:
            env_path = os.environ.get(env_var, "").strip()
            if env_path:
                path = Path(env_path)
                if path.exists():
                    logger.debug(f"Keypair found via {env_var}: {path}")
                    return path
        
        # Check hardwired locations
        for name, config in KEY_LOCATIONS.items():
            if not config.path.exists():
                continue

            if config.path.is_file():
                logger.debug(f"Keypair found at {name}: {config.path}")
                return config.path

            # SecureWallet directory: resolve to the active treasury key file
            if name == "secure_wallet_dir" and config.path.is_dir():
                key_path = self._find_secure_wallet_treasury_key(config.path)
                if key_path:
                    logger.debug(f"Treasury key discovered in SecureWallet dir: {key_path}")
                    return key_path
        
        # Search for any .json file with keypair structure in data/
        data_dir = PROJECT_ROOT / "data"
        if data_dir.exists():
            for json_file in data_dir.glob("*keypair*.json"):
                if json_file.exists():
                    logger.debug(f"Keypair discovered: {json_file}")
                    return json_file
        
        return None

    def _find_secure_wallet_treasury_key(self, wallet_dir: Path) -> Optional[Path]:
        """
        Resolve a SecureWallet directory (bots/treasury/.wallets) to the treasury key file.

        SecureWallet stores keys as <pubkey>.key and tracks public metadata in registry.json.
        """
        registry_path = wallet_dir / "registry.json"
        if registry_path.exists():
            try:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                treasury_addr: Optional[str] = None

                # Prefer the explicitly flagged treasury wallet
                for addr, info in registry.items():
                    if isinstance(info, dict) and info.get("is_treasury"):
                        treasury_addr = (info.get("address") or addr)
                        break

                # Fallback: first entry
                if not treasury_addr and registry:
                    first_addr, info = next(iter(registry.items()))
                    if isinstance(info, dict):
                        treasury_addr = (info.get("address") or first_addr)
                    else:
                        treasury_addr = first_addr

                if treasury_addr:
                    key_path = wallet_dir / f"{treasury_addr}.key"
                    if key_path.exists() and key_path.is_file():
                        return key_path
            except Exception as e:
                logger.warning(f"Failed to read secure wallet registry {registry_path}: {e}")

        # Last resort: if there's exactly one .key file, assume it is the treasury key
        key_files = sorted(wallet_dir.glob("*.key"))
        if len(key_files) == 1:
            return key_files[0]

        return None
    
    def _decrypt_nacl(self, data: dict) -> Optional[bytes]:
        """Decrypt NaCl-encrypted keypair."""
        if not self._password:
            logger.error("No password available for decryption")
            return None
        
        try:
            import nacl.secret
            import nacl.pwhash
            
            salt = base64.b64decode(data["salt"])
            nonce = base64.b64decode(data["nonce"])
            encrypted = base64.b64decode(data["encrypted_key"])
            
            key = nacl.pwhash.argon2id.kdf(
                nacl.secret.SecretBox.KEY_SIZE,
                self._password.encode(),
                salt,
                opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
                memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
            )
            
            box = nacl.secret.SecretBox(key)
            return box.decrypt(encrypted, nonce)
        
        except ImportError:
            logger.error("PyNaCl not installed: pip install pynacl")
            return None
        except Exception as e:
            logger.error(f"NaCl decryption failed: {e}")
            return None
    
    def _decrypt_fernet(self, encrypted_bytes: bytes, wallet_dir: Optional[Path] = None) -> Optional[bytes]:
        """Decrypt Fernet-encrypted keypair."""
        if not self._password:
            logger.error("No password available for decryption")
            return None
        
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            # Load salt from the SecureWallet directory. Prefer the key file's directory when available.
            salt_root = wallet_dir or KEY_LOCATIONS["secure_wallet_dir"].path
            salt_path = salt_root / ".salt"
            if not salt_path.exists():
                logger.error("Fernet salt file not found")
                return None
            
            salt = salt_path.read_bytes()
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(self._password.encode()))
            fernet = Fernet(key)
            token = encrypted_bytes.strip()
            return fernet.decrypt(token)
        
        except ImportError:
            logger.error("cryptography not installed: pip install cryptography")
            return None
        except Exception as e:
            logger.error(f"Fernet decryption failed: {e}")
            return None
    
    def load_treasury_keypair(self, force_reload: bool = False):
        """
        Load the treasury keypair from the hardwired locations.
        
        Returns:
            solders.keypair.Keypair or None
        """
        cache_key = "treasury"
        
        if not force_reload and cache_key in self._cached_keypairs:
            return self._cached_keypairs[cache_key]
        
        keypair_path = self._find_keypair_path()
        if not keypair_path:
            logger.error("No treasury keypair found in any known location")
            logger.error(f"Checked locations: {[str(c.path) for c in KEY_LOCATIONS.values()]}")
            return None
        
        try:
            decrypted: Optional[bytes] = None

            # SecureWallet stores Fernet tokens as raw bytes in <pubkey>.key
            if keypair_path.suffix == ".key":
                decrypted = self._decrypt_fernet(keypair_path.read_bytes(), wallet_dir=keypair_path.parent)
            else:
                with open(keypair_path, encoding="utf-8") as f:
                    data = json.load(f)

                # Determine encryption type
                if isinstance(data, dict) and "encrypted_key" in data and "salt" in data and "nonce" in data:
                    # NaCl encrypted format
                    decrypted = self._decrypt_nacl(data)
                elif isinstance(data, list):
                    # Raw keypair bytes (unencrypted)
                    decrypted = bytes(data)
                elif isinstance(data, dict) and "key" in data:
                    # Simple encrypted format stored as JSON
                    decrypted = self._decrypt_fernet(base64.b64decode(data["key"]), wallet_dir=keypair_path.parent)

            # If we couldn't parse JSON, but the file exists, try treating it as a raw Fernet token.
            if not decrypted:
                try:
                    decrypted = self._decrypt_fernet(keypair_path.read_bytes(), wallet_dir=keypair_path.parent)
                except Exception:
                    decrypted = None

            if not decrypted:
                logger.error("Failed to decrypt keypair")
                return None

            from solders.keypair import Keypair
            keypair = Keypair.from_bytes(decrypted)
            
            # Cache for future use
            self._cached_keypairs[cache_key] = keypair
            
            address = str(keypair.pubkey())
            logger.info(f"Treasury keypair loaded: {address[:8]}...{address[-6:]}")
            
            return keypair
        
        except Exception as e:
            logger.error(f"Failed to load treasury keypair: {e}")
            return None
    
    def get_treasury_address(self) -> Optional[str]:
        """Get treasury address without loading full keypair."""
        keypair_path = self._find_keypair_path()
        if not keypair_path:
            return None

        # SecureWallet-style filenames embed the pubkey in the filename
        if keypair_path.suffix == ".key":
            stem = keypair_path.stem
            if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,64}", stem):
                return stem
        
        try:
            with open(keypair_path) as f:
                data = json.load(f)
            
            # Check for pubkey field
            if "pubkey" in data:
                return data["pubkey"]
            
            # Otherwise load full keypair
            keypair = self.load_treasury_keypair()
            if keypair:
                return str(keypair.pubkey())
        except Exception:  # noqa: BLE001 - intentional catch-all
            pass
        
        return None
    
    def verify_key_access(self) -> Dict[str, Any]:
        """
        Verify all key locations and access.
        
        Returns:
            Dict with status of each key location
        """
        results = {
            "password_available": self._password is not None,
            "locations": {},
            "treasury_accessible": False,
        }
        
        for name, config in KEY_LOCATIONS.items():
            results["locations"][name] = {
                "path": str(config.path),
                "exists": config.path.exists(),
                "encrypted": config.encrypted,
                "description": config.description,
            }
        
        # Try to load treasury
        keypair = self.load_treasury_keypair()
        if keypair:
            results["treasury_accessible"] = True
            results["treasury_address"] = str(keypair.pubkey())
        
        return results
    
    def get_status_report(self) -> str:
        """Get human-readable status report."""
        status = self.verify_key_access()
        
        lines = ["=== Key Manager Status ==="]
        lines.append(f"Password: {'Set' if status['password_available'] else 'NOT SET'}")
        lines.append(f"Treasury: {'ACCESSIBLE' if status['treasury_accessible'] else 'NOT ACCESSIBLE'}")
        
        if status.get("treasury_address"):
            addr = status["treasury_address"]
            lines.append(f"Address: {addr[:8]}...{addr[-6:]}")
        
        lines.append("\nKey Locations:")
        for name, info in status["locations"].items():
            exists = "YES" if info["exists"] else "NO"
            lines.append(f"  {name}: {exists} - {info['path']}")
        
        return "\n".join(lines)


# Singleton accessor
_key_manager: Optional[KeyManager] = None

def get_key_manager() -> KeyManager:
    """Get the singleton KeyManager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


def load_treasury_keypair():
    """Convenience function to load treasury keypair."""
    return get_key_manager().load_treasury_keypair()


def get_treasury_address() -> Optional[str]:
    """Convenience function to get treasury address."""
    return get_key_manager().get_treasury_address()
