"""
Treasury Trading Bot.

Autonomous trading bot for treasury management:
- DCA strategies
- Mean reversion trading
- Arbitrage detection
- Risk controls with circuit breakers
- All trades through Bags.fm for partner fees
- Weekly profit distribution to staking pool
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("jarvis.trading.treasury_bot")


# =============================================================================
# Configuration
# =============================================================================


class TradingStrategy(Enum):
    """Available trading strategies."""
    DCA = "dca"
    MEAN_REVERSION = "mean_reversion"
    ARBITRAGE = "arbitrage"


@dataclass
class RiskLimits:
    """Risk management limits."""
    max_position_pct: float = 0.10  # Max 10% of treasury per position
    max_daily_loss_pct: float = 0.05  # Max 5% daily loss
    max_drawdown_pct: float = 0.15  # Stop trading at 15% drawdown
    min_reserve_pct: float = 0.30  # Always keep 30% in reserve
    max_trade_size_sol: float = 100.0  # Max single trade size

    def validate_trade(
        self,
        trade_size_sol: float,
        treasury_balance_sol: float,
        daily_pnl_sol: float,
        total_drawdown_pct: float,
    ) -> tuple[bool, str]:
        """Validate if trade is within risk limits."""
        # Check single trade size
        if trade_size_sol > self.max_trade_size_sol:
            return False, f"Trade size {trade_size_sol} exceeds max {self.max_trade_size_sol}"

        # Check position size relative to treasury
        position_pct = trade_size_sol / max(treasury_balance_sol, 1)
        if position_pct > self.max_position_pct:
            return False, f"Position {position_pct:.1%} exceeds max {self.max_position_pct:.1%}"

        # Check daily loss
        daily_loss_pct = abs(min(0, daily_pnl_sol)) / max(treasury_balance_sol, 1)
        if daily_loss_pct >= self.max_daily_loss_pct:
            return False, f"Daily loss {daily_loss_pct:.1%} at limit"

        # Check drawdown
        if total_drawdown_pct >= self.max_drawdown_pct:
            return False, f"Drawdown {total_drawdown_pct:.1%} at limit - trading stopped"

        # Check reserve
        available_pct = 1 - self.min_reserve_pct
        if trade_size_sol > treasury_balance_sol * available_pct:
            return False, "Trade would breach reserve requirement"

        return True, "OK"


@dataclass
class TradingConfig:
    """Trading bot configuration."""
    # Tokens
    sol_mint: str = "So11111111111111111111111111111111111111112"
    usdc_mint: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    kr8tiv_mint: str = os.getenv("KR8TIV_MINT", "")

    # DCA settings
    dca_interval_hours: int = 4
    dca_amount_sol: float = 1.0

    # Mean reversion settings
    mean_reversion_window: int = 24  # hours
    mean_reversion_threshold: float = 0.05  # 5% deviation from mean

    # General settings
    slippage_bps: int = 50
    risk_limits: RiskLimits = field(default_factory=RiskLimits)


# =============================================================================
# Position Tracker
# =============================================================================


@dataclass
class Position:
    """A trading position."""
    token_mint: str
    entry_price: float
    amount: float
    opened_at: datetime
    strategy: TradingStrategy
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None


class PositionTracker:
    """Tracks open positions and P&L."""

    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._closed_trades: List[Dict] = []
        self._daily_pnl: Dict[str, float] = {}  # date -> pnl
        self._peak_balance: float = 0.0
        self._current_balance: float = 0.0

    def open_position(self, position: Position):
        """Record a new position."""
        key = f"{position.token_mint}_{position.strategy.value}"
        self._positions[key] = position
        logger.info(
            f"Opened {position.strategy.value} position: "
            f"{position.amount} @ {position.entry_price}"
        )

    def close_position(
        self,
        token_mint: str,
        strategy: TradingStrategy,
        exit_price: float,
        amount: float,
    ) -> float:
        """Close a position and calculate P&L."""
        key = f"{token_mint}_{strategy.value}"
        position = self._positions.get(key)

        if not position:
            return 0.0

        # Calculate P&L
        pnl = (exit_price - position.entry_price) * amount

        # Record closed trade
        self._closed_trades.append({
            "token_mint": token_mint,
            "strategy": strategy.value,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "amount": amount,
            "pnl": pnl,
            "opened_at": position.opened_at.isoformat(),
            "closed_at": datetime.now(timezone.utc).isoformat(),
        })

        # Update daily P&L
        today = datetime.now(timezone.utc).date().isoformat()
        self._daily_pnl[today] = self._daily_pnl.get(today, 0) + pnl

        # Remove position
        if amount >= position.amount:
            del self._positions[key]
        else:
            position.amount -= amount

        logger.info(
            f"Closed {strategy.value} position: "
            f"{amount} @ {exit_price} | P&L: {pnl:.4f} SOL"
        )

        return pnl

    def get_daily_pnl(self) -> float:
        """Get today's P&L."""
        today = datetime.now(timezone.utc).date().isoformat()
        return self._daily_pnl.get(today, 0)

    def get_drawdown_pct(self) -> float:
        """Calculate current drawdown percentage."""
        if self._peak_balance <= 0:
            return 0.0

        drawdown = (self._peak_balance - self._current_balance) / self._peak_balance
        return max(0, drawdown)

    def update_balance(self, balance: float):
        """Update balance tracking."""
        self._current_balance = balance
        self._peak_balance = max(self._peak_balance, balance)

    def get_stats(self) -> Dict[str, Any]:
        """Get position and P&L statistics."""
        total_pnl = sum(self._daily_pnl.values())
        winning_trades = sum(1 for t in self._closed_trades if t["pnl"] > 0)
        total_trades = len(self._closed_trades)

        return {
            "open_positions": len(self._positions),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": winning_trades / max(1, total_trades),
            "total_pnl_sol": total_pnl,
            "daily_pnl_sol": self.get_daily_pnl(),
            "drawdown_pct": self.get_drawdown_pct(),
            "peak_balance_sol": self._peak_balance,
            "current_balance_sol": self._current_balance,
        }


