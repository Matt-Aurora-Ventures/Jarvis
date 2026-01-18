"""
Paper Trading Simulator for Jarvis Treasury
Provides realistic simulation of trading without real funds

Features:
- Simulated wallet with configurable starting balance
- Real market prices from Jupiter/DexScreener
- Simulated slippage and fees
- Full position tracking with P&L
- Performance analytics and reporting
- Separate state files from live trading
"""

import os
import json
import random
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import uuid

from .jupiter import JupiterClient, SwapQuote, SwapResult, TokenInfo
from .trading import (
    TradingEngine, Position, TradeDirection, TradeStatus,
    RiskLevel, TradeReport
)

logger = logging.getLogger(__name__)


@dataclass
class PaperBalance:
    """Tracks a paper trading balance for a token."""
    mint: str
    symbol: str
    balance: float
    avg_cost_basis: float = 0.0  # Average cost per token in USD

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mint': self.mint,
            'symbol': self.symbol,
            'balance': self.balance,
            'avg_cost_basis': self.avg_cost_basis
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PaperBalance':
        return cls(
            mint=data['mint'],
            symbol=data['symbol'],
            balance=data['balance'],
            avg_cost_basis=data.get('avg_cost_basis', 0.0)
        )


@dataclass
class PaperTrade:
    """Record of a paper trade execution."""
    id: str
    timestamp: str
    direction: str  # BUY or SELL
    input_mint: str
    input_symbol: str
    input_amount: float
    output_mint: str
    output_symbol: str
    output_amount: float
    price_usd: float
    slippage_pct: float
    fees_usd: float
    signature: str  # Simulated signature

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'direction': self.direction,
            'input_mint': self.input_mint,
            'input_symbol': self.input_symbol,
            'input_amount': self.input_amount,
            'output_mint': self.output_mint,
            'output_symbol': self.output_symbol,
            'output_amount': self.output_amount,
            'price_usd': self.price_usd,
            'slippage_pct': self.slippage_pct,
            'fees_usd': self.fees_usd,
            'signature': self.signature
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PaperTrade':
        return cls(**data)


@dataclass
class PerformanceMetrics:
    """Paper trading performance metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_usd: float = 0.0
    total_fees_paid: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    profit_factor: float = 0.0

    # Time-based metrics
    start_balance_usd: float = 0.0
    current_balance_usd: float = 0.0
    peak_balance_usd: float = 0.0
    started_at: str = ""

    def calculate_derived_metrics(self):
        """Calculate derived metrics from base data."""
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100

        if self.start_balance_usd > 0:
            total_return = ((self.current_balance_usd - self.start_balance_usd)
                          / self.start_balance_usd) * 100
        else:
            total_return = 0.0

        if self.peak_balance_usd > 0:
            self.max_drawdown_pct = ((self.peak_balance_usd - self.current_balance_usd)
                                    / self.peak_balance_usd) * 100

        # Profit factor = gross profits / gross losses
        if self.avg_loss_usd != 0 and self.losing_trades > 0:
            gross_losses = abs(self.avg_loss_usd * self.losing_trades)
            gross_profits = self.avg_win_usd * self.winning_trades if self.winning_trades > 0 else 0
            self.profit_factor = gross_profits / gross_losses if gross_losses > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl_usd': self.total_pnl_usd,
            'total_fees_paid': self.total_fees_paid,
            'best_trade_pnl': self.best_trade_pnl,
            'worst_trade_pnl': self.worst_trade_pnl,
            'max_drawdown_pct': self.max_drawdown_pct,
            'sharpe_ratio': self.sharpe_ratio,
            'win_rate': self.win_rate,
            'avg_win_usd': self.avg_win_usd,
            'avg_loss_usd': self.avg_loss_usd,
            'profit_factor': self.profit_factor,
            'start_balance_usd': self.start_balance_usd,
            'current_balance_usd': self.current_balance_usd,
            'peak_balance_usd': self.peak_balance_usd,
            'started_at': self.started_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PerformanceMetrics':
        return cls(**data)

    def to_report(self) -> str:
        """Generate a formatted performance report."""
        pnl_emoji = "" if self.total_pnl_usd >= 0 else ""
        total_return = 0.0
        if self.start_balance_usd > 0:
            total_return = ((self.current_balance_usd - self.start_balance_usd)
                          / self.start_balance_usd) * 100

        return f"""
PAPER TRADING PERFORMANCE REPORT
{'='*40}

