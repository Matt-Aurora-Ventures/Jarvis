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
        if self.admin_user_ids:
            if not user_id or not self.is_admin(user_id):
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
        if self.admin_user_ids:
            if not user_id or not self.is_admin(user_id):
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

                        # Get SOL price from Jupiter
                        sol_mint = "So11111111111111111111111111111111111111112"
                        price_url = f"https://price.jup.ag/v6/price?ids={sol_mint}"
                        async with session.get(price_url) as price_resp:
                            if price_resp.status == 200:
                                price_data = await price_resp.json()
                                sol_price = price_data.get("data", {}).get(sol_mint, {}).get("price", 0)
                                return sol_balance, sol_balance * sol_price

                        return sol_balance, 0.0
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0, 0.0

    async def get_token_balances(self, address: str = None) -> Dict[str, Dict]:
        """Get token balances for the wallet."""
        return {}

    def sign_transaction(self, tx):
        """Sign a transaction with the keypair."""
        return tx.sign([self._keypair])

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
            # Try to load keypair from treasury_keypair.json first
            from pathlib import Path
            keypair_path = Path(__file__).resolve().parents[2] / "data" / "treasury_keypair.json"

            wallet = None
            treasury_address = None

            if keypair_path.exists():
                try:
                    keypair = self._load_encrypted_keypair(keypair_path)
                    if keypair:
                        treasury_address = str(keypair.pubkey())
                        logger.info(f"Loaded treasury keypair: {treasury_address[:8]}...")

                        # Create a minimal wallet wrapper that works with TradingEngine
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

            # Create trading engine (start in live mode, not dry run)
            self._engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=False,  # Live trading
                max_positions=10,
            )

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

        try:
            # Resolve partial contract address if needed
            full_mint = await self._resolve_token_mint(token_mint, token_symbol)
            if not full_mint:
                return {
                    "success": False,
                    "error": f"Could not resolve token address for {token_symbol or token_mint}",
                    "tx_signature": "",
                }

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
            return partial_mint

        # Try to search by symbol using DexScreener
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                search_term = symbol or partial_mint
                url = f"https://api.dexscreener.com/latest/dex/search?q={search_term}"

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

        password = os.environ.get('JARVIS_WALLET_PASSWORD', '')
        if not password:
            logger.warning("JARVIS_WALLET_PASSWORD not set - cannot decrypt keypair")
            return None

        try:
            with open(keypair_path) as f:
                data = json.load(f)

            # Check if this is an encrypted format
            if 'encrypted_key' in data and 'salt' in data and 'nonce' in data:
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
