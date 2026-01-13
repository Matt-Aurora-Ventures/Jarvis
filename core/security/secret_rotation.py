"""Secret rotation management."""
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Callable, Optional, Any
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class SecretRotationManager:
    """Manage automatic rotation of secrets."""
    
    def __init__(self, vault=None, rotation_days: int = 90):
        self.vault = vault
        self.rotation_days = rotation_days
        self.rotation_handlers: Dict[str, Callable[[], str]] = {}
        self.metadata_path = Path("data/rotation_metadata.json")
        self._metadata: Dict[str, dict] = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, dict]:
        if self.metadata_path.exists():
            try:
                return json.loads(self.metadata_path.read_text())
            except Exception:
                return {}
        return {}
    
    def _save_metadata(self):
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(json.dumps(self._metadata, indent=2))
    
    def register_handler(self, secret_name: str, handler: Callable[[], str]):
        """Register a rotation handler for a secret."""
        self.rotation_handlers[secret_name] = handler
        if secret_name not in self._metadata:
            self._metadata[secret_name] = {
                "last_rotation": datetime.now().isoformat(),
                "rotation_count": 0
            }
            self._save_metadata()
    
    def needs_rotation(self, secret_name: str) -> bool:
        """Check if a secret needs rotation."""
        if secret_name not in self._metadata:
            return True
        
        last_rotation = datetime.fromisoformat(self._metadata[secret_name]["last_rotation"])
        return datetime.now() - last_rotation > timedelta(days=self.rotation_days)
    
    def rotate(self, secret_name: str) -> Optional[str]:
        """Rotate a specific secret."""
        if secret_name not in self.rotation_handlers:
            logger.error(f"No handler registered for secret: {secret_name}")
            return None
        
        try:
            new_secret = self.rotation_handlers[secret_name]()
            
            if self.vault:
                self.vault.set(secret_name, new_secret)
            
            self._metadata[secret_name] = {
                "last_rotation": datetime.now().isoformat(),
                "rotation_count": self._metadata.get(secret_name, {}).get("rotation_count", 0) + 1
            }
            self._save_metadata()
            
            logger.info(f"Successfully rotated secret: {secret_name}")
            return new_secret
        
        except Exception as e:
            logger.error(f"Failed to rotate secret {secret_name}: {e}")
            return None
    
    def check_and_rotate_all(self) -> Dict[str, bool]:
        """Check all registered secrets and rotate if needed."""
        results = {}
        
        for secret_name in self.rotation_handlers:
            if self.needs_rotation(secret_name):
                result = self.rotate(secret_name)
                results[secret_name] = result is not None
            else:
                results[secret_name] = False
        
        return results
    
    def get_rotation_status(self) -> Dict[str, dict]:
        """Get rotation status for all secrets."""
        status = {}
        
        for name, metadata in self._metadata.items():
            last_rotation = datetime.fromisoformat(metadata["last_rotation"])
            days_since = (datetime.now() - last_rotation).days
            
            status[name] = {
                "last_rotation": metadata["last_rotation"],
                "days_since_rotation": days_since,
                "needs_rotation": days_since >= self.rotation_days,
                "rotation_count": metadata.get("rotation_count", 0)
            }
        
        return status


def generate_api_secret() -> str:
    """Generate a new API secret."""
    return secrets.token_urlsafe(32)


def generate_jwt_secret() -> str:
    """Generate a new JWT secret."""
    return secrets.token_hex(64)


def generate_encryption_key() -> str:
    """Generate a new encryption key."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()
