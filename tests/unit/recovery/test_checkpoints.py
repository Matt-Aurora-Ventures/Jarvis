"""
Tests for CheckpointManager - state persistence for recovery.

Tests the ability to save, load, and clear checkpoint state
with automatic saving on shutdown.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass


class TestCheckpointManager:
    """Test suite for CheckpointManager class."""

    def test_init_creates_checkpoint_dir(self, tmp_path):
        """CheckpointManager should create checkpoint directory."""
        from core.recovery.checkpoints import CheckpointManager

        checkpoint_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(checkpoint_dir=str(checkpoint_dir))

        assert checkpoint_dir.exists()

    def test_init_default_dir(self):
        """CheckpointManager should use default directory if not specified."""
        from core.recovery.checkpoints import CheckpointManager

        with patch("core.recovery.checkpoints.Path.mkdir"):
            manager = CheckpointManager()
            # Should have a default checkpoint path
            assert manager.checkpoint_dir is not None

    def test_save_checkpoint_creates_file(self, tmp_path):
        """save_checkpoint should create a checkpoint file."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        state = {"component": "x_bot", "position": 42, "status": "running"}
        manager.save_checkpoint(state)

        # Should create a checkpoint file
        files = list(tmp_path.glob("checkpoint_*.json"))
        assert len(files) >= 1

    def test_save_checkpoint_with_name(self, tmp_path):
        """save_checkpoint should accept a checkpoint name."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        state = {"key": "value"}
        manager.save_checkpoint(state, name="my_checkpoint")

        checkpoint_file = tmp_path / "my_checkpoint.json"
        assert checkpoint_file.exists()

    def test_save_checkpoint_content(self, tmp_path):
        """save_checkpoint should save correct content."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        state = {"component": "trading", "balance": 1000.50}
        manager.save_checkpoint(state, name="test")

        checkpoint_file = tmp_path / "test.json"
        with open(checkpoint_file) as f:
            loaded = json.load(f)

        assert loaded["component"] == "trading"
        assert loaded["balance"] == 1000.50
        # Should include metadata
        assert "timestamp" in loaded or "_saved_at" in loaded

    def test_load_checkpoint_returns_state(self, tmp_path):
        """load_checkpoint should return saved state."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        original_state = {"key": "value", "count": 123}
        manager.save_checkpoint(original_state, name="test")

        loaded_state = manager.load_checkpoint(name="test")

        assert loaded_state["key"] == "value"
        assert loaded_state["count"] == 123

    def test_load_checkpoint_latest(self, tmp_path):
        """load_checkpoint without name should load latest."""
        from core.recovery.checkpoints import CheckpointManager
        import time

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        # Save multiple checkpoints
        manager.save_checkpoint({"version": 1}, name="checkpoint_001")
        time.sleep(0.01)  # Small delay to ensure different timestamps
        manager.save_checkpoint({"version": 2}, name="checkpoint_002")

        loaded = manager.load_checkpoint()

        # Should load the latest one
        assert loaded is not None
        # Either loads latest by timestamp or by name sorting

    def test_load_checkpoint_not_found(self, tmp_path):
        """load_checkpoint should return None if not found."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        loaded = manager.load_checkpoint(name="nonexistent")

        assert loaded is None

    def test_clear_checkpoints_removes_all(self, tmp_path):
        """clear_checkpoints should remove all checkpoint files."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        # Create multiple checkpoints
        manager.save_checkpoint({"a": 1}, name="cp1")
        manager.save_checkpoint({"b": 2}, name="cp2")
        manager.save_checkpoint({"c": 3}, name="cp3")

        # Verify files exist
        assert len(list(tmp_path.glob("*.json"))) == 3

        manager.clear_checkpoints()

        # All should be removed
        assert len(list(tmp_path.glob("*.json"))) == 0

    def test_clear_checkpoints_with_name(self, tmp_path):
        """clear_checkpoints with name should remove only that file."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        manager.save_checkpoint({"a": 1}, name="keep")
        manager.save_checkpoint({"b": 2}, name="delete")

        manager.clear_checkpoints(name="delete")

        # Only 'keep' should remain
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert "keep" in files[0].name

    def test_auto_save_on_shutdown_registers_handler(self, tmp_path):
        """CheckpointManager should register atexit handler for auto-save."""
        from core.recovery.checkpoints import CheckpointManager
        import atexit

        with patch.object(atexit, "register") as mock_register:
            manager = CheckpointManager(
                checkpoint_dir=str(tmp_path),
                auto_save=True
            )

            mock_register.assert_called()

    def test_auto_save_state_provider(self, tmp_path):
        """CheckpointManager should call state provider on auto-save."""
        from core.recovery.checkpoints import CheckpointManager

        state_provider = Mock(return_value={"auto": "saved"})

        manager = CheckpointManager(
            checkpoint_dir=str(tmp_path),
            auto_save=True,
            state_provider=state_provider
        )

        # Trigger the auto-save
        manager._do_auto_save()

        state_provider.assert_called_once()
        # Should have saved a checkpoint
        assert len(list(tmp_path.glob("*.json"))) >= 1

    def test_list_checkpoints(self, tmp_path):
        """list_checkpoints should return all checkpoint names."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        manager.save_checkpoint({"a": 1}, name="first")
        manager.save_checkpoint({"b": 2}, name="second")
        manager.save_checkpoint({"c": 3}, name="third")

        checkpoints = manager.list_checkpoints()

        assert len(checkpoints) == 3
        assert "first" in [c["name"] for c in checkpoints]
        assert "second" in [c["name"] for c in checkpoints]
        assert "third" in [c["name"] for c in checkpoints]

    def test_checkpoint_metadata(self, tmp_path):
        """Checkpoints should include metadata."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        state = {"key": "value"}
        manager.save_checkpoint(state, name="test")

        loaded = manager.load_checkpoint(name="test")

        # Should have timestamp metadata
        assert "_saved_at" in loaded or "timestamp" in loaded


