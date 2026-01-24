"""
Trading Analytics and Reporting

P&L calculations, performance metrics, and trade analysis.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .types import Position, TradeStatus, TradeReport, TradeDirection

logger = logging.getLogger(__name__)

# Import self-correcting AI system
try:
    from core.self_correcting import (
        get_shared_memory,
        get_message_bus,
        get_ollama_router,
        get_self_adjuster,
        LearningType,
        MessageType,
        MessagePriority,
        TaskType,
        Parameter,
        MetricType,
    )
    SELF_CORRECTING_AVAILABLE = True
except ImportError:
    SELF_CORRECTING_AVAILABLE = False
    get_shared_memory = None
    get_message_bus = None
    get_ollama_router = None
    get_self_adjuster = None
    LearningType = None
    MessageType = None
    MessagePriority = None
    TaskType = None
    Parameter = None
    MetricType = None


class TradingAnalytics:
    """Analytics and reporting for trading performance."""

    def __init__(self, memory=None, bus=None, router=None, adjuster=None):
        """
        Initialize trading analytics.

        Args:
            memory: Shared memory for self-correcting AI
            bus: Message bus for inter-bot communication
            router: Ollama router for AI analysis
            adjuster: Self-adjuster for parameter tuning
        """
        self.memory = memory
        self.bus = bus
        self.router = router
        self.adjuster = adjuster

    @staticmethod
    def calculate_daily_pnl(trade_history: List[Position], open_positions: List[Position]) -> float:
        """
        Calculate total P&L for today (realized + unrealized).

        Args:
            trade_history: List of closed positions
            open_positions: List of open positions

        Returns:
            Total daily P&L in USD (positive = profit, negative = loss)
        """
        today = datetime.utcnow().date()

        # Realized P&L from closed positions today
        realized_pnl = sum(
            p.pnl_usd for p in trade_history
            if p.status == TradeStatus.CLOSED and
            p.closed_at and
            datetime.fromisoformat(p.closed_at.replace('Z', '+00:00')).date() == today
        )

        # Unrealized P&L from positions opened today
        unrealized_pnl = sum(
            p.unrealized_pnl for p in open_positions
            if p.is_open and
            datetime.fromisoformat(p.opened_at.replace('Z', '+00:00')).date() == today
        )

        return realized_pnl + unrealized_pnl

    @staticmethod
    def generate_report(trade_history: List[Position], open_positions: List[Position]) -> TradeReport:
        """Generate trading performance report."""
        closed = [p for p in trade_history if p.status == TradeStatus.CLOSED]

        if not closed and not open_positions:
            return TradeReport()

        winning = [p for p in closed if p.pnl_usd > 0]
        losing = [p for p in closed if p.pnl_usd < 0]

        total_pnl = sum(p.pnl_usd for p in closed)
        unrealized = sum(p.unrealized_pnl for p in open_positions)

        pnls = [p.pnl_usd for p in closed]

        # Calculate average win and loss
        avg_win = sum(p.pnl_usd for p in winning) / len(winning) if winning else 0
        avg_loss = sum(p.pnl_usd for p in losing) / len(losing) if losing else 0

        return TradeReport(
            total_trades=len(closed),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=(len(winning) / len(closed) * 100) if closed else 0,
            total_pnl_usd=total_pnl,
            total_pnl_pct=(total_pnl / sum(p.amount_usd for p in closed) * 100) if closed else 0,
            best_trade_pnl=max(pnls) if pnls else 0,
            worst_trade_pnl=min(pnls) if pnls else 0,
            avg_trade_pnl=(total_pnl / len(closed)) if closed else 0,
            average_win_usd=avg_win,
            average_loss_usd=avg_loss,
            open_positions=len(open_positions),
            unrealized_pnl=unrealized
        )

    # ==========================================================================
    # SELF-CORRECTING AI INTEGRATION
    # ==========================================================================

    def record_trade_learning(
        self,
        token: str,
        action: str,
        pnl: float,
        pnl_pct: float,
        sentiment_score: float = None,
        context: Dict[str, Any] = None
    ):
        """Record a trade outcome as a learning for future reference."""
        if not SELF_CORRECTING_AVAILABLE or not self.memory:
            return

        try:
            import asyncio

            # Determine learning type based on P&L
            if pnl_pct > 0.1:  # 10%+ profit
                learning_type = LearningType.SUCCESS_PATTERN
                content = f"Successful {action} on {token}: {pnl_pct:.1%} profit"
                confidence = min(0.9, 0.5 + (pnl_pct / 0.3))
            elif pnl_pct < -0.05:  # 5%+ loss
                learning_type = LearningType.FAILURE_PATTERN
                content = f"Loss on {token}: {abs(pnl_pct):.1%} - avoid similar patterns"
                confidence = 0.8
            else:
                # Small gain/loss - not significant enough to learn from
                return

            # Store learning
            learning_context = {
                "token": token,
                "action": action,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                **(context or {})
            }

            if sentiment_score is not None:
                learning_context["sentiment_score"] = sentiment_score

            learning_id = self.memory.add_learning(
                component="treasury_bot",
                learning_type=learning_type,
                content=content,
                context=learning_context,
                confidence=confidence
            )

            logger.info(f"Stored learning {learning_id}: {content}")

            # Broadcast to other bots
            if self.bus:
                asyncio.create_task(
                    self.bus.publish(
                        sender="treasury_bot",
                        message_type=MessageType.NEW_LEARNING,
                        data={
                            "learning_id": learning_id,
                            "content": content,
                            "pnl_pct": pnl_pct,
                            "token": token
                        },
                        priority=MessagePriority.NORMAL
                    )
                )

            # Record metric for self-adjuster
            if self.adjuster:
                self.adjuster.record_metric(
                    component="treasury_bot",
                    metric_type=MetricType.SUCCESS_RATE,
                    value=1.0 if pnl_pct > 0 else 0.0
                )

        except Exception as e:
            logger.error(f"Error recording trade learning: {e}", exc_info=True)

    async def query_ai_for_trade_analysis(
        self,
        token: str,
        sentiment: str,
        score: float,
        past_learnings: List = None
    ) -> str:
        """Use Ollama/Claude to analyze trade opportunity."""
        if not SELF_CORRECTING_AVAILABLE or not self.router:
            return ""

        try:
            learning_context = ""
            if past_learnings:
                learning_context = "\n\nPast learnings:\n" + "\n".join(
                    f"- {l.content}" for l in past_learnings[:3]
                )

            prompt = f"""Analyze this trading opportunity:
