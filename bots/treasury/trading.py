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

    POSITIONS_FILE = Path(__file__).parent / '.positions.json'
    HISTORY_FILE = Path(__file__).parent / '.trade_history.json'
    AUDIT_LOG_FILE = Path(__file__).parent / '.audit_log.json'
    DAILY_VOLUME_FILE = Path(__file__).parent / '.daily_volume.json'

    # CRITICAL: Spending caps to protect treasury (per guide)
    MAX_TRADE_USD = 100.0      # Maximum single trade size
    MAX_DAILY_USD = 500.0      # Maximum daily trading volume
    MAX_POSITION_PCT = 0.20    # Max 20% of portfolio in single position
    MAX_ALLOCATION_PER_TOKEN = 0.20  # Max 20% of portfolio per token (stacked positions)
    ALLOW_STACKING = False  # Set to False to prevent duplicate positions in same token

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
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
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

    # ==========================================================================
    # TOKEN SAFETY METHODS - Protect against rug pulls and illiquid tokens
    # ==========================================================================

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
        """Load positions and history from disk with file locking."""
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
            except Exception as e:
                logger.error(f"Failed to load positions: {e}")

            try:
                data = self._history_state.read()
                self.trade_history = [Position.from_dict(p) for p in data]
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
                except Exception as e:
                    logger.error(f"Failed to load positions: {e}")

            if self.HISTORY_FILE.exists():
                try:
                    with open(self.HISTORY_FILE) as f:
                        data = json.load(f)
                        self.trade_history = [Position.from_dict(p) for p in data]
                except Exception as e:
                    logger.error(f"Failed to load history: {e}")

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
        """Save positions and history to disk with file locking."""
        try:
            if SAFE_STATE_AVAILABLE and hasattr(self, '_positions_state'):
                # Use SafeState for atomic writes with locking
                self._positions_state.write([p.to_dict() for p in self.positions.values()])
                self._history_state.write([p.to_dict() for p in self.trade_history])
            else:
                # Fallback to original implementation
                with open(self.POSITIONS_FILE, 'w') as f:
                    json.dump([p.to_dict() for p in self.positions.values()], f, indent=2)
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
                if daily_volume < self.MIN_LIQUIDITY_USD:  # Use configurable minimum
                    logger.warning(f"Trade rejected: {token_symbol} has insufficient liquidity (${daily_volume:.0f}/day)")
                    self._log_audit("OPEN_POSITION_REJECTED", {
                        "token": token_symbol,
                        "reason": "low_liquidity",
                        "daily_volume": daily_volume,
                    }, user_id, False)
                    return False, f"⛔ Trade blocked: {token_symbol} has insufficient liquidity (${daily_volume:.0f}/day)", None
                liquidity_verified = True
                logger.debug(f"Liquidity OK for {token_symbol}: ${daily_volume:.0f}/day")
        except Exception as e:
            logger.warning(f"Could not check liquidity for {token_symbol}: {e}")

        # FAIL-SAFE: Reject HIGH_RISK and MICRO tokens if liquidity not verified
        # ESTABLISHED tokens get a pass (they have proven liquidity history)
        if not liquidity_verified and risk_tier in ("HIGH_RISK", "MICRO"):
            self._log_audit("OPEN_POSITION_REJECTED", {
                "token": token_symbol,
                "reason": "liquidity_check_failed",
                "risk_tier": risk_tier,
            }, user_id, False)
            return False, f"⛔ Trade blocked: Cannot verify liquidity for {risk_tier} token {token_symbol}", None

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

        # Enforce per-token allocation cap while allowing stacking
        if portfolio_usd > 0:
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

            # Execute swap
            result = await self.jupiter.execute_swap(quote, self.wallet)

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
                                result = await self.jupiter.execute_swap(quote, self.wallet)
                                if result.success:
                                    logger.info(f"Sold {position.token_symbol} via {reason}: {result.signature}")
                    except Exception as sell_err:
                        logger.error(f"Failed to sell {position.token_symbol}: {sell_err}")

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
                logger.error(f"Failed to close position {pos_id}: {e}")

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
                    if resp.status == 200:
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
                max_positions=50,  # Increased from 10 to support more concurrent positions
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
