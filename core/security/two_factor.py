"""Two-factor authentication support."""
import time
import hmac
import struct
import hashlib
import base64
import secrets
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TOTPConfig:
    secret: str
    enabled: bool = False
    backup_codes: list = None
    created_at: float = None


class TwoFactorAuth:
    """TOTP-based two-factor authentication."""
    
    def __init__(self, vault=None, issuer: str = "Jarvis"):
        self.vault = vault
        self.issuer = issuer
        self.digits = 6
        self.period = 30
        self.algorithm = "sha1"
    
    def setup_2fa(self, user_id: str) -> Tuple[str, str, list]:
        """
        Set up 2FA for a user.
        Returns: (secret, provisioning_uri, backup_codes)
        """
        secret = self._generate_secret()
        backup_codes = self._generate_backup_codes()
        
        config = TOTPConfig(
            secret=secret,
            enabled=False,
            backup_codes=backup_codes,
            created_at=time.time()
        )
        
        if self.vault:
            self.vault.set(f"2fa:{user_id}", {
                "secret": secret,
                "enabled": False,
                "backup_codes": backup_codes,
                "created_at": time.time()
            })
        
        uri = self._generate_provisioning_uri(secret, user_id)
        
        return secret, uri, backup_codes
    
    def enable_2fa(self, user_id: str, code: str) -> bool:
        """Enable 2FA after verifying the first code."""
        if not self.verify_code(user_id, code):
            return False
        
        if self.vault:
            data = self.vault.get(f"2fa:{user_id}")
            if data:
                data["enabled"] = True
                self.vault.set(f"2fa:{user_id}", data)
        
        logger.info(f"2FA enabled for user {user_id}")
        return True
    
    def disable_2fa(self, user_id: str):
        """Disable 2FA for a user."""
        if self.vault:
            self.vault.delete(f"2fa:{user_id}")
        logger.info(f"2FA disabled for user {user_id}")
    
    def verify_code(self, user_id: str, code: str, valid_window: int = 1) -> bool:
        """Verify a TOTP code."""
        data = self._get_user_data(user_id)
        if not data:
            return False
        
        secret = data.get("secret")
        if not secret:
            return False
        
        current_time = int(time.time())
        
        for offset in range(-valid_window, valid_window + 1):
            time_step = (current_time // self.period) + offset
            expected_code = self._generate_totp(secret, time_step)
            
            if hmac.compare_digest(code.zfill(self.digits), expected_code):
                return True
        
        return False
    
    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify and consume a backup code."""
        data = self._get_user_data(user_id)
        if not data:
            return False
        
        backup_codes = data.get("backup_codes", [])
        
        if code in backup_codes:
            backup_codes.remove(code)
            
            if self.vault:
                data["backup_codes"] = backup_codes
                self.vault.set(f"2fa:{user_id}", data)
            
            logger.info(f"Backup code used for user {user_id}")
            return True
        
        return False
    
    def is_enabled(self, user_id: str) -> bool:
        """Check if 2FA is enabled for a user."""
        data = self._get_user_data(user_id)
        return data.get("enabled", False) if data else False
    
    def get_remaining_backup_codes(self, user_id: str) -> int:
        """Get count of remaining backup codes."""
        data = self._get_user_data(user_id)
        if not data:
            return 0
        return len(data.get("backup_codes", []))
    
    def regenerate_backup_codes(self, user_id: str) -> list:
        """Regenerate backup codes for a user."""
        data = self._get_user_data(user_id)
        if not data:
            return []
        
        new_codes = self._generate_backup_codes()
        data["backup_codes"] = new_codes
        
        if self.vault:
            self.vault.set(f"2fa:{user_id}", data)
        
        return new_codes
    
    def _get_user_data(self, user_id: str) -> Optional[dict]:
        """Get 2FA data for a user."""
        if self.vault:
            return self.vault.get(f"2fa:{user_id}")
        return None
    
    def _generate_secret(self, length: int = 32) -> str:
        """Generate a random base32 secret."""
        random_bytes = secrets.token_bytes(length)
        return base64.b32encode(random_bytes).decode('utf-8').rstrip('=')
    
    def _generate_backup_codes(self, count: int = 10) -> list:
        """Generate backup codes."""
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    def _generate_provisioning_uri(self, secret: str, user_id: str) -> str:
        """Generate otpauth:// URI for QR code."""
        from urllib.parse import quote
        return (
            f"otpauth://totp/{quote(self.issuer)}:{quote(user_id)}"
            f"?secret={secret}&issuer={quote(self.issuer)}"
            f"&algorithm={self.algorithm.upper()}&digits={self.digits}&period={self.period}"
        )
    
    def _generate_totp(self, secret: str, time_step: int) -> str:
        """Generate TOTP code for a specific time step."""
        try:
            key = base64.b32decode(secret.upper() + '=' * (-len(secret) % 8))
        except Exception:
            key = secret.encode()
        
        msg = struct.pack('>Q', time_step)
        
        h = hmac.new(key, msg, hashlib.sha1).digest()
        
        offset = h[-1] & 0x0f
        code = struct.unpack('>I', h[offset:offset + 4])[0]
        code = (code & 0x7fffffff) % (10 ** self.digits)
        
        return str(code).zfill(self.digits)