# =============================================================================
# Trading Strategies
# =============================================================================


class DCAStrategy:
    """Dollar Cost Averaging strategy."""

    def __init__(self, config: TradingConfig):
        self.config = config
        self._last_buy: Dict[str, datetime] = {}

    async def should_execute(self, token_mint: str) -> bool:
        """Check if DCA should execute."""
        last = self._last_buy.get(token_mint)
        if not last:
            return True

        interval = timedelta(hours=self.config.dca_interval_hours)
        return datetime.now(timezone.utc) - last >= interval

    async def get_trade_params(
        self,
        token_mint: str,
        treasury_balance: float,
    ) -> Optional[Dict]:
        """Get DCA trade parameters."""
        if not await self.should_execute(token_mint):
            return None

        amount = min(
            self.config.dca_amount_sol,
            treasury_balance * (1 - self.config.risk_limits.min_reserve_pct) * 0.1,
        )

        if amount < 0.01:  # Minimum trade size
            return None

        return {
            "input_mint": self.config.sol_mint,
            "output_mint": token_mint,
            "amount_sol": amount,
            "strategy": TradingStrategy.DCA,
        }

    def record_execution(self, token_mint: str):
        """Record DCA execution."""
        self._last_buy[token_mint] = datetime.now(timezone.utc)


class MeanReversionStrategy:
    """Mean reversion strategy for KR8TIV."""

    def __init__(self, config: TradingConfig):
        self.config = config
        self._price_history: List[float] = []
        self._max_history = config.mean_reversion_window * 4  # 4 samples/hour

    def add_price(self, price: float):
        """Add price to history."""
        self._price_history.append(price)
        if len(self._price_history) > self._max_history:
            self._price_history = self._price_history[-self._max_history:]

    def get_mean_price(self) -> float:
        """Calculate mean price."""
        if not self._price_history:
            return 0.0
        return sum(self._price_history) / len(self._price_history)

    async def should_buy(self, current_price: float) -> tuple[bool, float]:
        """Check if we should buy (price below mean)."""
        mean = self.get_mean_price()
        if mean == 0:
            return False, 0

        deviation = (current_price - mean) / mean

        # Buy if price is below mean by threshold
        if deviation < -self.config.mean_reversion_threshold:
            return True, abs(deviation)

        return False, deviation

    async def should_sell(self, current_price: float) -> tuple[bool, float]:
        """Check if we should sell (price above mean)."""
        mean = self.get_mean_price()
        if mean == 0:
            return False, 0

        deviation = (current_price - mean) / mean

        # Sell if price is above mean by threshold
        if deviation > self.config.mean_reversion_threshold:
            return True, deviation

        return False, deviation


# =============================================================================
# Treasury Trading Bot
# =============================================================================


