"""
Memory Explosion Prevention for ClawdBots.

Prevents unbounded memory growth by:
1. Enforcing per-bot memory quotas
2. Auto-pruning old/low-value memories
3. Deduplication of similar entries
4. Compression of conversation histories

Thresholds:
- Max memories per bot: 10,000
- Max conversation history: 50 messages
- Auto-prune entries older than 90 days with low access count
- Deduplicate entries with >90% similarity
"""

import difflib
import json
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class MemoryGuard:
    """Enforces memory limits across ClawdBots to prevent unbounded growth."""

    DEFAULT_LIMITS = {
        "max_memories_per_bot": 10000,
        "max_conversation_history": 50,
        "max_memory_age_days": 90,
        "dedup_similarity_threshold": 0.9,
        "max_state_file_size_mb": 10,
    }

    def __init__(self, data_dir: str = "/root/clawdbots", limits: Optional[Dict[str, Any]] = None):
        self.data_dir = Path(data_dir)
        self.limits = {**self.DEFAULT_LIMITS, **(limits or {})}

    def _memory_dir(self, bot_name: str) -> Path:
        return self.data_dir / "memory" / bot_name

    def _bot_names(self) -> List[str]:
        """Discover bot names from memory directory."""
        mem_root = self.data_dir / "memory"
        if not mem_root.exists():
            return []
        return [d.name for d in mem_root.iterdir() if d.is_dir()]

    def check_health(self) -> Dict[str, Any]:
        """Check memory health across all bots.

        Returns:
            {"warnings": [...], "stats": {...}}
        """
        warnings = []
        stats = self.get_memory_stats()

        max_mem = self.limits["max_memories_per_bot"]
        for bot, bot_stats in stats.items():
            count = bot_stats.get("file_count", 0)
            if count > max_mem * 0.8:
                warnings.append(
                    f"{bot}: {count}/{max_mem} memory files "
                    f"({'OVER LIMIT' if count > max_mem else 'approaching limit'})"
                )
            total_mb = bot_stats.get("total_size_mb", 0)
            if total_mb > self.limits["max_state_file_size_mb"]:
                warnings.append(f"{bot}: total memory size {total_mb:.1f}MB exceeds limit")

        # Check state files
        size_warnings = self.check_file_sizes()
        for sw in size_warnings:
            if sw.get("warning"):
                warnings.append(sw["warning"])

        return {"warnings": warnings, "stats": stats}

    def enforce_limits(self, bot_name: Optional[str] = None) -> Dict[str, Any]:
        """Enforce memory limits for a bot (or all bots).

        Returns:
            {"actions": [...]}
        """
        actions = []
        bots = [bot_name] if bot_name else self._bot_names()

        for bot in bots:
            mem_dir = self._memory_dir(bot)
            if not mem_dir.exists():
                continue

            files = sorted(mem_dir.glob("*.json"))
            max_mem = self.limits["max_memories_per_bot"]

            if len(files) > max_mem:
                # Sort by last_access, prune oldest
                file_access = []
                for f in files:
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        last_access = data.get("last_access", "2000-01-01T00:00:00Z")
                        file_access.append((f, last_access))
                    except Exception:
                        file_access.append((f, "2000-01-01T00:00:00Z"))

                file_access.sort(key=lambda x: x[1])
                to_remove = len(file_access) - max_mem

                with _lock:
                    for f, _ in file_access[:to_remove]:
                        try:
                            f.unlink()
                            actions.append(f"Removed {f.name} from {bot} (over quota)")
                        except Exception as e:
                            logger.error(f"Failed to remove {f}: {e}")

        return {"actions": actions}

    def prune_old_entries(self, bot_name: str, max_age_days: Optional[int] = None) -> int:
        """Remove entries older than threshold with low access.

        Returns:
            Number of entries pruned.
        """
        max_age = max_age_days or self.limits["max_memory_age_days"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age)
        cutoff_str = cutoff.isoformat()
        pruned = 0

        mem_dir = self._memory_dir(bot_name)
        if not mem_dir.exists():
            return 0

        with _lock:
            for f in mem_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    last_access = data.get("last_access", "2000-01-01T00:00:00Z")
                    if last_access < cutoff_str:
                        f.unlink()
                        pruned += 1
                except Exception as e:
                    logger.error(f"Error pruning {f}: {e}")

        return pruned

    def deduplicate(self, bot_name: str) -> int:
        """Remove near-duplicate memory entries using difflib.

        Returns:
            Number of entries removed.
        """
        mem_dir = self._memory_dir(bot_name)
        if not mem_dir.exists():
            return 0

        threshold = self.limits["dedup_similarity_threshold"]
        files = sorted(mem_dir.glob("*.json"))
        if len(files) < 2:
            return 0

        # Load content strings for comparison
        file_contents: List[tuple] = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                # Flatten messages to a comparable string
                messages = data.get("messages", [])
                content_str = " ".join(m.get("content", "") for m in messages)
                last_access = data.get("last_access", "2000-01-01T00:00:00Z")
                file_contents.append((f, content_str, last_access))
            except Exception:
                continue

        removed = 0
        to_remove = set()

        for i in range(len(file_contents)):
            if file_contents[i][0] in to_remove:
                continue
            for j in range(i + 1, len(file_contents)):
                if file_contents[j][0] in to_remove:
                    continue
                ratio = difflib.SequenceMatcher(
                    None,
                    file_contents[i][1],
                    file_contents[j][1],
                ).ratio()
                if ratio >= threshold:
                    # Remove the one with older last_access
                    if file_contents[i][2] <= file_contents[j][2]:
                        to_remove.add(file_contents[i][0])
                    else:
                        to_remove.add(file_contents[j][0])

        with _lock:
            for f in to_remove:
                try:
                    f.unlink()
                    removed += 1
                except Exception as e:
                    logger.error(f"Failed to remove duplicate {f}: {e}")

        return removed

    def compress_conversations(self, bot_name: str) -> int:
        """Trim conversation histories to max length.

        Returns:
            Number of conversations trimmed.
        """
        mem_dir = self._memory_dir(bot_name)
        if not mem_dir.exists():
            return 0

        max_msgs = self.limits["max_conversation_history"]
        trimmed = 0

        with _lock:
            for f in mem_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    messages = data.get("messages", [])
                    if len(messages) > max_msgs:
                        data["messages"] = messages[-max_msgs:]
                        f.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        trimmed += 1
                except Exception as e:
                    logger.error(f"Error compressing {f}: {e}")

        return trimmed

    def check_file_sizes(self) -> List[Dict[str, Any]]:
        """Check all state files against size limits.

        Returns:
            List of dicts with file info and optional warnings.
        """
        results = []
        max_mb = self.limits["max_state_file_size_mb"]

        # Check JSON files in data_dir root and memory subdirs
        patterns = ["*.json", "*.db"]
        for pattern in patterns:
            for f in self.data_dir.glob(pattern):
                if not f.is_file():
                    continue
                size_mb = f.stat().st_size / (1024 * 1024)
                entry: Dict[str, Any] = {"file": str(f), "size_mb": round(size_mb, 2)}
                if size_mb > max_mb:
                    entry["warning"] = f"{f.name}: {size_mb:.1f}MB exceeds {max_mb}MB limit"
                results.append(entry)

        return results

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get per-bot memory usage statistics.

        Returns:
            {bot_name: {"file_count": int, "total_size_mb": float}}
        """
        stats: Dict[str, Any] = {}
        for bot in self._bot_names():
            mem_dir = self._memory_dir(bot)
            files = list(mem_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            stats[bot] = {
                "file_count": len(files),
                "total_size_mb": round(total_size / (1024 * 1024), 3),
            }
        return stats
