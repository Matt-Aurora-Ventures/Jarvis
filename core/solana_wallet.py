"""Wallet utilities for Solana key management and balance checks."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

try:
    import base58
    from solders.keypair import Keypair
    HAS_SOLANA = True
except Exception:
    HAS_SOLANA = False
    Keypair = None

ROOT = Path(__file__).resolve().parents[1]


def _load_keypair_from_file(path: Path) -> Optional["Keypair"]:
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return Keypair.from_bytes(bytes(data))
    except Exception:
        return None
    return None


def _load_keypair_from_lifeos_secrets(path: Path) -> Optional["Keypair"]:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None

    for key_name in ("solana_private_key", "solana_key", "private_key", "wallet_key"):
        if key_name not in data:
            continue
        key_value = data[key_name]
        if isinstance(key_value, list):
            try:
                return Keypair.from_bytes(bytes(key_value))
            except Exception:
                continue
        if isinstance(key_value, str):
            try:
                return Keypair.from_bytes(base58.b58decode(key_value))
            except Exception:
                continue
    return None


def load_keypair(path: Optional[str] = None) -> Optional["Keypair"]:
    """Load keypair from file or env. Returns None if unavailable."""
    if not HAS_SOLANA:
        return None

    if path:
        return _load_keypair_from_file(Path(path))

    solana_default = Path.home() / ".config" / "solana" / "id.json"
    if solana_default.exists():
        kp = _load_keypair_from_file(solana_default)
        if kp:
            return kp

    lifeos_wallets = Path.home() / ".lifeos" / "wallets"
    if lifeos_wallets.exists():
        json_wallet = lifeos_wallets / "phantom_trading_wallet.json"
        if json_wallet.exists():
            kp = _load_keypair_from_file(json_wallet)
            if kp:
                return kp
        base58_wallet = lifeos_wallets / "phantom_trading_wallet.base58"
        if base58_wallet.exists():
            try:
                key_str = base58_wallet.read_text().strip()
                return Keypair.from_bytes(base58.b58decode(key_str))
            except Exception:
                pass

    lifeos_secrets = ROOT / "secrets" / "keys.json"
    if lifeos_secrets.exists():
        kp = _load_keypair_from_lifeos_secrets(lifeos_secrets)
        if kp:
            return kp

    env_key = os.environ.get("SOLANA_PRIVATE_KEY")
    if env_key:
        try:
            return Keypair.from_bytes(base58.b58decode(env_key))
        except Exception:
            return None

    return None
