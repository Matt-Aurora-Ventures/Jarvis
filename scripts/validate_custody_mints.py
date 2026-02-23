#!/usr/bin/env python3
"""
validate_custody_mints.py — Verify Jupiter Perps custody PDAs exist on mainnet.

Calls getAccountInfo for each derived custody PDA and confirms:
    1. Account exists (non-null)
    2. Account is owned by Jupiter Perps program
    3. Account has the Custody discriminator

Run after bootstrap.py and before first trade.

Usage:
    HELIUS_RPC_URL=https://... python scripts/validate_custody_mints.py
    python scripts/validate_custody_mints.py   (uses public RPC)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

RPC_URL = os.environ.get("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
JUPITER_PERPS_PROGRAM_ID = "PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu"
CUSTODY_DISCRIMINATOR = hashlib.sha256(b"account:Custody").digest()[:8]


def rpc_call(method: str, params: list) -> dict:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode()
    req = urllib.request.Request(
        RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def derive_pdas() -> dict[str, str]:
    """Derive all custody PDAs. Returns {symbol: pda_address}."""
    try:
        from core.jupiter_perps.pda import (  # noqa: PLC0415
            CUSTODY_MINTS,
            derive_custody_pda,
            derive_pool_pda,
        )
        pool = derive_pool_pda()
        return {
            symbol: str(derive_custody_pda(pool, mint))
            for symbol, mint in CUSTODY_MINTS.items()
        }
    except ImportError as e:
        print(f"ERROR: Cannot import pda.py — {e}")
        print("  Install: pip install solders==0.26.0")
        sys.exit(1)


def main() -> None:
    print(f"Validating Jupiter Perps custody PDAs via {RPC_URL}\n")
    pdas = derive_pdas()

    all_ok = True
    for symbol, pda in pdas.items():
        result = rpc_call("getAccountInfo", [pda, {"encoding": "base64", "commitment": "confirmed"}])
        value = result.get("result", {}).get("value")

        if value is None:
            print(f"  [{symbol:5}] MISSING   {pda[:20]}... — account does not exist on-chain")
            print(f"           This means the custody PDA seed for {symbol} is wrong.")
            all_ok = False
            continue

        owner = value.get("owner", "")
        if owner != JUPITER_PERPS_PROGRAM_ID:
            print(f"  [{symbol:5}] WRONG OWNER  {pda[:20]}... — owner={owner[:20]}...")
            all_ok = False
            continue

        import base64
        data_b64 = value.get("data", [""])[0]
        raw = base64.b64decode(data_b64) if data_b64 else b""
        disc_ok = raw[:8] == CUSTODY_DISCRIMINATOR if len(raw) >= 8 else False

        status = "OK" if disc_ok else "WRONG_DISC"
        print(f"  [{symbol:5}] {status:<12} {pda[:20]}...  ({len(raw)} bytes)")
        if not disc_ok:
            all_ok = False

    print()
    if all_ok:
        print("All custody PDAs validated. PDA seeds are correct.")
    else:
        print("ERROR: Some custody PDAs failed validation.")
        print("The custody mint addresses in pda.py may need updating.")
        print("After running anchorpy client-gen, check:")
        print("  core/jupiter_perps/client/accounts/custody.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
