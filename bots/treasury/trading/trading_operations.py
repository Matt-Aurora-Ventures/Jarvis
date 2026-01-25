"""
Trading Operations

Core trading operations: open_position, close_position, update_positions, monitor_stop_losses.
These are added as a mixin to TradingEngine.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from .types import Position, TradeStatus, TradeDirection
from .constants import (
    ALLOW_STACKING, MAX_ALLOCATION_PER_TOKEN, MIN_LIQUIDITY_USD
)
from .logging_utils import (
    logger, log_trading_error, log_trading_event, log_position_change,
    STRUCTURED_LOGGING_AVAILABLE
)

# Import memory hooks for trade outcome storage
from .memory_hooks import (
    store_trade_outcome_async,
    should_enter_based_on_history,
)

# Import risk management types
try:
    from core.risk import AlertLevel
    RISK_MANAGER_AVAILABLE = True
except ImportError:
    RISK_MANAGER_AVAILABLE = False
    AlertLevel = None


class TradingOperationsMixin:
    """Mixin providing core trading operations for TradingEngine."""

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

        # BLOCKED TOKEN CHECK
        is_blocked, block_reason = self.is_blocked_token(token_mint, token_symbol)
        if is_blocked:
            logger.warning(f"Trade rejected: {block_reason}")
            return False, f"X {block_reason}", None

        # MANDATORY ADMIN CHECK
        if not user_id:
            logger.warning("Trade rejected: No user_id provided")
            return False, "X Admin only - please authenticate", None

        if not self.is_admin(user_id):
            logger.warning(f"Trade rejected: User {user_id} is not authorized")
            return False, "X Admin only - you are not authorized to trade", None

        # MANDATORY TP/SL VALIDATION
        if sentiment_grade in ['D', 'F']:
            logger.warning(f"Trade rejected: Grade {sentiment_grade} is too risky")
            return False, f"X Trade blocked: Grade {sentiment_grade} is too risky", None

        # HIGH-RISK TOKEN WARNING
        if self.is_high_risk_token(token_mint):
            logger.warning(f"HIGH-RISK TOKEN: {token_symbol} is a pump.fun token - using 15% position size")

        # Classify token risk tier
        risk_tier = self.classify_token_risk(token_mint, token_symbol)
        logger.info(f"Token {token_symbol} classified as: {risk_tier}")

        # OPTIONAL: Check historical performance
        try:
            should_enter, history_reason = await should_enter_based_on_history(
                token_symbol=token_symbol,
                min_win_rate=0.3,
                min_trades=3,
            )
            logger.info(f"Historical check for {token_symbol}: {history_reason}")

            # Log warning if history suggests avoiding, but don't block (configurable)
            if not should_enter:
                logger.warning(f"Historical performance warning for {token_symbol}: {history_reason}")
                # Note: Not blocking trade, just logging. User can decide to proceed.
        except Exception as e:
            logger.warning(f"Failed to check historical performance for {token_symbol}: {e}")

        # Check max positions limit
        open_positions = [p for p in self.positions.values() if p.is_open]

        # Check for existing positions in this token
        existing_in_token = [p for p in open_positions if p.token_mint == token_mint]
        if existing_in_token:
            if not ALLOW_STACKING:
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

        # LIQUIDITY CHECK
        liquidity_verified = False
        try:
            token_info = await self.jupiter.get_token_info(token_mint)
            if token_info and hasattr(token_info, 'daily_volume'):
                daily_volume = getattr(token_info, 'daily_volume', 0) or 0
                if daily_volume > 0 and daily_volume < MIN_LIQUIDITY_USD:
                    logger.warning(f"Trade rejected: {token_symbol} has insufficient liquidity (${daily_volume:.0f}/day)")
                    self._log_audit("OPEN_POSITION_REJECTED", {
                        "token": token_symbol,
                        "reason": "low_liquidity",
                        "daily_volume": daily_volume,
                    }, user_id, False)
                    return False, f"X Trade blocked: {token_symbol} has insufficient liquidity (${daily_volume:.0f}/day)", None
                if daily_volume >= MIN_LIQUIDITY_USD:
                    liquidity_verified = True
                    logger.debug(f"Liquidity OK for {token_symbol}: ${daily_volume:.0f}/day")
        except Exception as e:
            logger.warning(f"Could not check liquidity for {token_symbol}: {e}")

        # Log warning for unverified liquidity
        if not liquidity_verified and risk_tier in ("HIGH_RISK", "MICRO"):
            logger.warning(f"Liquidity not verified for {risk_tier} token {token_symbol} - proceeding anyway")
            self._log_audit("LIQUIDITY_UNVERIFIED", {
                "token": token_symbol,
                "risk_tier": risk_tier,
                "action": "proceeding",
            }, user_id, True)

        # Get portfolio value for limit checks
        _, portfolio_usd = await self.get_portfolio_value()

        # INPUT VALIDATION
        if amount_usd is not None:
            try:
                amount_usd = float(amount_usd)
            except (TypeError, ValueError):
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "invalid_amount",
                    "amount_usd": str(amount_usd),
                }, user_id, False)
                return False, "X Invalid amount: must be a number", None

            if amount_usd <= 0:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "non_positive_amount",
                    "amount_usd": amount_usd,
                }, user_id, False)
                return False, "X Invalid amount: must be positive", None

        # Calculate position size
        if not amount_usd:
            amount_usd = self.calculate_position_size(portfolio_usd)

        # RISK-ADJUSTED POSITION SIZING
        original_amount = amount_usd
        amount_usd, risk_tier = self.get_risk_adjusted_position_size(
            token_mint, token_symbol, amount_usd
        )

        if amount_usd == 0:
            self._log_audit("OPEN_POSITION_REJECTED", {
                "token": token_symbol,
                "reason": "risk_too_high",
                "risk_tier": risk_tier,
            }, user_id, False)
            return False, f"X Trade blocked: {token_symbol} classified as {risk_tier}", None

        if amount_usd < original_amount:
            logger.info(f"Position size reduced: ${original_amount:.2f} -> ${amount_usd:.2f} ({risk_tier})")

        # Per-token allocation cap (if enabled)
        if MAX_ALLOCATION_PER_TOKEN is not None and portfolio_usd > 0:
            existing_token_usd = sum(p.amount_usd for p in existing_in_token)
            total_token_usd = existing_token_usd + amount_usd
            token_allocation_pct = total_token_usd / portfolio_usd
            if token_allocation_pct > MAX_ALLOCATION_PER_TOKEN:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "token_allocation",
                    "existing_token_usd": existing_token_usd,
                    "amount_usd": amount_usd,
                    "allocation_pct": token_allocation_pct,
                }, user_id, False)
                return False, (
                    f"Token allocation {token_allocation_pct*100:.1f}% exceeds max "
                    f"{MAX_ALLOCATION_PER_TOKEN*100:.0f}% for {token_symbol}"
                ), None

        # ENHANCED: Check comprehensive risk limits via RiskManager
        if self.risk_manager and RISK_MANAGER_AVAILABLE:
            daily_pnl = self._calculate_daily_pnl()
            existing_token_usd = sum(p.amount_usd for p in existing_in_token)
            total_token_exposure = existing_token_usd + amount_usd
            deployed_capital = sum(p.amount_usd for p in open_positions) + amount_usd

            today = datetime.utcnow().date()
            trades_today = len([
                p for p in self.trade_history
                if datetime.fromisoformat(p.opened_at.replace('Z', '+00:00')).date() == today
            ])

            all_passed, risk_alerts = self.risk_manager.check_all_limits(
                position_size=amount_usd,
                daily_loss=abs(min(daily_pnl, 0)),
                token_concentration={token_symbol: (total_token_exposure, portfolio_usd)},
                deployed_capital=deployed_capital,
                total_portfolio=portfolio_usd,
                trades_today=trades_today
            )

            if self.risk_manager.circuit_breaker_active:
                self._log_audit("OPEN_POSITION_REJECTED", {
                    "token": token_symbol,
                    "reason": "circuit_breaker",
                }, user_id, False)
                return False, "CIRCUIT BREAKER ACTIVE - Trading halted. Contact admin to reset.", None

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
                    return False, f"X Risk limit exceeded: {alert_msg}", None

            warning_alerts = [a for a in risk_alerts if a.level == AlertLevel.WARNING]
            if warning_alerts:
                for alert in warning_alerts:
                    logger.warning(f"Risk warning: {alert.message}")

        # Check spending limits
        allowed, limit_reason = self._check_spending_limits(amount_usd, portfolio_usd)
        if not allowed:
            self._log_audit("OPEN_POSITION_REJECTED", {
                "token": token_symbol,
                "reason": "spending_limit",
                "limit_reason": limit_reason,
                "amount_usd": amount_usd,
            }, user_id, False)
            return False, f"X {limit_reason}", None

        # Calculate TP/SL
        tp_price, sl_price = self.get_tp_sl_levels(
            current_price, sentiment_grade, custom_tp, custom_sl
        )

        # Generate position ID
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
            sentiment_score=sentiment_score,
            peak_price=current_price  # Initialize peak price at entry
        )

        if self.dry_run:
            async with self._trade_execution_lock:
                position.status = TradeStatus.OPEN
                self.positions[position_id] = position
                self._save_state()

            self._add_daily_volume(amount_usd)

            log_position_change("OPEN", position_id, token_symbol, {
                "amount_usd": amount_usd,
                "entry_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "sentiment_grade": sentiment_grade,
                "risk_tier": risk_tier,
                "dry_run": True,
                "user_id": user_id,
            })

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

            return True, f"[DRY RUN] Position opened", position

        # Execute real trade
        try:
            from ..jupiter import JupiterClient

            sol_amount = int(amount_usd / await self.jupiter.get_token_price(JupiterClient.SOL_MINT) * 1e9)
            slippage = 200

            quote = await self.jupiter.get_quote(
                JupiterClient.SOL_MINT,
                token_mint,
                sol_amount,
                slippage_bps=slippage
            )

            if not quote:
                return False, "Failed to get swap quote", None

            result = await self._execute_swap(quote)

            if not result.success:
                return False, f"Swap failed: {result.error}", None

            position.status = TradeStatus.OPEN
            position.amount = quote.output_amount_ui

            if self.order_manager:
                token_info = await self.jupiter.get_token_info(token_mint)
                token_decimals = token_info.decimals if token_info else 9
                amount_smallest_unit = int(position.amount * (10 ** token_decimals))

                tp_id = await self.order_manager.create_take_profit(
                    token_mint, amount_smallest_unit, tp_price
                )
                sl_id = await self.order_manager.create_stop_loss(
                    token_mint, amount_smallest_unit, sl_price
                )
                position.tp_order_id = tp_id
                position.sl_order_id = sl_id

            async with self._trade_execution_lock:
                self.positions[position_id] = position
                self._save_state()

            self._add_daily_volume(amount_usd)

            log_position_change("OPEN", position_id, token_symbol, {
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

            # Track in scorekeeper
            try:
                from ..scorekeeper import get_scorekeeper
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
        # SECURITY FIX - Strict admin check
        if not self.admin_user_ids:
            logger.warning("SECURITY WARNING: admin_user_ids is empty - no users can close positions")
            self._log_audit("CLOSE_POSITION_REJECTED", {
                "position_id": position_id,
                "reason": "no_admins_configured",
            }, user_id, False)
            return False, "X No admins configured - cannot close positions"

        if not user_id or not self.is_admin(user_id):
            self._log_audit("CLOSE_POSITION_REJECTED", {
                "position_id": position_id,
                "reason": "unauthorized",
            }, user_id, False)
            return False, "X Unauthorized - admin access required"

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

        current_price = await self.jupiter.get_token_price(position.token_mint)

        if self.dry_run:
            position.status = TradeStatus.CLOSED
            position.closed_at = datetime.utcnow().isoformat()
            position.exit_price = current_price
            position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)

            async with self._trade_execution_lock:
                self.trade_history.append(position)
                del self.positions[position_id]
                self._save_state()

            log_position_change("CLOSE", position_id, position.token_symbol, {
                "entry_price": position.entry_price,
                "exit_price": current_price,
                "pnl_usd": position.pnl_usd,
                "pnl_pct": position.pnl_pct,
                "reason": reason,
                "dry_run": True,
                "user_id": user_id,
            })

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

            self._record_trade_learning(
                token=position.token_symbol,
                action="close",
                pnl=position.pnl_usd,
                pnl_pct=position.pnl_pct / 100,
                context={"reason": reason, "dry_run": True}
            )

            # Store trade outcome in memory (fire-and-forget, dry_run)
            try:
                hold_duration = (datetime.fromisoformat(position.closed_at) - datetime.fromisoformat(position.opened_at)).total_seconds() / 3600.0

                logger.info(f"Storing trade outcome for {position.token_symbol} in memory (dry_run)")
                store_trade_outcome_async(
                    token_symbol=position.token_symbol,
                    token_mint=position.token_mint,
                    entry_price=position.entry_price,
                    exit_price=position.exit_price,
                    pnl_pct=position.pnl_pct,
                    hold_duration_hours=hold_duration,
                    strategy="treasury",  # TODO: Extract actual strategy from position
                    sentiment_score=position.sentiment_score if position.sentiment_score > 0 else None,
                    exit_reason=reason,
                    metadata={
                        "position_id": position_id,
                        "dry_run": True,
                        "sentiment_grade": position.sentiment_grade,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to store trade outcome in memory: {e}")

            return True, f"[DRY RUN] Closed with P&L: ${position.pnl_usd:+.2f} ({position.pnl_pct:+.1f}%)"

        # Execute real close
        try:
            if self.order_manager:
                if position.tp_order_id:
                    await self.order_manager.cancel_order(position.tp_order_id)
                if position.sl_order_id:
                    await self.order_manager.cancel_order(position.sl_order_id)

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

                self._log_audit("CLOSE_POSITION", {
                    "position_id": position_id,
                    "token": position.token_symbol,
                    "reason": "no_balance",
                    "dry_run": False,
                }, user_id, True)
                return True, "Position closed (no balance)"

            from ..jupiter import JupiterClient

            token_info = await self.jupiter.get_token_info(position.token_mint)
            decimals = token_info.decimals if token_info else 9
            amount = int(token_balance * (10 ** decimals))

            quote = await self.jupiter.get_quote(
                position.token_mint,
                JupiterClient.SOL_MINT,
                amount,
                slippage_bps=200
            )

            if not quote:
                self._log_audit("CLOSE_POSITION_FAILED", {
                    "position_id": position_id,
                    "token": position.token_symbol,
                    "error": "no_quote",
                }, user_id, False)
                return False, "Failed to get close quote"

            result = await self._execute_swap(quote)

            if not result.success:
                self._log_audit("CLOSE_POSITION_FAILED", {
                    "position_id": position_id,
                    "token": position.token_symbol,
                    "error": result.error,
                }, user_id, False)
                return False, f"Close failed: {result.error}"

            position.status = TradeStatus.CLOSED
            position.closed_at = datetime.utcnow().isoformat()
            position.exit_price = current_price
            position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)

            self.trade_history.append(position)
            del self.positions[position_id]
            self._save_state()

            log_position_change("CLOSE", position_id, position.token_symbol, {
                "entry_price": position.entry_price,
                "exit_price": current_price,
                "pnl_usd": position.pnl_usd,
                "pnl_pct": position.pnl_pct,
                "reason": reason,
                "tx_signature": result.signature,
                "dry_run": False,
                "user_id": user_id,
            })

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

            self._record_trade_learning(
                token=position.token_symbol,
                action="close",
                pnl=position.pnl_usd,
                pnl_pct=position.pnl_pct / 100,
                context={
                    "reason": reason,
                    "dry_run": False,
                    "tx_signature": result.signature
                }
            )

            # Track in scorekeeper
            try:
                from ..scorekeeper import get_scorekeeper
                from ..jupiter import JupiterClient
                scorekeeper = get_scorekeeper()
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

            # Store trade outcome in memory (fire-and-forget)
            try:
                hold_duration = (datetime.fromisoformat(position.closed_at) - datetime.fromisoformat(position.opened_at)).total_seconds() / 3600.0

                logger.info(f"Storing trade outcome for {position.token_symbol} in memory")
                store_trade_outcome_async(
                    token_symbol=position.token_symbol,
                    token_mint=position.token_mint,
                    entry_price=position.entry_price,
                    exit_price=position.exit_price,
                    pnl_pct=position.pnl_pct,
                    hold_duration_hours=hold_duration,
                    strategy="treasury",  # TODO: Extract actual strategy from position
                    sentiment_score=position.sentiment_score if position.sentiment_score > 0 else None,
                    exit_reason=reason,
                    metadata={
                        "position_id": position_id,
                        "tx_signature": result.signature,
                        "sentiment_grade": position.sentiment_grade,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to store trade outcome in memory: {e}")

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
                    if position.entry_price > 0:
                        position.pnl_pct = ((price - position.entry_price) / position.entry_price) * 100
                        position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)

        self._save_state()

    async def monitor_stop_losses(self) -> List[Dict[str, Any]]:
        """
        Active stop loss monitoring - catches positions that miss their limit orders.

        Returns:
            List of closed positions with their P&L
        """
        closed_positions = []
        positions_to_close = []

        # First pass: identify positions that need closing
        for pos_id, position in list(self.positions.items()):
            if not position.is_open:
                continue

            current_price = await self.jupiter.get_token_price(position.token_mint)
            if current_price <= 0:
                logger.warning(f"Could not get price for {position.token_symbol} - skipping SL check")
                continue

            position.current_price = current_price

            if position.direction == TradeDirection.LONG:
                # TRAILING STOP LOGIC
                # Initialize peak_price if not set (for legacy positions)
                if position.peak_price is None or position.peak_price == 0:
                    position.peak_price = position.entry_price

                # Update peak price if we've reached a new high
                if current_price > position.peak_price:
                    position.peak_price = current_price

                # Calculate current gain percentage
                current_gain_pct = ((current_price - position.entry_price) / position.entry_price) * 100

                # Apply trailing stop rules
                original_sl = position.stop_loss_price

                if current_gain_pct >= 15.0:
                    # Trail stop at 5% below peak price
                    position.stop_loss_price = position.peak_price * 0.95
                    if position.stop_loss_price != original_sl:
                        logger.info(
                            f"TRAILING STOP ACTIVATED: {position.token_symbol} | "
                            f"Gain: {current_gain_pct:.1f}% | "
                            f"Peak: ${position.peak_price:.8f} | "
                            f"SL updated: ${original_sl:.8f} -> ${position.stop_loss_price:.8f}"
                        )
                elif current_gain_pct >= 10.0:
                    # Move stop to breakeven (lock in 0% loss minimum)
                    if position.stop_loss_price < position.entry_price:
                        position.stop_loss_price = position.entry_price
                        logger.info(
                            f"BREAKEVEN STOP SET: {position.token_symbol} | "
                            f"Gain: {current_gain_pct:.1f}% | "
                            f"SL moved to breakeven: ${position.stop_loss_price:.8f}"
                        )

                # Now check if stop loss is breached
                if current_price <= position.stop_loss_price:
                    pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    logger.warning(
                        f"STOP LOSS BREACHED: {position.token_symbol} | "
                        f"Current: ${current_price:.8f} <= SL: ${position.stop_loss_price:.8f} | "
                        f"P&L: {pnl_pct:+.1f}%"
                    )
                    positions_to_close.append((pos_id, position, current_price, "SL_BREACH"))

                elif current_price < position.entry_price * 0.1:
                    pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    logger.warning(
                        f"EMERGENCY CLOSE: {position.token_symbol} down {pnl_pct:.1f}% | "
                        f"Entry: ${position.entry_price:.8f} -> ${current_price:.8f}"
                    )
                    positions_to_close.append((pos_id, position, current_price, "EMERGENCY_90PCT"))

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
                pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
                pnl_usd = position.amount_usd * (pnl_pct / 100)

                position.status = TradeStatus.CLOSED
                position.closed_at = datetime.utcnow().isoformat()
                position.exit_price = exit_price
                position.pnl_pct = pnl_pct
                position.pnl_usd = pnl_usd

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

                if not self.dry_run:
                    try:
                        from ..jupiter import JupiterClient

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
                                slippage_bps=500
                            )

                            if quote:
                                result = await self._execute_swap(quote)
                                if result.success:
                                    logger.info(f"Sold {position.token_symbol} via {reason}: {result.signature}")
                    except Exception as sell_err:
                        log_trading_error(sell_err, "sell_position", {
                            "symbol": position.token_symbol,
                            "reason": reason,
                        })

                self.trade_history.append(position)
                del self.positions[pos_id]

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
                log_trading_error(e, "close_position", {"position_id": pos_id})

        if closed_positions:
            self._save_state()

        return closed_positions

    async def reconcile_with_onchain(self) -> Dict[str, Any]:
        """
        Reconcile stored positions with actual on-chain token balances.

        Returns:
            Dict with reconciliation report
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
            treasury = self.wallet.get_treasury()
            if not treasury:
                report["errors"].append("No treasury wallet configured")
                logger.error("[RECONCILE] No treasury wallet configured")
                return report

            onchain_balances = await self.wallet.get_token_balances(treasury.address)
            logger.info(f"[RECONCILE] Found {len(onchain_balances)} tokens on-chain")

            matched_mints = set()

            for pos_id, position in list(self.positions.items()):
                if not position.is_open:
                    continue

                mint = position.token_mint
                onchain = onchain_balances.get(mint, {})
                onchain_balance = onchain.get('balance', 0)

                if onchain_balance <= 0:
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
                    report["matched"].append({
                        "position_id": pos_id,
                        "symbol": position.token_symbol,
                        "mint": mint,
                        "amount": position.amount
                    })
                    logger.debug(f"[RECONCILE] MATCHED: Position {pos_id} ({position.token_symbol})")

                matched_mints.add(mint)

            # Check for untracked tokens
            for mint, balance_info in onchain_balances.items():
                if mint not in matched_mints and balance_info.get('balance', 0) > 0:
                    if mint in [
                        "So11111111111111111111111111111111111111112",
                        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
                    ]:
                        continue

                    report["untracked"].append({
                        "mint": mint,
                        "balance": balance_info.get('balance', 0),
                        "decimals": balance_info.get('decimals', 0)
                    })
                    logger.warning(f"[RECONCILE] UNTRACKED: Token {mint} with balance {balance_info.get('balance', 0)}")

            logger.info(
                f"[RECONCILE] Complete: {len(report['matched'])} matched, "
                f"{len(report['orphaned'])} orphaned, {len(report['untracked'])} untracked, "
                f"{len(report['mismatched'])} mismatched"
            )

            return report

        except Exception as e:
            logger.error(f"[RECONCILE] Error during reconciliation: {e}")
            report["errors"].append(str(e))
            log_trading_error(e, "reconcile_with_onchain", {})
            return report

    async def auto_reconcile_orphaned(self, report: Dict[str, Any] = None) -> int:
        """
        Automatically close orphaned positions.

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

                try:
                    current_price = await self.jupiter.get_token_price(position.token_mint)
                except Exception:
                    current_price = 0

                position.status = TradeStatus.CLOSED
                position.closed_at = datetime.utcnow().isoformat()
                position.exit_price = current_price

                if current_price > 0:
                    position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)
                else:
                    position.pnl_pct = -100
                    position.pnl_usd = -position.amount_usd

                self.trade_history.append(position)
                del self.positions[pos_id]
                closed_count += 1

                logger.info(
                    f"[RECONCILE] Auto-closed orphaned position {pos_id} ({position.token_symbol}): "
                    f"P&L ${position.pnl_usd:+.2f} ({position.pnl_pct:+.1f}%)"
                )

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
