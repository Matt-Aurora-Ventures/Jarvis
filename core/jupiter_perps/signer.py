"""Local signer loader for live Jupiter Perps execution."""

from __future__ import annotations

import json
import os
from pathlib import Path

import base58
from solders.keypair import Keypair
from core.utils.secret_store import get_secret


def _decode_keypair_material(raw: str) -> bytes:
    """Decode base58 or JSON array keypair material into raw bytes."""
    raw = raw.strip()
    if not raw:
        raise RuntimeError("Empty keypair material")

    if raw.startswith("["):
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise RuntimeError("JSON keypair must be an integer array")
        return bytes(int(value) & 0xFF for value in payload)

    return base58.b58decode(raw)


def load_signer_keypair(expected_wallet_address: str = "") -> Keypair:
    """Load signer keypair from env and validate the expected wallet address."""
    keypair_b58 = get_secret("PERPS_SIGNER_KEYPAIR_B58")
    keypair_path = (
        os.environ.get("PERPS_SIGNER_KEYPAIR_B58_FILE", "").strip()
        or os.environ.get("PERPS_SIGNER_KEYPAIR_PATH", "").strip()
    )

    key_material: bytes
    if keypair_b58:
        key_material = _decode_keypair_material(keypair_b58)
    elif keypair_path:
        source = Path(keypair_path)
        if not source.exists():
            raise RuntimeError(
                "PERPS_SIGNER_KEYPAIR_B58_FILE/PERPS_SIGNER_KEYPAIR_PATH does not exist: "
                f"{source}"
            )
        key_material = _decode_keypair_material(source.read_text(encoding="utf-8"))
    else:
        raise RuntimeError(
            "Live mode requires PERPS_SIGNER_KEYPAIR_B58 or "
            "PERPS_SIGNER_KEYPAIR_B58_FILE (legacy: PERPS_SIGNER_KEYPAIR_PATH)"
        )

    if len(key_material) == 64:
        signer = Keypair.from_bytes(key_material)
    elif len(key_material) == 32:
        signer = Keypair.from_seed(key_material)
    else:
        raise RuntimeError(
            "Invalid keypair material length. Expected 32-byte seed or 64-byte keypair."
        )

    if expected_wallet_address and str(signer.pubkey()) != expected_wallet_address:
        raise RuntimeError(
            "Loaded signer does not match PERPS_WALLET_ADDRESS "
            f"expected={expected_wallet_address} actual={signer.pubkey()}"
        )

    return signer