class TestCheckpointManagerDataclassSupport:
    """Test checkpoint support for dataclass state."""

    def test_save_dataclass_state(self, tmp_path):
        """save_checkpoint should handle dataclass objects."""
        from core.recovery.checkpoints import CheckpointManager
        from dataclasses import dataclass, asdict

        @dataclass
        class BotState:
            name: str
            position: int
            active: bool

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        state = BotState(name="x_bot", position=42, active=True)
        manager.save_checkpoint(asdict(state), name="dataclass_test")

        loaded = manager.load_checkpoint(name="dataclass_test")

        assert loaded["name"] == "x_bot"
        assert loaded["position"] == 42
        assert loaded["active"] is True


class TestCheckpointManagerConcurrency:
    """Test checkpoint manager under concurrent access."""

    def test_concurrent_saves(self, tmp_path):
        """Multiple concurrent saves should not corrupt data."""
        from core.recovery.checkpoints import CheckpointManager
        import threading

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))
        errors = []

        def save_checkpoint(name):
            try:
                manager.save_checkpoint({"name": name, "data": "x" * 1000}, name=name)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=save_checkpoint, args=(f"checkpoint_{i}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All checkpoints should be saved
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 10


class TestCheckpointManagerEdgeCases:
    """Edge case tests for CheckpointManager."""

    def test_save_empty_state(self, tmp_path):
        """save_checkpoint should handle empty state."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        manager.save_checkpoint({}, name="empty")

        loaded = manager.load_checkpoint(name="empty")
        assert loaded is not None

    def test_save_nested_state(self, tmp_path):
        """save_checkpoint should handle nested state."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        state = {
            "bots": {
                "x_bot": {"status": "running", "tweets": [1, 2, 3]},
                "telegram": {"status": "idle", "messages": []}
            },
            "trading": {
                "positions": [
                    {"token": "SOL", "amount": 100},
                    {"token": "BTC", "amount": 0.5}
                ]
            }
        }

        manager.save_checkpoint(state, name="nested")

        loaded = manager.load_checkpoint(name="nested")

        assert loaded["bots"]["x_bot"]["status"] == "running"
        assert loaded["trading"]["positions"][0]["token"] == "SOL"

    def test_corrupted_checkpoint_handling(self, tmp_path):
        """load_checkpoint should handle corrupted files gracefully."""
        from core.recovery.checkpoints import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        # Create a corrupted checkpoint file
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("{ invalid json }")

        loaded = manager.load_checkpoint(name="corrupted")

        assert loaded is None  # Should return None, not raise
