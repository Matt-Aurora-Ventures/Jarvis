"""
JARVIS Error Tracker - Persistent error tracking with deduplication
"""
import json
import os
import hashlib
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
from functools import wraps
import asyncio

from core.security.scrubber import get_scrubber

ERROR_DB_PATH = os.environ.get("JARVIS_ERROR_DB", "data/logs/error_database.json")
ERROR_LOG_PATH = os.environ.get("JARVIS_ERROR_LOG", "logs/jarvis_errors.log")


class ErrorTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.errors: Dict[str, Dict[str, Any]] = {}
        self._setup_directories()
        self._load_database()
        self._setup_logging()

    def _setup_directories(self):
        for path in [ERROR_DB_PATH, ERROR_LOG_PATH]:
            dir_path = os.path.dirname(path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

    def _setup_logging(self):
        self.logger = logging.getLogger("JARVIS.ErrorTracker")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.FileHandler(ERROR_LOG_PATH)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s'
            ))
            self.logger.addHandler(handler)

    def _load_database(self):
        if os.path.exists(ERROR_DB_PATH):
            try:
                with open(ERROR_DB_PATH) as f:
                    self.errors = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.errors = {}

    def _save_database(self):
        try:
            with open(ERROR_DB_PATH, 'w') as f:
                json.dump(self.errors, f, indent=2, default=str)
        except IOError as e:
            self.logger.error(f"Failed to save error database: {e}")

    def _get_error_hash(self, error: Exception, context: str = "") -> str:
        scrubber = get_scrubber()
        try:
            tb = traceback.format_exception(type(error), error, error.__traceback__)
            tb_key = ''.join(tb[-3:]) if len(tb) >= 3 else ''.join(tb)
        except Exception:
            tb_key = ""
        safe_message, _ = scrubber.scrub(str(error)[:100])
        safe_tb_key, _ = scrubber.scrub(tb_key)
        key = f"{type(error).__name__}:{safe_message}:{context}:{safe_tb_key}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def track_error(
        self,
        error: Exception,
        context: str = "",
        component: str = "unknown",
        metadata: Optional[Dict] = None
    ) -> str:
        scrubber = get_scrubber()
        error_hash = self._get_error_hash(error, context)
        now = datetime.now().isoformat()
        safe_message, _ = scrubber.scrub(str(error)[:500])
        safe_traceback, _ = scrubber.scrub(traceback.format_exc()[:3000])

        if error_hash in self.errors:
            entry = self.errors[error_hash]
            entry["count"] += 1
            entry["last_seen"] = now
            entry["occurrences"].append({"timestamp": now, "metadata": metadata})
            entry["occurrences"] = entry["occurrences"][-50:]
            if entry["count"] >= 10 and entry["status"] == "new":
                entry["status"] = "critical"
        else:
            self.errors[error_hash] = {
                "id": error_hash,
                "type": type(error).__name__,
                "message": safe_message,
                "component": component,
                "context": context,
                "traceback": safe_traceback,
                "first_seen": now,
                "last_seen": now,
                "count": 1,
                "status": "new",
                "fix_attempts": [],
                "occurrences": [{"timestamp": now, "metadata": metadata}]
            }

        self._save_database()
        count = self.errors[error_hash]["count"]
        self.logger.error(f"[{error_hash}] {component} | {type(error).__name__}: {safe_message} | Count: {count}")
        return error_hash

    def get_unresolved_errors(self) -> List[Dict]:
        return [e for e in self.errors.values() if e["status"] not in ("fixed", "ignored")]

    def get_critical_errors(self) -> List[Dict]:
        return [e for e in self.errors.values() if e["status"] == "critical"]

    def get_frequent_errors(self, min_count: int = 3) -> List[Dict]:
        return sorted([e for e in self.errors.values() if e["count"] >= min_count],
                     key=lambda x: x["count"], reverse=True)

    def mark_fixed(self, error_id: str, fix_description: str):
        if error_id in self.errors:
            self.errors[error_id]["status"] = "fixed"
            self.errors[error_id]["fix_attempts"].append({
                "timestamp": datetime.now().isoformat(),
                "description": fix_description,
                "result": "fixed"
            })
            self._save_database()

    def generate_report(self) -> str:
        lines = ["# JARVIS Error Report", f"Generated: {datetime.now().isoformat()}", ""]

        critical = self.get_critical_errors()
        if critical:
            lines.append("## CRITICAL ERRORS")
            for e in critical:
                lines.append(f"- [{e['id']}] {e['component']}: {e['type']} x{e['count']} - {e['message'][:100]}")

        frequent = self.get_frequent_errors()
        if frequent:
            lines.append("\n## FREQUENT ERRORS")
            for e in frequent[:10]:
                lines.append(f"- [{e['id']}] {e['component']}: {e['type']} x{e['count']}")

        return "\n".join(lines)


error_tracker = ErrorTracker()


def track_errors(component: str):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_tracker.track_error(e, context=f"{func.__module__}.{func.__name__}", component=component)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_tracker.track_error(e, context=f"{func.__module__}.{func.__name__}", component=component)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