ACCOUNT
  Starting Balance: ${self.start_balance_usd:,.2f}
  Current Balance:  ${self.current_balance_usd:,.2f}
  Peak Balance:     ${self.peak_balance_usd:,.2f}
  Total Return:     {total_return:+.2f}%

TRADING STATS
  Total Trades:     {self.total_trades}
  Win Rate:         {self.win_rate:.1f}%
  Winning Trades:   {self.winning_trades}
  Losing Trades:    {self.losing_trades}

P&L BREAKDOWN
  {pnl_emoji} Total P&L:      ${self.total_pnl_usd:+,.2f}
  Best Trade:       ${self.best_trade_pnl:+,.2f}
  Worst Trade:      ${self.worst_trade_pnl:+,.2f}
  Avg Win:          ${self.avg_win_usd:+,.2f}
  Avg Loss:         ${self.avg_loss_usd:,.2f}
  Fees Paid:        ${self.total_fees_paid:.2f}

RISK METRICS
  Max Drawdown:     {self.max_drawdown_pct:.1f}%
  Profit Factor:    {self.profit_factor:.2f}
  Sharpe Ratio:     {self.sharpe_ratio:.2f}

Session Started: {self.started_at}
{'='*40}
"""


class PaperWallet:
    """
    Simulated wallet for paper trading.

    Tracks SOL and token balances without touching real funds.
    Uses real market prices for accurate simulation.
    """

    SOL_MINT = "So11111111111111111111111111111111111111112"

    def __init__(
        self,
        initial_sol: float = 100.0,
        jupiter_client: JupiterClient = None
    ):
        """
        Initialize paper wallet.

        Args:
            initial_sol: Starting SOL balance
            jupiter_client: JupiterClient for price lookups (uses real prices)
        """
        self.jupiter = jupiter_client or JupiterClient()
        self.balances: Dict[str, PaperBalance] = {}

        # Initialize with SOL balance
        self.balances[self.SOL_MINT] = PaperBalance(
            mint=self.SOL_MINT,
            symbol="SOL",
            balance=initial_sol,
            avg_cost_basis=0.0  # We don't track cost basis for initial SOL
        )

        self.initial_sol = initial_sol

    def get_balance(self, mint: str) -> float:
        """Get balance for a specific token."""
        if mint in self.balances:
            return self.balances[mint].balance
        return 0.0

    def get_sol_balance(self) -> float:
        """Get SOL balance."""
        return self.get_balance(self.SOL_MINT)

    async def get_balance_usd(self, mint: str) -> float:
        """Get balance value in USD."""
        balance = self.get_balance(mint)
        if balance <= 0:
            return 0.0
        price = await self.jupiter.get_token_price(mint)
        return balance * price

    async def get_total_value_usd(self) -> float:
        """Get total portfolio value in USD."""
        total = 0.0
        for mint, bal in self.balances.items():
            if bal.balance > 0:
                price = await self.jupiter.get_token_price(mint)
                total += bal.balance * price
        return total

    def add_balance(self, mint: str, symbol: str, amount: float, cost_usd: float = 0.0):
        """Add to a token balance."""
        if mint in self.balances:
            existing = self.balances[mint]
            # Update average cost basis
            if cost_usd > 0 and amount > 0:
                total_cost = (existing.avg_cost_basis * existing.balance) + cost_usd
                new_balance = existing.balance + amount
                existing.avg_cost_basis = total_cost / new_balance if new_balance > 0 else 0
            existing.balance += amount
        else:
            self.balances[mint] = PaperBalance(
                mint=mint,
                symbol=symbol,
                balance=amount,
                avg_cost_basis=cost_usd / amount if amount > 0 else 0
            )

    def subtract_balance(self, mint: str, amount: float) -> bool:
        """Subtract from a token balance. Returns False if insufficient."""
        if mint not in self.balances:
            return False
        if self.balances[mint].balance < amount:
            return False
        self.balances[mint].balance -= amount
        return True

    def get_all_balances(self) -> Dict[str, PaperBalance]:
        """Get all non-zero balances."""
        return {m: b for m, b in self.balances.items() if b.balance > 0}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'balances': {m: b.to_dict() for m, b in self.balances.items()},
            'initial_sol': self.initial_sol
        }

    @classmethod
    def from_dict(cls, data: Dict, jupiter_client: JupiterClient = None) -> 'PaperWallet':
        wallet = cls(initial_sol=data.get('initial_sol', 100.0), jupiter_client=jupiter_client)
        wallet.balances = {}
        for mint, bal_data in data.get('balances', {}).items():
            wallet.balances[mint] = PaperBalance.from_dict(bal_data)
        return wallet


class PaperJupiterClient:
    """
    Paper trading wrapper for JupiterClient.

    Uses real prices from Jupiter/DexScreener but simulates
    swap execution with realistic slippage and fees.
    """

    # Simulation parameters
    BASE_SLIPPAGE_PCT = 0.3   # 0.3% base slippage
    SLIPPAGE_VARIANCE = 0.2   # +/- 0.2% random variance
    BASE_FEE_PCT = 0.25       # 0.25% fee (Jupiter's typical fee)
    PRIORITY_FEE_SOL = 0.0001 # ~0.0001 SOL priority fee equivalent

    def __init__(self, real_client: JupiterClient = None, paper_wallet: PaperWallet = None):
        """
        Initialize paper Jupiter client.

        Args:
            real_client: Real JupiterClient for price lookups
            paper_wallet: PaperWallet for balance tracking
        """
        self.real_client = real_client or JupiterClient()
        self.wallet = paper_wallet

    async def get_quote(self, *args, **kwargs) -> Optional[SwapQuote]:
        """Get a real quote from Jupiter (for accurate pricing)."""
        return await self.real_client.get_quote(*args, **kwargs)

    async def get_token_price(self, mint: str) -> float:
        """Get real token price."""
        return await self.real_client.get_token_price(mint)

    async def get_token_info(self, mint: str) -> Optional[TokenInfo]:
        """Get real token info."""
        return await self.real_client.get_token_info(mint)

    def _simulate_slippage(self, amount: float) -> Tuple[float, float]:
        """
        Simulate realistic slippage.

        Returns:
            Tuple of (slippage_adjusted_amount, slippage_pct)
        """
        # Random slippage within variance
        slippage = self.BASE_SLIPPAGE_PCT + random.uniform(
            -self.SLIPPAGE_VARIANCE,
            self.SLIPPAGE_VARIANCE
        )
        # Slippage is always against the trader
        slippage = abs(slippage)
        adjusted = amount * (1 - slippage / 100)
        return adjusted, slippage

    def _calculate_fees(self, amount_usd: float) -> float:
        """Calculate trading fees in USD."""
        return amount_usd * (self.BASE_FEE_PCT / 100)

    async def execute_swap(
        self,
        quote: SwapQuote,
        wallet = None,  # Ignored, uses paper wallet
        simulate_first: bool = True,
        priority_fee: int = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> SwapResult:
        """
        Simulate swap execution.

        Uses real quote prices but simulates the execution
        with realistic slippage and fees.
        """
        if not self.wallet:
            return SwapResult(
                success=False,
                error="No paper wallet configured"
            )

        try:
            # Get token info
            input_info = await self.real_client.get_token_info(quote.input_mint)
            output_info = await self.real_client.get_token_info(quote.output_mint)

            input_symbol = input_info.symbol if input_info else "UNKNOWN"
            output_symbol = output_info.symbol if output_info else "UNKNOWN"

            # Check if we have enough balance
            input_balance = self.wallet.get_balance(quote.input_mint)
            if input_balance < quote.input_amount_ui:
                return SwapResult(
                    success=False,
                    error=f"Insufficient {input_symbol} balance: have {input_balance:.6f}, need {quote.input_amount_ui:.6f}"
                )

            # Simulate slippage
            output_amount, slippage_pct = self._simulate_slippage(quote.output_amount_ui)

            # Calculate fees
            input_price = await self.real_client.get_token_price(quote.input_mint)
            input_value_usd = quote.input_amount_ui * input_price
            fees_usd = self._calculate_fees(input_value_usd)

            # Deduct SOL for priority fee (if not swapping SOL)
            sol_mint = "So11111111111111111111111111111111111111112"
            if quote.input_mint != sol_mint:
                sol_balance = self.wallet.get_balance(sol_mint)
                if sol_balance < self.PRIORITY_FEE_SOL:
                    return SwapResult(
                        success=False,
                        error=f"Insufficient SOL for fees: have {sol_balance:.6f}, need {self.PRIORITY_FEE_SOL:.6f}"
                    )
                self.wallet.subtract_balance(sol_mint, self.PRIORITY_FEE_SOL)

            # Execute the paper trade
            self.wallet.subtract_balance(quote.input_mint, quote.input_amount_ui)

            # Get output price for cost basis tracking
            output_price = await self.real_client.get_token_price(quote.output_mint)
            cost_usd = output_amount * output_price

            self.wallet.add_balance(
                quote.output_mint,
                output_symbol,
                output_amount,
                cost_usd=cost_usd
            )

            # Generate fake signature
            fake_sig = f"PAPER_{uuid.uuid4().hex[:32]}"

            return SwapResult(
                success=True,
                signature=fake_sig,
                input_amount=quote.input_amount_ui,
                output_amount=output_amount,
                input_symbol=input_symbol,
                output_symbol=output_symbol,
                price_impact=quote.price_impact_pct,
                fees_usd=fees_usd,
                timestamp=datetime.utcnow().isoformat()
            )

        except Exception as e:
            logger.error(f"Paper swap failed: {e}")
            return SwapResult(
                success=False,
                error=str(e)
            )


class PaperTradingEngine:
    """
    Paper trading engine that wraps the real TradingEngine.

    Provides the same interface but operates on simulated funds.
    All business logic (risk management, TP/SL, position limits) is preserved.
    """

    # State files - separate from live trading
    STATE_DIR = Path(__file__).parent / '.paper_trading'
    POSITIONS_FILE = STATE_DIR / 'positions.json'
    HISTORY_FILE = STATE_DIR / 'trade_history.json'
    WALLET_FILE = STATE_DIR / 'wallet.json'
    TRADES_FILE = STATE_DIR / 'trades.json'
    METRICS_FILE = STATE_DIR / 'metrics.json'

    def __init__(
        self,
        initial_sol: float = 100.0,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        max_positions: int = 50,
        enable_real_prices: bool = True
    ):
        """
        Initialize paper trading engine.

        Args:
            initial_sol: Starting SOL balance
            risk_level: Risk level for position sizing
            max_positions: Maximum concurrent positions
            enable_real_prices: Use real market prices (recommended)
        """
        # Ensure state directory exists
        self.STATE_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize Jupiter client for real prices
        self.real_jupiter = JupiterClient() if enable_real_prices else None

        # Initialize paper wallet
        self.paper_wallet = PaperWallet(
            initial_sol=initial_sol,
            jupiter_client=self.real_jupiter
        )

        # Initialize paper Jupiter client
        self.paper_jupiter = PaperJupiterClient(
            real_client=self.real_jupiter,
            paper_wallet=self.paper_wallet
        )

        # Position tracking
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Position] = []
        self.paper_trades: List[PaperTrade] = []

        # Configuration (matches TradingEngine)
        self.risk_level = risk_level
        self.max_positions = max_positions

        # Spending limits (same as live)
        self.MAX_TRADE_USD = 100.0
        self.MAX_DAILY_USD = 500.0
        self.MAX_POSITION_PCT = 0.20

        # Daily volume tracking
        self._daily_volume = 0.0
        self._daily_volume_date = datetime.utcnow().strftime('%Y-%m-%d')

        # Performance metrics
        self.metrics = PerformanceMetrics(
            started_at=datetime.utcnow().isoformat()
        )

        # Load existing state
        self._load_state()

        # TP/SL configuration (same as TradingEngine)
        self.TP_SL_CONFIG = TradingEngine.TP_SL_CONFIG
        self.POSITION_SIZE = TradingEngine.POSITION_SIZE

        logger.info(f"Paper trading engine initialized with {initial_sol} SOL")

    def _load_state(self):
        """Load state from disk."""
        try:
            # Load wallet
            if self.WALLET_FILE.exists():
                with open(self.WALLET_FILE) as f:
                    data = json.load(f)
                    self.paper_wallet = PaperWallet.from_dict(data, self.real_jupiter)
                    self.paper_jupiter.wallet = self.paper_wallet

            # Load positions
            if self.POSITIONS_FILE.exists():
                with open(self.POSITIONS_FILE) as f:
                    data = json.load(f)
                    for pos_data in data:
                        pos = Position.from_dict(pos_data)
                        self.positions[pos.id] = pos

            # Load history
            if self.HISTORY_FILE.exists():
                with open(self.HISTORY_FILE) as f:
                    data = json.load(f)
                    self.trade_history = [Position.from_dict(p) for p in data]

            # Load paper trades
            if self.TRADES_FILE.exists():
                with open(self.TRADES_FILE) as f:
                    data = json.load(f)
                    self.paper_trades = [PaperTrade.from_dict(t) for t in data]

            # Load metrics
            if self.METRICS_FILE.exists():
                with open(self.METRICS_FILE) as f:
                    data = json.load(f)
                    self.metrics = PerformanceMetrics.from_dict(data)

            logger.info(f"Loaded paper trading state: {len(self.positions)} positions, {len(self.trade_history)} historical trades")

        except Exception as e:
            logger.error(f"Failed to load paper trading state: {e}")

    def _save_state(self):
        """Save state to disk."""
        try:
            # Save wallet
            with open(self.WALLET_FILE, 'w') as f:
                json.dump(self.paper_wallet.to_dict(), f, indent=2)

            # Save positions
            with open(self.POSITIONS_FILE, 'w') as f:
                json.dump([p.to_dict() for p in self.positions.values()], f, indent=2)

            # Save history
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump([p.to_dict() for p in self.trade_history], f, indent=2)

            # Save paper trades
            with open(self.TRADES_FILE, 'w') as f:
                json.dump([t.to_dict() for t in self.paper_trades], f, indent=2)

            # Update and save metrics
            asyncio.create_task(self._update_metrics())

        except Exception as e:
            logger.error(f"Failed to save paper trading state: {e}")

    async def _update_metrics(self):
        """Update performance metrics."""
        try:
            self.metrics.total_trades = len(self.trade_history)
            self.metrics.current_balance_usd = await self.paper_wallet.get_total_value_usd()

            if self.metrics.start_balance_usd == 0:
                self.metrics.start_balance_usd = self.metrics.current_balance_usd

            if self.metrics.current_balance_usd > self.metrics.peak_balance_usd:
                self.metrics.peak_balance_usd = self.metrics.current_balance_usd

            # Calculate win/loss stats
            wins = [t for t in self.trade_history if t.pnl_usd > 0]
            losses = [t for t in self.trade_history if t.pnl_usd < 0]

            self.metrics.winning_trades = len(wins)
            self.metrics.losing_trades = len(losses)
            self.metrics.total_pnl_usd = sum(t.pnl_usd for t in self.trade_history)

            if wins:
                self.metrics.avg_win_usd = sum(t.pnl_usd for t in wins) / len(wins)
                self.metrics.best_trade_pnl = max(t.pnl_usd for t in wins)

            if losses:
                self.metrics.avg_loss_usd = sum(t.pnl_usd for t in losses) / len(losses)
                self.metrics.worst_trade_pnl = min(t.pnl_usd for t in losses)

            self.metrics.total_fees_paid = sum(t.fees_usd for t in self.paper_trades)

            self.metrics.calculate_derived_metrics()

            # Save metrics
            with open(self.METRICS_FILE, 'w') as f:
                json.dump(self.metrics.to_dict(), f, indent=2)

        except Exception as e:
            logger.error(f"Failed to update metrics: {e}")

    def _check_daily_volume(self) -> Tuple[float, float]:
        """Check daily volume and reset if new day."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if today != self._daily_volume_date:
            self._daily_volume = 0.0
            self._daily_volume_date = today
        return self._daily_volume, self.MAX_DAILY_USD - self._daily_volume

    def _add_daily_volume(self, amount_usd: float):
        """Add to daily volume."""
        self._check_daily_volume()  # Reset if new day
        self._daily_volume += amount_usd

    async def get_portfolio_value(self) -> Tuple[float, float]:
        """Get portfolio value in SOL and USD."""
        sol_balance = self.paper_wallet.get_sol_balance()
        usd_value = await self.paper_wallet.get_total_value_usd()
        return sol_balance, usd_value

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open]

    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.get_open_positions())

    async def execute_buy(
        self,
        token_mint: str,
        amount_usd: float,
        sentiment_grade: str = "B",
        sentiment_score: float = 0.5,
        custom_tp: float = None,
        custom_sl: float = None
    ) -> Tuple[bool, str, Optional[Position]]:
        """
        Execute a paper buy order.

        Args:
            token_mint: Token to buy
            amount_usd: Amount in USD to spend
            sentiment_grade: Grade for TP/SL calculation
            sentiment_score: Sentiment score
            custom_tp: Custom take profit percentage
            custom_sl: Custom stop loss percentage

        Returns:
            Tuple of (success, message, position)
        """
        try:
            # Check position limits
            if self.get_position_count() >= self.max_positions:
                return False, f"Max positions ({self.max_positions}) reached", None

            # Check spending limits
            if amount_usd > self.MAX_TRADE_USD:
                return False, f"Amount ${amount_usd:.2f} exceeds max trade ${self.MAX_TRADE_USD}", None

            used_volume, remaining = self._check_daily_volume()
            if amount_usd > remaining:
                return False, f"Daily limit: used ${used_volume:.2f}, remaining ${remaining:.2f}", None

            # Get current prices
            sol_price = await self.paper_jupiter.get_token_price(PaperWallet.SOL_MINT)
            token_price = await self.paper_jupiter.get_token_price(token_mint)

            if token_price <= 0:
                return False, "Could not get token price", None

            # Calculate SOL needed
            sol_needed = amount_usd / sol_price
            sol_balance = self.paper_wallet.get_sol_balance()

            if sol_balance < sol_needed:
                return False, f"Insufficient SOL: have {sol_balance:.4f}, need {sol_needed:.4f}", None

            # Get token info
            token_info = await self.paper_jupiter.get_token_info(token_mint)
            token_symbol = token_info.symbol if token_info else "UNKNOWN"

            # Get quote for accurate output amount
            sol_lamports = int(sol_needed * 1e9)
            quote = await self.paper_jupiter.get_quote(
                input_mint=PaperWallet.SOL_MINT,
                output_mint=token_mint,
                amount=sol_lamports
            )

            if not quote:
                return False, "Failed to get swap quote", None

            # Execute paper swap
            result = await self.paper_jupiter.execute_swap(quote)

            if not result.success:
                return False, f"Swap failed: {result.error}", None

            # Calculate TP/SL
            entry_price = token_price
            tp_price, sl_price = self._get_tp_sl_levels(entry_price, sentiment_grade, custom_tp, custom_sl)

            # Create position
            position_id = f"PAPER_{uuid.uuid4().hex[:8]}"
            position = Position(
                id=position_id,
                token_mint=token_mint,
                token_symbol=token_symbol,
                direction=TradeDirection.LONG,
                entry_price=entry_price,
                current_price=entry_price,
                amount=result.output_amount,
                amount_usd=amount_usd,
                take_profit_price=tp_price,
                stop_loss_price=sl_price,
                status=TradeStatus.OPEN,
                opened_at=datetime.utcnow().isoformat(),
                sentiment_grade=sentiment_grade,
                sentiment_score=sentiment_score
            )

            self.positions[position_id] = position

            # Record paper trade
            paper_trade = PaperTrade(
                id=position_id,
                timestamp=datetime.utcnow().isoformat(),
                direction="BUY",
                input_mint=PaperWallet.SOL_MINT,
                input_symbol="SOL",
                input_amount=result.input_amount,
                output_mint=token_mint,
                output_symbol=token_symbol,
                output_amount=result.output_amount,
                price_usd=entry_price,
                slippage_pct=0.3,  # Approximate
                fees_usd=result.fees_usd,
                signature=result.signature
            )
            self.paper_trades.append(paper_trade)

            # Update daily volume
            self._add_daily_volume(amount_usd)

            # Save state
            self._save_state()

            tp_pct = ((tp_price - entry_price) / entry_price) * 100
            sl_pct = ((sl_price - entry_price) / entry_price) * 100

            msg = (
                f"PAPER BUY: {result.output_amount:.6f} {token_symbol}\n"
                f"Entry: ${entry_price:.6f}\n"
                f"TP: ${tp_price:.6f} (+{tp_pct:.1f}%)\n"
                f"SL: ${sl_price:.6f} ({sl_pct:.1f}%)\n"
                f"Tx: {result.signature}"
            )

            logger.info(f"Paper buy executed: {position_id} - {token_symbol}")
            return True, msg, position

        except Exception as e:
            logger.error(f"Paper buy failed: {e}")
            return False, f"Error: {str(e)}", None

    async def execute_sell(
        self,
        position_id: str,
        reason: str = "manual"
    ) -> Tuple[bool, str]:
        """
        Execute a paper sell order to close a position.

        Args:
            position_id: ID of position to close
            reason: Reason for closing (manual, tp, sl, etc.)

        Returns:
            Tuple of (success, message)
        """
        try:
            if position_id not in self.positions:
                return False, f"Position {position_id} not found"

            position = self.positions[position_id]
            if not position.is_open:
                return False, f"Position {position_id} is already closed"

            # Get current price
            current_price = await self.paper_jupiter.get_token_price(position.token_mint)
            if current_price <= 0:
                return False, "Could not get current token price"

            # Get quote for sell
            token_info = await self.paper_jupiter.get_token_info(position.token_mint)
            decimals = token_info.decimals if token_info else 9
            token_amount = int(position.amount * (10 ** decimals))

            quote = await self.paper_jupiter.get_quote(
                input_mint=position.token_mint,
                output_mint=PaperWallet.SOL_MINT,
                amount=token_amount
            )

            if not quote:
                return False, "Failed to get sell quote"

            # Execute paper swap
            result = await self.paper_jupiter.execute_swap(quote)

            if not result.success:
                return False, f"Sell swap failed: {result.error}"

            # Calculate P&L
            exit_value_usd = result.output_amount * await self.paper_jupiter.get_token_price(PaperWallet.SOL_MINT)
            pnl_usd = exit_value_usd - position.amount_usd
            pnl_pct = (pnl_usd / position.amount_usd) * 100 if position.amount_usd > 0 else 0

            # Update position
            position.status = TradeStatus.CLOSED
            position.closed_at = datetime.utcnow().isoformat()
            position.exit_price = current_price
            position.current_price = current_price
            position.pnl_usd = pnl_usd
            position.pnl_pct = pnl_pct

            # Move to history
            self.trade_history.append(position)
            del self.positions[position_id]

            # Record paper trade
            paper_trade = PaperTrade(
                id=f"{position_id}_sell",
                timestamp=datetime.utcnow().isoformat(),
                direction="SELL",
                input_mint=position.token_mint,
                input_symbol=position.token_symbol,
                input_amount=position.amount,
                output_mint=PaperWallet.SOL_MINT,
                output_symbol="SOL",
                output_amount=result.output_amount,
                price_usd=current_price,
                slippage_pct=0.3,
                fees_usd=result.fees_usd,
                signature=result.signature
            )
            self.paper_trades.append(paper_trade)

            # Save state
            self._save_state()

            pnl_emoji = "" if pnl_usd >= 0 else ""
            msg = (
                f"PAPER SELL ({reason}): {position.token_symbol}\n"
                f"Exit: ${current_price:.6f}\n"
                f"{pnl_emoji} P&L: ${pnl_usd:+.2f} ({pnl_pct:+.1f}%)\n"
                f"Tx: {result.signature}"
            )

            logger.info(f"Paper sell executed: {position_id} - {position.token_symbol} - P&L: ${pnl_usd:+.2f}")
            return True, msg

        except Exception as e:
            logger.error(f"Paper sell failed: {e}")
            return False, f"Error: {str(e)}"

    async def check_tp_sl(self) -> List[Tuple[str, str, str]]:
        """
        Check all positions for TP/SL triggers.

        Returns:
            List of (position_id, action, message) tuples for triggered positions
        """
        triggered = []

        for pos_id, position in list(self.positions.items()):
            if not position.is_open:
                continue

            try:
                current_price = await self.paper_jupiter.get_token_price(position.token_mint)
                if current_price <= 0:
                    continue

                position.current_price = current_price

                # Check take profit
                if current_price >= position.take_profit_price:
                    success, msg = await self.execute_sell(pos_id, reason="take_profit")
                    if success:
                        triggered.append((pos_id, "TP", msg))

                # Check stop loss
                elif current_price <= position.stop_loss_price:
                    success, msg = await self.execute_sell(pos_id, reason="stop_loss")
                    if success:
                        triggered.append((pos_id, "SL", msg))

            except Exception as e:
                logger.error(f"Error checking TP/SL for {pos_id}: {e}")

        if triggered:
            self._save_state()

        return triggered

    async def update_positions(self):
        """Update current prices for all positions."""
        for position in self.positions.values():
            if position.is_open:
                try:
                    price = await self.paper_jupiter.get_token_price(position.token_mint)
                    if price > 0:
                        position.current_price = price
                except Exception as e:
                    logger.error(f"Failed to update price for {position.token_symbol}: {e}")
        self._save_state()

    def _get_tp_sl_levels(
        self,
        entry_price: float,
        sentiment_grade: str,
        custom_tp: float = None,
        custom_sl: float = None
    ) -> Tuple[float, float]:
        """Calculate TP/SL prices."""
        config = self.TP_SL_CONFIG.get(sentiment_grade, {'take_profit': 0.20, 'stop_loss': 0.10})

        tp_pct = custom_tp if custom_tp else config['take_profit']
        sl_pct = custom_sl if custom_sl else config['stop_loss']

        take_profit = entry_price * (1 + tp_pct)
        stop_loss = entry_price * (1 - sl_pct)

        return take_profit, stop_loss

    def get_performance_report(self) -> str:
        """Get formatted performance report."""
        return self.metrics.to_report()

    async def get_status(self) -> str:
        """Get current paper trading status."""
        sol_balance, usd_value = await self.get_portfolio_value()
        open_positions = self.get_open_positions()

        # Calculate unrealized P&L
        unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)

        status = f"""
PAPER TRADING STATUS
{'='*30}
Portfolio: ${usd_value:,.2f} ({sol_balance:.4f} SOL)
Open Positions: {len(open_positions)}
Unrealized P&L: ${unrealized_pnl:+,.2f}
Daily Volume: ${self._daily_volume:.2f} / ${self.MAX_DAILY_USD}
"""

        if open_positions:
            status += "\nPOSITIONS:\n"
            for p in open_positions:
                pnl_pct = p.unrealized_pnl_pct
                emoji = "" if pnl_pct >= 0 else ""
                status += f"  {emoji} {p.token_symbol}: ${p.current_price:.6f} ({pnl_pct:+.1f}%)\n"

        return status

    def reset(self, initial_sol: float = None):
        """Reset paper trading state."""
        if initial_sol is None:
            initial_sol = self.paper_wallet.initial_sol

        # Clear state files
        for f in [self.POSITIONS_FILE, self.HISTORY_FILE, self.WALLET_FILE,
                  self.TRADES_FILE, self.METRICS_FILE]:
            if f.exists():
                f.unlink()

        # Reinitialize
        self.paper_wallet = PaperWallet(
            initial_sol=initial_sol,
            jupiter_client=self.real_jupiter
        )
        self.paper_jupiter.wallet = self.paper_wallet
        self.positions = {}
        self.trade_history = []
        self.paper_trades = []
        self._daily_volume = 0.0
        self.metrics = PerformanceMetrics(
            started_at=datetime.utcnow().isoformat()
        )

        self._save_state()
        logger.info(f"Paper trading reset with {initial_sol} SOL")


