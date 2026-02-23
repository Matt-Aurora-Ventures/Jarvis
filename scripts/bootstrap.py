#!/usr/bin/env python3
"""
bootstrap.py — Single command to make the Jupiter Perps stack runnable.

Run this ONCE before first deploy. Works on Windows without bash.

Steps:
    1. Download Jupiter Perps IDL JSON from GitHub reference repo
    2. Canonicalize JSON (sorted keys, deterministic)
    3. Compute SHA256, write .sha256 lockfile
    4. Verify integrity round-trip
    5. Print all Anchor account discriminators
    6. (Optional) Run pip-compile on requirements/signer.in

Usage:
    python scripts/bootstrap.py
    python scripts/bootstrap.py --skip-compile    skip pip-compile
    python scripts/bootstrap.py --verify-only     just verify existing files
    python scripts/bootstrap.py --force           re-download even if IDL exists
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
IDL_DIR = REPO_ROOT / "core" / "jupiter_perps" / "idl"
IDL_PATH = IDL_DIR / "jupiter_perps.json"
HASH_PATH = IDL_DIR / "jupiter_perps.json.sha256"
SIGNER_IN = REPO_ROOT / "requirements" / "signer.in"
SIGNER_TXT = REPO_ROOT / "requirements" / "signer.txt"

PROGRAM_ID = "PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu"
IDL_URL = (
    "https://raw.githubusercontent.com/"
    "julianfssen/jupiter-perps-anchor-idl-parsing/"
    "main/src/idl/jupiter-perpetuals-idl-json.json"
)

# Anchor account discriminators (sha256("account:{Name}")[:8])
# Pre-computed so this script works offline
KNOWN_DISCRIMINATORS = {
    "Position":        hashlib.sha256(b"account:Position").digest()[:8],
    "PositionRequest": hashlib.sha256(b"account:PositionRequest").digest()[:8],
    "Custody":         hashlib.sha256(b"account:Custody").digest()[:8],
    "Pool":            hashlib.sha256(b"account:Pool").digest()[:8],
    "Perpetuals":      hashlib.sha256(b"account:Perpetuals").digest()[:8],
}


def _banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def _ok(text: str) -> None:
    print(f"  [OK] {text}")


def _err(text: str) -> None:
    print(f"  [ERR] {text}", file=sys.stderr)


def download_idl() -> bytes:
    """Download IDL JSON from GitHub reference repo."""
    _banner("Step 1: Download Jupiter Perps IDL")
    print(f"  URL: {IDL_URL}")
    req = urllib.request.Request(IDL_URL, headers={"User-Agent": "jarvis-bootstrap/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        _ok(f"Downloaded {len(raw):,} bytes")
        return raw
    except Exception as e:
        _err(f"Download failed: {e}")
        _err("Manual fallback:")
        _err(f"  curl -L '{IDL_URL}' -o core/jupiter_perps/idl/jupiter_perps.json")
        _err("Then re-run: python scripts/bootstrap.py --skip-compile")
        sys.exit(1)


def canonicalize(raw: bytes) -> bytes:
    """Parse JSON and re-serialize with sorted keys for deterministic hashing."""
    try:
        obj = json.loads(raw)
        return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
    except json.JSONDecodeError as e:
        _err(f"IDL is not valid JSON: {e}")
        sys.exit(1)


def validate_idl_structure(obj: dict) -> None:
    """Lightly validate the IDL has required top-level fields."""
    _banner("Step 2: Validate IDL structure")
    required = ["version", "name", "instructions", "accounts", "types"]
    for field in required:
        if field not in obj:
            _err(f"IDL missing required field: '{field}'")
            sys.exit(1)
    _ok(f"IDL name:         {obj['name']}")
    _ok(f"IDL version:      {obj['version']}")
    _ok(f"Instructions:     {len(obj['instructions'])}")
    _ok(f"Accounts:         {len(obj['accounts'])}")
    _ok(f"Types:            {len(obj['types'])}")


def write_idl_and_hash(canonical: bytes) -> str:
    """Write IDL JSON and SHA256 lockfile. Return hex hash."""
    _banner("Step 3: Write IDL and SHA256 lockfile")
    IDL_DIR.mkdir(parents=True, exist_ok=True)
    IDL_PATH.write_bytes(canonical)
    _ok(f"IDL written:      {IDL_PATH}")

    sha256_hex = hashlib.sha256(canonical).hexdigest()
    HASH_PATH.write_text(sha256_hex + "\n")
    _ok(f"Hash written:     {HASH_PATH}")
    _ok(f"SHA256:           {sha256_hex}")
    return sha256_hex


def verify_existing() -> bool:
    """Verify existing IDL + hash match. Returns True if OK."""
    if not IDL_PATH.exists() or not HASH_PATH.exists():
        return False
    stored = HASH_PATH.read_text().strip()
    actual = hashlib.sha256(IDL_PATH.read_bytes()).hexdigest()
    return stored == actual


def print_discriminators() -> None:
    """Print all Anchor account discriminators."""
    _banner("Anchor Account Discriminators")
    for name, disc in KNOWN_DISCRIMINATORS.items():
        hex_repr = disc.hex()
        bytes_repr = repr(disc)
        print(f"  {name:<18} {bytes_repr}  (hex: {hex_repr})")
    print()
    print("  Copy the 'Position' discriminator into reconciliation.py:")
    pos = KNOWN_DISCRIMINATORS["Position"]
    print(f"  _POSITION_DISCRIMINATOR = {repr(pos)}")


def run_pip_compile() -> None:
    """Run pip-compile to generate requirements/signer.txt lockfile."""
    _banner("Step 4: Compile signer dependency lockfile")
    if not SIGNER_IN.exists():
        _err(f"requirements/signer.in not found at {SIGNER_IN}")
        return

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "piptools", "compile",
                "--generate-hashes",
                "--resolver=backtracking",
                "--output-file", str(SIGNER_TXT),
                str(SIGNER_IN),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            _ok(f"Lockfile written: {SIGNER_TXT}")
        else:
            _err("pip-compile failed:")
            _err(result.stderr[-1000:] if result.stderr else "(no output)")
            _err("Install pip-tools first: pip install pip-tools")
    except FileNotFoundError:
        _err("pip-tools not found. Install: pip install pip-tools")
    except subprocess.TimeoutExpired:
        _err("pip-compile timed out after 5 minutes")


def run_anchorpy_client_gen() -> None:
    """Run anchorpy client-gen to generate Python bindings."""
    _banner("Step 5: Generate AnchorPy client bindings")
    client_out = REPO_ROOT / "core" / "jupiter_perps" / "client"
    if not IDL_PATH.exists():
        _err("IDL not found — run bootstrap first without --skip-compile")
        return

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "anchorpy", "client-gen",
                str(IDL_PATH),
                str(client_out),
                "--program-id", PROGRAM_ID,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            generated = list(client_out.rglob("*.py"))
            _ok(f"Generated {len(generated)} Python files in {client_out}")
        else:
            _err("anchorpy client-gen failed:")
            _err(result.stderr[-1000:] if result.stderr else result.stdout[-500:])
            _err("Install anchorpy: pip install anchorpy==0.21.0")
    except FileNotFoundError:
        _err("anchorpy not found. Install: pip install anchorpy==0.21.0")
    except subprocess.TimeoutExpired:
        _err("anchorpy client-gen timed out")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Jupiter Perps stack")
    parser.add_argument("--skip-compile", action="store_true", help="Skip pip-compile step")
    parser.add_argument("--skip-client-gen", action="store_true", help="Skip anchorpy client-gen")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing IDL hash")
    parser.add_argument("--force", action="store_true", help="Re-download IDL even if it exists")
    args = parser.parse_args()

    print("\nJarvis Jupiter Perps Bootstrap")
    print("=" * 60)

    # Discriminators are always printed (stdlib only, always works)
    print_discriminators()

    if args.verify_only:
        _banner("Verify-only mode")
        if verify_existing():
            stored = HASH_PATH.read_text().strip()
            _ok(f"IDL integrity OK: {stored[:32]}...")
        else:
            _err("IDL integrity FAILED — run python scripts/bootstrap.py --force")
            sys.exit(1)
        return

    # Check if IDL already exists and is valid
    if IDL_PATH.exists() and not args.force:
        if verify_existing():
            stored = HASH_PATH.read_text().strip()
            _ok(f"IDL already exists and is valid: {stored[:32]}...")
            _ok("Use --force to re-download")
        else:
            _err("IDL file exists but hash is INVALID — re-running with --force behavior")
            args.force = True

    if not IDL_PATH.exists() or args.force:
        raw = download_idl()
        canonical = canonicalize(raw)
        validate_idl_structure(json.loads(canonical))
        write_idl_and_hash(canonical)

    if not args.skip_compile:
        run_pip_compile()

    if not args.skip_client_gen:
        run_anchorpy_client_gen()

    _banner("Bootstrap Complete")
    print("  Next steps:")
    print("  1. Commit the IDL files:")
    print("     git add core/jupiter_perps/idl/")
    print("     git add requirements/signer.txt")
    print("  2. Verify imports work:")
    print("     python -c \"from core.jupiter_perps import reconciliation; print('OK')\"")
    print("     python -c \"from core.jupiter_perps import execution_service; print('OK')\"")
    print("  3. Verify IDL integrity:")
    print("     python -m core.jupiter_perps.integrity")
    print()


if __name__ == "__main__":
    main()
