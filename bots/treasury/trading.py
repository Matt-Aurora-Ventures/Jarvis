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
from .scorekeeper import get_scorekeeper, Scorekeeper

# Import structured logging for comprehensive JSON logs
try:
    from core.logging import get_structured_logger, JsonFormatter
    STRUCTURED_LOGGING_AVAILABLE = True
except ImportError:
    STRUCTURED_LOGGING_AVAILABLE = False

# Import safe state management for race-condition-free file access
try:
    from core.safe_state import SafeState
    SAFE_STATE_AVAILABLE = True
except ImportError:
    SAFE_STATE_AVAILABLE = False
    SafeState = None

# Import centralized audit trail for security logging
try:
    from core.security.audit_trail import audit_trail, AuditEventType
    AUDIT_TRAIL_AVAILABLE = True
except ImportError:
    AUDIT_TRAIL_AVAILABLE = False
    audit_trail = None
    AuditEventType = None

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

# Import emergency stop mechanism
try:
    from core.trading.emergency_stop import get_emergency_stop_manager, StopLevel
    EMERGENCY_STOP_AVAILABLE = True
except ImportError:
    EMERGENCY_STOP_AVAILABLE = False
    get_emergency_stop_manager = None
    StopLevel = None

# Import enhanced risk management
try:
    from core.risk import RiskManager, AlertLevel, LimitType
    RISK_MANAGER_AVAILABLE = True
except ImportError:
    RISK_MANAGER_AVAILABLE = False
    RiskManager = None
    AlertLevel = None
    LimitType = None

# Import CoinGlass for liquidation data
try:
    from integrations.coinglass.client import CoinGlassClient
    COINGLASS_AVAILABLE = True
except ImportError:
    COINGLASS_AVAILABLE = False

# Import Bags.fm trade adapter for partner fee earning
try:
    from core.trading.bags_adapter import BagsTradeAdapter
    BAGS_AVAILABLE = True
except ImportError:
    BAGS_AVAILABLE = False
    BagsTradeAdapter = None

# Initialize structured logger if available, fallback to standard logger
if STRUCTURED_LOGGING_AVAILABLE:
    logger = get_structured_logger("jarvis.trading", service="trading_engine")
else:
    logger = logging.getLogger(__name__)


# Structured error logging integration for health bus
def _log_trading_error(error: Exception, context: str, metadata: dict = None):
    """Log error with structured data and track in error rate system."""
    try:
        from core.monitoring.supervisor_health_bus import log_component_error
        log_component_error(
            component="treasury_trading",
            error=error,
            context={"operation": context, **(metadata or {})},
            severity="error"
        )
    except ImportError:
        logger.error(f"[{context}] {error}", exc_info=True)


def _log_trading_event(event_type: str, message: str, data: dict = None):
    """Log trading event with structured data."""
    try:
        from core.monitoring.supervisor_health_bus import log_bot_event
        log_bot_event("treasury", event_type, message, data)
    except ImportError:
        logger.info(f"[{event_type}] {message}")


