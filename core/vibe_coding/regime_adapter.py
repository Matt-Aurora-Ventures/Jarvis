"""
Regime Adapter - Applies sentiment-driven code changes.

Autonomously updates trading parameters without manual intervention:
- Reads current Grok sentiment
- Maps to market regime
- Applies parameter changes
- Logs all adaptations

This is the "vibe coding" - sentiment → behavior.
"""

import logging
from typing import Dict, Optional, Callable, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RegimeAdapter:
    """
    Applies market regime adaptations automatically.

    Workflow:
    1. Grok sentiment analyzed
    2. Market regime determined
    3. Parameters calculated
    4. Callbacks notify trading engine
    5. Changes applied in real-time
    """

    def __init__(self):
        """Initialize adapter."""
        self.current_parameters: Dict = {}
        self.adaptation_history: List = []
        self._parameter_callbacks: Dict[str, Callable] = {}
        self.last_adaptation = None

    def register_parameter_callback(self, param_name: str, callback: Callable):
        """
        Register a callback for parameter changes.

        Callback will be called when parameter changes:
        ```
        adapter.register_parameter_callback(
            "MAX_POSITION_SIZE_USD",
            lambda new_value: update_trading_config(new_value)
        )
        ```
        """
        self._parameter_callbacks[param_name] = callback
        logger.info(f"Registered callback for parameter: {param_name}")

    async def adapt_to_regime(self, sentiment_mapper, sentiment_score: float) -> Dict:
        """
        Adapt trading parameters to current market sentiment.

        Returns:
            Dict of parameters that were changed
        """
        try:
            # Analyze sentiment to regime
            regime = sentiment_mapper.analyze_sentiment(sentiment_score)

            # Get new parameters
            new_params = sentiment_mapper.get_trading_parameters(regime)

            # Compare to current and identify changes
            changes = {}
            for key, value in new_params.items():
                old_value = self.current_parameters.get(key)

                if old_value != value:
                    changes[key] = {
                        "old": old_value,
                        "new": value,
                    }

                    # Apply change
                    await self._apply_parameter(key, value)

            # Record adaptation
            if changes:
                self.adaptation_history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "regime": regime.value,
                    "sentiment_score": sentiment_score,
                    "changes": changes,
                })
                self.last_adaptation = datetime.now(timezone.utc)

                logger.info(f"Adapted to {regime.value}: {len(changes)} parameter(s) changed")

            # Update current parameters
            self.current_parameters = new_params

            return changes

        except Exception as e:
            logger.error(f"Regime adaptation failed: {e}")
            return {}

    async def _apply_parameter(self, param_name: str, new_value) -> bool:
        """
        Apply a parameter change.

        Calls registered callbacks to update trading engine.
        """
        try:
            if param_name in self._parameter_callbacks:
                callback = self._parameter_callbacks[param_name]
                await callback(new_value) if hasattr(callback, '__await__') else callback(new_value)
                logger.info(f"Applied parameter: {param_name} = {new_value}")
                return True
            else:
                logger.debug(f"No callback registered for {param_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to apply parameter {param_name}: {e}")
            return False

    def get_adaptation_log(self, limit: int = 10) -> List[Dict]:
        """Get recent adaptations."""
        return self.adaptation_history[-limit:]

    def should_adapt(self, sentiment_mapper, new_sentiment: float, threshold: float = 10.0) -> bool:
        """
        Determine if significant enough change to warrant adaptation.

        Args:
            sentiment_mapper: Analyzer with sentiment history
            new_sentiment: Latest sentiment score
            threshold: Minimum change in sentiment to trigger adaptation

        Returns:
            True if should adapt
        """
        if not sentiment_mapper.sentiment_history:
            return True  # First time, always adapt

        # Compare to last few sentiments
        recent = sentiment_mapper.sentiment_history[-5:]
        avg_recent = sum(recent) / len(recent)

        change = abs(new_sentiment - avg_recent)

        return change >= threshold

    def get_vibe_status(self) -> Dict:
        """Get current vibe/regime status."""
        if not self.current_parameters:
            return {"status": "No regime active"}

        recent_adaptations = self.get_adaptation_log(3)

        return {
            "current_parameters": self.current_parameters,
            "recent_adaptations": recent_adaptations,
            "last_adaptation": self.last_adaptation.isoformat() if self.last_adaptation else None,
            "total_adaptations": len(self.adaptation_history),
        }
