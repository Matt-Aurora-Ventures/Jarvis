"""Core secrets package for centralized secret management."""

from .vault import SecretVault, get_vault, reset_vault

__all__ = ['SecretVault', 'get_vault', 'reset_vault']
