"""
Dexter Scratchpad - Append-only decision logging for transparency.

Logs all reasoning steps, tool executions, and final trading decisions
for full transparency and debugging.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Scratchpad:
    """Append-only JSONL logging for Dexter reasoning and decisions."""

    def __init__(self, session_id: str, scratchpad_dir: Optional[Path] = None):
        """Initialize scratchpad for a session.

        Args:
            session_id: Unique session identifier
            scratchpad_dir: Directory for scratchpad logs (default: data/dexter/scratchpad)
        """
        self.session_id = session_id
        self.scratchpad_dir = Path(scratchpad_dir) if scratchpad_dir else Path("data/dexter/scratchpad")
        self.scratchpad_dir.mkdir(parents=True, exist_ok=True)
        self.scratchpad_path = self.scratchpad_dir / f"{session_id}.jsonl"
        self._entries = []

    def start_session(self, goal: str, symbol: Optional[str] = None):
        """Alias for log_start used by tests."""
        self.log_start(goal, symbol)

    def log_start(self, goal: str, symbol: Optional[str] = None):
        """Log the start of a reasoning session.

        Args:
            goal: What the agent is trying to accomplish
            symbol: Optional token symbol being analyzed
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "ts": timestamp,
            "timestamp": timestamp,
            "type": "start",
            "goal": goal,
            "symbol": symbol,
        }
        self._append(entry)
        logger.info(f"Dexter session started: {goal}" + (f" for {symbol}" if symbol else ""))

    def log_reasoning(self, thought: str, iteration: int):
        """Log a reasoning step.

        Args:
            thought: The agent's reasoning at this step
            iteration: Which iteration of the loop (1-based)
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "ts": timestamp,
            "timestamp": timestamp,
            "type": "reasoning",
            "thought": thought,
            "iteration": iteration,
        }
        self._append(entry)
        logger.debug(f"Iteration {iteration}: {thought[:100]}...")

    def log_action(self, tool: str, args: Dict[str, Any], result: str):
        """Log a tool execution.

        Args:
            tool: Name of the tool that was called
            args: Arguments passed to the tool
            result: Result from the tool (formatted as string)
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "ts": timestamp,
            "timestamp": timestamp,
            "type": "action",
            "tool": tool,
            "args": args,
            "result": result[:500],  # Cap result size
        }
        self._append(entry)
        logger.info(f"Tool executed: {tool}")

    def log_decision(self, action: str, symbol: str, rationale: str, confidence: float):
        """Log the final trading decision.

        Args:
            action: BUY, SELL, or HOLD
            symbol: Token symbol
            rationale: Why this decision was made
            confidence: 0-100 confidence score
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "ts": timestamp,
            "timestamp": timestamp,
            "type": "decision",
            "action": action,
            "symbol": symbol,
            "rationale": rationale,
            "confidence": confidence,
        }
        self._append(entry)
        logger.info(f"Decision: {action} {symbol} (confidence: {confidence}%)")

    def log_error(self, error_type: str, error_message: str = "", iteration: Optional[int] = None):
        """Log an error that occurred during reasoning.

        Args:
            error_type: Error type/category
            error_message: Error message
            iteration: Which iteration the error occurred on
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "ts": timestamp,
            "timestamp": timestamp,
            "type": "error",
            "error_type": error_type,
            "error_message": error_message,
            "error": error_message or error_type,
        }
        if iteration is not None:
            entry["iteration"] = iteration
        self._append(entry)
        logger.error(f"Error on iteration {iteration}: {error_type} {error_message}")

    def _append(self, entry: Dict[str, Any]):
        """Append an entry to the scratchpad.

        Args:
            entry: Entry to append (dict)
        """
        self._entries.append(entry)

        # Append to file
        try:
            with open(self.scratchpad_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except IOError as e:
            logger.warning(f"Failed to write to scratchpad: {e}")

    def get_entries(self) -> list:
        """Get all scratchpad entries for this session.

        Returns:
            List of logged entries
        """
        return self._entries

    @property
    def entries(self) -> list:
        """Public alias for entries."""
        return self._entries

    def save_to_disk(self) -> None:
        """Write entries to disk as JSONL."""
        try:
            with open(self.scratchpad_path, "w") as f:
                for entry in self._entries:
                    f.write(json.dumps(entry) + "\n")
        except IOError as e:
            logger.warning(f"Failed to write scratchpad: {e}")

    def get_summary(self) -> str:
        """Get a human-readable summary of the reasoning process.

        Returns:
            Formatted summary of the session
        """
        lines = ["=== Dexter Reasoning Session ===", ""]

        for entry in self._entries:
            ts = entry.get("ts", "")
            entry_type = entry.get("type", "unknown")

            if entry_type == "start":
                lines.append(f"START: {entry.get('goal')}")
                if entry.get('symbol'):
                    lines.append(f"Symbol: {entry['symbol']}")
                lines.append("")

            elif entry_type == "reasoning":
                lines.append(f"[Iteration {entry.get('iteration')}] REASON:")
                lines.append(f"  {entry.get('thought')}")
                lines.append("")

            elif entry_type == "action":
                lines.append(f"[Action] Called {entry.get('tool')}")
                lines.append(f"  Result: {entry.get('result')[:200]}...")
                lines.append("")

            elif entry_type == "decision":
                lines.append(f"[DECISION] {entry.get('action')} {entry.get('symbol')}")
                lines.append(f"  Confidence: {entry.get('confidence')}%")
                lines.append(f"  Rationale: {entry.get('rationale')}")
                lines.append("")

            elif entry_type == "error":
                lines.append(f"[ERROR] {entry.get('error_type')}: {entry.get('error_message')}")
                lines.append("")

        return "\n".join(lines)


__all__ = ["Scratchpad"]
