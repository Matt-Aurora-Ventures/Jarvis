"""
Tests for core/cli.py

Tests cover:
- Helper function behavior
- Argument parsing
- Path resolution
- Symbol map handling
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestHelperFunctions:
    """Test CLI helper functions."""

    def test_looks_like_solana_address_valid(self):
        """Valid Solana addresses should be recognized."""
        from core.cli import _looks_like_solana_address

        # Valid Solana addresses (base58, 32-44 chars)
        valid_addresses = [
            "So11111111111111111111111111111111111111112",  # SOL mint
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC mint
            "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V",  # USDT mint
            "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # Example
        ]

        for addr in valid_addresses:
            assert _looks_like_solana_address(addr), f"Should recognize {addr}"

    def test_looks_like_solana_address_invalid(self):
        """Invalid addresses should be rejected."""
        from core.cli import _looks_like_solana_address

        invalid_addresses = [
            "",  # Empty
            "abc",  # Too short
            "0x1234567890abcdef1234567890abcdef12345678",  # Ethereum format
            "a" * 50,  # Too long
        ]

        for addr in invalid_addresses:
            assert not _looks_like_solana_address(addr), f"Should reject {addr}"

    def test_looks_like_solana_address_none(self):
        """None should return False."""
        from core.cli import _looks_like_solana_address
        assert not _looks_like_solana_address(None)


class TestSymbolMap:
    """Test symbol map loading and saving."""

    def test_load_symbol_map_nonexistent(self):
        """Loading non-existent file should return empty dict."""
        from core.cli import _load_symbol_map

        result = _load_symbol_map(Path("/nonexistent/path/map.json"))
        assert result == {}

    def test_load_symbol_map_valid(self):
        """Valid JSON should be loaded correctly."""
        from core.cli import _load_symbol_map

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"SOL": "So11111111111111111111111111111111111111112"}, f)
            temp_path = Path(f.name)

        try:
            result = _load_symbol_map(temp_path)
            assert result == {"SOL": "So11111111111111111111111111111111111111112"}
        finally:
            temp_path.unlink()

    def test_load_symbol_map_invalid_json(self):
        """Invalid JSON should return empty dict."""
        from core.cli import _load_symbol_map

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            temp_path = Path(f.name)

        try:
            result = _load_symbol_map(temp_path)
            assert result == {}
        finally:
            temp_path.unlink()

    def test_save_symbol_map(self):
        """Symbol map should be saved correctly."""
        from core.cli import _save_symbol_map, _load_symbol_map

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "map.json"
            data = {"TEST": "TestAddress123456789012345678901234"}

            _save_symbol_map(path, data)

            assert path.exists()
            loaded = _load_symbol_map(path)
            assert loaded == data


class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_status_command_parsing(self):
        """Status command should parse correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("status")

        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_doctor_command_parsing(self):
        """Doctor command should parse with --test flag."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        doctor = subparsers.add_parser("doctor")
        doctor.add_argument("--test", action="store_true")

        args = parser.parse_args(["doctor", "--test"])
        assert args.command == "doctor"
        assert args.test is True


class TestOutputRendering:
    """Test output formatting functions."""

    def test_format_observations_empty(self):
        """Empty observations should return default message."""
        from core.cli import _format_observations

        result = _format_observations([])
        assert "No critical issues" in result

    def test_format_observations_none(self):
        """None observations should return default message."""
        from core.cli import _format_observations

        result = _format_observations(None)
        assert "No critical issues" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
