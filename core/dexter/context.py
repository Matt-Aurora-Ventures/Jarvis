"""
Dexter Context Manager - Memory and Token Management

Handles large data efficiently by persisting full market data to disk
while keeping only summaries in LLM context to prevent token overflow.

Built on Dexter framework: https://github.com/virattt/dexter
License: MIT
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Manages context compaction and memory efficiency for Dexter agent.

    Strategy:
    - Full data persisted to disk: `data/dexter/sessions/{session_id}/market_state_{ts}.json`
    - Summaries kept in memory for LLM: last 3 iterations + current
    - Compaction triggered when > context_max_tokens
    """

    def __init__(
        self,
        session_id: str,
        session_dir: str = "data/dexter/sessions",
        context_max_tokens: int = 100000,
    ):
        """Initialize context manager"""
        self.session_id = session_id
        self.session_dir = Path(session_dir) / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.context_max_tokens = context_max_tokens

        # In-memory storage
        self.full_data = {}  # Raw data from tools
        self.summaries = []  # Compressed summaries for LLM
        self.history = []  # All previous iterations

        logger.info(f"ContextManager initialized for session {session_id}")

    def save_full_data(self, data: Dict[str, Any], data_type: str) -> str:
        """
        Persist full data to disk, return summary for LLM

        Args:
            data: Full raw data from tool
            data_type: Type of data (market_data, sentiment, liquidations, etc)

        Returns:
            Compressed summary for LLM context
        """
        # Save full data to disk
        timestamp = datetime.utcnow().isoformat()
        filename = f"{data_type}_{timestamp.replace(':', '-')}.json"
        filepath = self.session_dir / filename

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Full data saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save full data: {e}")

        # Store reference in memory
        self.full_data[data_type] = {"file": str(filepath), "ts": timestamp}

        # Return compressed summary
        return self._compress_data(data, data_type)

    def get_summary(self) -> str:
        """Get compressed context suitable for LLM prompt"""
        summary_text = "## Current Context Summary\n\n"

        # Show recent summaries (last 3 iterations)
        if self.summaries:
            summary_text += "### Recent Analysis\n"
            for i, summary in enumerate(self.summaries[-3:], 1):
                summary_text += f"{i}. {summary}\n"

        # Show data references
        if self.full_data:
            summary_text += "\n### Available Data (on disk)\n"
            for data_type, ref in self.full_data.items():
                summary_text += f"- {data_type}: {ref['file']}\n"

        return summary_text

    def add_summary(self, summary: str):
        """Add compressed summary to context"""
        self.summaries.append(summary)
        logger.debug(f"Summary added ({len(summary)} chars)")

    def check_context_overflow(self) -> bool:
        """Check if context would overflow LLM limit"""
        # Rough token estimate: 1 token ≈ 4 chars
        current_context = self.get_summary()
        estimated_tokens = len(current_context) / 4
        return estimated_tokens > self.context_max_tokens

    def compact_context(self):
        """Remove oldest summaries if context is full"""
        if self.check_context_overflow():
            # Keep only last 2 summaries
            if len(self.summaries) > 2:
                removed = self.summaries[0]
                self.summaries = self.summaries[1:]
                logger.info(f"Context compacted: removed old summary ({len(removed)} chars)")

    def save_session_state(self):
        """Save session state to disk for recovery"""
        state = {
            "session_id": self.session_id,
            "ts": datetime.utcnow().isoformat(),
            "summaries_count": len(self.summaries),
            "full_data_refs": self.full_data,
        }
        state_file = self.session_dir / "state.json"
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        logger.info(f"Session state saved: {state_file}")

    def _compress_data(self, data: Dict[str, Any], data_type: str) -> str:
        """Compress raw data into brief summary"""
        if data_type == "market_data":
            symbol = data.get("symbol", "?")
            price = data.get("price", 0)
            volume = data.get("volume", 0)
            return f"Market: {symbol} @ ${price:.2f}, 24h vol: ${volume/1e9:.1f}B"

        elif data_type == "sentiment":
            avg_score = data.get("aggregate_score", 0)
            sources = len(data.get("sources", []))
            return f"Sentiment: {avg_score:.1f}/100 from {sources} sources"

        elif data_type == "liquidations":
            levels = data.get("heatmap", {})
            high_level = max(levels.values()) if levels else 0
            return f"Liquidations: Peak heat at {high_level} entities"

        elif data_type == "positions":
            count = len(data.get("positions", []))
            total_pnl = sum(p.get("pnl", 0) for p in data.get("positions", []))
            return f"Positions: {count} open, PnL: ${total_pnl:.2f}"

        else:
            # Generic compression
            size_mb = len(json.dumps(data)) / (1024 * 1024)
            return f"Data ({data_type}): {size_mb:.1f}MB compressed"
