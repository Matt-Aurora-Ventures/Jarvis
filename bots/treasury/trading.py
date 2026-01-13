"""
Jarvis Trading Engine
Connects sentiment analysis to trade execution with risk management

Integrates:
- Liquidation-based signals (CoinGlass)
- Dual MA reversal strategy
- Meta-labeling for signal quality
- Cooldown system (tracks closures, not entries)
- Decision matrix for multi-signal confirmation
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

# Import new trading modules
try:
    from core.trading.decision_matrix import DecisionMatrix, TradeDecision, DecisionType
    from core.trading.signals.liquidation import LiquidationAnalyzer, LiquidationSignal
    from core.trading.signals.dual_ma import DualMAAnalyzer, DualMASignal
    from core.trading.signals.meta_labeler import MetaLabeler
    from core.trading.cooldown import CooldownManager, CooldownType
    SIGNALS_AVAILABLE = True
except ImportError:
    SIGNALS_AVAILABLE = False
    # Fallback types for type hints when signals not available
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

# Import CoinGlass for liquidation data
try:
    from integrations.coinglass.client import CoinGlassClient
    COINGLASS_AVAILABLE = True
except ImportError:
    COINGLASS_AVAILABLE = False

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
    - Spending caps and audit logging (per guide)
    """

    POSITIONS_FILE = Path(__file__).parent / '.positions.json'
    HISTORY_FILE = Path(__file__).parent / '.trade_history.json'
    AUDIT_LOG_FILE = Path(__file__).parent / '.audit_log.json'
    DAILY_VOLUME_FILE = Path(__file__).parent / '.daily_volume.json'

    # CRITICAL: Spending caps to protect treasury (per guide)
    MAX_TRADE_USD = 100.0      # Maximum single trade size
    MAX_DAILY_USD = 500.0      # Maximum daily trading volume
    MAX_POSITION_PCT = 0.20    # Max 20% of portfolio in single position

    # Default TP/SL percentages by sentiment grade
    # MANDATORY: Every trade MUST have TP/SL set based on grade
    TP_SL_CONFIG = {
        'A+': {'take_profit': 0.30, 'stop_loss': 0.08},  # 30% TP, 8% SL - highest conviction
        'A': {'take_profit': 0.30, 'stop_loss': 0.08},   # 30% TP, 8% SL
        'A-': {'take_profit': 0.25, 'stop_loss': 0.10},
        'B+': {'take_profit': 0.20, 'stop_loss': 0.10},  # 20% TP, 10% SL
        'B': {'take_profit': 0.18, 'stop_loss': 0.12},   # 18% TP, 12% SL
        'B-': {'take_profit': 0.15, 'stop_loss': 0.12},
        'C+': {'take_profit': 0.12, 'stop_loss': 0.15},
        'C': {'take_profit': 0.10, 'stop_loss': 0.15},   # 10% TP, 15% SL - lower conviction
        'C-': {'take_profit': 0.08, 'stop_loss': 0.15},
        'D': {'take_profit': 0.05, 'stop_loss': 0.20},   # Very risky
        'F': {'take_profit': 0.05, 'stop_loss': 0.20},   # DO NOT TRADE
    }

    # Grade emoji mappings for UI
    GRADE_EMOJI = {
        'A+': '🟢🟢', 'A': '🟢🟢', 'A-': '🟢',
        'B+': '🟢', 'B': '🟡', 'B-': '🟡',
        'C+': '🟡', 'C': '🟠', 'C-': '🟠',
        'D': '🔴', 'F': '🔴🔴'
    }

    # Admin ID for trade execution (MUST match)
    ADMIN_USER_ID = 8527130908

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
        dry_run: bool = True,  # Start in dry run mode
        enable_signals: bool = True,  # Enable advanced signal analysis
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
            enable_signals: Enable advanced signal analysis (liquidation, MA, etc.)
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

        # Initialize advanced signal analyzers
        self._decision_matrix: Optional[DecisionMatrix] = None
        self._liquidation_analyzer: Optional[LiquidationAnalyzer] = None
        self._ma_analyzer: Optional[DualMAAnalyzer] = None
        self._meta_labeler: Optional[MetaLabeler] = None
        self._coinglass: Optional[CoinGlassClient] = None

        if enable_signals and SIGNALS_AVAILABLE:
            self._decision_matrix = DecisionMatrix()
            self._liquidation_analyzer = LiquidationAnalyzer()
            self._ma_analyzer = DualMAAnalyzer()
            self._meta_labeler = MetaLabeler()
            logger.info("Advanced signal analyzers initialized")

        if enable_signals and COINGLASS_AVAILABLE:
            self._coinglass = CoinGlassClient()
            logger.info("CoinGlass client initialized")

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

    def _get_daily_volume(self) -> float:
        """Get total trading volume for today (UTC)."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        try:
            if self.DAILY_VOLUME_FILE.exists():
                with open(self.DAILY_VOLUME_FILE) as f:
                    data = json.load(f)
                    if data.get('date') == today:
                        return data.get('volume_usd', 0.0)
        except Exception as e:
            logger.debug(f"Failed to load daily volume: {e}")
        return 0.0

    def _add_daily_volume(self, amount_usd: float):
        """Add to daily trading volume."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        current = self._get_daily_volume()
        try:
            with open(self.DAILY_VOLUME_FILE, 'w') as f:
                json.dump({'date': today, 'volume_usd': current + amount_usd}, f)
        except Exception as e:
            logger.error(f"Failed to save daily volume: {e}")

    def _check_spending_limits(self, amount_usd: float, portfolio_usd: float) -> Tuple[bool, str]:
        """
        Check if trade passes spending limits.

        Per guide: "Implement spending caps to protect treasury from
        runaway losses or accidental large trades."

        Returns:
            Tuple of (allowed, reason)
        """
        # Check single trade limit
        if amount_usd > self.MAX_TRADE_USD:
            return False, f"Trade ${amount_usd:.2f} exceeds max single trade ${self.MAX_TRADE_USD}"

        # Check daily limit
        daily_volume = self._get_daily_volume()
        if daily_volume + amount_usd > self.MAX_DAILY_USD:
            remaining = self.MAX_DAILY_USD - daily_volume
            return False, f"Daily limit reached. Used ${daily_volume:.2f}/{self.MAX_DAILY_USD}. Remaining: ${remaining:.2f}"

        # Check position concentration
        if portfolio_usd > 0:
            position_pct = amount_usd / portfolio_usd
            if position_pct > self.MAX_POSITION_PCT:
                return False, f"Position {position_pct*100:.1f}% exceeds max {self.MAX_POSITION_PCT*100:.0f}% of portfolio"

        return True, ""

    def _log_audit(
        self,
        action: str,
        details: Dict[str, Any],
        user_id: int = None,
        success: bool = True
    ):
        """
        Log trade action to audit log.

        Per guide: "Maintain comprehensive audit trails for all
        trading operations for regulatory compliance and debugging."
        """
        try:
            # Load existing log
            audit_log = []
            if self.AUDIT_LOG_FILE.exists():
                with open(self.AUDIT_LOG_FILE) as f:
                    audit_log = json.load(f)

            # Add new entry
            entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'action': action,
                'user_id': user_id,
                'success': success,
                'details': details,
            }
            audit_log.append(entry)

            # Keep last 1000 entries
            if len(audit_log) > 1000:
                audit_log = audit_log[-1000:]

            with open(self.AUDIT_LOG_FILE, 'w') as f:
                json.dump(audit_log, f, indent=2)

            logger.info(f"AUDIT: {action} | user={user_id} | success={success}")

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

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
        """Check if user is authorized to trade. Admin only."""
        # MUST be the authorized admin ID
        if user_id == self.ADMIN_USER_ID:
            return True
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
        # Default: +20% TP, -10% SL if grade not found
        config = self.TP_SL_CONFIG.get(sentiment_grade, {'take_profit': 0.20, 'stop_loss': 0.10})

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

    async def analyze_liquidation_signal(
        self,
        symbol: str = "BTC",
    ) -> Tuple[TradeDirection, str, Optional[LiquidationSignal]]:
        """
        Analyze liquidation data for contrarian trading signals.

        Key insight from video learnings:
        - Go LONG after large long liquidations (weak hands flushed)
        - Go SHORT after large short liquidations

        Args:
            symbol: Trading symbol (BTC, ETH, SOL)

        Returns:
            Tuple of (direction, reasoning, signal)
        """
        if not self._coinglass or not self._liquidation_analyzer:
            return TradeDirection.NEUTRAL, "Liquidation analysis not available", None

        try:
            # Fetch liquidation data from CoinGlass
            liq_data = await self._coinglass.get_liquidations(symbol, interval="5m", limit=12)

            if not liq_data:
                return TradeDirection.NEUTRAL, "No liquidation data available", None

            # Convert to internal format
            from core.trading.signals.liquidation import Liquidation
            liquidations = []
            for ld in liq_data:
                # Long liquidations
                if ld.long_liquidations > 0:
                    liquidations.append(Liquidation(
                        timestamp=ld.timestamp,
                        symbol=symbol,
                        side='long',
                        size_usd=ld.long_liquidations,
                        price=0,  # Not available from aggregated data
                        exchange='aggregated',
                    ))
                # Short liquidations
                if ld.short_liquidations > 0:
                    liquidations.append(Liquidation(
                        timestamp=ld.timestamp,
                        symbol=symbol,
                        side='short',
                        size_usd=ld.short_liquidations,
                        price=0,
                        exchange='aggregated',
                    ))

            # Analyze for signal
            signal = self._liquidation_analyzer.analyze(liquidations)

            if not signal:
                return TradeDirection.NEUTRAL, "No liquidation signal detected", None

            # Convert signal direction
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
    ) -> Tuple[TradeDirection, str, Optional[DualMASignal]]:
        """
        Analyze dual moving average signal.

        Key insight from video learnings:
        - Fast MA 7-13, Slow MA 30-45
        - Use 100 SMA as trend filter (NOT 200)
        - Only trade in direction of trend

        Args:
            prices: List of price data (most recent last)
            symbol: Trading symbol

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
        prices: Optional[List[float]] = None,
    ) -> Tuple[TradeDirection, str, float]:
        """
        Get combined signal from all sources using decision matrix.

        Combines:
        - Sentiment analysis
        - Liquidation signals
        - MA signals
        - Meta-labeling

        Args:
            token_mint: Token address
            symbol: Trading symbol
            sentiment_score: Sentiment score
            sentiment_grade: Sentiment grade
            prices: Optional price history for MA analysis

        Returns:
            Tuple of (direction, reasoning, confidence)
        """
        if not self._decision_matrix:
            # Fall back to sentiment-only
            direction, reason = await self.analyze_sentiment_signal(
                token_mint, sentiment_score, sentiment_grade
            )
            return direction, reason, 0.5

        signals = []
        reasons = []

        # 1. Sentiment signal
        sent_dir, sent_reason = await self.analyze_sentiment_signal(
            token_mint, sentiment_score, sentiment_grade
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

        # 4. Use decision matrix to combine
        if not signals:
            return TradeDirection.NEUTRAL, "No signals detected", 0.0

        # Simple majority vote with confidence weighting
        long_score = sum(conf for _, dir, conf in signals if dir == 'long')
        short_score = sum(conf for _, dir, conf in signals if dir == 'short')

        if long_score > short_score and long_score > 0.5:
            direction = TradeDirection.LONG
            confidence = long_score / len(signals)
        elif short_score > long_score and short_score > 0.5:
            direction = TradeDirection.SHORT
            confidence = short_score / len(signals)
        else:
            direction = TradeDirection.NEUTRAL
            confidence = 0.0

        combined_reason = " | ".join(reasons)
        return direction, combined_reason, confidence

    async def get_liquidation_summary(self, symbol: str = "BTC") -> Dict[str, Any]:
        """
        Get 24h liquidation summary for a symbol.

        Returns:
            Dict with liquidation statistics and bias
        """
        if not self._coinglass:
            return {"error": "CoinGlass not available"}

        try:
            return await self._coinglass.get_liquidation_summary(symbol)
        except Exception as e:
            logger.error(f"Error fetching liquidation summary: {e}")
            return {"error": str(e)}

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
        # MANDATORY ADMIN CHECK - Only authorized admins can execute trades
        if not user_id:
            logger.warning("Trade rejected: No user_id provided")
            return False, "⛔ Admin only - please authenticate", None

        if not self.is_admin(user_id):
            logger.warning(f"Trade rejected: User {user_id} is not authorized")
            return False, "⛔ Admin only - you are not authorized to trade", None

        # MANDATORY TP/SL VALIDATION - Every trade must have TP/SL
        if sentiment_grade in ['D', 'F']:
            logger.warning(f"Trade rejected: Grade {sentiment_grade} is too risky")
            return False, f"⛔ Trade blocked: Grade {sentiment_grade} is too risky", None

        # Check existing positions
        existing = [p for p in self.positions.values()
                   if p.token_mint == token_mint and p.is_open]
        if existing:
            self._log_audit("OPEN_POSITION_REJECTED", {"token": token_symbol, "reason": "duplicate"}, user_id, False)
            return False, f"Already have position in {token_symbol}", None

        if len([p for p in self.positions.values() if p.is_open]) >= self.max_positions:
            self._log_audit("OPEN_POSITION_REJECTED", {"token": token_symbol, "reason": "max_positions"}, user_id, False)
            return False, "Maximum positions reached", None

        # Get current price
        current_price = await self.jupiter.get_token_price(token_mint)
        if current_price <= 0:
            self._log_audit("OPEN_POSITION_REJECTED", {"token": token_symbol, "reason": "no_price"}, user_id, False)
            return False, "Failed to get token price", None

        # Get portfolio value for limit checks
        _, portfolio_usd = await self.get_portfolio_value()

        # Calculate position size
        if not amount_usd:
            amount_usd = self.calculate_position_size(portfolio_usd)

        # CRITICAL: Check spending limits before proceeding
        allowed, limit_reason = self._check_spending_limits(amount_usd, portfolio_usd)
        if not allowed:
            self._log_audit("OPEN_POSITION_REJECTED", {
                "token": token_symbol,
                "reason": "spending_limit",
                "limit_reason": limit_reason,
                "amount_usd": amount_usd,
            }, user_id, False)
            return False, f"⛔ {limit_reason}", None

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

            # Track daily volume even in dry run
            self._add_daily_volume(amount_usd)

            # Audit log
            self._log_audit("OPEN_POSITION", {
                "position_id": position_id,
                "token": token_symbol,
                "token_mint": token_mint,
                "amount_usd": amount_usd,
                "entry_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "sentiment_grade": sentiment_grade,
                "dry_run": True,
            }, user_id, True)

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

            # Track daily volume
            self._add_daily_volume(amount_usd)

            # Audit log
            self._log_audit("OPEN_POSITION", {
                "position_id": position_id,
                "token": token_symbol,
                "token_mint": token_mint,
                "amount_usd": amount_usd,
                "entry_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "sentiment_grade": sentiment_grade,
                "tx_signature": result.signature,
                "dry_run": False,
            }, user_id, True)

            logger.info(f"Opened position {position_id}: {token_symbol} @ ${current_price}")
            return True, f"Position opened: {result.signature}", position

        except Exception as e:
            self._log_audit("OPEN_POSITION_FAILED", {
                "token": token_symbol,
                "error": str(e),
            }, user_id, False)
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
        if self.admin_user_ids:
            if not user_id or not self.is_admin(user_id):
                self._log_audit("CLOSE_POSITION_REJECTED", {
                    "position_id": position_id,
                    "reason": "unauthorized",
                }, user_id, False)
                return False, "Unauthorized"

        if position_id not in self.positions:
            self._log_audit("CLOSE_POSITION_REJECTED", {
                "position_id": position_id,
                "reason": "not_found",
            }, user_id, False)
            return False, "Position not found"

        position = self.positions[position_id]

        if not position.is_open:
            self._log_audit("CLOSE_POSITION_REJECTED", {
                "position_id": position_id,
                "token": position.token_symbol,
                "reason": "already_closed",
            }, user_id, False)
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

            # Audit log for dry run close
            self._log_audit("CLOSE_POSITION", {
                "position_id": position_id,
                "token": position.token_symbol,
                "entry_price": position.entry_price,
                "exit_price": current_price,
                "pnl_usd": position.pnl_usd,
                "pnl_pct": position.pnl_pct,
                "reason": reason,
                "dry_run": True,
            }, user_id, True)

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

                self._log_audit("CLOSE_POSITION", {
                    "position_id": position_id,
                    "token": position.token_symbol,
                    "reason": "no_balance",
                    "dry_run": False,
                }, user_id, True)
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
                self._log_audit("CLOSE_POSITION_FAILED", {
                    "position_id": position_id,
                    "token": position.token_symbol,
                    "error": "no_quote",
                }, user_id, False)
                return False, "Failed to get close quote"

            result = await self.jupiter.execute_swap(quote, self.wallet)

            if not result.success:
                self._log_audit("CLOSE_POSITION_FAILED", {
                    "position_id": position_id,
                    "token": position.token_symbol,
                    "error": result.error,
                }, user_id, False)
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

            # Audit log for successful close
            self._log_audit("CLOSE_POSITION", {
                "position_id": position_id,
                "token": position.token_symbol,
                "token_mint": position.token_mint,
                "entry_price": position.entry_price,
                "exit_price": current_price,
                "pnl_usd": position.pnl_usd,
                "pnl_pct": position.pnl_pct,
                "reason": reason,
                "tx_signature": result.signature,
                "dry_run": False,
            }, user_id, True)

            logger.info(f"Closed position {position_id}: P&L ${position.pnl_usd:+.2f}")
            return True, f"Closed: {result.signature}, P&L: ${position.pnl_usd:+.2f}"

        except Exception as e:
            self._log_audit("CLOSE_POSITION_FAILED", {
                "position_id": position_id,
                "error": str(e),
            }, user_id, False)
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
        if self._coinglass:
            await self._coinglass.close()
        await self.jupiter.close()
        self._save_state()


# =============================================================================
# SIMPLE WALLET WRAPPER - For direct keypair usage
# =============================================================================

class _SimpleWallet:
    """
    Minimal wallet wrapper for direct keypair usage.

    Provides the interface TradingEngine expects without
    the complexity of SecureWallet encryption.
    """

    def __init__(self, keypair, address: str):
        self._keypair = keypair
        self._address = address
        self._treasury_info = WalletInfo(
            address=address,
            created_at="",
            label="Treasury",
            is_treasury=True,
        )

    def get_treasury(self) -> Optional[WalletInfo]:
        """Return the treasury wallet info."""
        return self._treasury_info

    async def get_balance(self, address: str = None) -> Tuple[float, float]:
        """Get wallet balance in SOL and USD."""
        import aiohttp
        try:
            target = address or self._address
            rpc_url = os.environ.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

            async with aiohttp.ClientSession() as session:
                # Get SOL balance
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [target]
                }
                async with session.post(rpc_url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        lamports = data.get("result", {}).get("value", 0)
                        sol_balance = lamports / 1e9

                        # Get SOL price from Jupiter, fallback to CoinGecko
                        sol_mint = "So11111111111111111111111111111111111111112"
                        price_url = f"https://price.jup.ag/v6/price?ids={sol_mint}"
                        sol_price = 0.0
                        try:
                            async with session.get(price_url) as price_resp:
                                if price_resp.status == 200:
                                    price_data = await price_resp.json()
                                    sol_price = float(
                                        price_data.get("data", {}).get(sol_mint, {}).get("price", 0) or 0
                                    )
                        except Exception as price_err:
                            logger.warning(f"Jupiter price fetch failed, falling back: {price_err}")

                        if sol_price <= 0:
                            try:
                                cg_url = "https://api.coingecko.com/api/v3/simple/price"
                                params = {"ids": "solana", "vs_currencies": "usd"}
                                async with session.get(cg_url, params=params) as cg_resp:
                                    if cg_resp.status == 200:
                                        cg_data = await cg_resp.json()
                                        sol_price = float(cg_data.get("solana", {}).get("usd", 0) or 0)
                            except Exception as cg_err:
                                logger.warning(f"CoinGecko price fetch failed: {cg_err}")

                        return sol_balance, sol_balance * sol_price if sol_price > 0 else 0.0
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0, 0.0

    async def get_token_balances(self, address: str = None) -> Dict[str, Dict]:
        """Get token balances for the wallet."""
        return {}

    def sign_transaction(self, address: str, transaction) -> bytes:
        """Sign a transaction with the keypair."""
        tx_bytes = transaction
        if isinstance(transaction, (bytes, bytearray)):
            tx_bytes = bytes(transaction)
        if isinstance(tx_bytes, (bytes, bytearray)):
            try:
                from solders.transaction import VersionedTransaction

                versioned = VersionedTransaction.from_bytes(tx_bytes)
                signed_tx = VersionedTransaction(versioned.message, [self._keypair])
                return bytes(signed_tx)
            except Exception:
                signature = self._keypair.sign_message(tx_bytes)
                return bytes(signature)

        if hasattr(transaction, "sign"):
            transaction.sign([self._keypair])
            try:
                return bytes(transaction)
            except Exception:
                return b""

        signature = self._keypair.sign_message(transaction)
        return bytes(signature)

    @property
    def keypair(self):
        """Get the underlying keypair for signing."""
        return self._keypair


# =============================================================================
# TREASURY TRADER - Simple Interface for Ape Buttons
# =============================================================================

class TreasuryTrader:
    """
    Simple trading interface for ape buttons.

    Provides a clean execute_buy_with_tp_sl method that handles:
    - Wallet initialization
    - Jupiter quote fetching
    - Trade execution with TP/SL orders
    """

    _instance: Optional['TreasuryTrader'] = None
    _engine: Optional[TradingEngine] = None
    _initialized: bool = False

    def __new__(cls):
        """Singleton pattern for shared state."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _ensure_initialized(self) -> Tuple[bool, str]:
        """Initialize wallet and jupiter client if not already done."""
        if self._initialized and self._engine:
            return True, "Already initialized"

        try:
            # Use centralized KeyManager for robust key loading
            try:
                from core.security.key_manager import get_key_manager
                key_manager = get_key_manager()
                keypair = key_manager.load_treasury_keypair()
                
                if keypair:
                    treasury_address = str(keypair.pubkey())
                    wallet = _SimpleWallet(keypair, treasury_address)
                    logger.info(f"Loaded treasury via KeyManager: {treasury_address[:8]}...")
                else:
                    wallet = None
                    treasury_address = None
            except ImportError:
                # Fallback to legacy loading if KeyManager not available
                logger.warning("KeyManager not available, using legacy loader")
                wallet = None
                treasury_address = None
                
                root = Path(__file__).resolve().parents[2]
                env_paths = (root / "tg_bot" / ".env", root / ".env")
                try:
                    from dotenv import load_dotenv
                    for env_path in env_paths:
                        if env_path.exists():
                            load_dotenv(env_path, override=False)
                except Exception:
                    pass

                if not os.environ.get("JARVIS_WALLET_PASSWORD"):
                    for env_path in env_paths:
                        if not env_path.exists():
                            continue
                        try:
                            for line in env_path.read_text(encoding="utf-8").splitlines():
                                line = line.strip()
                                if not line or line.startswith("#") or "=" not in line:
                                    continue
                                key, value = line.split("=", 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                if key and key not in os.environ:
                                    os.environ[key] = value
                        except Exception:
                            continue

                # Try to load keypair from treasury_keypair.json first
                default_path = Path(__file__).resolve().parents[2] / "data" / "treasury_keypair.json"
                env_path_str = os.environ.get("TREASURY_WALLET_PATH", "").strip()
                keypair_path = Path(env_path_str) if env_path_str else default_path

                if keypair_path.exists():
                    try:
                        keypair = self._load_encrypted_keypair(keypair_path)
                        if keypair:
                            treasury_address = str(keypair.pubkey())
                            logger.info(f"Loaded treasury keypair: {treasury_address[:8]}...")
                            wallet = _SimpleWallet(keypair, treasury_address)
                    except Exception as kp_err:
                        logger.warning(f"Keypair load failed: {kp_err}")

            # Fallback to SecureWallet if direct load failed
            if not wallet:
                wallet_password = os.environ.get('JARVIS_WALLET_PASSWORD')
                if not wallet_password:
                    logger.warning("JARVIS_WALLET_PASSWORD not set - running in simulation mode")
                    return False, "No wallet found - check treasury_keypair.json or JARVIS_WALLET_PASSWORD"

                try:
                    secure_wallet = SecureWallet()
                    treasury = secure_wallet.get_treasury()
                    if treasury:
                        wallet = secure_wallet
                        treasury_address = treasury.address
                except Exception as wallet_err:
                    logger.warning(f"SecureWallet init failed: {wallet_err}")

            if not wallet:
                return False, "No treasury wallet found - create data/treasury_keypair.json"

            # Initialize Jupiter client
            jupiter = JupiterClient()

            admin_ids = []
            admin_ids_str = os.environ.get("TREASURY_ADMIN_IDS") or os.environ.get("TELEGRAM_ADMIN_IDS", "")
            if admin_ids_str:
                admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

            # Create trading engine (respect TREASURY_LIVE_MODE)
            live_mode = os.environ.get("TREASURY_LIVE_MODE", "false").lower() in ("1", "true", "yes", "on")
            self._engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=not live_mode,
                max_positions=10,
                admin_user_ids=admin_ids,
            )
            await self._engine.initialize_order_manager()

            self._initialized = True
            logger.info(f"TreasuryTrader initialized with wallet {treasury_address[:8]}...")
            return True, f"Initialized with {treasury_address[:8]}..."

        except Exception as e:
            logger.error(f"Failed to initialize TreasuryTrader: {e}")
            return False, str(e)

    async def execute_buy_with_tp_sl(
        self,
        token_mint: str,
        amount_sol: float,
        take_profit_price: float,
        stop_loss_price: float,
        token_symbol: str = "",
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a buy trade with take profit and stop loss.

        Args:
            token_mint: Token contract address (can be partial)
            amount_sol: Amount in SOL to spend
            take_profit_price: Take profit target price
            stop_loss_price: Stop loss target price
            token_symbol: Token symbol for logging

        Returns:
            Dict with success, tx_signature, error, and message
        """
        # Initialize if needed
        initialized, init_msg = await self._ensure_initialized()
        if not initialized:
            return {
                "success": False,
                "error": init_msg,
                "tx_signature": "",
            }
        if user_id is None:
            return {
                "success": False,
                "error": "User ID required for trade authorization",
                "tx_signature": "",
            }

        try:
            # Resolve partial contract address if needed
            logger.info(f"Resolving token: mint={token_mint}, symbol={token_symbol}")
            full_mint = await self._resolve_token_mint(token_mint, token_symbol)
            if not full_mint:
                logger.error(f"Failed to resolve token address for {token_symbol or token_mint}")
                return {
                    "success": False,
                    "error": f"Could not resolve token address for {token_symbol or token_mint}",
                    "tx_signature": "",
                }
            logger.info(f"Resolved to: {full_mint}")

            # Get current price for position sizing
            current_price = await self._engine.jupiter.get_token_price(full_mint)
            if current_price <= 0:
                return {
                    "success": False,
                    "error": "Could not fetch current token price",
                    "tx_signature": "",
                }

            # Get SOL price for USD conversion
            sol_price = await self._engine.jupiter.get_token_price(JupiterClient.SOL_MINT)
            amount_usd = amount_sol * sol_price

            # Calculate custom TP/SL percentages from prices
            tp_pct = (take_profit_price - current_price) / current_price
            sl_pct = (current_price - stop_loss_price) / current_price

            # Get token info for symbol
            token_info = await self._engine.jupiter.get_token_info(full_mint)
            symbol = token_symbol or (token_info.symbol if token_info else "UNKNOWN")

            logger.info(
                f"Executing buy: {symbol} | {amount_sol:.4f} SOL (${amount_usd:.2f}) | "
                f"Entry: ${current_price:.6f} | TP: ${take_profit_price:.6f} | SL: ${stop_loss_price:.6f}"
            )

            # Open position through trading engine
            success, message, position = await self._engine.open_position(
                token_mint=full_mint,
                token_symbol=symbol,
                direction=TradeDirection.LONG,
                amount_usd=amount_usd,
                sentiment_grade="B",  # Default grade
                custom_tp=tp_pct,
                custom_sl=sl_pct,
                user_id=user_id,
            )

            if success and position:
                return {
                    "success": True,
                    "tx_signature": message.split(": ")[-1] if ": " in message else "",
                    "message": message,
                    "position_id": position.id,
                    "entry_price": position.entry_price,
                    "amount_tokens": position.amount,
                }
            else:
                return {
                    "success": False,
                    "error": message,
                    "tx_signature": "",
                }

        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "tx_signature": "",
            }

    async def _resolve_token_mint(self, partial_mint: str, symbol: str = "") -> Optional[str]:
        """
        Resolve a partial token mint to full address.

        Uses DexScreener search if the mint is truncated.
        """
        # If it looks like a full Solana address, return as-is
        if len(partial_mint) >= 32:
            logger.info(f"Token mint already full length: {partial_mint[:12]}...")
            return partial_mint

        # Try to search by symbol using DexScreener
        import aiohttp

        logger.info(f"Resolving partial mint '{partial_mint}' with symbol '{symbol}'")
        try:
            async with aiohttp.ClientSession() as session:
                search_term = symbol or partial_mint
                url = f"https://api.dexscreener.com/latest/dex/search?q={search_term}"
                logger.info(f"DexScreener search: {url}")

                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get("pairs", [])

                        # Filter for Solana pairs
                        solana_pairs = [
                            p for p in pairs
                            if p.get("chainId") == "solana"
                            and (
                                p.get("baseToken", {}).get("symbol", "").upper() == search_term.upper()
                                or search_term.upper() in p.get("baseToken", {}).get("name", "").upper()
                                or p.get("baseToken", {}).get("address", "").startswith(partial_mint)
                            )
                        ]

                        if solana_pairs:
                            # Get most liquid pair
                            best = max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                            full_address = best.get("baseToken", {}).get("address")
                            if full_address:
                                logger.info(f"Resolved {search_term} to {full_address[:8]}...")
                                return full_address
        except Exception as e:
            logger.error(f"Failed to resolve token mint: {e}")

        return None

    def _load_encrypted_keypair(self, keypair_path):
        """
        Load and decrypt keypair from encrypted treasury_keypair.json.

        The file format:
        {
            "salt": "<base64>",
            "nonce": "<base64>",
            "encrypted_key": "<base64>",
            "pubkey": "<address>"
        }
        """
        import json
        import base64
        import hashlib

        try:
            with open(keypair_path) as f:
                data = json.load(f)

            # Check if this is an encrypted format
            if 'encrypted_key' in data and 'salt' in data and 'nonce' in data:
                password = os.environ.get('JARVIS_WALLET_PASSWORD', '')
                if not password:
                    logger.warning("JARVIS_WALLET_PASSWORD not set - cannot decrypt keypair")
                    return None
                salt = base64.b64decode(data['salt'])
                nonce = base64.b64decode(data['nonce'])
                encrypted_key = base64.b64decode(data['encrypted_key'])

                # Try PyNaCl (libsodium) decryption
                try:
                    import nacl.secret
                    import nacl.pwhash

                    # Derive key from password using Argon2
                    key = nacl.pwhash.argon2id.kdf(
                        nacl.secret.SecretBox.KEY_SIZE,
                        password.encode(),
                        salt,
                        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
                        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
                    )

                    box = nacl.secret.SecretBox(key)
                    decrypted = box.decrypt(encrypted_key, nonce)

                    from solders.keypair import Keypair
                    return Keypair.from_bytes(decrypted)

                except ImportError:
                    logger.warning("PyNaCl not installed, trying Fernet")

                # Try Fernet decryption as fallback
                try:
                    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.fernet import Fernet

                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=salt,
                        iterations=480000,
                    )
                    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
                    fernet = Fernet(key)
                    decrypted = fernet.decrypt(encrypted_key)

                    from solders.keypair import Keypair
                    return Keypair.from_bytes(decrypted)

                except Exception as e:
                    logger.error(f"Fernet decryption failed: {e}")

            # Check if raw format (list of bytes)
            elif isinstance(data, list):
                from solders.keypair import Keypair
                return Keypair.from_bytes(bytes(data))

            # Has pubkey but couldn't decrypt - return None
            if 'pubkey' in data:
                logger.warning(f"Found encrypted keypair for {data['pubkey'][:8]}... but could not decrypt")

        except Exception as e:
            logger.error(f"Failed to load keypair: {e}")

        return None

    async def get_balance(self) -> Tuple[float, float]:
        """Get treasury balance in SOL and USD."""
        initialized, _ = await self._ensure_initialized()
        if not initialized:
            return 0.0, 0.0
        return await self._engine.get_portfolio_value()

    async def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        initialized, _ = await self._ensure_initialized()
        if not initialized:
            return []
        return self._engine.get_open_positions()

    async def close_position(self, position_id: str) -> Tuple[bool, str]:
        """Close a position by ID."""
        initialized, msg = await self._ensure_initialized()
        if not initialized:
            return False, msg
        return await self._engine.close_position(position_id)
