"""
Jarvis Trading Engine
Connects sentiment analysis to trade execution with risk management
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path

from .wallet import SecureWallet, WalletInfo
from .jupiter import JupiterClient, SwapQuote, SwapResult, LimitOrderManager

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    LONG = "LONG"      # Buy token
    SHORT = "SHORT"    # Sell token (or skip)
    NEUTRAL = "NEUTRAL"


class TradeStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class RiskLevel(Enum):
    CONSERVATIVE = "CONSERVATIVE"  # 1% position size
    MODERATE = "MODERATE"          # 2% position size
    AGGRESSIVE = "AGGRESSIVE"      # 5% position size
    DEGEN = "DEGEN"                # 10% position size (shitcoins)


@dataclass
class Position:
    """Represents an open trading position."""
    id: str
    token_mint: str
    token_symbol: str
    direction: TradeDirection
    entry_price: float
    current_price: float
    amount: float              # Token amount
    amount_usd: float          # Entry value in USD
    take_profit_price: float   # TP target
    stop_loss_price: float     # SL target
    status: TradeStatus
    opened_at: str
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    sentiment_grade: str = ""
    sentiment_score: float = 0.0
    tp_order_id: Optional[str] = None
    sl_order_id: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN

    @property
    def unrealized_pnl(self) -> float:
        if self.direction == TradeDirection.LONG:
            return ((self.current_price - self.entry_price) / self.entry_price) * self.amount_usd
        return 0.0

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price > 0:
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'token_mint': self.token_mint,
            'token_symbol': self.token_symbol,
            'direction': self.direction.value,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'amount': self.amount,
            'amount_usd': self.amount_usd,
            'take_profit_price': self.take_profit_price,
            'stop_loss_price': self.stop_loss_price,
            'status': self.status.value,
            'opened_at': self.opened_at,
            'closed_at': self.closed_at,
            'exit_price': self.exit_price,
            'pnl_usd': self.pnl_usd,
            'pnl_pct': self.pnl_pct,
            'sentiment_grade': self.sentiment_grade,
            'sentiment_score': self.sentiment_score,
            'tp_order_id': self.tp_order_id,
            'sl_order_id': self.sl_order_id
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        return cls(
            id=data['id'],
            token_mint=data['token_mint'],
            token_symbol=data['token_symbol'],
            direction=TradeDirection(data['direction']),
            entry_price=data['entry_price'],
            current_price=data.get('current_price', data['entry_price']),
            amount=data['amount'],
            amount_usd=data['amount_usd'],
            take_profit_price=data['take_profit_price'],
            stop_loss_price=data['stop_loss_price'],
            status=TradeStatus(data['status']),
            opened_at=data['opened_at'],
            closed_at=data.get('closed_at'),
            exit_price=data.get('exit_price'),
            pnl_usd=data.get('pnl_usd', 0),
            pnl_pct=data.get('pnl_pct', 0),
            sentiment_grade=data.get('sentiment_grade', ''),
            sentiment_score=data.get('sentiment_score', 0),
            tp_order_id=data.get('tp_order_id'),
            sl_order_id=data.get('sl_order_id')
        )


@dataclass
class TradeReport:
    """Summary of trading performance."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl_usd: float = 0.0
    total_pnl_pct: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    avg_trade_pnl: float = 0.0
    open_positions: int = 0
    unrealized_pnl: float = 0.0

    def to_telegram_message(self) -> str:
        """Format report for Telegram."""
        emoji = "" if self.total_pnl_usd >= 0 else ""

        return f"""
<b>TRADING PERFORMANCE REPORT</b>

<b>Summary:</b>
Total Trades: <code>{self.total_trades}</code>
Win Rate: <code>{self.win_rate:.1f}%</code> ({self.winning_trades}W / {self.losing_trades}L)

<b>P&L:</b>
{emoji} Total: <code>${self.total_pnl_usd:+.2f}</code> (<code>{self.total_pnl_pct:+.1f}%</code>)
Best Trade: <code>${self.best_trade_pnl:+.2f}</code>
Worst Trade: <code>${self.worst_trade_pnl:+.2f}</code>
Average: <code>${self.avg_trade_pnl:+.2f}</code>

<b>Open Positions:</b>
Count: <code>{self.open_positions}</code>
Unrealized P&L: <code>${self.unrealized_pnl:+.2f}</code>
"""