# CLI interface for paper trading
async def main():
    """CLI interface for paper trading."""
    import argparse

    parser = argparse.ArgumentParser(description="Jarvis Paper Trading Simulator")
    parser.add_argument("command", choices=["status", "buy", "sell", "positions", "history", "report", "reset", "check"],
                       help="Command to execute")
    parser.add_argument("--token", "-t", help="Token mint address")
    parser.add_argument("--amount", "-a", type=float, help="Amount in USD")
    parser.add_argument("--position", "-p", help="Position ID")
    parser.add_argument("--grade", "-g", default="B", help="Sentiment grade (A-F)")
    parser.add_argument("--initial-sol", type=float, default=100.0, help="Initial SOL for reset")

    args = parser.parse_args()

    # Initialize engine
    engine = PaperTradingEngine(initial_sol=args.initial_sol)

    if args.command == "status":
        print(await engine.get_status())

    elif args.command == "buy":
        if not args.token or not args.amount:
            print("Error: --token and --amount required for buy")
            return
        success, msg, _ = await engine.execute_buy(
            token_mint=args.token,
            amount_usd=args.amount,
            sentiment_grade=args.grade
        )
        print(msg)

    elif args.command == "sell":
        if not args.position:
            print("Error: --position required for sell")
            return
        success, msg = await engine.execute_sell(args.position)
        print(msg)

    elif args.command == "positions":
        positions = engine.get_open_positions()
        if not positions:
            print("No open positions")
        else:
            print(f"\nOpen Positions ({len(positions)}):\n")
            for p in positions:
                pnl = p.unrealized_pnl_pct
                print(f"  {p.id}: {p.amount:.6f} {p.token_symbol}")
                print(f"    Entry: ${p.entry_price:.6f} | Current: ${p.current_price:.6f}")
                print(f"    P&L: {pnl:+.1f}% | TP: ${p.take_profit_price:.6f} | SL: ${p.stop_loss_price:.6f}\n")

    elif args.command == "history":
        history = engine.trade_history[-10:]  # Last 10 trades
        if not history:
            print("No trade history")
        else:
            print(f"\nRecent Trades ({len(engine.trade_history)} total):\n")
            for t in history:
                emoji = "" if t.pnl_usd >= 0 else ""
                print(f"  {emoji} {t.token_symbol}: ${t.pnl_usd:+.2f} ({t.pnl_pct:+.1f}%)")
                print(f"    Entry: ${t.entry_price:.6f} | Exit: ${t.exit_price:.6f}")
                print(f"    Closed: {t.closed_at}\n")

    elif args.command == "report":
        await engine._update_metrics()
        print(engine.get_performance_report())

    elif args.command == "reset":
        engine.reset(initial_sol=args.initial_sol)
        print(f"Paper trading reset with {args.initial_sol} SOL")

    elif args.command == "check":
        triggered = await engine.check_tp_sl()
        if triggered:
            print(f"Triggered {len(triggered)} TP/SL orders:")
            for pos_id, action, msg in triggered:
                print(f"\n{action}: {msg}")
        else:
            print("No TP/SL triggers")

    # Cleanup
    if engine.real_jupiter:
        await engine.real_jupiter.close()


if __name__ == "__main__":
    asyncio.run(main())