class TreasuryTradingBot:
    """
    Autonomous treasury trading bot.

    Features:
    - Multiple trading strategies
    - Risk management with circuit breakers
    - All trades through Bags.fm
    - Weekly profit distribution
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(
        self,
        config: TradingConfig = None,
        trade_executor: Callable = None,
        balance_fetcher: Callable = None,
        price_fetcher: Callable = None,
    ):
        self.config = config or TradingConfig()
        self._executor = trade_executor
        self._get_balance = balance_fetcher
        self._get_price = price_fetcher

        self.positions = PositionTracker()
        self.dca = DCAStrategy(self.config)
        self.mean_reversion = MeanReversionStrategy(self.config)

        self._running = False
        self._paused = False
        self._main_loop_task: Optional[asyncio.Task] = None

        self._stats = {
            "trades_executed": 0,
            "trades_rejected": 0,
            "total_volume_sol": 0.0,
            "fees_earned_sol": 0.0,
            "last_distribution": None,
        }

    async def start(self):
        """Start the trading bot."""
        if self._running:
            logger.warning("Bot already running")
            return

        self._running = True
        self._main_loop_task = asyncio.create_task(self._main_loop())
        logger.info("Treasury trading bot started")

    async def stop(self):
        """Stop the trading bot."""
        self._running = False
        if self._main_loop_task:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
        logger.info("Treasury trading bot stopped")

    def pause(self):
        """Pause trading (keep running but don't execute trades)."""
        self._paused = True
        logger.info("Trading paused")

    def resume(self):
        """Resume trading."""
        self._paused = False
        logger.info("Trading resumed")

    async def _main_loop(self):
        """Main trading loop."""
        while self._running:
            try:
                if not self._paused:
                    await self._execute_cycle()

                # Run every 15 minutes
                await asyncio.sleep(900)

            except Exception as e:
                logger.error(f"Trading cycle error: {e}")
                await asyncio.sleep(60)

    async def _execute_cycle(self):
        """Execute one trading cycle."""
        # Get treasury balance
        balance = await self._get_treasury_balance()
        self.positions.update_balance(balance)

        # Check if we should be trading
        if not self._can_trade(balance):
            return

        # Update price data
        await self._update_prices()

        # Execute strategies
        await self._execute_dca(balance)
        await self._execute_mean_reversion(balance)
        await self._check_profit_distribution()

    async def _get_treasury_balance(self) -> float:
        """Get current treasury balance in SOL."""
        if self._get_balance:
            return await self._get_balance()

        # Mock balance for development
        return 100.0

    async def _update_prices(self):
        """Update price data for strategies."""
        if self._get_price:
            kr8tiv_price = await self._get_price(self.config.kr8tiv_mint)
            if kr8tiv_price:
                self.mean_reversion.add_price(kr8tiv_price)

    def _can_trade(self, balance: float) -> bool:
        """Check if trading is allowed based on risk limits."""
        # Check drawdown
        drawdown = self.positions.get_drawdown_pct()
        if drawdown >= self.config.risk_limits.max_drawdown_pct:
            logger.warning(
                f"Trading stopped: drawdown {drawdown:.1%} >= "
                f"{self.config.risk_limits.max_drawdown_pct:.1%}"
            )
            return False

        # Check daily loss
        daily_pnl = self.positions.get_daily_pnl()
        max_loss = balance * self.config.risk_limits.max_daily_loss_pct
        if daily_pnl < -max_loss:
            logger.warning(f"Trading stopped: daily loss limit reached")
            return False

        return True

    async def _execute_dca(self, balance: float):
        """Execute DCA strategy."""
        # DCA into USDC
        trade = await self.dca.get_trade_params(self.config.usdc_mint, balance)
        if trade:
            await self._execute_trade(trade, balance)
            self.dca.record_execution(self.config.usdc_mint)

        # DCA into KR8TIV if configured
        if self.config.kr8tiv_mint:
            trade = await self.dca.get_trade_params(self.config.kr8tiv_mint, balance)
            if trade:
                await self._execute_trade(trade, balance)
                self.dca.record_execution(self.config.kr8tiv_mint)

    async def _execute_mean_reversion(self, balance: float):
        """Execute mean reversion strategy."""
        if not self.config.kr8tiv_mint:
            return

        current_price = await self._get_price(self.config.kr8tiv_mint) if self._get_price else None
        if not current_price:
            return

        should_buy, deviation = await self.mean_reversion.should_buy(current_price)
        if should_buy:
            # Calculate trade size based on deviation
            base_size = self.config.dca_amount_sol * 2
            size = base_size * min(2, 1 + deviation)

            trade = {
                "input_mint": self.config.sol_mint,
                "output_mint": self.config.kr8tiv_mint,
                "amount_sol": size,
                "strategy": TradingStrategy.MEAN_REVERSION,
            }

            await self._execute_trade(trade, balance)

        should_sell, deviation = await self.mean_reversion.should_sell(current_price)
        if should_sell:
            # Check if we have a position to sell
            # Would implement position closing here
            pass

    async def _execute_trade(self, trade: Dict, balance: float):
        """Execute a trade with risk checks."""
        amount_sol = trade["amount_sol"]

        # Validate against risk limits
        allowed, reason = self.config.risk_limits.validate_trade(
            trade_size_sol=amount_sol,
            treasury_balance_sol=balance,
            daily_pnl_sol=self.positions.get_daily_pnl(),
            total_drawdown_pct=self.positions.get_drawdown_pct(),
        )

        if not allowed:
            logger.warning(f"Trade rejected: {reason}")
            self._stats["trades_rejected"] += 1
            return

        # Execute through Bags adapter
        try:
            if self._executor:
                signature, output_amount = await self._executor(
                    input_mint=trade["input_mint"],
                    output_mint=trade["output_mint"],
                    amount=int(amount_sol * self.LAMPORTS_PER_SOL),
                    slippage=self.config.slippage_bps / 10000,
                )

                # Record position
                self.positions.open_position(Position(
                    token_mint=trade["output_mint"],
                    entry_price=amount_sol * self.LAMPORTS_PER_SOL / max(1, output_amount),
                    amount=output_amount / self.LAMPORTS_PER_SOL,
                    opened_at=datetime.now(timezone.utc),
                    strategy=trade["strategy"],
                ))

                # Update stats
                self._stats["trades_executed"] += 1
                self._stats["total_volume_sol"] += amount_sol
                self._stats["fees_earned_sol"] += amount_sol * 0.0025  # Partner fee

                logger.info(
                    f"Trade executed: {trade['strategy'].value} | "
                    f"{amount_sol:.4f} SOL -> {output_amount / self.LAMPORTS_PER_SOL:.4f} tokens"
                )

            else:
                logger.info(f"[MOCK] Would execute trade: {trade}")
                self._stats["trades_executed"] += 1

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            self._stats["trades_rejected"] += 1

    async def _check_profit_distribution(self):
        """Check if it's time for weekly profit distribution."""
        last_dist = self._stats.get("last_distribution")

        if last_dist:
            last_dist_date = datetime.fromisoformat(last_dist)
            if datetime.now(timezone.utc) - last_dist_date < timedelta(days=7):
                return

        await self._distribute_profits()

    async def _distribute_profits(self):
        """Distribute profits to staking pool."""
        stats = self.positions.get_stats()
        profit = stats["total_pnl_sol"]

        if profit <= 0:
            logger.info("No profits to distribute")
            return

        # Keep 30% in treasury
        distributable = profit * 0.70

        # Distribution: 60% staking, 25% ops, 15% dev
        to_staking = distributable * 0.60
        to_operations = distributable * 0.25
        to_development = distributable * 0.15

        logger.info(
            f"Profit distribution: "
            f"Staking: {to_staking:.4f} SOL, "
            f"Ops: {to_operations:.4f} SOL, "
            f"Dev: {to_development:.4f} SOL"
        )

        # In production, would execute actual transfers
        self._stats["last_distribution"] = datetime.now(timezone.utc).isoformat()

    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        position_stats = self.positions.get_stats()

        return {
            **self._stats,
            **position_stats,
            "running": self._running,
            "paused": self._paused,
            "strategies_active": {
                "dca": True,
                "mean_reversion": bool(self.config.kr8tiv_mint),
                "arbitrage": False,  # Not implemented yet
            },
        }


# =============================================================================
# Singleton
# =============================================================================

_bot: Optional[TreasuryTradingBot] = None


def get_treasury_bot() -> TreasuryTradingBot:
    """Get singleton treasury bot."""
    global _bot
    if _bot is None:
        _bot = TreasuryTradingBot()
    return _bot


# =============================================================================
# FastAPI Routes
# =============================================================================


def create_treasury_bot_router():
    """Create FastAPI router for treasury bot."""
    try:
        from fastapi import APIRouter, HTTPException
    except ImportError:
        return None

    router = APIRouter(prefix="/api/treasury/bot", tags=["Treasury Bot"])
    bot = get_treasury_bot()

    @router.get("/status")
    async def get_status():
        """Get bot status."""
        return bot.get_stats()

    @router.post("/start")
    async def start_bot():
        """Start the trading bot."""
        await bot.start()
        return {"status": "started"}

    @router.post("/stop")
    async def stop_bot():
        """Stop the trading bot."""
        await bot.stop()
        return {"status": "stopped"}

    @router.post("/pause")
    async def pause_bot():
        """Pause trading."""
        bot.pause()
        return {"status": "paused"}

    @router.post("/resume")
    async def resume_bot():
        """Resume trading."""
        bot.resume()
        return {"status": "resumed"}

    @router.get("/positions")
    async def get_positions():
        """Get open positions."""
        return {
            "positions": list(bot.positions._positions.values()),
            "stats": bot.positions.get_stats(),
        }

    return router
