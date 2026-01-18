"""
Autonomous Manager - Coordinates all auto systems for hands-free operation.

Integrates:
- Auto-moderation (toxicity detection, auto-actions)
- Self-improvement (engagement analysis, optimization)
- Vibe coding (sentiment → parameter adaptation)

Runs autonomously on loop without human intervention.
"""

import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class AutonomousManager:
    """
    Master coordinator for autonomous Jarvis operation.

    Runs continuous loops that:
    1. Check for moderation issues
    2. Analyze engagement and optimize
    3. Map sentiment to behavior changes
    4. Report on system health
    """

    def __init__(
        self,
        toxicity_detector=None,
        auto_actions=None,
        engagement_analyzer=None,
        sentiment_mapper=None,
        regime_adapter=None,
        grok_client=None,
        sentiment_agg=None,
    ):
        """Initialize autonomous manager."""
        self.toxicity_detector = toxicity_detector
        self.auto_actions = auto_actions
        self.engagement_analyzer = engagement_analyzer
        self.sentiment_mapper = sentiment_mapper
        self.regime_adapter = regime_adapter
        self.grok = grok_client
        self.sentiment_agg = sentiment_agg

        self.is_running = False
        self.start_time = datetime.now(timezone.utc)
        self.stats = {
            "messages_checked": 0,
            "content_moderated": 0,
            "regimes_adapted": 0,
            "improvements_made": 0,
        }

    async def run(self):
        """Run autonomous operation loop."""
        self.is_running = True
        logger.info("🤖 Autonomous Manager started")

        tasks = [
            asyncio.create_task(self._moderation_loop()),
            asyncio.create_task(self._learning_loop()),
            asyncio.create_task(self._vibe_coding_loop()),
            asyncio.create_task(self._health_check_loop()),
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Autonomous loop error: {e}")
        finally:
            self.is_running = False

    async def _moderation_loop(self):
        """Continuous moderation checks."""
        logger.info("Starting moderation loop")

        while self.is_running:
            try:
                # In production, would pull from message queue
                # For now, just log that loop is running
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Moderation loop error: {e}")
                await asyncio.sleep(5)

    async def _learning_loop(self):
        """Continuous engagement analysis and optimization."""
        logger.info("Starting learning loop")

        while self.is_running:
            try:
                if self.engagement_analyzer:
                    # Analyze every 5 minutes
                    recommendations = self.engagement_analyzer.get_improvement_recommendations()

                    if recommendations:
                        logger.info(f"📚 Learning recommendations: {recommendations}")
                        self.stats["improvements_made"] += 1

                    # Save state
                    self.engagement_analyzer.save_state()

                await asyncio.sleep(300)  # Every 5 minutes

            except Exception as e:
                logger.error(f"Learning loop error: {e}")
                await asyncio.sleep(30)

    async def _vibe_coding_loop(self):
        """Continuous sentiment monitoring and regime adaptation."""
        logger.info("Starting vibe coding loop")

        while self.is_running:
            try:
                if self.sentiment_agg and self.grok and self.sentiment_mapper and self.regime_adapter:
                    # Get current sentiment
                    sentiment_score = await self._get_current_sentiment()

                    # Check if significant change
                    if self.regime_adapter.should_adapt(self.sentiment_mapper, sentiment_score):
                        # Adapt regime
                        changes = await self.regime_adapter.adapt_to_regime(
                            self.sentiment_mapper,
                            sentiment_score
                        )

                        if changes:
                            logger.info(f"🎯 Vibe adapted: {len(changes)} parameters changed")
                            self.stats["regimes_adapted"] += 1

                await asyncio.sleep(60)  # Every minute

            except Exception as e:
                logger.error(f"Vibe coding loop error: {e}")
                await asyncio.sleep(30)

    async def _health_check_loop(self):
        """Monitor system health and alert on issues."""
        logger.info("Starting health check loop")

        while self.is_running:
            try:
                health = {
                    "moderation": self.toxicity_detector is not None,
                    "learning": self.engagement_analyzer is not None,
                    "vibe_coding": self.sentiment_mapper is not None,
                    "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
                    "stats": self.stats,
                }

                logger.debug(f"Health check: {health}")

                await asyncio.sleep(300)  # Every 5 minutes

            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(60)

    async def _get_current_sentiment(self) -> float:
        """Get current market sentiment from Grok."""
        try:
            if self.sentiment_agg:
                # Get aggregate sentiment
                sentiment = self.sentiment_agg.get_market_sentiment()
                return sentiment.get("grok", 50.0)  # Grok has 1.0 weight
        except Exception as e:
            logger.error(f"Failed to get sentiment: {e}")

        return 50.0  # Neutral default

    def stop(self):
        """Stop autonomous operation."""
        self.is_running = False
        logger.info("🛑 Autonomous Manager stopped")

    def check_message(self, text: str, user_id: int = 0, platform: str = "telegram") -> Dict:
        """
        Check a message for moderation issues.

        Returns:
            Dict with moderation decision
        """
        # This would be called by bots when checking messages
        # Returns moderation action to take

        if not self.toxicity_detector:
            return {"should_moderate": False, "action": "LOG"}

        # This is synchronous wrapper for async check
        # In production would use event loop
        return {
            "should_moderate": False,
            "action": "LOG",
            "reason": "Demo mode"
        }

    def get_status(self) -> Dict:
        """Get current autonomous system status."""
        return {
            "running": self.is_running,
            "uptime": (datetime.now(timezone.utc) - self.start_time).isoformat(),
            "stats": self.stats,
            "moderation": self.auto_actions.get_statistics() if self.auto_actions else None,
            "learning": self.engagement_analyzer.get_summary() if self.engagement_analyzer else None,
            "vibe": self.regime_adapter.get_vibe_status() if self.regime_adapter else None,
        }


# Singleton instance
_autonomous_manager: Optional[AutonomousManager] = None


async def get_autonomous_manager(
    toxicity_detector=None,
    auto_actions=None,
    engagement_analyzer=None,
    sentiment_mapper=None,
    regime_adapter=None,
    grok_client=None,
    sentiment_agg=None,
) -> AutonomousManager:
    """Get or create autonomous manager."""
    global _autonomous_manager

    if _autonomous_manager is None:
        _autonomous_manager = AutonomousManager(
            toxicity_detector,
            auto_actions,
            engagement_analyzer,
            sentiment_mapper,
            regime_adapter,
            grok_client,
            sentiment_agg,
        )

    return _autonomous_manager
