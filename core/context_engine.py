"""
JARVIS Context Engine - Timing controls for reports, tweets, sentiment
Prevents expensive operations on every restart
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

STATE_FILE = os.environ.get("JARVIS_CONTEXT_STATE", "data/context_state.json")
logger = logging.getLogger("JARVIS.ContextEngine")


class ContextEngine:
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
        os.makedirs(os.path.dirname(STATE_FILE) if os.path.dirname(STATE_FILE) else "data", exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "last_sentiment_report": None,
            "last_tweet": None,
            "last_full_report": None,
            "startup_count_today": 0,
            "last_startup_date": None,
            "sentiment_cache_valid": False
        }

    def _save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save context state: {e}")

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return None

    def can_run_sentiment(self, min_interval_hours: int = 4) -> bool:
        """Check if sentiment analysis should run (cached or stale)"""
        last = self._parse_datetime(self.state.get("last_sentiment_report"))
        if not last:
            return True
        elapsed = datetime.now() - last
        can_run = elapsed > timedelta(hours=min_interval_hours)
        if not can_run:
            remaining = timedelta(hours=min_interval_hours) - elapsed
            logger.info(f"Sentiment blocked - {remaining} until next allowed")
        return can_run

    def record_sentiment_run(self):
        self.state["last_sentiment_report"] = datetime.now().isoformat()
        self.state["sentiment_cache_valid"] = True
        self._save_state()
        logger.info("Recorded sentiment run")

    def can_tweet(self, min_interval_minutes: int = 30) -> bool:
        last = self._parse_datetime(self.state.get("last_tweet"))
        if not last:
            return True
        return datetime.now() - last > timedelta(minutes=min_interval_minutes)

    def record_tweet(self):
        self.state["last_tweet"] = datetime.now().isoformat()
        self._save_state()

    def can_send_report(self, min_interval_hours: int = 1) -> bool:
        last = self._parse_datetime(self.state.get("last_full_report"))
        if not last:
            return True
        return datetime.now() - last > timedelta(hours=min_interval_hours)

    def record_report(self):
        self.state["last_full_report"] = datetime.now().isoformat()
        self._save_state()

    def record_startup(self):
        today = datetime.now().date().isoformat()
        if self.state.get("last_startup_date") != today:
            self.state["startup_count_today"] = 0
            self.state["last_startup_date"] = today
        self.state["startup_count_today"] += 1
        self._save_state()
        logger.info(f"Startup #{self.state['startup_count_today']} today")

    def is_restart_loop(self, max_per_day: int = 15) -> bool:
        return self.state.get("startup_count_today", 0) > max_per_day

    def get_status(self) -> Dict[str, Any]:
        return {
            "sentiment_cache_valid": self.state.get("sentiment_cache_valid", False),
            "last_sentiment": self.state.get("last_sentiment_report"),
            "last_tweet": self.state.get("last_tweet"),
            "restarts_today": self.state.get("startup_count_today", 0),
            "can_run_sentiment": self.can_run_sentiment(),
            "can_tweet": self.can_tweet()
        }


context = ContextEngine()
