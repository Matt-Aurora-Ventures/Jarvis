"""
integrity.py — IDL hash enforcement for Jupiter Perps execution service.

Called at startup BEFORE loading any keys or accepting any intents.
If the IDL hash does not match the stored expected value, the process exits.

This protects against:
  - Silent Jupiter Perps contract upgrades
  - Supply-chain tampering of the IDL JSON in the repo
  - Accidental IDL drift between environments

Usage:
    from core.jupiter_perps.integrity import verify_idl
    verify_idl()  # raises SystemExit if mismatch
"""

import hashlib
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Paths relative to this file
_THIS_DIR = Path(__file__).parent
IDL_PATH = _THIS_DIR / "idl" / "jupiter_perps.json"
HASH_PATH = _THIS_DIR / "idl" / "jupiter_perps.json.sha256"


class IDLIntegrityError(Exception):
    """Raised when IDL hash does not match expected value."""


def compute_idl_hash() -> str:
    """Compute SHA256 of the stored IDL JSON bytes."""
    if not IDL_PATH.exists():
        raise FileNotFoundError(
            f"Jupiter Perps IDL not found at {IDL_PATH}. "
            "Run: python scripts/fetch_idl.py"
        )
    return hashlib.sha256(IDL_PATH.read_bytes()).hexdigest()


def get_expected_hash() -> str:
    """Read the pinned expected hash from the lockfile."""
    if not HASH_PATH.exists():
        raise FileNotFoundError(
            f"IDL hash lockfile not found at {HASH_PATH}. "
            "Run: python scripts/fetch_idl.py"
        )
    return HASH_PATH.read_text().strip()


def verify_idl(fatal: bool = True) -> bool:
    """
    Verify the Jupiter Perps IDL against the pinned SHA256 hash.

    Args:
        fatal: If True (default), calls sys.exit(1) on mismatch.
               If False, raises IDLIntegrityError instead.

    Returns:
        True if IDL is valid.

    Raises:
        IDLIntegrityError: if fatal=False and hashes don't match.
        SystemExit: if fatal=True and hashes don't match.
        FileNotFoundError: if IDL or hash file is missing and fatal=False.
    """
    try:
        expected = get_expected_hash()
        actual = compute_idl_hash()
    except FileNotFoundError as e:
        msg = f"IDL integrity check failed: {e}"
        log.critical(msg)
        if fatal:
            sys.exit(f"FATAL: {msg}")
        raise

    if actual != expected:
        msg = (
            f"FATAL: Jupiter Perps IDL hash mismatch!\n"
            f"  Expected : {expected}\n"
            f"  Actual   : {actual}\n"
            f"  IDL file : {IDL_PATH}\n\n"
            "This may indicate a silent program upgrade or tampering.\n"
            "If this is expected (e.g. Jupiter upgraded the contract), run:\n"
            "  python scripts/fetch_idl.py --force\n"
            "Then review the diff, update tests, and re-commit the hash.\n"
            "DO NOT bypass this check."
        )
        log.critical(msg)
        if fatal:
            sys.exit(msg)
        raise IDLIntegrityError(msg)

    log.info("IDL integrity OK (sha256=%s)", actual[:16] + "...")
    return True


def get_idl_dict() -> dict:
    """
    Load and return the IDL as a Python dict, after verifying hash.

    Always verifies integrity before returning.
    """
    import json

    verify_idl(fatal=True)
    return json.loads(IDL_PATH.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    # Allow running directly: python -m core.jupiter_perps.integrity
    logging.basicConfig(level=logging.INFO)
    try:
        verify_idl(fatal=False)
        print(f"OK — IDL hash matches: {get_expected_hash()}")
    except IDLIntegrityError as e:
        print(f"FAIL — {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"MISSING — {e}")
        sys.exit(1)