class TradingEngine:
    """
    Main trading engine for Jarvis Treasury.

    Features:
    - Sentiment-based trade signals
    - Automatic take profit and stop loss
    - Position sizing based on risk level
    - Full trade history and reporting
    - Real-time P&L tracking
    """

    POSITIONS_FILE = Path(__file__).parent / '.positions.json'
    HISTORY_FILE = Path(__file__).parent / '.trade_history.json'

    # Default TP/SL percentages by sentiment grade
    TP_SL_CONFIG = {
        'A': {'take_profit': 0.30, 'stop_loss': 0.10},   # 30% TP, 10% SL
        'A-': {'take_profit': 0.25, 'stop_loss': 0.10},
        'B+': {'take_profit': 0.20, 'stop_loss': 0.08},
        'B': {'take_profit': 0.15, 'stop_loss': 0.08},
        'C+': {'take_profit': 0.10, 'stop_loss': 0.05},
        'C': {'take_profit': 0.08, 'stop_loss': 0.05},
    }

    # Position sizing by risk level (% of portfolio)
    POSITION_SIZE = {
        RiskLevel.CONSERVATIVE: 0.01,   # 1%
        RiskLevel.MODERATE: 0.02,       # 2%
        RiskLevel.AGGRESSIVE: 0.05,     # 5%
        RiskLevel.DEGEN: 0.10,          # 10%
    }

    def __init__(
        self,
        wallet: SecureWallet,
        jupiter: JupiterClient,
        admin_user_ids: List[int] = None,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        max_positions: int = 5,
        dry_run: bool = True  # Start in dry run mode
    ):
        """
        Initialize trading engine.

        Args:
            wallet: SecureWallet for signing transactions
            jupiter: JupiterClient for swaps
            admin_user_ids: Telegram user IDs allowed to trade
            risk_level: Default position sizing
            max_positions: Maximum concurrent positions
            dry_run: If True, simulate trades without execution
        """
        self.wallet = wallet
        self.jupiter = jupiter
        self.admin_user_ids = admin_user_ids or []
        self.risk_level = risk_level
        self.max_positions = max_positions
        self.dry_run = dry_run

        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Position] = []
        self.order_manager: Optional[LimitOrderManager] = None

        # Load existing state
        self._load_state()

    def _load_state(self):
        """Load positions and history from disk."""
        # Load positions
        if self.POSITIONS_FILE.exists():
            try:
                with open(self.POSITIONS_FILE) as f:
                    data = json.load(f)
                    for pos_data in data:
                        pos = Position.from_dict(pos_data)
                        self.positions[pos.id] = pos
            except Exception as e:
                logger.error(f"Failed to load positions: {e}")

        # Load history
        if self.HISTORY_FILE.exists():
            try:
                with open(self.HISTORY_FILE) as f:
                    data = json.load(f)
                    self.trade_history = [Position.from_dict(p) for p in data]
            except Exception as e:
                logger.error(f"Failed to load history: {e}")

    def _save_state(self):
        """Save positions and history to disk."""
        try:
            # Save positions
            with open(self.POSITIONS_FILE, 'w') as f:
                json.dump([p.to_dict() for p in self.positions.values()], f, indent=2)

            # Save history
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump([p.to_dict() for p in self.trade_history], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def is_admin(self, user_id: int) -> bool:
        """Check if user is authorized to trade."""
        return user_id in self.admin_user_ids

    def add_admin(self, user_id: int):
        """Add an admin user."""
        if user_id not in self.admin_user_ids:
            self.admin_user_ids.append(user_id)

    async def get_portfolio_value(self) -> Tuple[float, float]:
        """
        Get total portfolio value in SOL and USD.

        Returns:
            Tuple of (sol_value, usd_value)
        """
        treasury = self.wallet.get_treasury()
        if not treasury:
            return 0.0, 0.0

        sol_balance, usd_value = await self.wallet.get_balance(treasury.address)

        # Add token values
        token_balances = await self.wallet.get_token_balances(treasury.address)

        for mint, info in token_balances.items():
            price = await self.jupiter.get_token_price(mint)
            usd_value += info['balance'] * price

        return sol_balance, usd_value

    def calculate_position_size(self, portfolio_usd: float, risk_override: RiskLevel = None) -> float:
        """Calculate position size in USD based on risk level."""
        risk = risk_override or self.risk_level
        return portfolio_usd * self.POSITION_SIZE[risk]

    def get_tp_sl_levels(
        self,
        entry_price: float,
        sentiment_grade: str,
        custom_tp: float = None,
        custom_sl: float = None
    ) -> Tuple[float, float]:
        """
        Calculate take profit and stop loss prices.

        Args:
            entry_price: Entry price in USD
            sentiment_grade: A, B+, C, etc.
            custom_tp: Override TP percentage
            custom_sl: Override SL percentage

        Returns:
            Tuple of (take_profit_price, stop_loss_price)
        """
        config = self.TP_SL_CONFIG.get(sentiment_grade, {'take_profit': 0.15, 'stop_loss': 0.08})

        tp_pct = custom_tp if custom_tp else config['take_profit']
        sl_pct = custom_sl if custom_sl else config['stop_loss']

        take_profit = entry_price * (1 + tp_pct)
        stop_loss = entry_price * (1 - sl_pct)

        return take_profit, stop_loss

    async def analyze_sentiment_signal(
        self,
        token_mint: str,
        sentiment_score: float,
        sentiment_grade: str
    ) -> Tuple[TradeDirection, str]:
        """
        Analyze sentiment and determine trade direction.

        Returns:
            Tuple of (direction, reasoning)
        """
        # Get current positions for this token
        existing = [p for p in self.positions.values()
                   if p.token_mint == token_mint and p.is_open]

        if existing:
            return TradeDirection.NEUTRAL, "Already have open position"

        if len(self.positions) >= self.max_positions:
            return TradeDirection.NEUTRAL, "Max positions reached"

        # Determine direction based on sentiment
        if sentiment_score > 0.35 and sentiment_grade in ['A', 'A-', 'B+']:
            return TradeDirection.LONG, f"Strong bullish signal (Grade {sentiment_grade})"

        if sentiment_score > 0.20 and sentiment_grade in ['B', 'B+']:
            return TradeDirection.LONG, f"Moderate bullish signal (Grade {sentiment_grade})"

        if sentiment_score < -0.35:
            return TradeDirection.SHORT, f"Strong bearish signal - avoid"

        return TradeDirection.NEUTRAL, "Signal not strong enough"

    async def open_position(
        self,
        token_mint: str,
        token_symbol: str,
        direction: TradeDirection,
        amount_usd: float = None,
        sentiment_grade: str = "B",
        sentiment_score: float = 0.0,
        custom_tp: float = None,
        custom_sl: float = None,
        user_id: int = None
    ) -> Tuple[bool, str, Optional[Position]]:
        """
        Open a new trading position.

        Args:
            token_mint: Token mint address
            token_symbol: Token symbol
            direction: LONG or SHORT
            amount_usd: Position size in USD (or use default)
            sentiment_grade: Grade for TP/SL calculation
            sentiment_score: Raw sentiment score
            custom_tp: Custom take profit %
            custom_sl: Custom stop loss %
            user_id: Telegram user ID for auth

        Returns:
            Tuple of (success, message, position)
        """
        # Check admin auth
        if user_id and not self.is_admin(user_id):
            return False, "Unauthorized", None

        # Check existing positions
        existing = [p for p in self.positions.values()
                   if p.token_mint == token_mint and p.is_open]
        if existing:
            return False, f"Already have position in {token_symbol}", None

        if len([p for p in self.positions.values() if p.is_open]) >= self.max_positions:
            return False, "Maximum positions reached", None

        # Get current price
        current_price = await self.jupiter.get_token_price(token_mint)
        if current_price <= 0:
            return False, "Failed to get token price", None

        # Calculate position size
        if not amount_usd:
            _, portfolio_usd = await self.get_portfolio_value()
            amount_usd = self.calculate_position_size(portfolio_usd)

        # Calculate TP/SL
        tp_price, sl_price = self.get_tp_sl_levels(
            current_price, sentiment_grade, custom_tp, custom_sl
        )

        # Generate position ID
        import uuid
        position_id = str(uuid.uuid4())[:8]

        # Calculate token amount
        token_amount = amount_usd / current_price

        # Create position
        position = Position(
            id=position_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            direction=direction,
            entry_price=current_price,
            current_price=current_price,
            amount=token_amount,
            amount_usd=amount_usd,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            status=TradeStatus.PENDING,
            opened_at=datetime.utcnow().isoformat(),
            sentiment_grade=sentiment_grade,
            sentiment_score=sentiment_score
        )

        if self.dry_run:
            # Simulate trade
            position.status = TradeStatus.OPEN
            self.positions[position_id] = position
            self._save_state()

            logger.info(f"[DRY RUN] Opened position {position_id}: {token_symbol}")
            return True, f"[DRY RUN] Position opened", position

        # Execute real trade
        try:
            # Get quote for SOL -> token
            sol_amount = int(amount_usd / await self.jupiter.get_token_price(JupiterClient.SOL_MINT) * 1e9)

            quote = await self.jupiter.get_quote(
                JupiterClient.SOL_MINT,
                token_mint,
                sol_amount
            )

            if not quote:
                return False, "Failed to get swap quote", None

            # Execute swap
            result = await self.jupiter.execute_swap(quote, self.wallet)

            if not result.success:
                return False, f"Swap failed: {result.error}", None

            # Update position
            position.status = TradeStatus.OPEN
            position.amount = quote.output_amount_ui

            # Set up TP/SL orders
            if self.order_manager:
                tp_id = await self.order_manager.create_take_profit(
                    token_mint,
                    int(position.amount * (10 ** 9)),
                    tp_price
                )
                sl_id = await self.order_manager.create_stop_loss(
                    token_mint,
                    int(position.amount * (10 ** 9)),
                    sl_price
                )
                position.tp_order_id = tp_id
                position.sl_order_id = sl_id

            self.positions[position_id] = position
            self._save_state()

            logger.info(f"Opened position {position_id}: {token_symbol} @ ${current_price}")
            return True, f"Position opened: {result.signature}", position

        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            return False, f"Error: {str(e)}", None

    async def close_position(
        self,
        position_id: str,
        user_id: int = None,
        reason: str = "Manual close"
    ) -> Tuple[bool, str]:
        """
        Close an open position.

        Args:
            position_id: Position ID to close
            user_id: Telegram user ID for auth
            reason: Reason for closing

        Returns:
            Tuple of (success, message)
        """
        if user_id and not self.is_admin(user_id):
            return False, "Unauthorized"

        if position_id not in self.positions:
            return False, "Position not found"

        position = self.positions[position_id]

        if not position.is_open:
            return False, "Position already closed"

        # Get current price
        current_price = await self.jupiter.get_token_price(position.token_mint)

        if self.dry_run:
            # Simulate close
            position.status = TradeStatus.CLOSED
            position.closed_at = datetime.utcnow().isoformat()
            position.exit_price = current_price
            position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)

            # Move to history
            self.trade_history.append(position)
            del self.positions[position_id]
            self._save_state()

            logger.info(f"[DRY RUN] Closed position {position_id}: P&L ${position.pnl_usd:+.2f}")
            return True, f"[DRY RUN] Closed with P&L: ${position.pnl_usd:+.2f} ({position.pnl_pct:+.1f}%)"

        # Execute real close
        try:
            # Cancel pending orders
            if self.order_manager:
                if position.tp_order_id:
                    await self.order_manager.cancel_order(position.tp_order_id)
                if position.sl_order_id:
                    await self.order_manager.cancel_order(position.sl_order_id)

            # Get token balance
            balances = await self.wallet.get_token_balances()
            token_balance = balances.get(position.token_mint, {}).get('balance', 0)

            if token_balance <= 0:
                position.status = TradeStatus.CLOSED
                position.closed_at = datetime.utcnow().isoformat()
                self.trade_history.append(position)
                del self.positions[position_id]
                self._save_state()
                return True, "Position closed (no balance)"

            # Get quote token -> SOL
            token_info = await self.jupiter.get_token_info(position.token_mint)
            decimals = token_info.decimals if token_info else 9
            amount = int(token_balance * (10 ** decimals))

            quote = await self.jupiter.get_quote(
                position.token_mint,
                JupiterClient.SOL_MINT,
                amount
            )

            if not quote:
                return False, "Failed to get close quote"

            result = await self.jupiter.execute_swap(quote, self.wallet)

            if not result.success:
                return False, f"Close failed: {result.error}"

            # Update position
            position.status = TradeStatus.CLOSED
            position.closed_at = datetime.utcnow().isoformat()
            position.exit_price = current_price
            position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)

            self.trade_history.append(position)
            del self.positions[position_id]
            self._save_state()

            logger.info(f"Closed position {position_id}: P&L ${position.pnl_usd:+.2f}")
            return True, f"Closed: {result.signature}, P&L: ${position.pnl_usd:+.2f}"

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False, f"Error: {str(e)}"

    async def update_positions(self):
        """Update current prices for all open positions."""
        for position in self.positions.values():
            if position.is_open:
                price = await self.jupiter.get_token_price(position.token_mint)
                if price > 0:
                    position.current_price = price

        self._save_state()

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open]

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a specific position."""
        return self.positions.get(position_id)

    def generate_report(self) -> TradeReport:
        """Generate trading performance report."""
        closed = [p for p in self.trade_history if p.status == TradeStatus.CLOSED]
        open_positions = self.get_open_positions()

        if not closed and not open_positions:
            return TradeReport()

        winning = [p for p in closed if p.pnl_usd > 0]
        losing = [p for p in closed if p.pnl_usd < 0]

        total_pnl = sum(p.pnl_usd for p in closed)
        unrealized = sum(p.unrealized_pnl for p in open_positions)

        pnls = [p.pnl_usd for p in closed]

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
            open_positions=len(open_positions),
            unrealized_pnl=unrealized
        )

    async def initialize_order_manager(self):
        """Initialize the limit order manager."""
        self.order_manager = LimitOrderManager(self.jupiter, self.wallet)
        await self.order_manager.start_monitoring()

    async def shutdown(self):
        """Clean shutdown."""
        if self.order_manager:
            await self.order_manager.stop_monitoring()
        await self.jupiter.close()
        self._save_state()
