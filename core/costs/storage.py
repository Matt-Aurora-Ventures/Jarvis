"""
Cost Storage for persistent cost tracking data.

Stores daily cost entries in JSON files in bots/data/costs/.
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# Default storage directory
_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_DIR = _ROOT / "bots" / "data" / "costs"


class CostStorage:
    """
    Persistent storage for API cost tracking data.

    Stores daily cost data in JSON files with naming convention:
    costs_YYYY-MM-DD.json

    File format:
    {
        "date": "2026-02-02",
        "entries": [
            {"timestamp": "...", "provider": "openai", "model": "gpt-4o", "cost_usd": 0.045, ...},
            ...
        ],
        "daily_total": 5.50
    }
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize the storage.

        Args:
            storage_dir: Directory for storing cost files.
                        Defaults to bots/data/costs/
        """
        self._storage_dir = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def storage_dir(self) -> Path:
        """Get the storage directory path."""
        return self._storage_dir

    def _get_daily_file(self, target_date: date) -> Path:
        """Get the path for a daily cost file."""
        filename = f"costs_{target_date.isoformat()}.json"
        return self._storage_dir / filename

    def _load_daily_file(self, target_date: date) -> Dict[str, Any]:
        """Load a daily file or return empty structure."""
        file_path = self._get_daily_file(target_date)

        if not file_path.exists():
            return {
                "date": target_date.isoformat(),
                "entries": [],
                "daily_total": 0.0,
            }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cost file {file_path}: {e}")
            return {
                "date": target_date.isoformat(),
                "entries": [],
                "daily_total": 0.0,
            }

    def _save_daily_file(self, target_date: date, data: Dict[str, Any]) -> None:
        """Save data to a daily file."""
        file_path = self._get_daily_file(target_date)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save cost file {file_path}: {e}")

    def save_entry(self, entry: Dict[str, Any]) -> None:
        """
        Save a cost entry to the appropriate daily file.

        Args:
            entry: Cost entry dict with at least 'cost_usd' field.
                  Optional: timestamp, provider, model, input_tokens, output_tokens
        """
        # Get the date from entry timestamp or use today
        timestamp = entry.get("timestamp")
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                else:
                    dt = timestamp
                target_date = dt.date()
            except (ValueError, AttributeError):
                target_date = date.today()
        else:
            target_date = date.today()
            entry["timestamp"] = datetime.now().isoformat()

        # Load existing data
        data = self._load_daily_file(target_date)

        # Add entry
        data["entries"].append(entry)

        # Update total
        data["daily_total"] = sum(e.get("cost_usd", 0) for e in data["entries"])

        # Save
        self._save_daily_file(target_date, data)

    def load_daily(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Load all entries for a specific day.

        Args:
            target_date: The date to load entries for

        Returns:
            List of cost entries
        """
        data = self._load_daily_file(target_date)
        return data.get("entries", [])

    def get_daily_total(self, target_date: Optional[date] = None, provider: Optional[str] = None) -> float:
        """
        Get the total cost for a specific day.

        Args:
            target_date: Date to get total for (defaults to today)
            provider: Optional provider to filter by

        Returns:
            Total cost in USD
        """
        if target_date is None:
            target_date = date.today()

        data = self._load_daily_file(target_date)

        if provider:
            # Filter by provider
            provider_lower = provider.lower()
            entries = [
                e for e in data.get("entries", [])
                if e.get("provider", "").lower() == provider_lower
            ]
            return sum(e.get("cost_usd", 0) for e in entries)

        return data.get("daily_total", 0.0)

    def get_monthly_total(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> float:
        """
        Get the total cost for a specific month.

        Args:
            year: Year (defaults to current year)
            month: Month (defaults to current month)
            provider: Optional provider to filter by

        Returns:
            Total cost in USD
        """
        today = date.today()
        if year is None:
            year = today.year
        if month is None:
            month = today.month

        total = 0.0

        # Find all files for the month
        pattern = f"costs_{year:04d}-{month:02d}-*.json"
        for file_path in self._storage_dir.glob(pattern):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if provider:
                    provider_lower = provider.lower()
                    entries = [
                        e for e in data.get("entries", [])
                        if e.get("provider", "").lower() == provider_lower
                    ]
                    total += sum(e.get("cost_usd", 0) for e in entries)
                else:
                    total += data.get("daily_total", 0.0)

            except (json.JSONDecodeError, IOError):
                continue

        return total

    def get_monthly_by_provider(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Dict[str, float]:
        """
        Get monthly costs broken down by provider.

        Args:
            year: Year (defaults to current year)
            month: Month (defaults to current month)

        Returns:
            Dict mapping provider names to their total costs
        """
        today = date.today()
        if year is None:
            year = today.year
        if month is None:
            month = today.month

        by_provider: Dict[str, float] = {}

        # Find all files for the month
        pattern = f"costs_{year:04d}-{month:02d}-*.json"
        for file_path in self._storage_dir.glob(pattern):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for entry in data.get("entries", []):
                    provider = entry.get("provider", "unknown")
                    cost = entry.get("cost_usd", 0)
                    by_provider[provider] = by_provider.get(provider, 0) + cost

            except (json.JSONDecodeError, IOError):
                continue

        return by_provider

    def get_monthly_by_day(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Dict[str, float]:
        """
        Get monthly costs broken down by day.

        Args:
            year: Year (defaults to current year)
            month: Month (defaults to current month)

        Returns:
            Dict mapping date strings to daily totals
        """
        today = date.today()
        if year is None:
            year = today.year
        if month is None:
            month = today.month

        by_day: Dict[str, float] = {}

        # Find all files for the month
        pattern = f"costs_{year:04d}-{month:02d}-*.json"
        for file_path in self._storage_dir.glob(pattern):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                date_str = data.get("date", file_path.stem.replace("costs_", ""))
                by_day[date_str] = data.get("daily_total", 0.0)

            except (json.JSONDecodeError, IOError):
                continue

        return by_day
