"""
Dexter Context Manager - Memory management for token efficiency.

Implements context compaction to keep LLM context under 100K tokens
by persisting full data to disk and keeping only summaries in memory.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages context memory with persistence and compaction."""

    def __init__(
        self,
        session_id: str,
        session_dir: Optional[Path] = None,
        context_max_tokens: int = 100000,
        max_tokens: Optional[int] = None,
        data_dir: Optional[Path] = None,
    ):
        """Initialize context manager.

        Args:
            session_id: Unique session identifier
            session_dir: Optional directory for session data
            context_max_tokens: Maximum tokens to keep in memory (approximate)
            max_tokens: Legacy alias for context_max_tokens
            data_dir: Base directory for persisted data (default: data/dexter/sessions)
        """
        self.session_id = session_id
        if max_tokens is not None:
            context_max_tokens = max_tokens
        self.context_max_tokens = context_max_tokens
        self.max_tokens = context_max_tokens

        if session_dir is not None:
            base_dir = Path(session_dir)
        else:
            base_dir = data_dir or Path("data/dexter/sessions")
            base_dir = base_dir / session_id
        self.data_dir = base_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._full_data = {}  # Full market data
        self._summaries = []  # Compressed summaries (kept in memory)
        self._token_count = 0

    def save_full_data(self, data: Dict[str, Any], data_type: str):
        """Save full data to disk.

        Args:
            data: Data to persist
            data_type: Type of data (e.g., "market_state", "prices", "sentiment")
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        filename = self.data_dir / f"{data_type}_{timestamp.replace(':', '-')}.json"

        try:
            with open(filename, "w") as f:
                json.dump({"ts": timestamp, "type": data_type, "data": data}, f)
            logger.info(f"Saved {data_type} to {filename}")
            return str(filename)
        except IOError as e:
            logger.error(f"Failed to save data: {e}")
            return None

    def get_summary(self) -> str:
        """Get compressed context summary for LLM.

        Returns:
            Human-readable summary of current context
        """
        lines = ["=== Context Summary ===", ""]

        # Add summaries
        for summary in self._summaries[-3:]:  # Keep last 3 summaries
            lines.append(summary)

        return "\n".join(lines)

    def add_summary(self, summary: str):
        """Add a new context summary (compressed representation).

        Args:
            summary: Summary text
        """
        self._summaries.append(summary)
        self._token_count += len(summary.split())  # Rough estimate

        if self.check_context_overflow():
            self.compact_context()

    def check_context_overflow(self) -> bool:
        """Check whether context exceeds the configured token budget."""
        return self._token_count > self.context_max_tokens

    def compact_context(self) -> None:
        """Compact summaries to fit within token budget."""
        if not self._summaries:
            return
        # Keep only the most recent summaries
        self._summaries = self._summaries[-3:]
        self._token_count = sum(len(s.split()) for s in self._summaries)
        logger.info(f"Compacted context: {len(self._summaries)} summaries, ~{self._token_count} tokens")

    def load_historical(self, data_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load most recent historical data.

        Args:
            data_type: Type of data to load (e.g., "market_state")

        Returns:
            Most recent data file contents or None if not found
        """
        try:
            files = list(self.data_dir.glob(f"{data_type or '*'}_*.json"))
            if not files:
                return None

            # Get most recent file
            latest = sorted(files)[-1]
            with open(latest, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load historical data: {e}")
            return None

    def get_token_estimate(self) -> int:
        """Estimate current token count in memory.

        Returns:
            Approximate token count
        """
        return self._token_count

    @property
    def summaries(self) -> list:
        """Public alias for summaries list."""
        return self._summaries


__all__ = ["ContextManager"]