def _log_position_change(
    action: str,
    position_id: str,
    symbol: str,
    details: dict = None
):
    """
    Log all position changes with consistent formatting.

    Actions: OPEN, CLOSE, UPDATE, RECONCILE, ERROR
    """
    details = details or {}
    timestamp = datetime.utcnow().isoformat()

    # Build log message
    log_data = {
        "timestamp": timestamp,
        "action": action,
        "position_id": position_id,
        "symbol": symbol,
        **details
    }

    # Log to standard logger with consistent prefix
    if action == "OPEN":
        logger.info(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"amount=${details.get('amount_usd', 0):.2f}, "
            f"entry=${details.get('entry_price', 0):.6f}, "
            f"TP=${details.get('tp_price', 0):.6f}, SL=${details.get('sl_price', 0):.6f}"
        )
    elif action == "CLOSE":
        logger.info(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"P&L=${details.get('pnl_usd', 0):+.2f} ({details.get('pnl_pct', 0):+.1f}%), "
            f"exit=${details.get('exit_price', 0):.6f}, "
            f"reason={details.get('reason', 'unknown')}"
        )
    elif action == "UPDATE":
        logger.debug(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"price=${details.get('current_price', 0):.6f}, "
            f"unrealized_pnl=${details.get('unrealized_pnl', 0):+.2f}"
        )
    elif action == "ERROR":
        logger.error(
            f"[POSITION:{action}] {position_id} {symbol} - "
            f"error={details.get('error', 'unknown')}"
        )
    else:
        logger.info(f"[POSITION:{action}] {position_id} {symbol} - {details}")

    # Also send to trading event system
    _log_trading_event(f"POSITION_{action}", f"{symbol} position {action.lower()}", log_data)


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
    average_win_usd: float = 0.0
    average_loss_usd: float = 0.0
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
Avg Win: <code>${self.average_win_usd:+.2f}</code> | Avg Loss: <code>${self.average_loss_usd:.2f}</code>

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

    # State files - centralized under ~/.lifeos/trading/
    # Migration: Old files in bots/treasury/ will be auto-migrated on first access
    from core.state_paths import STATE_PATHS
    POSITIONS_FILE = STATE_PATHS.positions
    POSITIONS_FILE_SECONDARY = STATE_PATHS.trader_positions  # data/trader/positions.json
    HISTORY_FILE = STATE_PATHS.trading_dir / 'trade_history.json'
    AUDIT_LOG_FILE = STATE_PATHS.audit_log
    DAILY_VOLUME_FILE = STATE_PATHS.trading_dir / 'daily_volume.json'

    # CRITICAL: Spending caps to protect treasury (per guide)
    MAX_TRADE_USD = 100.0      # Maximum single trade size
    MAX_DAILY_USD = 500.0      # Maximum daily trading volume
    MAX_POSITION_PCT = 0.20    # Max 20% of portfolio in single position
    MAX_ALLOCATION_PER_TOKEN = None  # DISABLED: No maximum per-token allocation - allows unrestricted stacking
    ALLOW_STACKING = True  # ENABLED: Allow multiple positions in the same token

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
    ADMIN_USER_ID = int(os.environ.get("JARVIS_ADMIN_USER_ID", "8527130908"))

    # Position sizing by risk level (% of portfolio)
    POSITION_SIZE = {
        RiskLevel.CONSERVATIVE: 0.01,   # 1%
        RiskLevel.MODERATE: 0.02,       # 2%
        RiskLevel.AGGRESSIVE: 0.05,     # 5%
        RiskLevel.DEGEN: 0.10,          # 10%
    }

    # ==========================================================================
    # TOKEN SAFETY SYSTEM - HARDCODED REMEDIATIONS FROM PERFORMANCE AUDIT
    # ==========================================================================
    # Performance audit showed 3 catastrophic -99% losses from pump.fun tokens.
    # These tokens have no liquidity for stop loss execution.
    # ==========================================================================

    # ESTABLISHED TOKENS - Vetted, liquid, safe to trade with normal position sizes
    # These tokens have proven liquidity and legitimate projects
    ESTABLISHED_TOKENS = {
        # Major Solana tokens
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
        "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
        "So11111111111111111111111111111111111111112": "SOL",
        "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "MSOL",
        "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": "STSOL",
        "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
        "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": "RNDR",
        "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
        "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ": "W",
        "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4": "JTO",

        # WRAPPED MAJOR TOKENS - Cross-chain bridged assets (Portal/Wormhole)
        "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": "WETH",  # Wrapped ETH (Portal)
        "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh": "WBTC",  # Wrapped BTC (Portal)
        "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E": "WBTC_SOL",  # Wrapped BTC (Sollet)
        "FYfQ9uaRaYvRiaEGUmct45F9WKam3BYXArTrotnTNFXF": "WADA",  # Wrapped ADA (Portal)
        "A9mUU4qviSctJVPJdBJWkb28deg915LYJKrzQ19ji3FM": "WDOT",  # Wrapped DOT (Portal)
        "CWE8jPTUYhdCTZYWPTe1o5DFqfdjzWKc9WKz6PBjkgy8": "WAVAX", # Wrapped AVAX (Portal)
        "9bzWNhJcgbVnUPV1T1QMMLj9a4PEcXXPKzPNxMcGUP8n": "WMATIC", # Wrapped MATIC (Portal)
        "CDJWUqTcYTVAKXAVXoQZFes5JUFc7owSeq7eMQcDSbo5": "WLINK", # Wrapped LINK (Portal)
        "4wjPQJ6PrkC4dHhYghwJzGBVP78DkBzA2U3kHoFNBuhj": "WUNI",  # Wrapped UNI (Portal)
        "AUrMpCDYYcPuHhyNX8gEEqbmDPFUpBpHrNW3vPeCFn5Z": "WAAVE", # Wrapped AAVE (Portal)
        "EchesyfXePKdLtoiZSL8pBe8Myagyy8ZRqsACNCFGnvp": "WFIL",  # Wrapped FIL (Portal)
        "7i5KKsX2weiTkry7jA4ZwSuXGhs5eJBEjY8vVxR4pfRx": "GMT",   # STEPN
        "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": "RAY",   # Raydium
        "AFbX8oGjGpmVFywbVouvhQSRmiW2aR1mohfahi4Y2AdB": "GST",   # Green Satoshi Token
        "BRjpCHtyQLNCo8gqRUr8jtdAj5AjPYQaoqbvcZiHok1k": "devUSDC",  # Dev USDC
        "Saber2gLauYim4Mvftnrasomsv6NvAuncvMEZwcLpD1": "SBR",   # Saber
        "GENEtH5amGSi8kHAtQoezp1XEXwZJ8vcuePYnXdKrMYz": "GENE",  # Genopets
        "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE": "ORCA",  # Orca
        "MNDEFzGvMt87ueuHvVU9VcTqsAP5b3fTGPsHuuPA5ey": "MNDE",  # Marinade
        "kinXdEcpDQeHPEuQnqmUgtYykqKGVFq6CeVX5iAHJq6": "KIN",   # Kin

        # TOP 30 BY MARKET CAP (Solana ecosystem)
        "SHDWyBxihqiCj6YekG2GUr7wqKLeLAMK1gHZck9pL6y": "SHDW",  # Shadow
        "BLZEEuZUBVqFhj8adcCFPJvPVCiCyVmh3hkJMrU8KuJA": "BLZE",  # Blaze
        "TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6": "TNSR",  # Tensor
        "HxhWkVpk5NS4Ltg5nij2G671CKXFRKM5AGKUWZK3Q8KV": "HAWK",  # Hawksight
        "mb1eu7TzEc71KxDpsmsKoucSSuuoGLv1drys1oP2jh6": "MOBILE", # Helium Mobile
        "iotEVVZLEywoTn1QdwNPddxPWszn3zFhEot3MfL9fns": "IOT",   # Helium IOT
        "HNTkznmTnk98R9RnFMn6Y7Sbkg6bz5D7WTxo1sXX9G4F": "HNT",  # Helium

        # Tokenized equities (XStocks) - backed by real assets
        "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W": "SPYx",
        "XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB": "TSLAX",
        "Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh": "NVDAX",
        "Xsv9hRk1z5ystj9MhnA7Lq4vjSsLwzL2nxrwmwtD3re": "GLDx",
        "XsjQP3iMAaQ3kQScQKthQpx9ALRbjKAjQtHg6TFomoc": "TQQQx",
        "XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp": "AAPLx",
        "XsMGMDhxqnWAqtF4xk2Z5i4wJBhZnJ4Wk6c8XJNhE3J": "GOOGLx",
        "XsMSFTs3E5UT7cRUhP7sQDh9KRo6LGp5TE8yPkMiL5F": "MSFTx",
    }

    # HIGH RISK TOKEN PATTERNS - Require extra scrutiny and smaller positions
    # Pump.fun tokens CAN work but need careful analysis:
    # - Check liquidity before entry
    # - Use smaller position sizes
    # - Set tighter stop losses
    # - Monitor more frequently
    HIGH_RISK_PATTERNS = [
        "pump",     # pump.fun tokens - high risk, small positions only
    ]

    # BLOCKED TOKENS - Never trade these (stablecoins only)
    # These are not valid trading targets - we only trade volatile assets
    # NOTE: SOL/WSOL is NOT blocked - it's our base trading currency
    BLOCKED_TOKENS = {
        # USD-pegged stablecoins
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
        "BRjpCHtyQLNCo8gqRUr8jtdAj5AjPYQaoqbvcZiHok1k": "devUSDC",
        # Other stablecoins
        "USDH1SM1ojwWUga67PGrgFWUHibbjqMvuMaDkRJTgkX": "USDH",
        "7kbnvuGBxxj8AG9qp8Scn56muWGaRaFqxg1FsRp3PaFT": "UXD",
        "Dn4noZ5jgGfkntzcQSUZ8czkreiZ1ForXYoV2H8Dm7S1": "USDCet",  # Wormhole USDC
    }

    BLOCKED_SYMBOLS = {"USDC", "USDT", "USDH", "UXD", "BUSD", "DAI", "TUSD", "FRAX", "USDD", "devUSDC"}

    # MINIMUM REQUIREMENTS FOR HIGH-RISK TOKENS (pump.fun, new launches, etc.)
    MIN_LIQUIDITY_USD = 5000       # $5k minimum liquidity for any trade
    MIN_VOLUME_24H_USD = 2500      # $2.5k minimum daily volume
    MIN_TOKEN_AGE_HOURS = 1        # At least 1 hour old (not instant rugs)
    MAX_HIGH_RISK_POSITION_PCT = 0.15  # Max 15% of normal position for high-risk
    MAX_UNVETTED_POSITION_PCT = 0.25   # Max 25% of normal position for unvetted

    def __init__(
        self,
        wallet: SecureWallet,
        jupiter: JupiterClient,
        admin_user_ids: List[int] = None,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        max_positions: int = 50,
        dry_run: bool = True,  # Start in dry run mode
        enable_signals: bool = True,  # Enable advanced signal analysis
        use_bags: bool = None,  # Use Bags.fm for trading (earns partner fees)
        state_profile: Optional[str] = None,  # Isolate state per profile (e.g., demo)
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
            use_bags: Use Bags.fm as primary executor (env: USE_BAGS_TRADING)
        """
        self.wallet = wallet
        self.jupiter = jupiter
        self.admin_user_ids = admin_user_ids or []
        self.risk_level = risk_level
        self.max_positions = max_positions
        self.dry_run = dry_run

        # Optional per-profile state isolation (demo vs treasury)
        self._state_profile = (state_profile or "").strip().lower()
        if self._state_profile and self._state_profile != "treasury":
            self._configure_state_paths(self._state_profile)

        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Position] = []
        self.order_manager: Optional[LimitOrderManager] = None

        # Initialize Bags.fm adapter for partner fee earning
        # Bags routes trades through bags.fm first, falls back to Jupiter
        self.bags_adapter: Optional[BagsTradeAdapter] = None
        if use_bags is None:
            use_bags = os.environ.get("USE_BAGS_TRADING", "").lower() in ("1", "true", "yes")

        if use_bags and BAGS_AVAILABLE:
            try:
                self.bags_adapter = BagsTradeAdapter(
                    partner_code=os.environ.get("BAGS_PARTNER_CODE"),
                    enable_fallback=True,  # Fall back to Jupiter on failure
                    wallet_keypair=wallet.keypair if hasattr(wallet, 'keypair') else None,
                )
                logger.info("Bags.fm trade adapter initialized (earns partner fees)")
            except Exception as e:
                logger.warning(f"Failed to initialize Bags adapter: {e} - using Jupiter only")
        elif use_bags and not BAGS_AVAILABLE:
            logger.warning("USE_BAGS_TRADING enabled but Bags adapter not available")

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

        # Initialize enhanced risk management
        self.risk_manager: Optional[RiskManager] = None
        if RISK_MANAGER_AVAILABLE:
            self.risk_manager = RiskManager(enable_alerts=True)
            logger.info("Enhanced risk manager initialized")

        # CRITICAL: Mutex for trade execution to prevent race conditions from concurrent X/Telegram bot trades
        # Ensures only one trade executes at a time, protecting against position limit overruns
        self._trade_execution_lock = asyncio.Lock()

        # Load existing state
        self._load_state()

    def _configure_state_paths(self, profile: str) -> None:
        """Override state files for a non-treasury profile."""
        base_dir = Path.home() / ".lifeos" / profile
        trading_dir = base_dir / "trading"
        logs_dir = base_dir / "logs"
        trading_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        self.POSITIONS_FILE = trading_dir / "positions.json"
        self.HISTORY_FILE = trading_dir / "trade_history.json"
        self.AUDIT_LOG_FILE = logs_dir / "audit.jsonl"
        self.DAILY_VOLUME_FILE = trading_dir / "daily_volume.json"

        secondary_dir = Path(__file__).resolve().parents[2] / "data" / profile / "trader"
        secondary_dir.mkdir(parents=True, exist_ok=True)
        self.POSITIONS_FILE_SECONDARY = secondary_dir / "positions.json"

    # ==========================================================================
    # SWAP EXECUTION - Routes through Bags.fm (with Jupiter fallback) or Jupiter
    # ==========================================================================

    async def _execute_swap(
        self,
        quote: SwapQuote,
        input_mint: str = None,
        output_mint: str = None,
    ) -> SwapResult:
        """
        Execute a swap, routing through Bags.fm if available (earns partner fees).

        Falls back to Jupiter if Bags fails or isn't configured.

        Uses unified recovery engine for retries and circuit breaking.

        Args:
            quote: SwapQuote from Jupiter (used for Jupiter execution or as fallback)
            input_mint: Input token mint (optional, extracted from quote if not provided)
            output_mint: Output token mint (optional, extracted from quote if not provided)

        Returns:
            SwapResult with success status and transaction details
        """
        # Extract mints from quote if not provided
        if input_mint is None:
            input_mint = quote.input_mint
        if output_mint is None:
            output_mint = quote.output_mint

        # =====================================================================
        # RECOVERY ADAPTER - Unified retry/circuit-breaker handling
        # =====================================================================
        try:
            from core.recovery.adapters import TradingAdapter

            adapter = TradingAdapter()

            # Check if trading circuit is open (too many failures)
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
            adapter = None
            logger.debug("Recovery adapter not available, using direct execution")
        except Exception as e:
            adapter = None
            logger.warning(f"Recovery adapter error (continuing): {e}")

        # Try Bags.fm first if available (earns partner fees)
        if self.bags_adapter is not None:
            try:
                logger.info(f"Executing swap via Bags.fm: {input_mint[:8]}... -> {output_mint[:8]}...")

                signature, output_amount = await self.bags_adapter.execute_swap(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount=quote.in_amount,
                    slippage=quote.slippage_bps / 100.0,  # Convert bps to percentage
                )

                # Build SwapResult compatible with existing code
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

                # Record success with recovery adapter
                if adapter:
                    adapter.record_success("execute_swap_bags")

                return result

            except Exception as bags_error:
                logger.warning(f"Bags.fm swap failed, falling back to Jupiter: {bags_error}")
                # Record failure but don't trip circuit (fallback available)
                if adapter:
                    adapter.record_failure("execute_swap_bags", str(bags_error))
                # Fall through to Jupiter execution

        # Execute via Jupiter (fallback or primary if Bags not configured)
        result = await self.jupiter.execute_swap(quote, self.wallet)

        # Record result with recovery adapter
        if adapter:
            if result.success:
                adapter.record_success("execute_swap_jupiter")
            else:
                adapter.record_failure("execute_swap_jupiter", result.error or "Unknown")

        return result

    # ==========================================================================
    # TOKEN SAFETY METHODS - Protect against rug pulls and illiquid tokens
    # ==========================================================================

    def is_blocked_token(self, token_mint: str, token_symbol: str = "") -> Tuple[bool, str]:
        """
        Check if token is blocked from trading (stablecoins, WSOL, etc.).

        Returns:
            Tuple of (is_blocked, reason)
        """
        if token_mint in self.BLOCKED_TOKENS:
            name = self.BLOCKED_TOKENS[token_mint]
            return True, f"{name} is a stablecoin/blocked token - not tradeable"
        if token_symbol.upper() in self.BLOCKED_SYMBOLS:
            return True, f"{token_symbol} is a stablecoin - not tradeable"
        return False, ""

    def is_high_risk_token(self, token_mint: str) -> bool:
        """
        Check if token matches high-risk patterns (e.g., pump.fun).

        High-risk tokens aren't blocked but get:
        - Smaller position sizes (15% of normal)
        - Extra liquidity checks
        - Tighter monitoring

        Pump.fun tokens caused 3 big losses in our audit, but banning
        them entirely would miss opportunities. Instead, we trade smarter.
        """
        mint_lower = token_mint.lower()
        for pattern in self.HIGH_RISK_PATTERNS:
            if pattern in mint_lower:
                return True
        return False

    def is_established_token(self, token_mint: str) -> bool:
        """Check if token is in our vetted established tokens list."""
        return token_mint in self.ESTABLISHED_TOKENS

    def classify_token_risk(self, token_mint: str, token_symbol: str) -> str:
        """
        Classify token into risk tiers for position sizing.

        Returns:
            ESTABLISHED - Vetted tokens, full position size
            MID - Known symbols but not in whitelist, 50% position
            MICRO - Unknown tokens with liquidity, 25% position
            HIGH_RISK - Pump.fun and similar, 15% position + extra checks
        """
        # Established whitelist - these are safe
        if self.is_established_token(token_mint):
            return "ESTABLISHED"

        # XStocks pattern (starts with Xs) - backed assets
        if token_mint.startswith("Xs"):
            return "ESTABLISHED"

        # High-risk patterns (pump.fun etc) - trade with caution, not banned
        if self.is_high_risk_token(token_mint):
            return "HIGH_RISK"

        # Known major symbols (might be on different mint)
        major_symbols = ["BTC", "ETH", "SOL", "USDC", "USDT", "BONK", "WIF", "JUP", "PYTH"]
        if token_symbol.upper() in major_symbols:
            return "MID"

        # Tokenized equity symbols
        if token_symbol.upper().endswith("X") and len(token_symbol) <= 6:
            return "MID"

        # Everything else is micro cap risk
        return "MICRO"

    def get_risk_adjusted_position_size(
        self,
        token_mint: str,
        token_symbol: str,
        base_position_usd: float
    ) -> Tuple[float, str]:
        """
        Adjust position size based on token risk classification.

        Returns:
            Tuple of (adjusted_position_usd, risk_tier)
        """
        risk_tier = self.classify_token_risk(token_mint, token_symbol)

        if risk_tier == "ESTABLISHED":
            return base_position_usd, risk_tier  # Full size

        elif risk_tier == "MID":
            return base_position_usd * 0.50, risk_tier  # 50% size

        elif risk_tier == "HIGH_RISK":
            # Pump.fun and similar - small positions, not banned
            return base_position_usd * self.MAX_HIGH_RISK_POSITION_PCT, risk_tier  # 15% size

        else:  # MICRO
            return base_position_usd * self.MAX_UNVETTED_POSITION_PCT, risk_tier  # 25% size

    def _load_state(self):
        """Load positions and history from disk with file locking.

        Attempts to load from primary location first, falls back to secondary.
        Logs all position loading for debugging.
        """
        logger.info("Loading trading state...")

        # Use SafeState for race-condition-free access
        if SAFE_STATE_AVAILABLE:
            self._positions_state = SafeState(self.POSITIONS_FILE, default_value=[])
            self._history_state = SafeState(self.HISTORY_FILE, default_value=[])
            self._volume_state = SafeState(self.DAILY_VOLUME_FILE, default_value={})
            self._audit_state = SafeState(self.AUDIT_LOG_FILE, default_value=[])

            try:
                data = self._positions_state.read()
                for pos_data in data:
                    pos = Position.from_dict(pos_data)
                    self.positions[pos.id] = pos
                    logger.info(f"[LOAD] Position {pos.id}: {pos.token_symbol} - status={pos.status.value}, amount=${pos.amount_usd:.2f}")
            except Exception as e:
                logger.error(f"Failed to load positions from primary: {e}")
                # Try secondary location
                self._load_from_secondary()
            else:
                primary_missing = not self.POSITIONS_FILE.exists()
                primary_empty = self.POSITIONS_FILE.exists() and self.POSITIONS_FILE.stat().st_size == 0
                if (primary_missing or primary_empty) and self.POSITIONS_FILE_SECONDARY.exists() and not self.positions:
                    self._load_from_secondary()

            try:
                data = self._history_state.read()
                self.trade_history = [Position.from_dict(p) for p in data]
                logger.info(f"[LOAD] Trade history: {len(self.trade_history)} closed positions")
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
        else:
            # Fallback to original implementation
            if self.POSITIONS_FILE.exists():
                try:
                    with open(self.POSITIONS_FILE) as f:
                        data = json.load(f)
                        for pos_data in data:
                            pos = Position.from_dict(pos_data)
                            self.positions[pos.id] = pos
                            logger.info(f"[LOAD] Position {pos.id}: {pos.token_symbol} - status={pos.status.value}, amount=${pos.amount_usd:.2f}")
                except Exception as e:
                    logger.error(f"Failed to load positions from primary: {e}")
                    self._load_from_secondary()
            elif self.POSITIONS_FILE_SECONDARY.exists():
                # Primary doesn't exist, try secondary
                self._load_from_secondary()

            if self.HISTORY_FILE.exists():
                try:
                    with open(self.HISTORY_FILE) as f:
                        data = json.load(f)
                        self.trade_history = [Position.from_dict(p) for p in data]
                        logger.info(f"[LOAD] Trade history: {len(self.trade_history)} closed positions")
                except Exception as e:
                    logger.error(f"Failed to load history: {e}")

        # Log summary
        open_count = len([p for p in self.positions.values() if p.is_open])
        total_value = sum(p.amount_usd for p in self.positions.values() if p.is_open)
        logger.info(f"[LOAD] State loaded: {open_count} open positions, total value ${total_value:.2f}")

    def _load_from_secondary(self):
        """Load positions from secondary location (data/trader/positions.json)."""
        if self.POSITIONS_FILE_SECONDARY.exists():
            try:
                with open(self.POSITIONS_FILE_SECONDARY) as f:
                    data = json.load(f)
                    for pos_data in data:
                        pos = Position.from_dict(pos_data)
                        if pos.id not in self.positions:  # Don't overwrite existing
                            self.positions[pos.id] = pos
                            logger.info(f"[LOAD-SECONDARY] Position {pos.id}: {pos.token_symbol}")
                logger.info(f"[LOAD-SECONDARY] Recovered {len(data)} positions from secondary location")
            except Exception as e:
                logger.error(f"Failed to load positions from secondary: {e}")

    async def reconcile_with_onchain(self) -> Dict[str, Any]:
        """
        Reconcile stored positions with actual on-chain token balances.

        This method should be called on startup to detect discrepancies between
        what we think we hold vs what's actually in the wallet.

        Returns:
            Dict with reconciliation report:
            - matched: positions that match on-chain balances
            - orphaned: positions with no on-chain balance (may have been sold)
            - untracked: on-chain tokens not in our position list
            - mismatched: positions with different amounts than on-chain
        """
        logger.info("[RECONCILE] Starting on-chain reconciliation...")

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "matched": [],
            "orphaned": [],
            "untracked": [],
            "mismatched": [],
            "errors": []
        }

        try:
            # Get treasury address
            treasury = self.wallet.get_treasury()
            if not treasury:
                report["errors"].append("No treasury wallet configured")
                logger.error("[RECONCILE] No treasury wallet configured")
                return report

            # Get actual on-chain token balances
            onchain_balances = await self.wallet.get_token_balances(treasury.address)
            logger.info(f"[RECONCILE] Found {len(onchain_balances)} tokens on-chain")

            # Track which on-chain tokens we've matched
            matched_mints = set()

            # Check each stored position against on-chain
            for pos_id, position in list(self.positions.items()):
                if not position.is_open:
                    continue

                mint = position.token_mint
                onchain = onchain_balances.get(mint, {})
                onchain_balance = onchain.get('balance', 0)

                if onchain_balance <= 0:
                    # Position exists in state but no on-chain balance
                    report["orphaned"].append({
                        "position_id": pos_id,
                        "symbol": position.token_symbol,
                        "mint": mint,
                        "stored_amount": position.amount,
                        "stored_usd": position.amount_usd,
                        "reason": "No on-chain balance found"
                    })
                    logger.warning(f"[RECONCILE] ORPHANED: Position {pos_id} ({position.token_symbol}) has no on-chain balance")

                elif abs(onchain_balance - position.amount) / max(position.amount, 0.0001) > 0.05:
                    # Balance differs by more than 5%
                    report["mismatched"].append({
                        "position_id": pos_id,
                        "symbol": position.token_symbol,
                        "mint": mint,
                        "stored_amount": position.amount,
                        "onchain_amount": onchain_balance,
                        "difference_pct": ((onchain_balance - position.amount) / position.amount) * 100
                    })
                    logger.warning(
                        f"[RECONCILE] MISMATCH: Position {pos_id} ({position.token_symbol}) "
                        f"stored={position.amount:.6f} vs onchain={onchain_balance:.6f}"
                    )
                else:
                    # Position matches on-chain
                    report["matched"].append({
                        "position_id": pos_id,
                        "symbol": position.token_symbol,
                        "mint": mint,
                        "amount": position.amount
                    })
                    logger.debug(f"[RECONCILE] MATCHED: Position {pos_id} ({position.token_symbol})")

                matched_mints.add(mint)

            # Check for untracked tokens (on-chain but not in our positions)
            for mint, balance_info in onchain_balances.items():
                if mint not in matched_mints and balance_info.get('balance', 0) > 0:
                    # Skip SOL and stablecoins
                    if mint in [
                        "So11111111111111111111111111111111111111112",  # Wrapped SOL
                        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
                    ]:
                        continue

                    report["untracked"].append({
                        "mint": mint,
                        "balance": balance_info.get('balance', 0),
                        "decimals": balance_info.get('decimals', 0)
                    })
                    logger.warning(f"[RECONCILE] UNTRACKED: Token {mint} with balance {balance_info.get('balance', 0)}")

            # Log summary
            logger.info(
                f"[RECONCILE] Complete: {len(report['matched'])} matched, "
                f"{len(report['orphaned'])} orphaned, {len(report['untracked'])} untracked, "
                f"{len(report['mismatched'])} mismatched"
            )

            # Save reconciliation report
            try:
                report_path = self.STATE_PATHS.reconcile_report
                report_path.parent.mkdir(parents=True, exist_ok=True)
                with open(report_path, 'w') as f:
                    json.dump(report, f, indent=2)
                logger.info(f"[RECONCILE] Report saved to {report_path}")
            except Exception as e:
                logger.warning(f"[RECONCILE] Failed to save report: {e}")

            return report

        except Exception as e:
            logger.error(f"[RECONCILE] Error during reconciliation: {e}")
            report["errors"].append(str(e))
            _log_trading_error(e, "reconcile_with_onchain", {})
            return report

    async def auto_reconcile_orphaned(self, report: Dict[str, Any] = None) -> int:
        """
        Automatically close orphaned positions (positions with no on-chain balance).

        This happens when tokens are sold outside of Jarvis (e.g., manually via Phantom)
        or when TP/SL orders execute without our knowledge.

        Args:
            report: Reconciliation report from reconcile_with_onchain(), or None to run reconciliation first

        Returns:
            Number of positions auto-closed
        """
        if report is None:
            report = await self.reconcile_with_onchain()

        closed_count = 0

        for orphan in report.get("orphaned", []):
            pos_id = orphan["position_id"]
            if pos_id in self.positions:
                position = self.positions[pos_id]

                # Mark as closed with unknown exit price (use current price or 0)
                try:
                    current_price = await self.jupiter.get_token_price(position.token_mint)
                except Exception:
                    current_price = 0

                position.status = TradeStatus.CLOSED
                position.closed_at = datetime.utcnow().isoformat()
                position.exit_price = current_price

                # Calculate P&L if we have a price
                if current_price > 0:
                    position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)
                else:
                    # Assume total loss if no price available
                    position.pnl_pct = -100
                    position.pnl_usd = -position.amount_usd

                # Move to history
                self.trade_history.append(position)
                del self.positions[pos_id]
                closed_count += 1

                logger.info(
                    f"[RECONCILE] Auto-closed orphaned position {pos_id} ({position.token_symbol}): "
                    f"P&L ${position.pnl_usd:+.2f} ({position.pnl_pct:+.1f}%)"
                )

                # Log audit event
                self._log_audit("AUTO_CLOSE_ORPHANED", {
                    "position_id": pos_id,
                    "token": position.token_symbol,
                    "pnl_usd": position.pnl_usd,
                    "pnl_pct": position.pnl_pct,
                    "reason": "No on-chain balance"
                }, None, True)

        if closed_count > 0:
            self._save_state()
            logger.info(f"[RECONCILE] Auto-closed {closed_count} orphaned positions")

        return closed_count

    def _get_daily_volume(self) -> float:
        """Get total trading volume for today (UTC) with file locking."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        try:
            if SAFE_STATE_AVAILABLE and hasattr(self, '_volume_state'):
                data = self._volume_state.read()
                if data.get('date') == today:
                    return data.get('volume_usd', 0.0)
            elif self.DAILY_VOLUME_FILE.exists():
                with open(self.DAILY_VOLUME_FILE) as f:
                    data = json.load(f)
                    if data.get('date') == today:
                        return data.get('volume_usd', 0.0)
        except Exception as e:
            logger.debug(f"Failed to load daily volume: {e}")
        return 0.0

    def _add_daily_volume(self, amount_usd: float):
        """Add to daily trading volume with file locking."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        current = self._get_daily_volume()
        try:
            if SAFE_STATE_AVAILABLE and hasattr(self, '_volume_state'):
                self._volume_state.write({'date': today, 'volume_usd': current + amount_usd})
            else:
                with open(self.DAILY_VOLUME_FILE, 'w') as f:
                    json.dump({'date': today, 'volume_usd': current + amount_usd}, f)
        except Exception as e:
            logger.error(f"Failed to save daily volume: {e}")

    def _calculate_daily_pnl(self) -> float:
        """
        Calculate total P&L for today (realized + unrealized).

        Returns:
            Total daily P&L in USD (positive = profit, negative = loss)
        """
        today = datetime.utcnow().date()

        # Realized P&L from closed positions today
        realized_pnl = sum(
            p.pnl_usd for p in self.trade_history
            if p.status == TradeStatus.CLOSED and
            p.closed_at and
            datetime.fromisoformat(p.closed_at.replace('Z', '+00:00')).date() == today
        )

        # Unrealized P&L from positions opened today
        unrealized_pnl = sum(
            p.unrealized_pnl for p in self.positions.values()
            if p.is_open and
            datetime.fromisoformat(p.opened_at.replace('Z', '+00:00')).date() == today
        )

        return realized_pnl + unrealized_pnl

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

        Logs to both:
        1. Local JSON file for quick access
        2. Centralized audit trail for security monitoring
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

            # Also log to centralized audit trail for security monitoring
            if AUDIT_TRAIL_AVAILABLE and audit_trail:
                # Map action to audit event type
                event_type = AuditEventType.TRADE_EXECUTE
                if "WALLET" in action:
                    event_type = AuditEventType.WALLET_ACCESS
                elif "REJECTED" in action or "FAILED" in action:
                    event_type = AuditEventType.SECURITY_ALERT if not success else AuditEventType.TRADE_EXECUTE

                audit_trail.log(
                    event_type=event_type,
                    actor_id=str(user_id) if user_id else "system",
                    action=action,
                    resource_type="treasury_trade",
                    resource_id=details.get("position_id", details.get("token", "unknown")),
                    details=details,
                    success=success,
                    error_message=details.get("error", "") if not success else ""
                )

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def _save_state(self):
        """Save positions and history to disk with file locking.

        Persists to both primary (~/.lifeos/trading/) and secondary (data/trader/) locations
        for redundancy and tooling access.
        """
        positions_data = [p.to_dict() for p in self.positions.values()]
        history_data = [p.to_dict() for p in self.trade_history]

        try:
            if SAFE_STATE_AVAILABLE and hasattr(self, '_positions_state'):
                # Use SafeState for atomic writes with locking (primary location)
                self._positions_state.write(positions_data)
                self._history_state.write(history_data)
            else:
                # Fallback to original implementation (primary location)
                with open(self.POSITIONS_FILE, 'w') as f:
                    json.dump(positions_data, f, indent=2)
                with open(self.HISTORY_FILE, 'w') as f:
                    json.dump(history_data, f, indent=2)

            # Always persist to secondary location (data/trader/positions.json)
            try:
                self.POSITIONS_FILE_SECONDARY.parent.mkdir(parents=True, exist_ok=True)
                with open(self.POSITIONS_FILE_SECONDARY, 'w') as f:
                    json.dump(positions_data, f, indent=2)
                logger.debug(f"Positions saved to secondary location: {self.POSITIONS_FILE_SECONDARY}")
            except Exception as e2:
                logger.warning(f"Failed to save to secondary positions file: {e2}")

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            _log_trading_error(e, "save_state", {"positions_count": len(self.positions)})

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

        balance_result = await self.wallet.get_balance(treasury.address)
        # Defensive: Handle None returns from get_balance
        if balance_result is None:
            logger.warning("get_balance returned None, defaulting to (0.0, 0.0)")
            sol_balance, usd_value = 0.0, 0.0
        else:
            sol_balance, usd_value = balance_result

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
        # Count open positions (allow multiple per token)
        open_positions = [p for p in self.positions.values() if p.is_open]

        # Check if we'd exceed max positions
        if len(open_positions) >= self.max_positions:
            return TradeDirection.NEUTRAL, "Max positions reached"

        # Determine direction based on sentiment
        # TIGHTENED THRESHOLDS - Require higher conviction for entries
        # A+/A grades: score > 0.40 (was 0.35) - highest conviction plays only
        if sentiment_score > 0.40 and sentiment_grade in ['A+', 'A']:
            return TradeDirection.LONG, f"High conviction bullish (Grade {sentiment_grade}, score {sentiment_score:.2f})"

        # A-/B+ grades: score > 0.35 (tightened from 0.35 for lower grades)
        if sentiment_score > 0.35 and sentiment_grade in ['A-', 'B+']:
            return TradeDirection.LONG, f"Strong bullish signal (Grade {sentiment_grade}, score {sentiment_score:.2f})"

        # B grade: score > 0.30 (was 0.20 - much tighter now)
        if sentiment_score > 0.30 and sentiment_grade == 'B':
            return TradeDirection.LONG, f"Moderate bullish signal (Grade {sentiment_grade}, score {sentiment_score:.2f})"

        # Strong bearish - avoid these tokens
        if sentiment_score < -0.30:
            return TradeDirection.SHORT, f"Bearish signal - avoid (score {sentiment_score:.2f})"

        return TradeDirection.NEUTRAL, f"Signal not strong enough (score {sentiment_score:.2f}, grade {sentiment_grade})"

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

        # TIGHTENED: Weighted voting with higher confidence requirements
        long_score = sum(conf for _, dir, conf in signals if dir == 'long')
        short_score = sum(conf for _, dir, conf in signals if dir == 'short')
        
        # Require at least 2 agreeing signals OR 1 signal with >0.6 confidence
        min_signal_count = len([s for s in signals if s[1] == 'long']) if long_score > short_score else len([s for s in signals if s[1] == 'short'])
        avg_confidence = max(long_score, short_score) / max(min_signal_count, 1)

        # TIGHTENED: Require 0.6 threshold (was 0.5) for combined signals
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
        if os.environ.get("LIFEOS_KILL_SWITCH", "").lower() in ("1", "true", "yes", "on"):
            logger.warning("Trade rejected: kill switch active")
            return False, "Kill switch active - trading disabled", None

        # BLOCKED TOKEN CHECK - Reject stablecoins and non-tradeable tokens
        is_blocked, block_reason = self.is_blocked_token(token_mint, token_symbol)
        if is_blocked:
            logger.warning(f"Trade rejected: {block_reason}")
            return False, f"⛔ {block_reason}", None

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

        # ==========================================================================
        # HIGH-RISK TOKEN WARNING - Learn from performance audit, but don't ban
        # Pump.fun tokens caused 3 big losses, but we trade smarter now:
        # - Smaller position sizes (15% of normal)
        # - Extra liquidity checks
        # - Tighter stop loss monitoring
        # ==========================================================================
        if self.is_high_risk_token(token_mint):
            logger.warning(f"HIGH-RISK TOKEN: {token_symbol} is a pump.fun token - using 15% position size")

        # Classify token risk tier
        risk_tier = self.classify_token_risk(token_mint, token_symbol)
        logger.info(f"Token {token_symbol} classified as: {risk_tier}")

        # Check max positions limit (allow multiple positions per token)
        open_positions = [p for p in self.positions.values() if p.is_open]

        # Check for existing positions in this token
        existing_in_token = [p for p in open_positions if p.token_mint == token_mint]
        if existing_in_token:
            if not self.ALLOW_STACKING:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "duplicate",
                    "existing_positions": len(existing_in_token),
                }, user_id, False)
                return False, f"Already have position in {token_symbol} (stacking disabled)", None
            logger.info(f"STACKING: Adding to existing position in {token_symbol} (currently {len(existing_in_token)} position(s))")

        if len(open_positions) >= self.max_positions:
            self._log_audit("OPEN_POSITION_REJECTED", {"token": token_symbol, "reason": "max_positions"}, user_id, False)
            return False, "Maximum positions reached", None

        # Get current price
        current_price = await self.jupiter.get_token_price(token_mint)
        if current_price <= 0:
            self._log_audit("OPEN_POSITION_REJECTED", {"token": token_symbol, "reason": "no_price"}, user_id, False)
            return False, "Failed to get token price", None

        # LIQUIDITY CHECK - Reject extremely illiquid tokens
        # These are the ones that cause 100% losses when limit orders can't execute
        # FAIL-SAFE: For HIGH_RISK and MICRO tokens, reject if liquidity unavailable
        liquidity_verified = False
        try:
            token_info = await self.jupiter.get_token_info(token_mint)
            if token_info and hasattr(token_info, 'daily_volume'):
                daily_volume = getattr(token_info, 'daily_volume', 0) or 0
                if daily_volume > 0 and daily_volume < self.MIN_LIQUIDITY_USD:  # Use configurable minimum
                    logger.warning(f"Trade rejected: {token_symbol} has insufficient liquidity (${daily_volume:.0f}/day)")
                    self._log_audit("OPEN_POSITION_REJECTED", {
                        "token": token_symbol,
                        "reason": "low_liquidity",
                        "daily_volume": daily_volume,
                    }, user_id, False)
                    return False, f"⛔ Trade blocked: {token_symbol} has insufficient liquidity (${daily_volume:.0f}/day)", None
                if daily_volume >= self.MIN_LIQUIDITY_USD:
                    liquidity_verified = True
                    logger.debug(f"Liquidity OK for {token_symbol}: ${daily_volume:.0f}/day")
        except Exception as e:
            logger.warning(f"Could not check liquidity for {token_symbol}: {e}")

        # LIQUIDITY VERIFICATION - Log warning but don't block trades
        # DISABLED: Per user request, all risk limits are disabled
        # Previously blocked HIGH_RISK/MICRO tokens when liquidity couldn't be verified
        # Now just logs a warning and proceeds with the trade
        if not liquidity_verified and risk_tier in ("HIGH_RISK", "MICRO"):
            logger.warning(f"⚠️ Liquidity not verified for {risk_tier} token {token_symbol} - proceeding anyway (risk limits disabled)")
            self._log_audit("LIQUIDITY_UNVERIFIED", {
                "token": token_symbol,
                "risk_tier": risk_tier,
                "action": "proceeding",
            }, user_id, True)  # True = not an error, just informational

        # Get portfolio value for limit checks
        _, portfolio_usd = await self.get_portfolio_value()

        # INPUT VALIDATION - Security fix for amount_usd parameter
        if amount_usd is not None:
            # Validate amount_usd is numeric
            try:
                amount_usd = float(amount_usd)
            except (TypeError, ValueError):
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "invalid_amount",
                    "amount_usd": str(amount_usd),
                }, user_id, False)
                return False, "⛔ Invalid amount: must be a number", None

            # Validate amount_usd is positive
            if amount_usd <= 0:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "non_positive_amount",
                    "amount_usd": amount_usd,
                }, user_id, False)
                return False, "⛔ Invalid amount: must be positive", None

            # Validate amount_usd doesn't exceed maximum single trade size
            if amount_usd > self.MAX_TRADE_USD:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "amount_exceeds_max",
                    "amount_usd": amount_usd,
                    "max_trade_usd": self.MAX_TRADE_USD,
                }, user_id, False)
                return False, f"⛔ Invalid amount: ${amount_usd:.2f} exceeds max single trade ${self.MAX_TRADE_USD:.2f}", None

        # Calculate position size
        if not amount_usd:
            amount_usd = self.calculate_position_size(portfolio_usd)

        # ==========================================================================
        # RISK-ADJUSTED POSITION SIZING - Based on token risk classification
        # Established tokens: 100% of base size
        # Mid-tier: 50% of base size
        # Micro caps: 25% of base size (MAX_UNVETTED_POSITION_PCT)
        # ==========================================================================
        original_amount = amount_usd
        amount_usd, risk_tier = self.get_risk_adjusted_position_size(
            token_mint, token_symbol, amount_usd
        )

        if amount_usd == 0:
            # Should not reach here due to pump.fun check above, but safety net
            self._log_audit("OPEN_POSITION_REJECTED", {
                "token": token_symbol,
                "reason": "risk_too_high",
                "risk_tier": risk_tier,
            }, user_id, False)
            return False, f"⛔ Trade blocked: {token_symbol} classified as {risk_tier}", None

        if amount_usd < original_amount:
            logger.info(f"Position size reduced: ${original_amount:.2f} -> ${amount_usd:.2f} ({risk_tier})")

        # DISABLED: Per-token allocation cap (MAX_ALLOCATION_PER_TOKEN = None)
        # This allows unlimited stacking per token while still checking overall portfolio limits
        if self.MAX_ALLOCATION_PER_TOKEN is not None and portfolio_usd > 0:
            existing_token_usd = sum(p.amount_usd for p in existing_in_token)
            total_token_usd = existing_token_usd + amount_usd
            token_allocation_pct = total_token_usd / portfolio_usd
            if token_allocation_pct > self.MAX_ALLOCATION_PER_TOKEN:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "token_allocation",
                    "existing_token_usd": existing_token_usd,
                    "amount_usd": amount_usd,
                    "allocation_pct": token_allocation_pct,
                }, user_id, False)
                return False, (
                    f"Token allocation {token_allocation_pct*100:.1f}% exceeds max "
                    f"{self.MAX_ALLOCATION_PER_TOKEN*100:.0f}% for {token_symbol}"
                ), None

        # ENHANCED: Check comprehensive risk limits via RiskManager
        if self.risk_manager:
            # Calculate current daily P&L
            daily_pnl = self._calculate_daily_pnl()

            # Calculate token concentration
            existing_token_usd = sum(p.amount_usd for p in existing_in_token)
            total_token_exposure = existing_token_usd + amount_usd

            # Calculate total deployed capital
            deployed_capital = sum(p.amount_usd for p in open_positions) + amount_usd

            # Count today's trades
            today = datetime.utcnow().date()
            trades_today = len([
                p for p in self.trade_history
                if datetime.fromisoformat(p.opened_at.replace('Z', '+00:00')).date() == today
            ])

            # Check all risk limits
            all_passed, risk_alerts = self.risk_manager.check_all_limits(
                position_size=amount_usd,
                daily_loss=abs(min(daily_pnl, 0)),  # Only pass loss amount
                token_concentration={token_symbol: (total_token_exposure, portfolio_usd)},
                deployed_capital=deployed_capital,
                total_portfolio=portfolio_usd,
                trades_today=trades_today
            )

            # If circuit breaker is active, block all trades
            if self.risk_manager.circuit_breaker_active:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "circuit_breaker",
                }, user_id, False)
                return False, "🔴 CIRCUIT BREAKER ACTIVE - Trading halted. Contact admin to reset.", None

            # Block trade if any critical limit violated
            if not all_passed:
                critical_alerts = [a for a in risk_alerts if a.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY)]
                if critical_alerts:
                    alert_msg = critical_alerts[0].message
                    self._log_audit("OPEN_POSITION_REJECTED", {
                        "token": token_symbol,
                        "reason": "risk_limit",
                        "alert": alert_msg,
                        "amount_usd": amount_usd,
                    }, user_id, False)
                    return False, f"⛔ Risk limit exceeded: {alert_msg}", None

            # Log warning alerts but allow trade
            warning_alerts = [a for a in risk_alerts if a.level == AlertLevel.WARNING]
            if warning_alerts:
                for alert in warning_alerts:
                    logger.warning(f"Risk warning: {alert.message}")

        # CRITICAL: Check spending limits before proceeding (legacy checks)
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
            # Simulate trade - CRITICAL: Use lock to prevent concurrent modifications
            async with self._trade_execution_lock:
                position.status = TradeStatus.OPEN
                self.positions[position_id] = position
                self._save_state()

            # Track daily volume even in dry run
            self._add_daily_volume(amount_usd)

            # Log position change with consistent formatting
            _log_position_change("OPEN", position_id, token_symbol, {
                "amount_usd": amount_usd,
                "entry_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "sentiment_grade": sentiment_grade,
                "risk_tier": risk_tier,
                "dry_run": True,
                "user_id": user_id,
            })

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

            # Structured log event for position opening
            if STRUCTURED_LOGGING_AVAILABLE and hasattr(logger, 'log_event'):
                logger.log_event(
                    "POSITION_OPENED",
                    position_id=position_id,
                    symbol=token_symbol,
                    token_mint=token_mint,
                    amount_usd=amount_usd,
                    entry_price=current_price,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    sentiment_grade=sentiment_grade,
                    sentiment_score=sentiment_score,
                    risk_tier=risk_tier,
                    dry_run=True,
                    user_id=str(user_id) if user_id else None,
                )
            return True, f"[DRY RUN] Position opened", position

        # Execute real trade
        try:
            # Get quote for SOL -> token
            sol_amount = int(amount_usd / await self.jupiter.get_token_price(JupiterClient.SOL_MINT) * 1e9)

            # Use higher slippage for volatile/illiquid assets (tokenized stocks, indexes, etc.)
            # Default 50 bps is often too tight for xStocks and similar tokenized assets
            slippage = 200  # 2% slippage tolerance
            quote = await self.jupiter.get_quote(
                JupiterClient.SOL_MINT,
                token_mint,
                sol_amount,
                slippage_bps=slippage
            )

            if not quote:
                return False, "Failed to get swap quote", None

            # Execute swap (routes through Bags.fm if available, falls back to Jupiter)
            result = await self._execute_swap(quote)

            if not result.success:
                return False, f"Swap failed: {result.error}", None

            # Update position
            position.status = TradeStatus.OPEN
            position.amount = quote.output_amount_ui

            # Set up TP/SL orders
            if self.order_manager:
                # Get token decimals for correct amount calculation
                token_info = await self.jupiter.get_token_info(token_mint)
                token_decimals = token_info.decimals if token_info else 9
                amount_smallest_unit = int(position.amount * (10 ** token_decimals))

                tp_id = await self.order_manager.create_take_profit(
                    token_mint,
                    amount_smallest_unit,
                    tp_price
                )
                sl_id = await self.order_manager.create_stop_loss(
                    token_mint,
                    amount_smallest_unit,
                    sl_price
                )
                position.tp_order_id = tp_id
                position.sl_order_id = sl_id

            # CRITICAL: Use lock to prevent concurrent modifications during position registration
            async with self._trade_execution_lock:
                self.positions[position_id] = position
                self._save_state()

            # Track daily volume
            self._add_daily_volume(amount_usd)

            # Log position change with consistent formatting
            _log_position_change("OPEN", position_id, token_symbol, {
                "amount_usd": amount_usd,
                "entry_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "sentiment_grade": sentiment_grade,
                "risk_tier": risk_tier,
                "tx_signature": result.signature,
                "dry_run": False,
                "user_id": user_id,
            })

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

            # Structured log event for live trade
            if STRUCTURED_LOGGING_AVAILABLE and hasattr(logger, 'log_event'):
                logger.log_event(
                    "POSITION_OPENED",
                    position_id=position_id,
                    symbol=token_symbol,
                    token_mint=token_mint,
                    amount_usd=amount_usd,
                    entry_price=current_price,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    sentiment_grade=sentiment_grade,
                    sentiment_score=sentiment_score,
                    risk_tier=risk_tier,
                    tx_signature=result.signature,
                    dry_run=False,
                    user_id=str(user_id) if user_id else None,
                )
            
            # Track in scorekeeper for persistent P&L tracking
            try:
                scorekeeper = get_scorekeeper()
                scorekeeper.open_position(
                    position_id=position_id,
                    symbol=token_symbol,
                    token_mint=token_mint,
                    entry_price=current_price,
                    entry_amount_sol=amount_usd / await self.jupiter.get_token_price(JupiterClient.SOL_MINT),
                    entry_amount_tokens=position.amount,
                    take_profit_price=tp_price,
                    stop_loss_price=sl_price,
                    tp_order_id=position.tp_order_id,
                    sl_order_id=position.sl_order_id,
                    tx_signature=result.signature,
                    user_id=user_id or 0,
                )
            except Exception as e:
                logger.warning(f"Failed to track in scorekeeper: {e}")
            
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
        # SECURITY FIX - Strict admin check prevents bypass when admin list is empty
        # Old logic: if admin_user_ids: check auth (allowed anyone when list empty)
        # New logic: ALWAYS check auth, warn if list is empty
        if not self.admin_user_ids:
            logger.warning("SECURITY WARNING: admin_user_ids is empty - no users can close positions")
            self._log_audit("CLOSE_POSITION_REJECTED", {
                "position_id": position_id,
                "reason": "no_admins_configured",
            }, user_id, False)
            return False, "⛔ No admins configured - cannot close positions"

        if not user_id or not self.is_admin(user_id):
            self._log_audit("CLOSE_POSITION_REJECTED", {
                "position_id": position_id,
                "reason": "unauthorized",
            }, user_id, False)
            return False, "⛔ Unauthorized - admin access required"

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

            # CRITICAL: Use lock to prevent concurrent close operations
            async with self._trade_execution_lock:
                # Move to history
                self.trade_history.append(position)
                del self.positions[position_id]
                self._save_state()

            # Log position change with consistent formatting
            _log_position_change("CLOSE", position_id, position.token_symbol, {
                "entry_price": position.entry_price,
                "exit_price": current_price,
                "pnl_usd": position.pnl_usd,
                "pnl_pct": position.pnl_pct,
                "reason": reason,
                "dry_run": True,
                "user_id": user_id,
            })

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

            # Structured log event for dry run close
            if STRUCTURED_LOGGING_AVAILABLE and hasattr(logger, 'log_event'):
                logger.log_event(
                    "POSITION_CLOSED",
                    position_id=position_id,
                    symbol=position.token_symbol,
                    token_mint=position.token_mint,
                    entry_price=position.entry_price,
                    exit_price=current_price,
                    pnl_usd=position.pnl_usd,
                    pnl_pct=position.pnl_pct,
                    reason=reason,
                    dry_run=True,
                    user_id=str(user_id) if user_id else None,
                )
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
                position.exit_price = current_price
                position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100 if current_price > 0 else -100
                position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)
                self.trade_history.append(position)
                del self.positions[position_id]
                self._save_state()

                # Log position change with consistent formatting
                _log_position_change("CLOSE", position_id, position.token_symbol, {
                    "entry_price": position.entry_price,
                    "exit_price": current_price,
                    "pnl_usd": position.pnl_usd,
                    "pnl_pct": position.pnl_pct,
                    "reason": "no_balance",
                    "dry_run": False,
                    "user_id": user_id,
                })

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

            # Use higher slippage for closing (2%) - same as opening
            quote = await self.jupiter.get_quote(
                position.token_mint,
                JupiterClient.SOL_MINT,
                amount,
                slippage_bps=200  # 2% slippage tolerance
            )

            if not quote:
                self._log_audit("CLOSE_POSITION_FAILED", {
                    "position_id": position_id,
                    "token": position.token_symbol,
                    "error": "no_quote",
                }, user_id, False)
                return False, "Failed to get close quote"

            # Execute swap (routes through Bags.fm if available, falls back to Jupiter)
            result = await self._execute_swap(quote)

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

            # Log position change with consistent formatting
            _log_position_change("CLOSE", position_id, position.token_symbol, {
                "entry_price": position.entry_price,
                "exit_price": current_price,
                "pnl_usd": position.pnl_usd,
                "pnl_pct": position.pnl_pct,
                "reason": reason,
                "tx_signature": result.signature,
                "dry_run": False,
                "user_id": user_id,
            })

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

            # Structured log event for live close
            if STRUCTURED_LOGGING_AVAILABLE and hasattr(logger, 'log_event'):
                logger.log_event(
                    "POSITION_CLOSED",
                    position_id=position_id,
                    symbol=position.token_symbol,
                    token_mint=position.token_mint,
                    entry_price=position.entry_price,
                    exit_price=current_price,
                    pnl_usd=position.pnl_usd,
                    pnl_pct=position.pnl_pct,
                    reason=reason,
                    tx_signature=result.signature,
                    dry_run=False,
                    user_id=str(user_id) if user_id else None,
                )

            # Track in scorekeeper
            try:
                scorekeeper = get_scorekeeper()
                # Determine close type based on price vs TP/SL
                close_type = "manual"
                if position.exit_price >= position.take_profit_price:
                    close_type = "tp"
                elif position.exit_price <= position.stop_loss_price:
                    close_type = "sl"
                
                sol_price = await self.jupiter.get_token_price(JupiterClient.SOL_MINT)
                exit_sol = position.pnl_usd / sol_price if sol_price > 0 else 0
                
                scorekeeper.close_position(
                    position_id=position_id,
                    exit_price=position.exit_price,
                    exit_amount_sol=exit_sol,
                    close_type=close_type,
                    tx_signature=result.signature,
                )
            except Exception as e:
                logger.warning(f"Failed to track close in scorekeeper: {e}")
            
            return True, f"Closed: {result.signature}, P&L: ${position.pnl_usd:+.2f}"

        except Exception as e:
            self._log_audit("CLOSE_POSITION_FAILED", {
                "position_id": position_id,
                "error": str(e),
            }, user_id, False)
            logger.error(f"Failed to close position: {e}")
            return False, f"Error: {str(e)}"

    async def update_positions(self):
        """Update current prices and unrealized PnL for all open positions."""
        for position in self.positions.values():
            if position.is_open:
                price = await self.jupiter.get_token_price(position.token_mint)
                if price > 0:
                    position.current_price = price
                    # Calculate unrealized PnL
                    if position.entry_price > 0:
                        position.pnl_pct = ((price - position.entry_price) / position.entry_price) * 100
                        position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)

        self._save_state()

    async def monitor_stop_losses(self) -> List[Dict[str, Any]]:
        """
        Active stop loss monitoring - catches positions that miss their limit orders.

        For illiquid tokens, Jupiter limit orders may never fill. This method
        actively checks prices and force-closes positions that have breached SL.

        Returns:
            List of closed positions with their P&L
        """
        closed_positions = []
        positions_to_close = []

        # First pass: identify positions that need closing
        for pos_id, position in list(self.positions.items()):
            if not position.is_open:
                continue

            # Get current price
            current_price = await self.jupiter.get_token_price(position.token_mint)
            if current_price <= 0:
                logger.warning(f"Could not get price for {position.token_symbol} - skipping SL check")
                continue

            position.current_price = current_price

            # Check if stop loss breached (for LONG positions)
            if position.direction == TradeDirection.LONG:
                if current_price <= position.stop_loss_price:
                    pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    logger.warning(
                        f"STOP LOSS BREACHED: {position.token_symbol} | "
                        f"Current: ${current_price:.8f} <= SL: ${position.stop_loss_price:.8f} | "
                        f"P&L: {pnl_pct:+.1f}%"
                    )
                    positions_to_close.append((pos_id, position, current_price, "SL_BREACH"))

                # Also check for extreme loss (>90% down) even if SL wasn't set properly
                elif current_price < position.entry_price * 0.1:  # Down >90%
                    pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    logger.warning(
                        f"EMERGENCY CLOSE: {position.token_symbol} down {pnl_pct:.1f}% | "
                        f"Entry: ${position.entry_price:.8f} -> ${current_price:.8f}"
                    )
                    positions_to_close.append((pos_id, position, current_price, "EMERGENCY_90PCT"))

                # Check for take profit hit
                elif current_price >= position.take_profit_price:
                    pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    logger.info(
                        f"TAKE PROFIT HIT: {position.token_symbol} | "
                        f"Current: ${current_price:.8f} >= TP: ${position.take_profit_price:.8f} | "
                        f"P&L: {pnl_pct:+.1f}%"
                    )
                    positions_to_close.append((pos_id, position, current_price, "TP_HIT"))

        # Second pass: close positions
        for pos_id, position, exit_price, reason in positions_to_close:
            try:
                # Calculate P&L
                pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
                pnl_usd = position.amount_usd * (pnl_pct / 100)

                # Update position
                position.status = TradeStatus.CLOSED
                position.closed_at = datetime.utcnow().isoformat()
                position.exit_price = exit_price
                position.pnl_pct = pnl_pct
                position.pnl_usd = pnl_usd

                # Cancel any pending limit orders
                if self.order_manager:
                    if position.tp_order_id:
                        try:
                            await self.order_manager.cancel_order(position.tp_order_id)
                        except Exception:
                            pass
                    if position.sl_order_id:
                        try:
                            await self.order_manager.cancel_order(position.sl_order_id)
                        except Exception:
                            pass

                # If not dry run, execute the actual sell
                if not self.dry_run:
                    try:
                        balances = await self.wallet.get_token_balances()
                        token_balance = balances.get(position.token_mint, {}).get('balance', 0)

                        if token_balance > 0:
                            token_info = await self.jupiter.get_token_info(position.token_mint)
                            decimals = token_info.decimals if token_info else 9
                            amount = int(token_balance * (10 ** decimals))

                            quote = await self.jupiter.get_quote(
                                position.token_mint,
                                JupiterClient.SOL_MINT,
                                amount,
                                slippage_bps=500  # 5% slippage for emergency closes
                            )

                            if quote:
                                # Execute swap (routes through Bags.fm if available)
                                result = await self._execute_swap(quote)
                                if result.success:
                                    logger.info(f"Sold {position.token_symbol} via {reason}: {result.signature}")
                    except Exception as sell_err:
                        _log_trading_error(sell_err, "sell_position", {
                            "symbol": position.token_symbol,
                            "amount": str(amount),
                            "reason": reason,
                        })

                # Move to history
                self.trade_history.append(position)
                del self.positions[pos_id]

                # Audit log
                self._log_audit(f"CLOSE_POSITION_{reason}", {
                    "position_id": pos_id,
                    "token": position.token_symbol,
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "sl_price": position.stop_loss_price,
                    "pnl_usd": pnl_usd,
                    "pnl_pct": pnl_pct,
                    "reason": reason,
                }, None, True)

                closed_positions.append({
                    "position_id": pos_id,
                    "symbol": position.token_symbol,
                    "reason": reason,
                    "pnl_usd": pnl_usd,
                    "pnl_pct": pnl_pct,
                })

                logger.info(
                    f"Closed {position.token_symbol} via {reason}: "
                    f"P&L ${pnl_usd:+.2f} ({pnl_pct:+.1f}%)"
                )

            except Exception as e:
                _log_trading_error(e, "close_position", {"position_id": pos_id})

        if closed_positions:
            self._save_state()

        return closed_positions

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

    def get_risk_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current risk status and alerts.

        Returns:
            Dict with risk metrics and active alerts, or None if risk manager unavailable
        """
        if not self.risk_manager:
            return None

        open_positions = self.get_open_positions()
        daily_pnl = self._calculate_daily_pnl()

        # Calculate portfolio peak (simplified - use current portfolio + max loss)
        from asyncio import get_event_loop
        try:
            loop = get_event_loop()
            _, portfolio_value = loop.run_until_complete(self.get_portfolio_value())
        except:
            portfolio_value = 0.0

        portfolio_peak = max(portfolio_value, portfolio_value - daily_pnl if daily_pnl < 0 else portfolio_value)

        # Get risk metrics
        metrics = self.risk_manager.get_risk_metrics(
            positions=open_positions,
            daily_pnl=daily_pnl,
            portfolio_peak=portfolio_peak,
            current_portfolio=portfolio_value
        )

        # Get active alerts
        alerts = self.risk_manager.get_active_alerts()

        return {
            'metrics': metrics.to_dict(),
            'alerts': [
                {
                    'level': a.level.value,
                    'type': a.limit_type.value,
                    'message': a.message,
                    'action_required': a.action_required
                }
                for a in alerts
            ],
            'circuit_breaker_active': self.risk_manager.circuit_breaker_active,
            'limits': self.risk_manager.get_limit_config()
        }

    async def initialize_order_manager(self):
        """Initialize the limit order manager with position closure callback."""
        self.order_manager = LimitOrderManager(
            self.jupiter,
            self.wallet,
            on_order_filled=self._handle_order_filled
        )
        await self.order_manager.start_monitoring()

    async def _handle_order_filled(
        self,
        order_id: str,
        order_type: str,
        token_mint: str,
        exit_price: float,
        output_amount: float,
        tx_signature: str
    ):
        """
        Handle TP/SL order filled callback.

        Closes the position and updates P&L tracking.
        """
        # Find position by token_mint
        position = None
        position_id = None
        for pid, pos in self.positions.items():
            if pos.token_mint == token_mint and pos.is_open:
                position = pos
                position_id = pid
                break

        if not position:
            logger.warning(f"Order {order_id} filled but no matching position found for {token_mint[:8]}...")
            return

        # Calculate P&L
        pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
        pnl_usd = position.amount_usd * (pnl_pct / 100)

        # Determine close type
        close_type = "tp" if order_type == "TAKE_PROFIT" else "sl"

        # Update position
        position.status = TradeStatus.CLOSED
        position.closed_at = datetime.utcnow().isoformat()
        position.exit_price = exit_price
        position.pnl_pct = pnl_pct
        position.pnl_usd = pnl_usd

        # Cancel the other order (TP cancelled SL or vice versa)
        if self.order_manager:
            other_order_id = position.sl_order_id if order_type == "TAKE_PROFIT" else position.tp_order_id
            if other_order_id:
                await self.order_manager.cancel_order(other_order_id)

        # Move to history
        self.trade_history.append(position)
        del self.positions[position_id]
        self._save_state()

        # Update scorekeeper
        try:
            scorekeeper = get_scorekeeper()
            sol_price = await self.jupiter.get_token_price(JupiterClient.SOL_MINT)
            exit_amount_sol = output_amount if sol_price <= 0 else output_amount

            scorekeeper.close_position(
                position_id=position_id,
                exit_price=exit_price,
                exit_amount_sol=exit_amount_sol,
                close_type=close_type,
                tx_signature=tx_signature
            )
        except Exception as e:
            logger.warning(f"Failed to update scorekeeper: {e}")

        # Audit log
        self._log_audit(f"CLOSE_POSITION_{order_type}", {
            "position_id": position_id,
            "token": position.token_symbol,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
            "order_id": order_id,
            "tx_signature": tx_signature,
        }, None, True)

        logger.info(
            f"Position {position_id} closed via {order_type}: "
            f"{position.token_symbol} P&L ${pnl_usd:+.2f} ({pnl_pct:+.1f}%)"
        )

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
                    if resp.status != 200:
                        logger.warning(f"RPC getBalance failed with status {resp.status}")
                        return 0.0, 0.0

                    data = await resp.json()
                    lamports = data.get("result", {}).get("value", 0)
                    sol_balance = lamports / 1e9

                    # Get SOL price - CoinGecko primary (reliable), DexScreener backup
                    sol_price = 0.0
                    try:
                        cg_url = "https://api.coingecko.com/api/v3/simple/price"
                        params = {"ids": "solana", "vs_currencies": "usd"}
                        async with session.get(cg_url, params=params) as cg_resp:
                            if cg_resp.status == 200:
                                cg_data = await cg_resp.json()
                                sol_price = float(cg_data.get("solana", {}).get("usd", 0) or 0)
                    except Exception:
                        pass  # Silent - will try fallback

                    if sol_price <= 0:
                        try:
                            sol_mint = "So11111111111111111111111111111111111111112"
                            ds_url = f"https://api.dexscreener.com/latest/dex/tokens/{sol_mint}"
                            async with session.get(ds_url) as ds_resp:
                                if ds_resp.status == 200:
                                    ds_data = await ds_resp.json()
                                    pairs = ds_data.get("pairs") or []
                                    sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                                    if sol_pairs:
                                        best = max(sol_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                        sol_price = float(best.get("priceUsd") or 0)
                        except Exception:
                            pass  # Silent fallback failure

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

    _instances: Dict[str, "TreasuryTrader"] = {}

    def __new__(cls, profile: str = "treasury"):
        """Singleton per profile (treasury, demo, etc.)."""
        key = (profile or "treasury").strip().lower()
        if key not in cls._instances:
            inst = super().__new__(cls)
            inst._profile = key
            inst._env_prefix = "" if key == "treasury" else f"{key.upper()}_"
            inst._engine = None
            inst._initialized = False
            inst._live_mode = False
            cls._instances[key] = inst
        return cls._instances[key]

    def __init__(self, profile: str = "treasury"):
        """No-op; profile config is handled in __new__."""
        pass

    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Read env var with profile prefix fallback."""
        if self._env_prefix:
            value = os.environ.get(f"{self._env_prefix}{key}")
            if value not in (None, ""):
                return value
        return os.environ.get(key, default)

    def _get_wallet_password(self) -> Optional[str]:
        """Resolve wallet password with profile-aware env keys."""
        for key in ("TREASURY_WALLET_PASSWORD", "JARVIS_WALLET_PASSWORD", "WALLET_PASSWORD"):
            value = self._get_env(key)
            if value:
                return value
        return None

    def _get_wallet_dir(self) -> Path:
        """Resolve wallet directory for this profile."""
        custom_dir = self._get_env("WALLET_DIR", "")
        if custom_dir:
            return Path(custom_dir).expanduser()
        if self._profile == "treasury":
            return SecureWallet.WALLET_DIR
        root = Path(__file__).resolve().parents[2]
        return root / "bots" / "treasury" / f".wallets-{self._profile}"

    def _default_keypair_path(self) -> Path:
        """Default keypair path for the profile."""
        root = Path(__file__).resolve().parents[2]
        if self._profile == "treasury":
            return root / "data" / "treasury_keypair.json"
        return root / "data" / f"{self._profile}_treasury_keypair.json"

    async def _ensure_initialized(self) -> Tuple[bool, str]:
        """Initialize wallet and jupiter client if not already done."""
        if self._initialized and self._engine:
            return True, "Already initialized"

        try:
            wallet = None
            treasury_address = None
            keypair = None

            # Use centralized KeyManager for treasury profile only
            if self._profile == "treasury":
                try:
                    from core.security.key_manager import get_key_manager
                    key_manager = get_key_manager()
                    keypair = key_manager.load_treasury_keypair()

                    if keypair:
                        treasury_address = str(keypair.pubkey())
                        wallet = _SimpleWallet(keypair, treasury_address)
                        logger.info(f"Loaded treasury via KeyManager: {treasury_address[:8]}...")
                except ImportError:
                    logger.warning("KeyManager not available, using legacy loader")

            # Fallback to legacy loading if KeyManager not available or profile is non-treasury
            if not wallet:
                root = Path(__file__).resolve().parents[2]
                env_paths = (root / "tg_bot" / ".env", root / ".env")
                try:
                    from dotenv import load_dotenv
                    for env_path in env_paths:
                        if env_path.exists():
                            load_dotenv(env_path, override=False)
                except Exception:
                    pass

                if not self._get_wallet_password():
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

                env_path_str = (self._get_env("TREASURY_KEYPAIR_PATH", "") or self._get_env("TREASURY_WALLET_PATH", "")).strip()
                keypair_path = Path(env_path_str).expanduser() if env_path_str else self._default_keypair_path()

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
                wallet_password = self._get_wallet_password()
                if not wallet_password:
                    logger.warning("Wallet password not set - running in simulation mode")
                    return False, "No wallet found - check treasury_keypair.json or wallet password env var"

                try:
                    secure_wallet = SecureWallet(
                        master_password=wallet_password,
                        wallet_dir=self._get_wallet_dir(),
                    )
                    treasury = secure_wallet.get_treasury()
                    if treasury:
                        wallet = secure_wallet
                        treasury_address = treasury.address
                except Exception as wallet_err:
                    logger.warning(f"SecureWallet init failed: {wallet_err}")

            if not wallet:
                return False, "No treasury wallet found - create data/treasury_keypair.json"

            # Initialize Jupiter client (allow profile-specific RPC)
            rpc_url = self._get_env("SOLANA_RPC_URL", None)
            jupiter = JupiterClient(rpc_url=rpc_url)

            admin_ids = []
            admin_ids_str = self._get_env("TREASURY_ADMIN_IDS") or self._get_env("TELEGRAM_ADMIN_IDS", "")
            if admin_ids_str:
                admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

            # Create trading engine (respect TREASURY_LIVE_MODE)
            live_mode = str(self._get_env("TREASURY_LIVE_MODE", "false")).lower() in ("1", "true", "yes", "on")
            self._live_mode = live_mode
            use_bags_env = str(self._get_env("USE_BAGS_TRADING", "")).lower() in ("1", "true", "yes", "on")
            use_bags = True if (self._profile != "treasury") else use_bags_env
            self._engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=not live_mode,
                max_positions=50,  # Increased from 10 to support more concurrent positions
                admin_user_ids=admin_ids,
                use_bags=use_bags,
                state_profile=self._profile if self._profile != "treasury" else None,
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
        sentiment_grade: str = "B",
    ) -> Dict[str, Any]:
        """
        Execute a buy trade with take profit and stop loss.

        Args:
            token_mint: Token contract address (can be partial)
            amount_sol: Amount in SOL to spend
            take_profit_price: Take profit target price
            stop_loss_price: Stop loss target price
            token_symbol: Token symbol for logging
            user_id: User ID for authorization
            sentiment_grade: Sentiment grade for TP/SL config (A, B, C, etc.)

        Returns:
            Dict with success, tx_signature, error, and message
        """
        # Check emergency stop FIRST (before any initialization)
        if EMERGENCY_STOP_AVAILABLE:
            emergency_manager = get_emergency_stop_manager()
            allowed, reason = emergency_manager.is_trading_allowed(token_mint)
            if not allowed:
                logger.warning(f"Trade blocked by emergency stop: {reason}")
                return {
                    "success": False,
                    "error": f"🚨 EMERGENCY STOP: {reason}",
                    "tx_signature": "",
                }

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
                sentiment_grade=sentiment_grade,  # Use actual grade from sentiment analysis
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

    async def monitor_and_close_breached_positions(self) -> List[Dict[str, Any]]:
        """
        Check all positions and close any that have breached their stop loss.

        Returns list of closed positions with P&L.
        """
        initialized, msg = await self._ensure_initialized()
        if not initialized:
            return []
        return await self._engine.monitor_stop_losses()

    async def get_position_health(self) -> Dict[str, Any]:
        """
        Get health status of all positions.

        Returns:
            Dict with overall health and per-position status
        """
        initialized, _ = await self._ensure_initialized()
        if not initialized:
            return {"healthy": False, "error": "Not initialized"}

        positions = self._engine.get_open_positions()
        if not positions:
            return {"healthy": True, "positions": [], "alerts": []}

        alerts = []
        position_status = []

        for pos in positions:
            # Calculate unrealized P&L
            if pos.entry_price > 0:
                pnl_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
            else:
                pnl_pct = 0

            status = "OK"
            if pos.current_price <= pos.stop_loss_price:
                status = "SL_BREACHED"
                alerts.append(f"{pos.token_symbol} has breached SL ({pnl_pct:+.1f}%)")
            elif pnl_pct <= -50:
                status = "CRITICAL"
                alerts.append(f"{pos.token_symbol} down {pnl_pct:.1f}%")
            elif pnl_pct <= -20:
                status = "WARNING"
            elif pos.current_price >= pos.take_profit_price:
                status = "TP_HIT"
                alerts.append(f"{pos.token_symbol} hit TP ({pnl_pct:+.1f}%)")

            position_status.append({
                "id": pos.id,
                "symbol": pos.token_symbol,
                "entry": pos.entry_price,
                "current": pos.current_price,
                "pnl_pct": pnl_pct,
                "tp": pos.take_profit_price,
                "sl": pos.stop_loss_price,
                "status": status,
            })

        return {
            "healthy": len(alerts) == 0,
            "positions": position_status,
            "alerts": alerts,
        }
