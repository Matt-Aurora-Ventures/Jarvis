"""Centralized secret management for Jarvis.

This module provides a secure vault for managing all API keys, tokens,
and sensitive configuration. All secrets are loaded from environment
variables and never hardcoded.

Usage:
    from core.secrets.vault import get_vault
    
    vault = get_vault()
    api_key = vault.get('anthropic_api_key')
"""

import os
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SecretConfig:
    """Configuration for a single secret."""
    name: str
    env_var: str
    required: bool = True
    description: str = ""


class SecretVault:
    """Secure secret storage and retrieval.
    
    Loads all secrets from environment variables on initialization.
    Provides safe access without exposing secrets in logs or repr().
    """
    
    # Define all secrets used by Jarvis
    SECRETS = [
        # AI/LLM APIs
        SecretConfig("anthropic_api_key", "ANTHROPIC_API_KEY", required=True, description="Claude API key"),
        SecretConfig("anthropic_cli_token", "ANTHROPIC_CLI_OAUTH_TOKEN", required=False, description="Claude CLI OAuth token"),
        SecretConfig("xai_api_key", "XAI_API_KEY", required=False, description="xAI (Grok) API key"),
        
        # Trading/DEX APIs
        SecretConfig("bags_api_key", "BAGS_API_KEY", required=False, description="bags.fm API key"),
        SecretConfig("bags_partner_key", "BAGS_PARTNER_KEY", required=False, description="bags.fm partner key"),
        SecretConfig("bags_partner_code", "BAGS_PARTNER_CODE", required=False, description="bags.fm partner code"),
        SecretConfig("helius_api_key", "HELIUS_API_KEY", required=False, description="Helius RPC API key"),
        
        # Social/Bot APIs
        SecretConfig("telegram_bot_token", "TELEGRAM_BOT_TOKEN", required=True, description="Telegram bot token"),
        SecretConfig("twitter_bearer_token", "TWITTER_BEARER_TOKEN", required=False, description="Twitter API bearer token"),
        SecretConfig("twitter_api_key", "TWITTER_API_KEY", required=False, description="Twitter API key"),
        SecretConfig("twitter_api_secret", "TWITTER_API_SECRET", required=False, description="Twitter API secret"),
        SecretConfig("twitter_access_token", "TWITTER_ACCESS_TOKEN", required=False, description="Twitter access token"),
        SecretConfig("twitter_access_secret", "TWITTER_ACCESS_TOKEN_SECRET", required=False, description="Twitter access token secret"),
        
        # Database
        SecretConfig("postgres_url", "DATABASE_URL", required=False, description="PostgreSQL connection URL"),
        
        # Monitoring/Analytics
        SecretConfig("sentry_dsn", "SENTRY_DSN", required=False, description="Sentry error tracking DSN"),
        
        # NOTE: Wallet passwords should NEVER be in env vars
        # Use encrypted keystore instead (see core/wallet/keystore.py)
    ]
    
    def __init__(self):
        """Initialize vault and load secrets from environment."""
        self._secrets: Dict[str, Optional[str]] = {}
        self._load_secrets()
    
    def _load_secrets(self):
        """Load all secrets from environment variables."""
        missing_required = []
        
        for secret in self.SECRETS:
            value = os.getenv(secret.env_var)
            
            if value:
                self._secrets[secret.name] = value
                logger.debug(f"Loaded secret: {secret.name}")
            else:
                self._secrets[secret.name] = None
                if secret.required:
                    missing_required.append(secret.env_var)
                else:
                    logger.debug(f"Optional secret not set: {secret.name}")
        
        if missing_required:
            raise ValueError(
                f"Required secrets missing from environment: {', '.join(missing_required)}\n"
                f"Please set these environment variables before starting Jarvis."
            )
    
    def get(self, name: str) -> Optional[str]:
        """Get secret value by name.
        
        Args:
            name: Secret name (e.g., 'anthropic_api_key')
            
        Returns:
            Secret value or None if not set
            
        Raises:
            KeyError: If secret name is not defined in SECRETS
        """
        if name not in self._secrets:
            valid_names = [s.name for s in self.SECRETS]
            raise KeyError(
                f"Unknown secret: {name}\n"
                f"Valid secrets: {', '.join(valid_names)}"
            )
        
        return self._secrets[name]
    
    def get_required(self, name: str) -> str:
        """Get required secret value.
        
        Args:
            name: Secret name
            
        Returns:
            Secret value (never None)
            
        Raises:
            KeyError: If secret name is not defined
            ValueError: If secret is not set
        """
        value = self.get(name)
        if value is None:
            raise ValueError(f"Required secret not set: {name}")
        return value
    
    def is_set(self, name: str) -> bool:
        """Check if a secret is set.
        
        Args:
            name: Secret name
            
        Returns:
            True if secret has a value
        """
        return self.get(name) is not None
    
    def list_secrets(self) -> List[Dict[str, str]]:
        """List all defined secrets (for diagnostics).
        
        Returns:
            List of dicts with name, env_var, required, set status
        """
        return [
            {
                "name": s.name,
                "env_var": s.env_var,
                "required": s.required,
                "description": s.description,
                "is_set": self.is_set(s.name),
            }
            for s in self.SECRETS
        ]
    
    def __repr__(self) -> str:
        """Safe repr - never expose secret values."""
        set_count = sum(1 for v in self._secrets.values() if v is not None)
        total_count = len(self._secrets)
        return f"<SecretVault: {set_count}/{total_count} secrets loaded>"
    
    def __str__(self) -> str:
        """Safe str representation."""
        return self.__repr__()


# Global singleton instance
_vault_instance: Optional[SecretVault] = None


def get_vault() -> SecretVault:
    """Get the global SecretVault singleton.
    
    Returns:
        Initialized SecretVault instance
        
    Raises:
        ValueError: If required secrets are missing
    """
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = SecretVault()
    return _vault_instance


def reset_vault():
    """Reset the global vault (for testing only)."""
    global _vault_instance
    _vault_instance = None
