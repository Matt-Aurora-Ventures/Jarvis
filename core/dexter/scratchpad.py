"""
Dexter Scratchpad - Decision Logging and Transparency

Logs all reasoning steps and tool execution for full transparency and debugging.
Provides append-only JSONL trail of the entire reasoning process.

Built on Dexter framework: https://github.com/virattt/dexter
License: MIT
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Scratchpad:
    """
    Append-only log of all Dexter reasoning steps and decisions.

    Each entry is a JSON object with:
    - ts: ISO timestamp
    - type: "start", "reasoning", "action", "decision", "error"
    - content: Varies by type

    Enables full audit trail of how trading decisions were made.
    """

    def __init__(self, session_id: str, scratchpad_dir: str = "data/dexter/scratchpad"):
        """Initialize scratchpad for a session"""
        self.session_id = session_id
        self.scratchpad_dir = Path(scratchpad_dir)
        self.scratchpad_dir.mkdir(parents=True, exist_ok=True)
        self.scratchpad_path = self.scratchpad_dir / f"{session_id}.jsonl"

        # In-memory buffer for this session
        self.entries = []

        logger.info(f"Scratchpad initialized for session {session_id} at {self.scratchpad_path}")

    def start_session(self, goal: str, symbol: Optional[str] = None, **kwargs):
        """Log session start"""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": "start",
            "goal": goal,
            "symbol": symbol,
            **kwargs,
        }
        self._append(entry)

    def log_reasoning(self, thought: str, iteration: int, **kwargs):
        """Log a reasoning step in the ReAct loop"""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": "reasoning",
            "thought": thought,
            "iteration": iteration,
            **kwargs,
        }
        self._append(entry)

    def log_action(self, tool: str, args: Dict[str, Any], result: str, **kwargs):
        """Log tool execution"""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": "action",
            "tool": tool,
            "args": args,
            "result": result,
            **kwargs,
        }
        self._append(entry)

    def log_decision(
        self,
        action: str,
        symbol: str,
        rationale: str,
        confidence: float,
        **kwargs,
    ):
        """Log final trading decision"""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": "decision",
            "action": action,  # BUY, SELL, HOLD, ERROR
            "symbol": symbol,
            "rationale": rationale,
            "confidence": confidence,
            **kwargs,
        }
        self._append(entry)

    def log_error(self, error_type: str, message: str, **kwargs):
        """Log an error during reasoning"""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": "error",
            "error_type": error_type,
            "message": message,
            **kwargs,
        }
        self._append(entry)

    def get_entries(self) -> list:
        """Get all entries logged so far"""
        return self.entries.copy()

    def get_summary(self) -> str:
        """Generate text summary of reasoning for LLM context"""
        if not self.entries:
            return "No reasoning steps logged yet"

        summary = []
        for i, entry in enumerate(self.entries, 1):
            ts = entry.get("ts", "?")
            entry_type = entry.get("type", "?")

            if entry_type == "start":
                summary.append(f"[{i}] START: {entry.get('goal')}")
            elif entry_type == "reasoning":
                thought = entry.get("thought", "")
                iteration = entry.get("iteration", 0)
                summary.append(f"[{i}] REASON (iter {iteration}): {thought}")
            elif entry_type == "action":
                tool = entry.get("tool", "?")
                result = entry.get("result", "")[:100]  # First 100 chars
                summary.append(f"[{i}] ACTION: {tool} → {result}...")
            elif entry_type == "decision":
                action = entry.get("action", "?")
                symbol = entry.get("symbol", "?")
                confidence = entry.get("confidence", 0)
                summary.append(
                    f"[{i}] DECISION: {action} {symbol} (confidence: {confidence:.1f}%)"
                )
            elif entry_type == "error":
                msg = entry.get("message", "")
                summary.append(f"[{i}] ERROR: {msg}")

        return "\n".join(summary)

    def save_to_disk(self):
        """Write all entries to JSONL file"""
        try:
            with open(self.scratchpad_path, "w") as f:
                for entry in self.entries:
                    f.write(json.dumps(entry) + "\n")
            logger.info(f"Scratchpad saved: {len(self.entries)} entries")
        except Exception as e:
            logger.error(f"Failed to save scratchpad: {e}")

    def _append(self, entry: Dict[str, Any]):
        """Internal: append entry to buffer"""
        self.entries.append(entry)
        logger.debug(f"Scratchpad entry: {entry['type']} - {entry.get('tool', entry.get('thought', ''))[:50]}")
