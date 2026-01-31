"""Compatibility shim for legacy imports.

Historically some handlers imported:
  from core.wallets.wallet_manager import get_treasury_keypair

The canonical key loading path is now:
  from core.security.key_manager import load_treasury_keypair

This module keeps legacy imports working without duplicating logic.
"""

from __future__ import annotations

from core.security.key_manager import load_treasury_keypair


def get_treasury_keypair():
    """Legacy alias. Returns a solders.keypair.Keypair or None."""
    return load_treasury_keypair()
