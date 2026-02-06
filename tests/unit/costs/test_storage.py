"""
Tests for core.costs.storage module.

Tests the CostStorage class for persistent cost data.
"""

import json
import pytest
from datetime import datetime, date
from pathlib import Path
from unittest.mock import patch


class TestCostStorage:
    """Test suite for CostStorage class."""

    @pytest.fixture
    def temp_storage_dir(self, tmp_path):
        """Create a temporary storage directory."""
        storage_dir = tmp_path / "costs"
        storage_dir.mkdir()
        return storage_dir

    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create a CostStorage instance with temp directory."""
        from core.costs.storage import CostStorage

        return CostStorage(storage_dir=temp_storage_dir)

    def test_storage_initialization(self, temp_storage_dir):
        """Test CostStorage can be instantiated."""
        from core.costs.storage import CostStorage

        storage = CostStorage(storage_dir=temp_storage_dir)
        assert storage is not None

    def test_storage_creates_directory_if_missing(self, tmp_path):
        """Test storage creates directory if it doesn't exist."""
        from core.costs.storage import CostStorage

        new_dir = tmp_path / "new_costs_dir"
        assert not new_dir.exists()

        storage = CostStorage(storage_dir=new_dir)

        assert new_dir.exists()

    def test_default_storage_dir(self):
        """Test default storage directory is bots/data/costs/."""
        from core.costs.storage import CostStorage, DEFAULT_STORAGE_DIR

        # Verify the constant is set correctly
        assert "bots" in str(DEFAULT_STORAGE_DIR) or "data" in str(DEFAULT_STORAGE_DIR)

    def test_save_cost_entry(self, storage, temp_storage_dir):
        """Test saving a single cost entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": "openai",
            "model": "gpt-4o",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cost_usd": 0.045
        }

        storage.save_entry(entry)

        # Check file was created
        today = date.today().isoformat()
        expected_file = temp_storage_dir / f"costs_{today}.json"
        assert expected_file.exists()

    def test_save_multiple_entries_same_day(self, storage, temp_storage_dir):
        """Test saving multiple entries on the same day."""
        entries = [
            {"timestamp": datetime.now().isoformat(), "provider": "openai", "cost_usd": 0.01},
            {"timestamp": datetime.now().isoformat(), "provider": "anthropic", "cost_usd": 0.02},
            {"timestamp": datetime.now().isoformat(), "provider": "grok", "cost_usd": 0.005},
        ]

        for entry in entries:
            storage.save_entry(entry)

        # Check all entries are in the file
        today = date.today().isoformat()
        file_path = temp_storage_dir / f"costs_{today}.json"

        with open(file_path, "r") as f:
            data = json.load(f)

        assert len(data["entries"]) == 3

    def test_load_daily_entries(self, storage, temp_storage_dir):
        """Test loading entries for a specific day."""
        # Create a test file
        today = date.today().isoformat()
        file_path = temp_storage_dir / f"costs_{today}.json"

        test_data = {
            "date": today,
            "entries": [
                {"provider": "openai", "cost_usd": 0.01},
                {"provider": "anthropic", "cost_usd": 0.02},
            ],
            "daily_total": 0.03
        }

        with open(file_path, "w") as f:
            json.dump(test_data, f)

        # Load and verify
        entries = storage.load_daily(date.today())

        assert len(entries) == 2
        assert entries[0]["provider"] == "openai"

    def test_load_daily_returns_empty_for_missing_file(self, storage):
        """Test loading a day with no data returns empty list."""
        from datetime import date, timedelta

        # Load a date in the past with no data
        old_date = date(2020, 1, 1)
        entries = storage.load_daily(old_date)

        assert entries == []

    def test_get_daily_total(self, storage, temp_storage_dir):
        """Test getting daily cost total."""
        entries = [
            {"timestamp": datetime.now().isoformat(), "provider": "openai", "cost_usd": 0.01},
            {"timestamp": datetime.now().isoformat(), "provider": "anthropic", "cost_usd": 0.02},
            {"timestamp": datetime.now().isoformat(), "provider": "grok", "cost_usd": 0.005},
        ]

        for entry in entries:
            storage.save_entry(entry)

        total = storage.get_daily_total(date.today())

        assert total == pytest.approx(0.035, rel=0.01)

    def test_get_monthly_total(self, storage, temp_storage_dir):
        """Test getting monthly cost total by aggregating daily files."""
        # Create multiple daily files for the current month
        today = date.today()

        for day_offset in range(3):
            target_date = date(today.year, today.month, max(1, today.day - day_offset))
            file_path = temp_storage_dir / f"costs_{target_date.isoformat()}.json"

            data = {
                "date": target_date.isoformat(),
                "entries": [{"cost_usd": 0.10}],
                "daily_total": 0.10
            }

            with open(file_path, "w") as f:
                json.dump(data, f)

        total = storage.get_monthly_total(today.year, today.month)

        # At least 0.10 for today's file
        assert total >= 0.10

    def test_get_monthly_total_by_provider(self, storage, temp_storage_dir):
        """Test getting monthly totals broken down by provider."""
        today = date.today()
        file_path = temp_storage_dir / f"costs_{today.isoformat()}.json"

        data = {
            "date": today.isoformat(),
            "entries": [
                {"provider": "openai", "cost_usd": 0.10},
                {"provider": "anthropic", "cost_usd": 0.20},
                {"provider": "openai", "cost_usd": 0.05},
            ],
            "daily_total": 0.35
        }

        with open(file_path, "w") as f:
            json.dump(data, f)

        by_provider = storage.get_monthly_by_provider(today.year, today.month)

        assert by_provider.get("openai", 0) == pytest.approx(0.15, rel=0.01)
        assert by_provider.get("anthropic", 0) == pytest.approx(0.20, rel=0.01)

    def test_file_naming_convention(self, storage, temp_storage_dir):
        """Test daily files follow costs_YYYY-MM-DD.json convention."""
        entry = {"timestamp": datetime.now().isoformat(), "cost_usd": 0.01}
        storage.save_entry(entry)

        files = list(temp_storage_dir.glob("costs_*.json"))
        assert len(files) == 1

        filename = files[0].name
        assert filename.startswith("costs_")
        assert filename.endswith(".json")
        # Verify date format YYYY-MM-DD
        date_part = filename.replace("costs_", "").replace(".json", "")
        assert len(date_part) == 10  # YYYY-MM-DD


class TestStorageFileFormat:
    """Test the JSON file format for storage."""

    @pytest.fixture
    def storage(self, tmp_path):
        from core.costs.storage import CostStorage

        storage_dir = tmp_path / "costs"
        storage_dir.mkdir()
        return CostStorage(storage_dir=storage_dir)

    def test_file_contains_date(self, storage, tmp_path):
        """Test file contains date field."""
        entry = {"timestamp": datetime.now().isoformat(), "cost_usd": 0.01}
        storage.save_entry(entry)

        storage_dir = tmp_path / "costs"
        files = list(storage_dir.glob("costs_*.json"))

        with open(files[0], "r") as f:
            data = json.load(f)

        assert "date" in data

    def test_file_contains_entries_array(self, storage, tmp_path):
        """Test file contains entries array."""
        entry = {"timestamp": datetime.now().isoformat(), "cost_usd": 0.01}
        storage.save_entry(entry)

        storage_dir = tmp_path / "costs"
        files = list(storage_dir.glob("costs_*.json"))

        with open(files[0], "r") as f:
            data = json.load(f)

        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_file_contains_daily_total(self, storage, tmp_path):
        """Test file contains daily_total field."""
        entry = {"timestamp": datetime.now().isoformat(), "cost_usd": 0.01}
        storage.save_entry(entry)

        storage_dir = tmp_path / "costs"
        files = list(storage_dir.glob("costs_*.json"))

        with open(files[0], "r") as f:
            data = json.load(f)

        assert "daily_total" in data
        assert data["daily_total"] == 0.01