Token: {token}
Sentiment: {sentiment} (score: {score:.2f})
{learning_context}

Should I trade this token? Consider:
1. Sentiment score strength
2. Past performance (from learnings)
3. Risk/reward ratio

Respond in 2-3 sentences."""

            response = await self.router.query(
                prompt=prompt,
                task_type=TaskType.REASONING
            )

            logger.info(
                f"AI analysis ({response.model_used}): {response.text[:100]}..."
            )
            return response.text

        except Exception as e:
            logger.error(f"Error querying AI: {e}", exc_info=True)
            return ""

    def handle_bus_message(self, message):
        """Handle incoming messages from other bots via message bus."""
        if not SELF_CORRECTING_AVAILABLE or not self.memory:
            return

        try:
            if message.type == MessageType.SENTIMENT_CHANGED:
                # Another bot detected sentiment change
                token = message.data.get('token')
                sentiment = message.data.get('sentiment')
                score = message.data.get('score', 0)

                logger.info(
                    f"Received sentiment signal: {token} = {sentiment} ({score:.2f})"
                )

                # Search for learnings about this token
                token_learnings = self.memory.search_learnings(
                    query=f"{token} trading",
                    min_confidence=0.6,
                    limit=3
                )

                if token_learnings:
                    logger.info(
                        f"Found {len(token_learnings)} past learnings about {token}"
                    )

            elif message.type == MessageType.PRICE_ALERT:
                # Price alert from monitoring bot
                token = message.data.get('token')
                alert_type = message.data.get('alert_type')
                logger.info(f"Price alert: {token} - {alert_type}")

            elif message.type == MessageType.NEW_LEARNING:
                # Another bot shared a learning
                learning_id = message.data.get('learning_id')
                logger.info(f"New learning shared: {learning_id}")

        except Exception as e:
            logger.error(f"Error handling bus message: {e}", exc_info=True)
