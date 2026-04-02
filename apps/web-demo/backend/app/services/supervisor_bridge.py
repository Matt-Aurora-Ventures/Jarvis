"""
Supervisor Bridge Service
Enables communication between web demo and Jarvis supervisor ecosystem.

This creates a bidirectional communication channel so the web demo can:
- Share data with other Jarvis bots (treasury, twitter, telegram, etc.)
- Receive updates from other components
- Contribute to the shared learning pool
- Coordinate actions across the ecosystem
"""

import logging
import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SupervisorBridge:
    """
    Bridge between web demo and Jarvis supervisor.

    Communication happens via shared state file that all components read/write.
    """

    def __init__(self):
        # Shared state file location
        self.state_dir = Path(os.getenv("JARVIS_STATE_DIR", "~/.lifeos/shared_state")).expanduser()
        self.state_file = self.state_dir / "web_demo_state.json"

        # Ensure directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self.shared_state: Dict[str, Any] = {}

        # Load existing state
        self._load_state()

        logger.info(f"Supervisor bridge initialized (state: {self.state_file})")

    def _load_state(self):
        """Load shared state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.shared_state = json.load(f)
                logger.info(f"Loaded shared state: {len(self.shared_state)} keys")
            except Exception as e:
                logger.error(f"Failed to load shared state: {e}")
                self.shared_state = {}
        else:
            self.shared_state = {
                "created_at": datetime.now().isoformat(),
                "component": "web_demo",
                "version": "1.0.0"
            }

    def _save_state(self):
        """Save shared state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.shared_state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save shared state: {e}")

    def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str = "web_demo"
    ):
        """
        Publish an event to the shared state for other components.

        Args:
            event_type: Type of event (e.g., "trade_executed", "ai_recommendation")
            data: Event data
            source: Component that generated the event

        Example:
            bridge.publish_event(
                event_type="trade_executed",
                data={
                    "token": "SOL",
                    "action": "buy",
                    "amount": 1.5,
                    "price": 125.50
                }
            )
        """
        # Ensure events list exists
        if "events" not in self.shared_state:
            self.shared_state["events"] = []

        # Add event
        event = {
            "type": event_type,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        self.shared_state["events"].append(event)

        # Keep only last 1000 events
        if len(self.shared_state["events"]) > 1000:
            self.shared_state["events"] = self.shared_state["events"][-1000:]

        # Save to disk
        self._save_state()

        logger.info(f"Published event: {event_type} from {source}")

    def get_events(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get events from shared state.

        Args:
            event_type: Filter by event type
            source: Filter by source component
            limit: Maximum number of events to return

        Returns:
            List of events (most recent first)
        """
        events = self.shared_state.get("events", [])

        # Filter
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        if source:
            events = [e for e in events if e.get("source") == source]

        # Return most recent first
        return events[-limit:][::-1]

    def share_data(self, key: str, value: Any):
        """
        Share data with other components.

        Args:
            key: Data key (e.g., "ai_recommendations", "portfolio_stats")
            value: Data value

        Example:
            bridge.share_data("current_positions", [
                {"token": "SOL", "amount": 10, "entry_price": 120},
                {"token": "USDC", "amount": 1000, "entry_price": 1.0}
            ])
        """
        self.shared_state[key] = value
        self.shared_state["last_updated"] = datetime.now().isoformat()
        self._save_state()

        logger.info(f"Shared data: {key}")

    def get_data(self, key: str, default: Any = None) -> Any:
        """
        Get data shared by other components.

        Args:
            key: Data key
            default: Default value if key doesn't exist

        Returns:
            Data value or default
        """
        # Reload state to get latest from disk
        self._load_state()
        return self.shared_state.get(key, default)

    def get_component_data(self, component: str) -> Dict[str, Any]:
        """
        Get all data shared by a specific component.

        Args:
            component: Component name (e.g., "treasury", "twitter", "telegram")

        Returns:
            Component's shared data
        """
        self._load_state()
        return self.shared_state.get(f"{component}_data", {})

    def share_learning(
        self,
        insight: str,
        category: str = "general",
        confidence: float = 0.5
    ):
        """
        Share a learning/insight with the ecosystem.

        This contributes to the collective knowledge base that all components
        can use to improve.

        Args:
            insight: The learning or insight
            category: Category (e.g., "trading", "market", "risk")
            confidence: Confidence in this learning (0.0 to 1.0)

        Example:
            bridge.share_learning(
                insight="Tokens with <10 SOL liquidity often rugpull within 24h",
                category="risk",
                confidence=0.85
            )
        """
        if "learnings" not in self.shared_state:
            self.shared_state["learnings"] = []

        learning = {
            "insight": insight,
            "category": category,
            "confidence": confidence,
            "source": "web_demo",
            "timestamp": datetime.now().isoformat()
        }

        self.shared_state["learnings"].append(learning)

        # Keep only last 500 learnings
        if len(self.shared_state["learnings"]) > 500:
            self.shared_state["learnings"] = self.shared_state["learnings"][-500:]

        self._save_state()

        logger.info(f"Shared learning: {insight[:50]}...")

    def get_learnings(
        self,
        category: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Get learnings from all components.

        Args:
            category: Filter by category
            min_confidence: Minimum confidence threshold

        Returns:
            List of learnings
        """
        self._load_state()
        learnings = self.shared_state.get("learnings", [])

        # Filter
        if category:
            learnings = [l for l in learnings if l.get("category") == category]
        if min_confidence > 0:
            learnings = [l for l in learnings if l.get("confidence", 0) >= min_confidence]

        return learnings

    def get_all_shared_state(self) -> Dict[str, Any]:
        """Get entire shared state for debugging/monitoring."""
        self._load_state()
        return self.shared_state.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        self._load_state()
        return {
            "total_events": len(self.shared_state.get("events", [])),
            "total_learnings": len(self.shared_state.get("learnings", [])),
            "shared_keys": list(self.shared_state.keys()),
            "last_updated": self.shared_state.get("last_updated"),
            "state_file_size": self.state_file.stat().st_size if self.state_file.exists() else 0
        }


# Global instance
_supervisor_bridge: Optional[SupervisorBridge] = None


def get_supervisor_bridge() -> SupervisorBridge:
    """Get or create global supervisor bridge instance."""
    global _supervisor_bridge
    if _supervisor_bridge is None:
        _supervisor_bridge = SupervisorBridge()
    return _supervisor_bridge
