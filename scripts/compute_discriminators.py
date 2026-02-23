#!/usr/bin/env python3
"""
compute_discriminators.py — Derive all Anchor account discriminators for Jupiter Perps.

Anchor discriminator formula: sha256("account:{AccountName}")[:8]

These are used in reconciliation.py to identify account types from raw chain data.

Usage:
    python scripts/compute_discriminators.py
"""

import hashlib

ACCOUNTS = [
    "Position",
    "PositionRequest",
    "Custody",
    "Pool",
    "Perpetuals",
    "TokenLedger",
    "BorrowPosition",
]

INSTRUCTIONS = [
    "increasePosition4",
    "decreasePosition4",
    "liquidateFullPosition4",
    "addLiquidity2",
    "removeLiquidity2",
]


def discriminator(name: str, prefix: str = "account") -> bytes:
    return hashlib.sha256(f"{prefix}:{name}".encode()).digest()[:8]


def main() -> None:
    print("=" * 65)
    print("  Jupiter Perps — Anchor Discriminators")
    print("=" * 65)

    print("\nAccount discriminators (sha256('account:{Name}')[:8]):\n")
    for name in ACCOUNTS:
        d = discriminator(name)
        print(f"  {name:<22} {repr(d)}   # hex: {d.hex()}")

    print("\nInstruction discriminators (sha256('global:{Name}')[:8]):\n")
    for name in INSTRUCTIONS:
        d = discriminator(name, prefix="global")
        print(f"  {name:<28} {repr(d)}   # hex: {d.hex()}")

    print()
    pos = discriminator("Position")
    pos_req = discriminator("PositionRequest")
    print("=" * 65)
    print("  Copy into reconciliation.py:")
    print(f"  _POSITION_DISCRIMINATOR         = {repr(pos)}")
    print(f"  _POSITION_REQUEST_DISCRIMINATOR = {repr(pos_req)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
