"""
Trading Execution

Swap execution, signal analysis, and trade operations.
"""

import os
import logging
from typing import Optional, Tuple, List, Dict, Any

from .types import TradeDirection
from .logging_utils import log_trading_error

logger = logging.getLogger(__name__)

# Import Jupiter client type hints
try:
    from ..jupiter import SwapQuote, SwapResult
except ImportError:
    SwapQuote = Any
    SwapResult = Any

# Import Bags.fm trade adapter
try:
    from core.trading.bags_adapter import BagsTradeAdapter
    BAGS_AVAILABLE = True
except ImportError:
    BAGS_AVAILABLE = False
    BagsTradeAdapter = None

# Import signal analyzers
try:
    from core.trading.decision_matrix import DecisionMatrix, TradeDecision, DecisionType
    from core.trading.signals.liquidation import LiquidationAnalyzer, LiquidationSignal, Liquidation
    from core.trading.signals.dual_ma import DualMAAnalyzer, DualMASignal
    from core.trading.signals.meta_labeler import MetaLabeler
    from core.trading.cooldown import CooldownManager, CooldownType
    SIGNALS_AVAILABLE = True
except ImportError:
    SIGNALS_AVAILABLE = False
    LiquidationSignal = None
    DualMASignal = None
    DecisionMatrix = None
    TradeDecision = None
    DecisionType = None
    MetaLabeler = None
    CooldownManager = None
    CooldownType = None
    LiquidationAnalyzer = None
    DualMAAnalyzer = None
    Liquidation = None

# Import CoinGlass for liquidation data
try:
    from integrations.coinglass.client import CoinGlassClient
    COINGLASS_AVAILABLE = True
except ImportError:
    COINGLASS_AVAILABLE = False
    CoinGlassClient = None


class SwapExecutor:
    """Handles swap execution via Bags.fm or Jupiter."""

    def __init__(self, jupiter_client, wallet, bags_adapter=None):
        """
        Initialize swap executor.

        Args:
            jupiter_client: JupiterClient for swap execution
            wallet: Wallet for transaction signing
            bags_adapter: Optional BagsTradeAdapter for partner fee earning
        """
        self.jupiter = jupiter_client
        self.wallet = wallet
        self.bags_adapter = bags_adapter

    async def execute_swap(
        self,
        quote: SwapQuote,
        input_mint: str = None,
        output_mint: str = None,
    ) -> SwapResult:
        """
        Execute a swap, routing through Bags.fm if available (earns partner fees).

        Falls back to Jupiter if Bags fails or isn't configured.

        Args:
            quote: SwapQuote from Jupiter
            input_mint: Input token mint (optional, extracted from quote)
            output_mint: Output token mint (optional, extracted from quote)

        Returns:
            SwapResult with success status and transaction details
        """
        # Extract mints from quote if not provided
        if input_mint is None:
            input_mint = quote.input_mint
        if output_mint is None:
            output_mint = quote.output_mint

        # Check recovery adapter circuit breaker
        adapter = None
        try:
            from core.recovery.adapters import TradingAdapter

            adapter = TradingAdapter()

            if not adapter.can_execute():
                status = adapter.get_status()
                logger.warning(
                    f"Trading circuit breaker OPEN - "
                    f"failures: {status.get('consecutive_failures', 0)}, "
                    f"recovers_at: {status.get('circuit_open_until', 'unknown')}"
                )
                return SwapResult(
                    success=False,
                    error="Trading temporarily disabled (circuit breaker open)",
                )

        except ImportError:
            logger.debug("Recovery adapter not available, using direct execution")
        except Exception as e:
            logger.warning(f"Recovery adapter error (continuing): {e}")

        # Try Bags.fm first if available (earns partner fees)
        if self.bags_adapter is not None:
            try:
                logger.info(f"Executing swap via Bags.fm: {input_mint[:8]}... -> {output_mint[:8]}...")

                signature, output_amount = await self.bags_adapter.execute_swap(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount=quote.in_amount,
                    slippage=quote.slippage_bps / 100.0,
                )

                result = SwapResult(
                    success=True,
                    signature=signature,
                    input_mint=input_mint,
                    output_mint=output_mint,
                    in_amount=quote.in_amount,
                    out_amount=output_amount,
                    price=quote.price if hasattr(quote, 'price') else 0.0,
                    error=None,
                )

                if adapter:
                    adapter.record_success("execute_swap_bags")

                return result

            except Exception as bags_error:
                logger.warning(f"Bags.fm swap failed, falling back to Jupiter: {bags_error}")
                if adapter:
                    adapter.record_failure("execute_swap_bags", str(bags_error))

        # Execute via Jupiter (fallback or primary if Bags not configured)
        result = await self.jupiter.execute_swap(quote, self.wallet)

        if adapter:
            if result.success:
                adapter.record_success("execute_swap_jupiter")
            else:
                adapter.record_failure("execute_swap_jupiter", result.error or "Unknown")

        return result


