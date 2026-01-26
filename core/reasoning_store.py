"""
Reasoning Chain Storage for Compliance and Learning

Stores debate reasoning chains for:
- Compliance and audit trails
- Performance tracking and calibration
- Machine learning and improvement

Based on the institutional hedge fund practice of recording
all decision reasoning for regulatory compliance.
"""

import json
import csv
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ReasoningChain:
    """
    A recorded reasoning chain from a debate.

    Contains all information needed to understand and replay
    the decision-making process.
    """

    debate_id: str
    symbol: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    market_data: Dict[str, Any] = field(default_factory=dict)
    signal: Dict[str, Any] = field(default_factory=dict)
    bull_case: str = ""
    bear_case: str = ""
    synthesis: str = ""
    recommendation: str = "HOLD"
    confidence: float = 50.0
    tokens_used: int = 0
    outcome: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert datetime to string
        if isinstance(data.get("timestamp"), datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningChain":
        """Create from dictionary."""
        # Parse timestamp if string
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                data["timestamp"] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                data["timestamp"] = datetime.now(timezone.utc)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StoreResult:
    """Result of a store operation."""

    success: bool
    chain_id: Optional[str] = None
    error: Optional[str] = None


class ReasoningStore:
    """
    Persistent storage for reasoning chains.

    Uses JSONL format for append-only efficiency.
    Supports querying, outcome tracking, and export.
    """

    def __init__(
        self,
        data_dir: str = "data/reasoning_chains",
        retention_days: int = 90,
    ):
        """
        Initialize reasoning store.

        Args:
            data_dir: Directory for storing chains
            retention_days: Days to retain chains before cleanup
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days

        # Main storage file
        self.chains_file = self.data_dir / "reasoning_chains.jsonl"

        # In-memory index for fast queries
        self._chains: Dict[str, Dict[str, Any]] = {}

        # Load existing chains
        self._load_chains()

    def store(self, chain: Dict[str, Any]) -> StoreResult:
        """
        Store a reasoning chain.

        Args:
            chain: Chain data dictionary

        Returns:
            StoreResult with chain_id
        """
        try:
            # Generate ID if not present
            chain_id = chain.get("debate_id") or chain.get("chain_id") or str(uuid.uuid4())[:12]
            chain["chain_id"] = chain_id

            # Add timestamp if not present
            if "timestamp" not in chain:
                chain["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Store in memory
            self._chains[chain_id] = chain

            # Append to file
            with open(self.chains_file, "a") as f:
                f.write(json.dumps(chain) + "\n")

            logger.info(f"Stored reasoning chain {chain_id}")

            return StoreResult(success=True, chain_id=chain_id)

        except Exception as e:
            logger.error(f"Failed to store chain: {e}")
            return StoreResult(success=False, error=str(e))

    def get(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chain by ID.

        Args:
            chain_id: The chain ID

        Returns:
            Chain data or None
        """
        return self._chains.get(chain_id)

    def query(
        self,
        symbol: Optional[str] = None,
        recommendation: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query chains with filters.

        Args:
            symbol: Filter by token symbol
            recommendation: Filter by recommendation (BUY/SELL/HOLD)
            start_date: Filter by minimum date
            end_date: Filter by maximum date
            limit: Maximum results

        Returns:
            List of matching chains
        """
        results = []

        for chain in self._chains.values():
            # Apply filters
            if symbol and chain.get("symbol") != symbol:
                continue

            if recommendation and chain.get("recommendation") != recommendation:
                continue

            if start_date or end_date:
                chain_timestamp = chain.get("timestamp", "")
                if isinstance(chain_timestamp, str):
                    try:
                        chain_dt = datetime.fromisoformat(chain_timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                else:
                    chain_dt = chain_timestamp

                if start_date and chain_dt < start_date:
                    continue
                if end_date and chain_dt > end_date:
                    continue

            results.append(chain)

            if len(results) >= limit:
                break

        return results

    def update_outcome(
        self,
        chain_id: str,
        outcome: Dict[str, Any],
    ) -> StoreResult:
        """
        Update a chain with actual outcome data.

        Args:
            chain_id: The chain ID
            outcome: Outcome data (pnl, was_correct, etc.)

        Returns:
            StoreResult
        """
        if chain_id not in self._chains:
            return StoreResult(success=False, error=f"Chain {chain_id} not found")

        try:
            self._chains[chain_id]["outcome"] = outcome

            # Rewrite file with updated data
            self._save_all()

            logger.info(f"Updated outcome for chain {chain_id}")

            return StoreResult(success=True, chain_id=chain_id)

        except Exception as e:
            logger.error(f"Failed to update outcome: {e}")
            return StoreResult(success=False, error=str(e))

    def get_accuracy_stats(self) -> Dict[str, Any]:
        """
        Calculate accuracy statistics from outcomes.

        Returns:
            Statistics dictionary
        """
        total = 0
        correct = 0
        buy_total = 0
        buy_correct = 0
        sell_total = 0
        sell_correct = 0

        for chain in self._chains.values():
            outcome = chain.get("outcome")
            if not outcome:
                continue

            total += 1
            if outcome.get("was_correct"):
                correct += 1

            rec = chain.get("recommendation")
            if rec == "BUY":
                buy_total += 1
                if outcome.get("was_correct"):
                    buy_correct += 1
            elif rec == "SELL":
                sell_total += 1
                if outcome.get("was_correct"):
                    sell_correct += 1

        return {
            "total_decisions": total,
            "overall_accuracy": correct / total if total > 0 else 0,
            "buy_accuracy": buy_correct / buy_total if buy_total > 0 else 0,
            "sell_accuracy": sell_correct / sell_total if sell_total > 0 else 0,
            "buy_count": buy_total,
            "sell_count": sell_total,
        }

    def export_json(self, filepath: str) -> None:
        """
        Export all chains to JSON file.

        Args:
            filepath: Output file path
        """
        with open(filepath, "w") as f:
            json.dump(list(self._chains.values()), f, indent=2, default=str)

        logger.info(f"Exported {len(self._chains)} chains to {filepath}")

    def export_csv(
        self,
        filepath: str,
        columns: Optional[List[str]] = None,
    ) -> None:
        """
        Export chains to CSV file.

        Args:
            filepath: Output file path
            columns: Columns to include (defaults to all)
        """
        if not self._chains:
            return

        chains_list = list(self._chains.values())

        if not columns:
            columns = list(chains_list[0].keys())

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for chain in chains_list:
                writer.writerow(chain)

        logger.info(f"Exported {len(chains_list)} chains to {filepath}")

    def cleanup_old(self) -> int:
        """
        Remove chains older than retention period.

        Returns:
            Number of chains removed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        removed = 0

        to_remove = []
        for chain_id, chain in self._chains.items():
            timestamp = chain.get("timestamp", "")
            if isinstance(timestamp, str):
                try:
                    chain_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                chain_dt = timestamp

            # Ensure chain_dt is timezone-aware for comparison
            if chain_dt.tzinfo is None:
                chain_dt = chain_dt.replace(tzinfo=timezone.utc)

            if chain_dt < cutoff:
                to_remove.append(chain_id)

        for chain_id in to_remove:
            del self._chains[chain_id]
            removed += 1

        if removed > 0:
            self._save_all()
            logger.info(f"Cleaned up {removed} old chains")

        return removed

    def _load_chains(self) -> None:
        """Load chains from file."""
        if not self.chains_file.exists():
            return

        try:
            with open(self.chains_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chain = json.loads(line)
                        chain_id = chain.get("chain_id") or chain.get("debate_id")
                        if chain_id:
                            self._chains[chain_id] = chain
                    except json.JSONDecodeError:
                        logger.warning(f"Skipping invalid JSON line")
                        continue

            logger.info(f"Loaded {len(self._chains)} reasoning chains")

        except Exception as e:
            logger.warning(f"Failed to load chains: {e}")

    def _save_all(self) -> None:
        """Save all chains to file."""
        with open(self.chains_file, "w") as f:
            for chain in self._chains.values():
                f.write(json.dumps(chain, default=str) + "\n")


__all__ = [
    "ReasoningStore",
    "ReasoningChain",
    "StoreResult",
]
