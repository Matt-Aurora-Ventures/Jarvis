"""
Trading Engine

Main orchestrator class that combines all trading modules.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .types import (
    Position, TradeStatus, TradeDirection, RiskLevel, TradeReport
)
from .constants import (
    ADMIN_USER_ID, MAX_ALLOCATION_PER_TOKEN, ALLOW_STACKING,
    AUDIT_LOG_FILE, TP_SL_CONFIG
)
from .logging_utils import (
    logger, log_trading_error, log_trading_event, log_position_change,
    STRUCTURED_LOGGING_AVAILABLE
)
from .trading_risk import RiskChecker
from .trading_positions import PositionManager
from .trading_execution import SwapExecutor, SignalAnalyzer
from .trading_analytics import TradingAnalytics
from .trading_operations import TradingOperationsMixin

# Import wallet types
try:
    from ..wallet import SecureWallet, WalletInfo
except ImportError:
    SecureWallet = Any
    WalletInfo = Any

# Import Jupiter client
try:
    from ..jupiter import JupiterClient, SwapQuote, SwapResult, LimitOrderManager
except ImportError:
    JupiterClient = Any
    SwapQuote = Any
    SwapResult = Any
    LimitOrderManager = None

# Import scorekeeper
try:
    from ..scorekeeper import get_scorekeeper, Scorekeeper
except ImportError:
    get_scorekeeper = None
    Scorekeeper = None

# Import SafeState
try:
    from core.safe_state import SafeState
    SAFE_STATE_AVAILABLE = True
except ImportError:
    SAFE_STATE_AVAILABLE = False
    SafeState = None

# Import centralized audit trail
try:
    from core.security.audit_trail import audit_trail, AuditEventType
    AUDIT_TRAIL_AVAILABLE = True
except ImportError:
    AUDIT_TRAIL_AVAILABLE = False
    audit_trail = None
    AuditEventType = None

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

# Import Bags.fm trade adapter
try:
    from core.trading.bags_adapter import BagsTradeAdapter
    BAGS_AVAILABLE = True
except ImportError:
    BAGS_AVAILABLE = False
    BagsTradeAdapter = None

# Import self-correcting AI
try:
    from core.self_correcting import (
        get_shared_memory, get_message_bus, get_ollama_router, get_self_adjuster,
        LearningType, MessageType, MessagePriority, TaskType, Parameter, MetricType,
    )
    SELF_CORRECTING_AVAILABLE = True
except ImportError:
    SELF_CORRECTING_AVAILABLE = False
    get_shared_memory = None
    get_message_bus = None
    get_ollama_router = None
    get_self_adjuster = None
    MessageType = None
    Parameter = None
    MetricType = None


class TradingEngine(TradingOperationsMixin):
    """
    Main trading engine for Jarvis Treasury.

    Features:
    - Sentiment-based trade signals
    - Automatic take profit and stop loss
    - Position sizing based on risk level
    - Full trade history and reporting
    - Real-time P&L tracking
    - Spending caps and audit logging
    """

    # Class-level constants (for backward compatibility with tests)
    from .constants import (
        ADMIN_USER_ID as ADMIN_USER_ID,
        TP_SL_CONFIG as TP_SL_CONFIG,
        POSITION_SIZE as POSITION_SIZE,
        MAX_TRADE_USD as MAX_TRADE_USD,
        MAX_DAILY_USD as MAX_DAILY_USD,
        MAX_POSITION_PCT as MAX_POSITION_PCT,
        MAX_ALLOCATION_PER_TOKEN as MAX_ALLOCATION_PER_TOKEN,
        ALLOW_STACKING as ALLOW_STACKING,
        MIN_LIQUIDITY_USD as MIN_LIQUIDITY_USD,
    )

    def __init__(
        self,
        wallet: SecureWallet,
        jupiter: JupiterClient,
        admin_user_ids: List[int] = None,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        max_positions: int = 50,
        dry_run: bool = True,
        enable_signals: bool = True,
        use_bags: bool = None,
        state_profile: Optional[str] = None,
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
            enable_signals: Enable advanced signal analysis
            use_bags: Use Bags.fm as primary executor
            state_profile: Isolate state per profile (e.g., demo)
        """
        self.wallet = wallet
        self.jupiter = jupiter
        self.admin_user_ids = admin_user_ids or []
        self.risk_level = risk_level
        self.max_positions = max_positions
        self.dry_run = dry_run

        # Initialize position manager
        self._position_manager = PositionManager(state_profile=state_profile)

        # Initialize risk checker
        self._risk_checker = RiskChecker()

        # Initialize Bags.fm adapter
        bags_adapter = None
        if use_bags is None:
            use_bags = os.environ.get("USE_BAGS_TRADING", "").lower() in ("1", "true", "yes")

        if use_bags and BAGS_AVAILABLE:
            try:
                bags_adapter = BagsTradeAdapter(
                    partner_code=os.environ.get("BAGS_PARTNER_CODE"),
                    enable_fallback=True,
                    wallet_keypair=wallet.keypair if hasattr(wallet, 'keypair') else None,
                )
                logger.info("Bags.fm trade adapter initialized (earns partner fees)")
            except Exception as e:
                logger.warning(f"Failed to initialize Bags adapter: {e} - using Jupiter only")
        elif use_bags and not BAGS_AVAILABLE:
            logger.warning("USE_BAGS_TRADING enabled but Bags adapter not available")

        # Initialize swap executor
        self._swap_executor = SwapExecutor(jupiter, wallet, bags_adapter)

        # Initialize signal analyzer
        self._signal_analyzer = SignalAnalyzer(enable_signals=enable_signals)

        # Initialize enhanced risk manager
        self.risk_manager: Optional[RiskManager] = None
        if RISK_MANAGER_AVAILABLE:
            self.risk_manager = RiskManager(enable_alerts=True)
            logger.info("Enhanced risk manager initialized")

        # Order manager for TP/SL
        self.order_manager: Optional[LimitOrderManager] = None

        # Trade execution lock for thread safety
        self._trade_execution_lock = asyncio.Lock()

        # Initialize self-correcting AI
        self._analytics = self._init_self_correcting_ai()

        # Audit log file
        self.AUDIT_LOG_FILE = AUDIT_LOG_FILE

        # Load existing state
        self._position_manager.load_state()

    def _init_self_correcting_ai(self) -> TradingAnalytics:
        """Initialize self-correcting AI system."""
        memory = None
        bus = None
        router = None
        adjuster = None

        if SELF_CORRECTING_AVAILABLE:
            try:
                memory = get_shared_memory()
                bus = get_message_bus()
                router = get_ollama_router()
                adjuster = get_self_adjuster()

                # Register tunable trading parameters
                adjuster.register_component("treasury_bot", {
                    "stop_loss_pct": Parameter(
                        name="stop_loss_pct",
                        current_value=15.0,
                        min_value=5.0,
                        max_value=25.0,
                        step=2.0,
                        affects_metrics=[MetricType.SUCCESS_RATE, MetricType.COST]
                    ),
                    "take_profit_pct": Parameter(
                        name="take_profit_pct",
                        current_value=30.0,
                        min_value=15.0,
                        max_value=50.0,
                        step=5.0,
                        affects_metrics=[MetricType.SUCCESS_RATE]
                    ),
                })

                # Load past learnings
                past_learnings = memory.search_learnings(
                    component="treasury_bot",
                    learning_type=LearningType.SUCCESS_PATTERN,
                    min_confidence=0.7
                )
                logger.info(f"Loaded {len(past_learnings)} past trading patterns from self-correcting memory")

            except Exception as e:
                logger.warning(f"Failed to initialize self-correcting AI: {e}")
                memory = bus = router = adjuster = None

        analytics = TradingAnalytics(memory, bus, router, adjuster)

        # Subscribe to messages if bus available
        if bus and analytics:
            bus.subscribe(
                subscriber="treasury_bot",
                message_types=[
                    MessageType.SENTIMENT_CHANGED,
                    MessageType.PRICE_ALERT,
                    MessageType.NEW_LEARNING,
                ],
                callback=analytics.handle_bus_message,
            )

        return analytics

    # ==========================================================================
    # PROPERTY ACCESSORS
    # ==========================================================================

    @property
    def positions(self) -> Dict[str, Position]:
        """Access positions dictionary."""
        return self._position_manager.positions

    @positions.setter
    def positions(self, value: Dict[str, Position]):
        """Set positions dictionary (for test compatibility)."""
        self._position_manager.positions = value

    @property
    def trade_history(self) -> List[Position]:
        """Access trade history."""
        return self._position_manager.trade_history

    @trade_history.setter
    def trade_history(self, value: List[Position]):
        """Set trade history (for test compatibility)."""
        self._position_manager.trade_history = value

    @property
    def _volume_state(self):
        """Access volume state for test compatibility."""
        return self._risk_checker._volume_state

    @property
    def bags_adapter(self):
        """Access Bags.fm adapter."""
        return self._swap_executor.bags_adapter

    # ==========================================================================
    # ADMIN AND AUTH
    # ==========================================================================

    def is_admin(self, user_id: int) -> bool:
        """Check if user is authorized to trade. Admin only."""
        if user_id == ADMIN_USER_ID:
            return True
        return user_id in self.admin_user_ids

    def add_admin(self, user_id: int):
        """Add an admin user."""
        if user_id not in self.admin_user_ids:
            self.admin_user_ids.append(user_id)

    # ==========================================================================
    # AUDIT LOGGING
    # ==========================================================================

    def _log_audit(
        self,
        action: str,
        details: Dict[str, Any],
        user_id: int = None,
        success: bool = True
    ):
        """Log trade action to audit log."""
        try:
            audit_log = []
            if self.AUDIT_LOG_FILE.exists():
                with open(self.AUDIT_LOG_FILE) as f:
                    audit_log = json.load(f)

            entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'action': action,
                'user_id': user_id,
                'success': success,
                'details': details,
            }
            audit_log.append(entry)

            if len(audit_log) > 1000:
                audit_log = audit_log[-1000:]

            self.AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.AUDIT_LOG_FILE, 'w') as f:
                json.dump(audit_log, f, indent=2)

            logger.info(f"AUDIT: {action} | user={user_id} | success={success}")

            # Also log to centralized audit trail
            if AUDIT_TRAIL_AVAILABLE and audit_trail:
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

    # ==========================================================================
    # STATE MANAGEMENT DELEGATIONS
    # ==========================================================================

    def _save_state(self):
        """Save positions and history to disk."""
        self._position_manager.save_state()

    def _load_state(self):
        """Load positions and history from disk."""
        self._position_manager.load_state()

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return self._position_manager.get_open_positions()

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a specific position."""
        return self._position_manager.get_position(position_id)

    # ==========================================================================
    # RISK MANAGEMENT DELEGATIONS
    # ==========================================================================

    def is_blocked_token(self, token_mint: str, token_symbol: str = "") -> Tuple[bool, str]:
        """Check if token is blocked from trading."""
        return RiskChecker.is_blocked_token(token_mint, token_symbol)

    def is_high_risk_token(self, token_mint: str) -> bool:
        """Check if token matches high-risk patterns."""
        return RiskChecker.is_high_risk_token(token_mint)

    def is_established_token(self, token_mint: str) -> bool:
        """Check if token is in established tokens list."""
        return RiskChecker.is_established_token(token_mint)

    def classify_token_risk(self, token_mint: str, token_symbol: str) -> str:
        """Classify token into risk tiers."""
        return RiskChecker.classify_token_risk(token_mint, token_symbol)

    def get_risk_adjusted_position_size(
        self, token_mint: str, token_symbol: str, base_position_usd: float
    ) -> Tuple[float, str]:
        """Get risk-adjusted position size."""
        return RiskChecker.get_risk_adjusted_position_size(token_mint, token_symbol, base_position_usd)

    def _check_spending_limits(self, amount_usd: float, portfolio_usd: float) -> Tuple[bool, str]:
        """Check if trade passes spending limits.

        Uses instance/class attributes for testability (can be overridden).
        """
        # Check single trade limit (use instance attr if set, else class attr)
        max_trade = getattr(self, 'MAX_TRADE_USD', TradingEngine.MAX_TRADE_USD)
        if amount_usd > max_trade:
            return False, f"Trade ${amount_usd:.2f} exceeds max single trade ${max_trade}"

        # Check daily limit
        max_daily = getattr(self, 'MAX_DAILY_USD', TradingEngine.MAX_DAILY_USD)
        daily_volume = self._risk_checker.get_daily_volume()
        if daily_volume + amount_usd > max_daily:
            remaining = max_daily - daily_volume
            return False, f"Daily limit reached. Used ${daily_volume:.2f}/{max_daily}. Remaining: ${remaining:.2f}"

        # Check position concentration
        max_position_pct = getattr(self, 'MAX_POSITION_PCT', TradingEngine.MAX_POSITION_PCT)
        if portfolio_usd > 0:
            position_pct = amount_usd / portfolio_usd
            if position_pct > max_position_pct:
                return False, f"Position {position_pct*100:.1f}% exceeds max {max_position_pct*100:.0f}% of portfolio"

        return True, ""

    def _get_daily_volume(self) -> float:
        """Get total trading volume for today."""
        return self._risk_checker.get_daily_volume()

    def _add_daily_volume(self, amount_usd: float):
        """Add to daily trading volume."""
        self._risk_checker.add_daily_volume(amount_usd)

    def get_tp_sl_levels(
        self, entry_price: float, sentiment_grade: str,
        custom_tp: float = None, custom_sl: float = None
    ) -> Tuple[float, float]:
        """Calculate take profit and stop loss prices."""
        return RiskChecker.get_tp_sl_levels(entry_price, sentiment_grade, custom_tp, custom_sl)

    def calculate_position_size(self, portfolio_usd: float, risk_override: RiskLevel = None) -> float:
        """Calculate position size in USD based on risk level."""
        return RiskChecker.calculate_position_size(portfolio_usd, risk_override or self.risk_level)

    def _calculate_daily_pnl(self) -> float:
        """Calculate total P&L for today."""
        return TradingAnalytics.calculate_daily_pnl(
            self.trade_history, self.get_open_positions()
        )

    # ==========================================================================
    # EXECUTION DELEGATIONS
    # ==========================================================================

    async def _execute_swap(
        self, quote: SwapQuote, input_mint: str = None, output_mint: str = None
    ) -> SwapResult:
        """Execute a swap via Bags.fm or Jupiter."""
        return await self._swap_executor.execute_swap(quote, input_mint, output_mint)

    # ==========================================================================
    # SIGNAL ANALYSIS DELEGATIONS
    # ==========================================================================

    async def analyze_sentiment_signal(
        self, token_mint: str, sentiment_score: float, sentiment_grade: str
    ) -> Tuple[TradeDirection, str]:
        """Analyze sentiment and determine trade direction."""
        open_count = len(self.get_open_positions())
        return await self._signal_analyzer.analyze_sentiment_signal(
            token_mint, sentiment_score, sentiment_grade, self.max_positions, open_count
        )

    async def analyze_liquidation_signal(self, symbol: str = "BTC"):
        """Analyze liquidation data for contrarian trading signals."""
        return await self._signal_analyzer.analyze_liquidation_signal(symbol)

    async def analyze_ma_signal(self, prices: List[float], symbol: str = "BTC"):
        """Analyze dual moving average signal."""
        return await self._signal_analyzer.analyze_ma_signal(prices, symbol)

    async def get_combined_signal(
        self, token_mint: str, symbol: str, sentiment_score: float,
        sentiment_grade: str, prices: Optional[List[float]] = None
    ) -> Tuple[TradeDirection, str, float]:
        """Get combined signal from all sources."""
        open_count = len(self.get_open_positions())
        return await self._signal_analyzer.get_combined_signal(
            token_mint, symbol, sentiment_score, sentiment_grade,
            self.max_positions, open_count, prices
        )

    async def get_liquidation_summary(self, symbol: str = "BTC") -> Dict[str, Any]:
        """Get 24h liquidation summary for a symbol."""
        return await self._signal_analyzer.get_liquidation_summary(symbol)

    # ==========================================================================
    # ANALYTICS DELEGATIONS
    # ==========================================================================

    def generate_report(self) -> TradeReport:
        """Generate trading performance report."""
        return TradingAnalytics.generate_report(self.trade_history, self.get_open_positions())

    def _record_trade_learning(self, token: str, action: str, pnl: float, pnl_pct: float, **kwargs):
        """Record a trade outcome as a learning."""
        self._analytics.record_trade_learning(token, action, pnl, pnl_pct, **kwargs)

    async def _query_ai_for_trade_analysis(self, token: str, sentiment: str, score: float, past_learnings=None):
        """Use AI to analyze trade opportunity."""
        return await self._analytics.query_ai_for_trade_analysis(token, sentiment, score, past_learnings)

    def _handle_bus_message(self, message):
        """Handle incoming messages from other bots."""
        self._analytics.handle_bus_message(message)

    # ==========================================================================
    # PORTFOLIO VALUE
    # ==========================================================================

    async def get_portfolio_value(self) -> Tuple[float, float]:
        """Get total portfolio value in SOL and USD."""
        treasury = self.wallet.get_treasury()
        if not treasury:
            return 0.0, 0.0

        balance_result = await self.wallet.get_balance(treasury.address)
        if balance_result is None:
            logger.warning("get_balance returned None, defaulting to (0.0, 0.0)")
            sol_balance, usd_value = 0.0, 0.0
        else:
            sol_balance, usd_value = balance_result

        token_balances = await self.wallet.get_token_balances(treasury.address)

        for mint, info in token_balances.items():
            price = await self.jupiter.get_token_price(mint)
            usd_value += info['balance'] * price

        return sol_balance, usd_value

    # ==========================================================================
    # RISK STATUS
    # ==========================================================================

    def get_risk_status(self) -> Optional[Dict[str, Any]]:
        """Get current risk status and alerts."""
        if not self.risk_manager:
            return None

        open_positions = self.get_open_positions()
        daily_pnl = self._calculate_daily_pnl()

        from asyncio import get_event_loop
        try:
            loop = get_event_loop()
            _, portfolio_value = loop.run_until_complete(self.get_portfolio_value())
        except:
            portfolio_value = 0.0

        portfolio_peak = max(portfolio_value, portfolio_value - daily_pnl if daily_pnl < 0 else portfolio_value)

        metrics = self.risk_manager.get_risk_metrics(
            positions=open_positions,
            daily_pnl=daily_pnl,
            portfolio_peak=portfolio_peak,
            current_portfolio=portfolio_value
        )

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

    # ==========================================================================
    # ORDER MANAGEMENT
    # ==========================================================================

    async def initialize_order_manager(self):
        """Initialize the limit order manager with position closure callback."""
        self.order_manager = LimitOrderManager(
            self.jupiter,
            self.wallet,
            on_order_filled=self._handle_order_filled
        )
        await self.order_manager.start_monitoring()

    async def _handle_order_filled(
        self, order_id: str, order_type: str, token_mint: str,
        exit_price: float, output_amount: float, tx_signature: str
    ):
        """Handle TP/SL order filled callback."""
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

        close_type = "tp" if order_type == "TAKE_PROFIT" else "sl"

        # Update position
        position.status = TradeStatus.CLOSED
        position.closed_at = datetime.utcnow().isoformat()
        position.exit_price = exit_price
        position.pnl_pct = pnl_pct
        position.pnl_usd = pnl_usd

        # Cancel the other order
        if self.order_manager:
            other_order_id = position.sl_order_id if order_type == "TAKE_PROFIT" else position.tp_order_id
            if other_order_id:
                await self.order_manager.cancel_order(other_order_id)

        # Move to history
        self.trade_history.append(position)
        del self.positions[position_id]
        self._save_state()

        # Update scorekeeper
        if get_scorekeeper:
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

    # ==========================================================================
    # SHUTDOWN
    # ==========================================================================

    async def shutdown(self):
        """Clean shutdown."""
        if self.order_manager:
            await self.order_manager.stop_monitoring()
        await self._signal_analyzer.close()
        await self.jupiter.close()
        self._save_state()
