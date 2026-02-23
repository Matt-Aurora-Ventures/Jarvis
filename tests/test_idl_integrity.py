"""
test_idl_integrity.py — Tests for IDL hash enforcement.

Tests:
    1. verify_idl() passes when hash matches
    2. verify_idl() raises IDLIntegrityError when hash doesn't match
    3. verify_idl() raises FileNotFoundError when IDL is missing
    4. get_idl_dict() returns a valid dict with expected keys
    5. compute_idl_hash() is deterministic
"""

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.jupiter_perps.integrity import (
    IDL_PATH,
    HASH_PATH,
    IDLIntegrityError,
    compute_idl_hash,
    get_expected_hash,
    get_idl_dict,
    verify_idl,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_idl_dir(tmp_path: Path):
    """Create a temporary IDL directory with a valid IDL and hash file."""
    idl_dir = tmp_path / "idl"
    idl_dir.mkdir()

    # Minimal valid IDL JSON
    idl_content = json.dumps({
        "version": "0.1.0",
        "name": "perpetuals",
        "instructions": [{"name": "init", "accounts": [], "args": []}],
        "accounts": [{"name": "Position", "type": {"kind": "struct", "fields": []}}],
        "types": [{"name": "Side", "type": {"kind": "enum", "variants": []}}],
    }, sort_keys=True, indent=2).encode("utf-8")

    idl_path = idl_dir / "jupiter_perps.json"
    hash_path = idl_dir / "jupiter_perps.json.sha256"

    idl_path.write_bytes(idl_content)
    expected_hash = hashlib.sha256(idl_content).hexdigest()
    hash_path.write_text(expected_hash + "\n")

    return idl_dir, idl_path, hash_path, expected_hash


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestVerifyIdl:
    def test_passes_when_hash_matches(self, temp_idl_dir, monkeypatch):
        """verify_idl() should return True when IDL hash matches stored hash."""
        idl_dir, idl_path, hash_path, _ = temp_idl_dir
        monkeypatch.setattr("core.jupiter_perps.integrity.IDL_PATH", idl_path)
        monkeypatch.setattr("core.jupiter_perps.integrity.HASH_PATH", hash_path)

        assert verify_idl(fatal=False) is True

    def test_raises_on_hash_mismatch(self, temp_idl_dir, monkeypatch):
        """verify_idl() should raise IDLIntegrityError when hash doesn't match."""
        idl_dir, idl_path, hash_path, _ = temp_idl_dir
        monkeypatch.setattr("core.jupiter_perps.integrity.IDL_PATH", idl_path)
        monkeypatch.setattr("core.jupiter_perps.integrity.HASH_PATH", hash_path)

        # Tamper with the IDL
        tampered = idl_path.read_bytes() + b"\n// tampered"
        idl_path.write_bytes(tampered)

        with pytest.raises(IDLIntegrityError, match="hash mismatch"):
            verify_idl(fatal=False)

    def test_sys_exit_when_fatal(self, temp_idl_dir, monkeypatch):
        """verify_idl(fatal=True) should call sys.exit() on mismatch."""
        idl_dir, idl_path, hash_path, _ = temp_idl_dir
        monkeypatch.setattr("core.jupiter_perps.integrity.IDL_PATH", idl_path)
        monkeypatch.setattr("core.jupiter_perps.integrity.HASH_PATH", hash_path)

        # Tamper
        idl_path.write_bytes(idl_path.read_bytes() + b"x")

        with pytest.raises(SystemExit):
            verify_idl(fatal=True)

    def test_raises_file_not_found_when_idl_missing(self, tmp_path, monkeypatch):
        """verify_idl() should raise FileNotFoundError if IDL doesn't exist."""
        missing_path = tmp_path / "does_not_exist.json"
        monkeypatch.setattr("core.jupiter_perps.integrity.IDL_PATH", missing_path)
        monkeypatch.setattr(
            "core.jupiter_perps.integrity.HASH_PATH",
            tmp_path / "also_missing.sha256",
        )

        with pytest.raises(FileNotFoundError):
            verify_idl(fatal=False)

    def test_hash_is_deterministic(self, temp_idl_dir, monkeypatch):
        """Same IDL bytes should always produce the same hash."""
        idl_dir, idl_path, hash_path, expected_hash = temp_idl_dir
        monkeypatch.setattr("core.jupiter_perps.integrity.IDL_PATH", idl_path)
        monkeypatch.setattr("core.jupiter_perps.integrity.HASH_PATH", hash_path)

        hash1 = compute_idl_hash()
        hash2 = compute_idl_hash()
        assert hash1 == hash2 == expected_hash


class TestGetIdlDict:
    def test_returns_valid_dict(self, temp_idl_dir, monkeypatch):
        """get_idl_dict() should return a dict with required IDL fields."""
        idl_dir, idl_path, hash_path, _ = temp_idl_dir
        monkeypatch.setattr("core.jupiter_perps.integrity.IDL_PATH", idl_path)
        monkeypatch.setattr("core.jupiter_perps.integrity.HASH_PATH", hash_path)

        idl = get_idl_dict()
        assert isinstance(idl, dict)
        assert "version" in idl
        assert "name" in idl
        assert "instructions" in idl
        assert "accounts" in idl
        assert "types" in idl

    def test_verifies_hash_before_returning(self, temp_idl_dir, monkeypatch):
        """get_idl_dict() should fail if hash doesn't match (not a bypass)."""
        idl_dir, idl_path, hash_path, _ = temp_idl_dir
        monkeypatch.setattr("core.jupiter_perps.integrity.IDL_PATH", idl_path)
        monkeypatch.setattr("core.jupiter_perps.integrity.HASH_PATH", hash_path)

        # Tamper after patching
        idl_path.write_bytes(idl_path.read_bytes() + b"x")

        with pytest.raises(SystemExit):
            get_idl_dict()
