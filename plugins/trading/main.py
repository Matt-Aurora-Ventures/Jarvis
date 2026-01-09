"""
Trading Plugin

Provides Solana trading functionality integrated with LifeOS:
- Position monitoring and management
- Risk management
- Trade execution via Jupiter
- Price feeds from BirdEye, DexScreener, GeckoTerminal
- Exit intent enforcement

This plugin registers PAE components:
- Providers: price_feed, position_status, wallet_balance
- Actions: execute_swap, create_exit_intent, cancel_order
- Evaluators: risk_check, opportunity_score
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from lifeos.plugins.base import Plugin, PluginContext
from lifeos.plugins.manifest import PluginManifest
from lifeos.pae import Provider, Action, Evaluator, EvaluationResult
from lifeos.memory import MemoryContext

logger = logging.getLogger(__name__)


class TradingPlugin(Plugin):
    """
    Main trading plugin class.

    Integrates existing trading functionality with LifeOS architecture.
    """

    def __init__(self, context: PluginContext, manifest: PluginManifest):
        super().__init__(context, manifest)
        self._daemon_task: Optional[asyncio.Task] = None
        self._paper_mode = True
        self._positions: Dict[str, Any] = {}

    async def on_load(self) -> None:
        """Initialize trading systems."""
        logger.info("Trading plugin loading...")

        # Get configuration
        config = self._context.config
        self._paper_mode = config.get("paper_mode", True)

        # Register PAE components
        self._register_providers()
        self._register_actions()
        self._register_evaluators()

        logger.info(f"Trading plugin loaded (paper_mode={self._paper_mode})")

    async def on_enable(self) -> None:
        """Start trading services."""
        logger.info("Trading plugin enabling...")

        # Start position monitoring daemon
        self._daemon_task = asyncio.create_task(self._monitoring_loop())

        # Emit event
        event_bus = self._context.services.get("event_bus")
        if event_bus:
            await event_bus.emit(
                "trading.enabled",
                {"paper_mode": self._paper_mode}
            )

    async def on_disable(self) -> None:
        """Stop trading services."""
        logger.info("Trading plugin disabling...")

        # Stop daemon
        if self._daemon_task:
            self._daemon_task.cancel()
            try:
                await self._daemon_task
            except asyncio.CancelledError:
                pass
            self._daemon_task = None

    async def on_unload(self) -> None:
        """Cleanup trading resources."""
        logger.info("Trading plugin unloading...")

    def _register_providers(self) -> None:
        """Register trading data providers."""
        jarvis = self._context.services.get("jarvis")
        if not jarvis or not jarvis.pae:
            return

        # Price feed provider
        jarvis.pae.register_provider(
            "price_feed",
            PriceFeedProvider("price_feed", self._context.services),
            tags={"trading", "market_data"}
        )

        # Position status provider
        jarvis.pae.register_provider(
            "position_status",
            PositionStatusProvider("position_status", self._context.services),
            tags={"trading", "positions"}
        )

        # Wallet balance provider
        jarvis.pae.register_provider(
            "wallet_balance",
            WalletBalanceProvider("wallet_balance", self._context.services),
            tags={"trading", "wallet"}
        )

    def _register_actions(self) -> None:
        """Register trading actions."""
        jarvis = self._context.services.get("jarvis")
        if not jarvis or not jarvis.pae:
            return

        # Execute swap action
        jarvis.pae.register_action(
            "execute_swap",
            ExecuteSwapAction("execute_swap", self._context.services, self._paper_mode),
            tags={"trading", "execution"}
        )

        # Create exit intent
        jarvis.pae.register_action(
            "create_exit_intent",
            CreateExitIntentAction("create_exit_intent", self._context.services),
            tags={"trading", "risk"}
        )

    def _register_evaluators(self) -> None:
        """Register trading evaluators."""
        jarvis = self._context.services.get("jarvis")
        if not jarvis or not jarvis.pae:
            return

        # Risk check evaluator
        jarvis.pae.register_evaluator(
            "risk_check",
            RiskCheckEvaluator("risk_check", self._context.services),
            tags={"trading", "risk"}
        )

        # Opportunity score evaluator
        jarvis.pae.register_evaluator(
            "opportunity_score",
            OpportunityScoreEvaluator("opportunity_score", self._context.services),
            tags={"trading", "analysis"}
        )

    async def _monitoring_loop(self) -> None:
        """Background position monitoring loop."""
        poll_seconds = self._context.config.get("poll_seconds", 60)

        while True:
            try:
                await self._check_positions()
                await asyncio.sleep(poll_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(poll_seconds)

    async def _check_positions(self) -> None:
        """Check and update positions."""
        # This would integrate with the actual trading daemon
        # For now, emit a heartbeat event
        event_bus = self._context.services.get("event_bus")
        if event_bus:
            await event_bus.emit(
                "trading.heartbeat",
                {"timestamp": datetime.now(timezone.utc).isoformat()}
            )


# =============================================================================
# Provider Components
# =============================================================================

class PriceFeedProvider(Provider):
    """Provides token price data from multiple sources."""

    async def provide(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get price for a token.

        Query params:
            token: Token address or symbol
            chain: Chain name (default: solana)
        """
        token = query.get("token")
        if not token:
            raise ValueError("token is required")

        # Try to import and use existing price modules
        try:
            from core import birdeye
            price_data = birdeye.get_token_price(token)
            if price_data:
                return {
                    "token": token,
                    "price_usd": price_data.get("value", 0),
                    "source": "birdeye",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.debug(f"BirdEye failed: {e}")

        try:
            from core import dexscreener
            price_data = dexscreener.get_token_price(token)
            if price_data:
                return {
                    "token": token,
                    "price_usd": price_data.get("priceUsd", 0),
                    "source": "dexscreener",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.debug(f"DexScreener failed: {e}")

        # Fallback - return zero price
        return {
            "token": token,
            "price_usd": 0,
            "source": "none",
            "error": "No price source available",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class PositionStatusProvider(Provider):
    """Provides current position status."""

    async def provide(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get position status.

        Query params:
            position_id: Optional specific position ID
            include_pnl: Whether to calculate PnL (default: True)
        """
        try:
            from core.risk_manager import get_risk_manager
            rm = get_risk_manager()
            positions = rm.get_positions() if hasattr(rm, 'get_positions') else []

            return {
                "positions": positions,
                "count": len(positions),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {
                "positions": [],
                "count": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


class WalletBalanceProvider(Provider):
    """Provides wallet balance information."""

    async def provide(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get wallet balance.

        Query params:
            wallet: Wallet address (uses default if not provided)
            include_tokens: Whether to include token balances
        """
        try:
            from core import config
            cfg = config.load_config()
            wallet = query.get("wallet") or cfg.get("wallet", {}).get("address")

            if not wallet:
                return {
                    "error": "No wallet configured",
                    "sol_balance": 0,
                    "tokens": [],
                }

            # Would call RPC to get balance
            # For now return placeholder
            return {
                "wallet": wallet,
                "sol_balance": 0,
                "tokens": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "error": str(e),
                "sol_balance": 0,
                "tokens": [],
            }


# =============================================================================
# Action Components
# =============================================================================

class ExecuteSwapAction(Action):
    """Executes a token swap via Jupiter."""

    def __init__(self, name: str, services: Dict[str, Any], paper_mode: bool = True):
        super().__init__(name, services)
        self._paper_mode = paper_mode

    @property
    def requires_confirmation(self) -> bool:
        return not self._paper_mode

    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a swap.

        Params:
            input_mint: Input token address
            output_mint: Output token address
            amount: Amount to swap (in smallest units)
            slippage: Slippage tolerance (default: 0.01)
        """
        input_mint = params.get("input_mint")
        output_mint = params.get("output_mint")
        amount = params.get("amount")
        slippage = params.get("slippage", 0.01)

        if not all([input_mint, output_mint, amount]):
            raise ValueError("input_mint, output_mint, and amount are required")

        if self._paper_mode:
            # Paper trading - simulate the swap
            return {
                "success": True,
                "paper_mode": True,
                "input_mint": input_mint,
                "output_mint": output_mint,
                "amount": amount,
                "slippage": slippage,
                "simulated": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Real trading - use Jupiter
        try:
            from core.jupiter import Jupiter
            jupiter = Jupiter()
            result = await jupiter.swap(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=int(slippage * 10000),
            )
            return {
                "success": True,
                "paper_mode": False,
                **result,
            }
        except Exception as e:
            logger.error(f"Swap failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }


class CreateExitIntentAction(Action):
    """Creates an exit intent for a position."""

    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create exit intent.

        Params:
            position_id: Position to create intent for
            exit_type: Type of exit (stop_loss, take_profit, trailing)
            trigger_price: Price to trigger exit
        """
        position_id = params.get("position_id")
        exit_type = params.get("exit_type", "stop_loss")
        trigger_price = params.get("trigger_price")

        if not position_id:
            raise ValueError("position_id is required")

        try:
            from core.exit_intents import create_exit_intent
            intent = create_exit_intent(
                position_id=position_id,
                exit_type=exit_type,
                trigger_price=trigger_price,
            )
            return {
                "success": True,
                "intent_id": intent.get("id"),
                "position_id": position_id,
                "exit_type": exit_type,
            }
        except ImportError:
            return {
                "success": False,
                "error": "exit_intents module not available",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


# =============================================================================
# Evaluator Components
# =============================================================================

class RiskCheckEvaluator(Evaluator):
    """Evaluates risk for a proposed trade."""

    async def evaluate(self, context: Dict[str, Any]) -> EvaluationResult:
        """
        Evaluate risk.

        Context params:
            trade: Proposed trade details
            portfolio: Current portfolio state
            max_position_pct: Maximum position size as percentage
        """
        trade = context.get("trade", {})
        max_position_pct = context.get("max_position_pct", 0.1)

        amount = trade.get("amount", 0)
        portfolio_value = context.get("portfolio_value", 0)

        if portfolio_value <= 0:
            return EvaluationResult(
                decision=False,
                confidence=1.0,
                reasoning="Cannot evaluate risk without portfolio value",
            )

        position_pct = amount / portfolio_value if portfolio_value > 0 else 1.0

        if position_pct > max_position_pct:
            return EvaluationResult(
                decision=False,
                confidence=0.95,
                reasoning=f"Position size {position_pct:.1%} exceeds max {max_position_pct:.1%}",
                metadata={"position_pct": position_pct, "max_pct": max_position_pct},
            )

        return EvaluationResult(
            decision=True,
            confidence=0.9,
            reasoning=f"Risk acceptable: {position_pct:.1%} of portfolio",
            metadata={"position_pct": position_pct},
        )


class OpportunityScoreEvaluator(Evaluator):
    """Evaluates trading opportunity quality."""

    async def evaluate(self, context: Dict[str, Any]) -> EvaluationResult:
        """
        Score a trading opportunity.

        Context params:
            token: Token address
            price_change_24h: 24h price change
            volume_24h: 24h volume
            liquidity: Available liquidity
        """
        price_change = context.get("price_change_24h", 0)
        volume = context.get("volume_24h", 0)
        liquidity = context.get("liquidity", 0)

        # Simple scoring logic
        score = 0.5  # Base score

        # Volume factor
        if volume > 1_000_000:
            score += 0.2
        elif volume > 100_000:
            score += 0.1

        # Liquidity factor
        if liquidity > 500_000:
            score += 0.15
        elif liquidity > 100_000:
            score += 0.1

        # Momentum factor (moderate moves are better)
        if 5 < abs(price_change) < 20:
            score += 0.15
        elif abs(price_change) > 50:
            score -= 0.2  # Too volatile

        decision = score >= 0.6

        return EvaluationResult(
            decision=decision,
            confidence=min(score, 1.0),
            reasoning=f"Opportunity score: {score:.2f}",
            metadata={
                "score": score,
                "price_change": price_change,
                "volume": volume,
                "liquidity": liquidity,
            },
        )
