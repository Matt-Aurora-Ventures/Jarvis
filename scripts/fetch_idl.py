#!/usr/bin/env python3
"""
fetch_idl.py — Download Jupiter Perps IDL, compute SHA256, and write lockfile.

Run this ONCE before first deploy, then commit the outputs:
  - core/jupiter_perps/idl/jupiter_perps.json
  - core/jupiter_perps/idl/jupiter_perps.json.sha256

At runtime, execution_service.py calls integrity.verify_idl() which reads
the stored hash and fails startup if the IDL file has changed.

Usage:
  python scripts/fetch_idl.py
  python scripts/fetch_idl.py --force  # overwrite existing IDL

Sources (in priority order):
  1. GitHub reference implementation (julianfssen/jupiter-perps-anchor-idl-parsing)
  2. On-chain via Helius RPC (requires HELIUS_API_KEY)
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
IDL_DIR = REPO_ROOT / "core" / "jupiter_perps" / "idl"
IDL_PATH = IDL_DIR / "jupiter_perps.json"
HASH_PATH = IDL_DIR / "jupiter_perps.json.sha256"

# Program ID
JUPITER_PERPS_PROGRAM_ID = "PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu"

# Known IDL sources
IDL_SOURCES = [
    {
        "name": "julianfssen/jupiter-perps-anchor-idl-parsing (GitHub)",
        "url": (
            "https://raw.githubusercontent.com/"
            "julianfssen/jupiter-perps-anchor-idl-parsing/"
            "main/src/idl/jupiter-perpetuals-idl-json.json"
        ),
    },
]


def fetch_idl_from_url(url: str) -> bytes:
    """Fetch IDL bytes from a URL."""
    print(f"  Fetching: {url}")
    headers = {"User-Agent": "jarvis-idl-fetcher/1.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch_idl_from_rpc() -> bytes:
    """Fetch IDL bytes from on-chain via Helius or public RPC."""
    import urllib.parse

    rpc_url = os.environ.get(
        "HELIUS_RPC_URL",
        "https://api.mainnet-beta.solana.com",
    )
    print(f"  Fetching on-chain IDL via RPC: {rpc_url}")

    # Jupiter IDL is stored at a derived PDA — fetch via getAccountInfo
    # IDL PDA = findProgramAddress(["anchor:idl"], programId)
    # Use Anchor's standard IDL fetch RPC method
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [
                # Anchor IDL account address for Jupiter Perps
                # Derived offline: anchor idl fetch <programId>
                JUPITER_PERPS_PROGRAM_ID,
                {"encoding": "base64"},
            ],
        }
    ).encode()

    req = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    account = result.get("result", {}).get("value")
    if account is None:
        raise RuntimeError("Program account not found on-chain")

    # The IDL is not directly in the program account — this requires
    # the anchor CLI approach. Fall back to GitHub source.
    raise NotImplementedError(
        "On-chain IDL fetch requires anchor CLI. Use GitHub source instead."
    )


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_idl_json(data: bytes) -> dict:
    """Parse and lightly validate the IDL structure."""
    try:
        idl = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"IDL is not valid JSON: {e}")

    required_fields = ["version", "name", "instructions", "accounts", "types"]
    for field in required_fields:
        if field not in idl:
            raise ValueError(f"IDL missing required field: {field}")

    if idl.get("name") not in ("perpetuals", "jupiter_perpetuals", "perp"):
        print(
            f"  WARNING: IDL name is '{idl.get('name')}' — verify this is the correct program."
        )

    print(f"  IDL version   : {idl.get('version')}")
    print(f"  IDL name      : {idl.get('name')}")
    print(f"  Instructions  : {len(idl.get('instructions', []))}")
    print(f"  Accounts      : {len(idl.get('accounts', []))}")
    print(f"  Types         : {len(idl.get('types', []))}")

    return idl


def main():
    parser = argparse.ArgumentParser(description="Fetch and hash Jupiter Perps IDL")
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing IDL file"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing IDL hash, do not fetch",
    )
    args = parser.parse_args()

    IDL_DIR.mkdir(parents=True, exist_ok=True)

    if args.verify_only:
        if not IDL_PATH.exists():
            print("ERROR: IDL file not found. Run without --verify-only first.")
            sys.exit(1)
        from core.jupiter_perps.integrity import verify_idl  # noqa: PLC0415

        verify_idl()
        print("IDL integrity verified.")
        return

    if IDL_PATH.exists() and not args.force:
        print(f"IDL already exists at {IDL_PATH}")
        print("Use --force to re-fetch and update the hash.")
        existing_hash = HASH_PATH.read_text().strip() if HASH_PATH.exists() else "N/A"
        print(f"Stored hash: {existing_hash}")
        return

    raw_idl: bytes | None = None
    for source in IDL_SOURCES:
        try:
            print(f"\nTrying source: {source['name']}")
            raw_idl = fetch_idl_from_url(source["url"])
            print("  Download OK")
            break
        except Exception as e:
            print(f"  FAILED: {e}")

    if raw_idl is None:
        print("\nAll URL sources failed. Trying on-chain RPC...")
        try:
            raw_idl = fetch_idl_from_rpc()
        except Exception as e:
            print(f"  RPC FAILED: {e}")
            print("\nERROR: Could not fetch IDL from any source.")
            print("Manual steps:")
            print(
                "  1. Install anchor CLI: cargo install anchor-cli --git https://github.com/coral-xyz/anchor"
            )
            print(
                f"  2. Run: anchor idl fetch {JUPITER_PERPS_PROGRAM_ID} --out core/jupiter_perps/idl/jupiter_perps.json"
            )
            print("  3. Run: python scripts/fetch_idl.py --force")
            sys.exit(1)

    print("\nValidating IDL structure...")
    validate_idl_json(raw_idl)

    # Canonicalize JSON (sorted keys, no extra whitespace) for deterministic hash
    idl_dict = json.loads(raw_idl)
    canonical = json.dumps(idl_dict, sort_keys=True, indent=2, ensure_ascii=False)
    canonical_bytes = canonical.encode("utf-8")

    sha256_hex = compute_sha256(canonical_bytes)

    print(f"\nWriting IDL to {IDL_PATH}")
    IDL_PATH.write_bytes(canonical_bytes)

    print(f"Writing hash to {HASH_PATH}")
    HASH_PATH.write_text(sha256_hex + "\n")

    print(f"\nSHA256: {sha256_hex}")
    print("\nDONE. Commit both files:")
    print(f"  {IDL_PATH.relative_to(REPO_ROOT)}")
    print(f"  {HASH_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