class SignalAnalyzer:
    """Analyzes trading signals from multiple sources."""

    def __init__(self, enable_signals: bool = True):
        """
        Initialize signal analyzer.

        Args:
            enable_signals: Enable advanced signal analysis
        """
        self._decision_matrix = None
        self._liquidation_analyzer = None
        self._ma_analyzer = None
        self._meta_labeler = None
        self._coinglass = None

        if enable_signals and SIGNALS_AVAILABLE:
            self._decision_matrix = DecisionMatrix()
            self._liquidation_analyzer = LiquidationAnalyzer()
            self._ma_analyzer = DualMAAnalyzer()
            self._meta_labeler = MetaLabeler()
            logger.info("Advanced signal analyzers initialized")

        if enable_signals and COINGLASS_AVAILABLE:
            self._coinglass = CoinGlassClient()
            logger.info("CoinGlass client initialized")

    async def close(self):
        """Clean up signal analyzer resources."""
        if self._coinglass:
            await self._coinglass.close()

    async def analyze_sentiment_signal(
        self,
        token_mint: str,
        sentiment_score: float,
        sentiment_grade: str,
        max_positions: int,
        open_positions_count: int
    ) -> Tuple[TradeDirection, str]:
        """
        Analyze sentiment and determine trade direction.

        Returns:
            Tuple of (direction, reasoning)
        """
        # Check if we'd exceed max positions
        if open_positions_count >= max_positions:
            return TradeDirection.NEUTRAL, "Max positions reached"

        # TIGHTENED THRESHOLDS - Require higher conviction for entries
        if sentiment_score > 0.40 and sentiment_grade in ['A+', 'A']:
            return TradeDirection.LONG, f"High conviction bullish (Grade {sentiment_grade}, score {sentiment_score:.2f})"

        if sentiment_score > 0.35 and sentiment_grade in ['A-', 'B+']:
            return TradeDirection.LONG, f"Strong bullish signal (Grade {sentiment_grade}, score {sentiment_score:.2f})"

        if sentiment_score > 0.30 and sentiment_grade == 'B':
            return TradeDirection.LONG, f"Moderate bullish signal (Grade {sentiment_grade}, score {sentiment_score:.2f})"

        if sentiment_score < -0.30:
            return TradeDirection.SHORT, f"Bearish signal - avoid (score {sentiment_score:.2f})"

        return TradeDirection.NEUTRAL, f"Signal not strong enough (score {sentiment_score:.2f}, grade {sentiment_grade})"

    async def analyze_liquidation_signal(
        self,
        symbol: str = "BTC",
    ) -> Tuple[TradeDirection, str, Optional[Any]]:
        """
        Analyze liquidation data for contrarian trading signals.

        Returns:
            Tuple of (direction, reasoning, signal)
        """
        if not self._coinglass or not self._liquidation_analyzer:
            return TradeDirection.NEUTRAL, "Liquidation analysis not available", None

        try:
            liq_data = await self._coinglass.get_liquidations(symbol, interval="5m", limit=12)

            if not liq_data:
                return TradeDirection.NEUTRAL, "No liquidation data available", None

            liquidations = []
            for ld in liq_data:
                if ld.long_liquidations > 0:
                    liquidations.append(Liquidation(
                        timestamp=ld.timestamp,
                        symbol=symbol,
                        side='long',
                        value_usd=ld.long_liquidations,
                        quantity=ld.long_liquidations / 100,  # Approximate quantity
                        price=0,
                        exchange='aggregated',
                    ))
                if ld.short_liquidations > 0:
                    liquidations.append(Liquidation(
                        timestamp=ld.timestamp,
                        symbol=symbol,
                        side='short',
                        value_usd=ld.short_liquidations,
                        quantity=ld.short_liquidations / 100,  # Approximate quantity
                        price=0,
                        exchange='aggregated',
                    ))

            signal = self._liquidation_analyzer.analyze(liquidations)

            if not signal:
                return TradeDirection.NEUTRAL, "No liquidation signal detected", None

            if signal.direction == 'long':
                direction = TradeDirection.LONG
                reason = f"Liquidation signal: {signal.reasoning} (confidence: {signal.confidence:.0%})"
            elif signal.direction == 'short':
                direction = TradeDirection.SHORT
                reason = f"Liquidation signal: {signal.reasoning} (confidence: {signal.confidence:.0%})"
            else:
                direction = TradeDirection.NEUTRAL
                reason = signal.reasoning

            return direction, reason, signal

        except Exception as e:
            logger.error(f"Error analyzing liquidation signal: {e}")
            return TradeDirection.NEUTRAL, f"Liquidation analysis error: {e}", None

    async def analyze_ma_signal(
        self,
        prices: List[float],
        symbol: str = "BTC",
    ) -> Tuple[TradeDirection, str, Optional[Any]]:
        """
        Analyze dual moving average signal.

        Returns:
            Tuple of (direction, reasoning, signal)
        """
        if not self._ma_analyzer:
            return TradeDirection.NEUTRAL, "MA analysis not available", None

        try:
            signal = self._ma_analyzer.analyze(prices, symbol)

            if not signal:
                return TradeDirection.NEUTRAL, "No MA signal detected", None

            if signal.direction == 'long':
                direction = TradeDirection.LONG
            elif signal.direction == 'short':
                direction = TradeDirection.SHORT
            else:
                direction = TradeDirection.NEUTRAL

            reason = f"MA signal: {signal.reasoning} (strength: {signal.strength:.0%})"
            return direction, reason, signal

        except Exception as e:
            logger.error(f"Error analyzing MA signal: {e}")
            return TradeDirection.NEUTRAL, f"MA analysis error: {e}", None

    async def get_combined_signal(
        self,
        token_mint: str,
        symbol: str,
        sentiment_score: float,
        sentiment_grade: str,
        max_positions: int,
        open_positions_count: int,
        prices: Optional[List[float]] = None,
    ) -> Tuple[TradeDirection, str, float]:
        """
        Get combined signal from all sources using decision matrix.

        Returns:
            Tuple of (direction, reasoning, confidence)
        """
        if not self._decision_matrix:
            direction, reason = await self.analyze_sentiment_signal(
                token_mint, sentiment_score, sentiment_grade, max_positions, open_positions_count
            )
            return direction, reason, 0.5

        signals = []
        reasons = []

        # 1. Sentiment signal
        sent_dir, sent_reason = await self.analyze_sentiment_signal(
            token_mint, sentiment_score, sentiment_grade, max_positions, open_positions_count
        )
        if sent_dir != TradeDirection.NEUTRAL:
            signals.append(('sentiment', sent_dir.value.lower(), sentiment_score))
            reasons.append(sent_reason)

        # 2. Liquidation signal
        liq_dir, liq_reason, liq_signal = await self.analyze_liquidation_signal(symbol)
        if liq_dir != TradeDirection.NEUTRAL and liq_signal:
            signals.append(('liquidation', liq_dir.value.lower(), liq_signal.confidence))
            reasons.append(liq_reason)

        # 3. MA signal (if prices available)
        if prices and len(prices) >= 100:
            ma_dir, ma_reason, ma_signal = await self.analyze_ma_signal(prices, symbol)
            if ma_dir != TradeDirection.NEUTRAL and ma_signal:
                signals.append(('ma', ma_dir.value.lower(), ma_signal.strength))
                reasons.append(ma_reason)

        if not signals:
            return TradeDirection.NEUTRAL, "No signals detected", 0.0

        # TIGHTENED: Weighted voting with higher confidence requirements
        long_score = sum(conf for _, dir, conf in signals if dir == 'long')
        short_score = sum(conf for _, dir, conf in signals if dir == 'short')

        min_signal_count = len([s for s in signals if s[1] == 'long']) if long_score > short_score else len([s for s in signals if s[1] == 'short'])
        avg_confidence = max(long_score, short_score) / max(min_signal_count, 1)

        if long_score > short_score and (long_score > 0.6 or (min_signal_count >= 2 and avg_confidence > 0.4)):
            direction = TradeDirection.LONG
            confidence = avg_confidence
        elif short_score > long_score and (short_score > 0.6 or (min_signal_count >= 2 and avg_confidence > 0.4)):
            direction = TradeDirection.SHORT
            confidence = avg_confidence
        else:
            direction = TradeDirection.NEUTRAL
            confidence = 0.0

        combined_reason = " | ".join(reasons)
        return direction, combined_reason, confidence

    async def get_liquidation_summary(self, symbol: str = "BTC") -> Dict[str, Any]:
        """Get 24h liquidation summary for a symbol."""
        if not self._coinglass:
            return {"error": "CoinGlass not available"}

        try:
            return await self._coinglass.get_liquidation_summary(symbol)
        except Exception as e:
            logger.error(f"Error fetching liquidation summary: {e}")
            return {"error": str(e)}
