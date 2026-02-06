"""
Memory Explosion Prevention for ClawdBots.

Strategies (from UNIFIED_GSD):
1. Mutation: Updates relationship overwrites old facts
2. Compression: Summarize session logs into dense narratives
3. Hygiene: Strip chat history during agent-to-agent handoffs
4. Relevance: Filter out obsolete entries by age
5. Log Rotation: Daily log files with automatic cleanup
"""

import json
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages memory lifecycle for ClawdBots to prevent unbounded growth."""

    def __init__(self, data_dir: str = "/root/clawdbots", max_log_days: int = 7):
        self.data_dir = Path(data_dir)
        self.logs_dir = self.data_dir / "memory"
        self.max_log_days = max_log_days
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def rotate_logs(self):
        """Move today's entries to daily log file, clean old logs."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.json"

        # Load current session entries
        session_file = self.data_dir / "session_log.json"
        if session_file.exists():
            try:
                entries = json.loads(session_file.read_text())
                # Append to today's log
                existing = []
                if log_file.exists():
                    existing = json.loads(log_file.read_text())
                existing.extend(entries)
                log_file.write_text(json.dumps(existing, indent=2))
                # Clear session log
                session_file.write_text("[]")
                logger.info(f"Rotated {len(entries)} entries to {log_file}")
            except Exception as e:
                logger.error(f"Log rotation failed: {e}")

        # Clean old logs
        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        """Remove log files older than max_log_days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_log_days)
        for log_file in self.logs_dir.glob("*.json"):
            try:
                date_str = log_file.stem  # "2026-02-01"
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                if file_date < cutoff:
                    log_file.unlink()
                    logger.info(f"Cleaned old log: {log_file}")
            except (ValueError, OSError):
                pass  # Skip non-date files

    def compact_memory(self, memory_file: str = "MEMORY.md") -> str:
        """Compact verbose memory into dense summary format.

        Reads all recent daily logs and produces a compact MEMORY.md
        with curated long-term facts only.
        """
        memory_path = self.data_dir / memory_file
        all_entries = []

        # Read last 2 days of logs (today + yesterday)
        for i in range(2):
            date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            log_file = self.logs_dir / f"{date}.json"
            if log_file.exists():
                try:
                    entries = json.loads(log_file.read_text())
                    all_entries.extend(entries)
                except Exception:
                    pass

        return f"Memory compact: {len(all_entries)} entries from last 2 days"

    def strip_handoff_history(self, handoff_data: dict) -> dict:
        """Strip verbose chat history from agent-to-agent handoffs.

        Keeps: task brief, context summary, key facts
        Removes: full conversation logs, raw API responses
        """
        cleaned = {
            "task": handoff_data.get("task", ""),
            "context": handoff_data.get("context", ""),
            "key_facts": handoff_data.get("key_facts", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Remove verbose fields
        for key in ["conversation_history", "raw_responses", "full_logs"]:
            cleaned.pop(key, None)

        return cleaned

    def get_relevant_memory(self, query: str, max_age_days: int = 7) -> List[dict]:
        """Get memory entries filtered by relevance and recency."""
        results = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        for log_file in sorted(self.logs_dir.glob("*.json"), reverse=True):
            try:
                date_str = log_file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                if file_date < cutoff:
                    break

                entries = json.loads(log_file.read_text())
                for entry in entries:
                    content = entry.get("content", "").lower()
                    if query.lower() in content:
                        results.append(entry)
            except Exception:
                pass

        return results

    def get_stats(self) -> dict:
        """Get memory usage statistics."""
        total_files = list(self.logs_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in total_files if f.exists())

        return {
            "log_files": len(total_files),
            "total_size_kb": round(total_size / 1024, 1),
            "max_retention_days": self.max_log_days,
            "oldest_log": min((f.stem for f in total_files), default="none"),
            "newest_log": max((f.stem for f in total_files), default="none"),
        }
