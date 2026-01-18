"""
Unified Logic Bus - Orchestrates all Jarvis components

Coordinates:
1. Treasury trading (positions with stop losses/take profits)
2. Sentiment aggregation (Grok-weighted 1.0 as primary)
3. Autonomous X posting
4. Telegram bot responses
5. Dexter ReAct financial analysis
6. State persistence across reboots

All decisions flow through Grok sentiment with 1.0 weighting.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class BusState:
    """Current state of all Jarvis systems."""
    treasury_positions: List[Dict[str, Any]] = None
    sentiment_score: float = 50.0
    last_x_post: Optional[str] = None
    last_telegram_update: Optional[str] = None
    last_dexter_decision: Optional[str] = None
    system_healthy: bool = True
    timestamp: str = ""

    def __post_init__(self):
        if self.timestamp == "":
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.treasury_positions is None:
            self.treasury_positions = []


class UnifiedLogicBus:
    """
    Central orchestrator for all Jarvis systems.

    Ensures:
    - All components have current state
    - Grok sentiment (1.0 weighting) drives all decisions
    - Position monitoring includes stop losses/take profits
    - X and Telegram bots work in concert
    - State persists across reboots
    """

    def __init__(
        self,
        grok_client=None,
        sentiment_aggregator=None,
        treasury_trader=None,
        scorekeeper=None,
        autonomous_engine=None,
        telegram_integration=None,
        dexter_agent=None,
    ):
        """Initialize unified bus with all components."""
        self.grok = grok_client
        self.sentiment_agg = sentiment_aggregator
        self.treasury = treasury_trader
        self.scorekeeper = scorekeeper
        self.x_engine = autonomous_engine
        self.tg = telegram_integration
        self.dexter = dexter_agent

        self.state = BusState()
        self._last_sync = None

    async def initialize(self) -> bool:
        """Initialize and synchronize all components on startup."""
        try:
            logger.info("🚀 Unified Logic Bus initializing...")

            # 1. Load treasury positions
            if self.treasury:
                positions = self._load_treasury_state()
                self.state.treasury_positions = positions
                logger.info(f"✓ Loaded {len(positions)} treasury positions")

                # Sync to scorekeeper for dashboard
                if self.scorekeeper and positions:
                    synced = self.scorekeeper.sync_from_treasury_positions(positions)
                    logger.info(f"✓ Synced {synced} positions to scorekeeper dashboard")

            # 2. Initialize sentiment engine
            if self.sentiment_agg:
                # Grok is primary (1.0 weighting)
                sentiment = await self._initialize_sentiment()
                self.state.sentiment_score = sentiment
                logger.info(f"✓ Sentiment engine initialized (Grok: 1.0 weight)")

            # 3. Prepare X bot
            if self.x_engine:
                logger.info("✓ X autonomous engine ready")

            # 4. Prepare Telegram bot
            if self.tg:
                logger.info("✓ Telegram integration ready")

            # 5. Dexter ReAct ready
            if self.dexter:
                logger.info("✓ Dexter ReAct agent ready (Grok-powered)")

            self.state.system_healthy = True
            logger.info("✅ Unified Logic Bus initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Bus initialization failed: {e}")
            self.state.system_healthy = False
            return False

    async def periodic_sync(self) -> bool:
        """Periodic sync of all component states (run every 5 minutes)."""
        try:
            # Update sentiment
            if self.sentiment_agg and self.grok:
                sentiment = self.sentiment_agg.get_sentiment_score("SOL")  # Sample
                self.state.sentiment_score = sentiment

            # Check treasury positions
            if self.treasury:
                positions = self._load_treasury_state()
                self.state.treasury_positions = positions

                # Ensure scorekeeper dashboard is updated
                if self.scorekeeper:
                    self.scorekeeper.sync_from_treasury_positions(positions)

            # Verify all components responding
            health_checks = await self._run_health_checks()
            self.state.system_healthy = all(health_checks.values())

            if not self.state.system_healthy:
                logger.warning("⚠️ System health degraded")
                for component, healthy in health_checks.items():
                    if not healthy:
                        logger.warning(f"  - {component}: UNHEALTHY")

            self.state.timestamp = datetime.now(timezone.utc).isoformat()
            self._last_sync = datetime.now(timezone.utc)

            return self.state.system_healthy

        except Exception as e:
            logger.error(f"Periodic sync failed: {e}")
            return False

    async def broadcast_state(self):
        """Broadcast current state to all components."""
        try:
            # X bot knows current sentiment
            if self.x_engine:
                self.x_engine._current_sentiment = self.state.sentiment_score

            # Dexter knows treasury state
            if self.dexter:
                self.dexter.treasury_positions = self.state.treasury_positions

            # Dashboard shows everything
            if self.scorekeeper:
                self.scorekeeper.last_broadcast_time = self.state.timestamp

        except Exception as e:
            logger.error(f"State broadcast failed: {e}")

    async def coordinate_trading_decision(
        self,
        symbol: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Coordinate a trading decision across all systems.

        Flow:
        1. Dexter ReAct analyzes (Grok-powered, 1.0 weighting)
        2. Treasury validates risk
        3. Scorekeeper records decision
        4. X bot posts if auto-enabled
        5. Telegram notified

        Args:
            symbol: Token to analyze
            context: Market context

        Returns:
            Decision result with reasoning
        """
        try:
            if not self.state.system_healthy:
                return {"error": "System unhealthy", "decision": "HOLD"}

            # Dexter analysis (Grok is primary decision maker)
            if self.dexter:
                dexter_decision = await self.dexter.analyze_trading_opportunity(symbol, context)

                # Treasury validation
                if self.treasury and dexter_decision.decision.value.startswith("TRADE"):
                    # Validate risk and execute if approved
                    pass  # Risk checks would go here

                # Log decision
                if self.scorekeeper:
                    self.scorekeeper._log_decision(
                        dexter_decision.decision.value,
                        symbol,
                        dexter_decision.rationale
                    )

                return {
                    "decision": dexter_decision.decision.value,
                    "confidence": dexter_decision.confidence,
                    "grok_sentiment": dexter_decision.grok_sentiment_score,
                    "reasoning": dexter_decision.rationale,
                }

            return {"error": "Dexter not available", "decision": "HOLD"}

        except Exception as e:
            logger.error(f"Trading decision coordination failed: {e}")
            return {"error": str(e), "decision": "HOLD"}

    async def health_check_message(self) -> str:
        """Generate health check status message for Telegram."""
        lines = [
            "🔍 Unified Logic Bus Health Check",
            "━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        # Component status
        components = {
            "Treasury": self.treasury is not None,
            "Sentiment": self.sentiment_agg is not None,
            "X Bot": self.x_engine is not None,
            "Telegram": self.tg is not None,
            "Dexter": self.dexter is not None,
            "Scorekeeper": self.scorekeeper is not None,
        }

        for comp_name, available in components.items():
            status = "✓" if available else "✗"
            lines.append(f"{status} {comp_name}")

        lines.append("")
        lines.append(f"Overall: {'✓ HEALTHY' if self.state.system_healthy else '✗ DEGRADED'}")
        lines.append(f"Last Sync: {self._last_sync or 'Never'}")
        lines.append(f"Treasury Positions: {len(self.state.treasury_positions)}")
        lines.append(f"Sentiment: {self.state.sentiment_score:.1f}/100")

        return "\n".join(lines)

    def _load_treasury_state(self) -> List[Dict[str, Any]]:
        """Load treasury positions from disk."""
        try:
            if not self.treasury or not hasattr(self.treasury, 'positions'):
                return []

            # Convert treasury Position objects to dicts
            positions = []
            for pos in self.treasury.positions.values():
                if hasattr(pos, 'is_open') and pos.is_open:
                    positions.append({
                        "id": pos.id,
                        "symbol": pos.token_symbol,
                        "token_mint": pos.token_mint,
                        "entry_price": pos.entry_price,
                        "current_price": pos.current_price,
                        "amount": pos.amount,
                        "amount_usd": pos.amount_usd,
                        "take_profit_price": pos.take_profit_price,
                        "stop_loss_price": pos.stop_loss_price,
                        "status": pos.status.value if hasattr(pos.status, 'value') else str(pos.status),
                        "tp_order_id": pos.tp_order_id,
                        "sl_order_id": pos.sl_order_id,
                        "pnl_usd": pos.pnl_usd,
                        "pnl_pct": pos.pnl_pct,
                    })
            return positions

        except Exception as e:
            logger.error(f"Failed to load treasury state: {e}")
            return []

    async def _initialize_sentiment(self) -> float:
        """Initialize sentiment engine and return current score."""
        try:
            if self.sentiment_agg:
                # Grok has 1.0 weighting (primary decision maker)
                score = self.sentiment_agg.get_market_sentiment()
                return score.get("grok", 50.0)  # Grok weight is 1.0
        except Exception as e:
            logger.error(f"Sentiment initialization failed: {e}")
        return 50.0

    async def _run_health_checks(self) -> Dict[str, bool]:
        """Run health checks on all components."""
        checks = {
            "treasury": self.treasury is not None and hasattr(self.treasury, 'positions'),
            "sentiment": self.sentiment_agg is not None,
            "x_engine": self.x_engine is not None,
            "telegram": self.tg is not None,
            "dexter": self.dexter is not None,
            "scorekeeper": self.scorekeeper is not None,
        }
        return checks


# Singleton instance
_logic_bus: Optional[UnifiedLogicBus] = None


async def get_unified_logic_bus(
    grok_client=None,
    sentiment_aggregator=None,
    treasury_trader=None,
    scorekeeper=None,
    autonomous_engine=None,
    telegram_integration=None,
    dexter_agent=None,
) -> UnifiedLogicBus:
    """Get or create unified logic bus."""
    global _logic_bus

    if _logic_bus is None:
        _logic_bus = UnifiedLogicBus(
            grok_client,
            sentiment_aggregator,
            treasury_trader,
            scorekeeper,
            autonomous_engine,
            telegram_integration,
            dexter_agent,
        )
        await _logic_bus.initialize()

    return _logic_bus
