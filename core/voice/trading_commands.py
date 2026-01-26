"""
Voice Trading Commands - Execute Trading Actions via Voice.

Handles voice command intents from the VoiceCommandParser and executes
appropriate trading actions or returns market data.

Commands:
- Morning briefing (market summary)
- Strategy control (activate/deactivate)
- Risk adjustments (position size, stop loss, etc.)
- Price alerts
- Position queries
- Market data queries
- Trade execution (with confirmation)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VoiceResponse:
    """Response from voice command execution."""
    success: bool
    response: str
    requires_confirmation: bool = False
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Valid strategy names
VALID_STRATEGIES = {
    "momentum", "dca", "grid", "scalping", "mean_reversion",
    "breakout", "trend_following",
}

# Risk limit ranges (for validation)
RISK_LIMITS = {
    "max_position_pct": (0.5, 20.0),  # 0.5% to 20%
    "stop_loss_pct": (1.0, 25.0),     # 1% to 25%
    "take_profit_pct": (5.0, 100.0),  # 5% to 100%
    "daily_loss_limit": (100.0, 10000.0),  # $100 to $10,000
    "max_drawdown_pct": (5.0, 30.0),  # 5% to 30%
}


class VoiceTradingCommands:
    """
    Execute voice trading commands.

    Provides a conversational interface to trading functionality.
    """

    def __init__(self):
        """Initialize the command handler."""
        self.handlers: Dict[str, Callable] = {
            "morning_briefing": self._handle_morning_briefing,
            "strategy_control": self._handle_strategy_control,
            "strategy_status": self._handle_strategy_status,
            "risk_adjustment": self._handle_risk_adjustment,
            "risk_query": self._handle_risk_query,
            "price_alert": self._handle_price_alert,
            "list_alerts": self._handle_list_alerts,
            "cancel_alert": self._handle_cancel_alert,
            "position_query": self._handle_position_query,
            "price_query": self._handle_price_query,
            "market_overview": self._handle_market_overview,
            "trade_command": self._handle_trade_command,
            "unknown": self._handle_unknown,
        }

        # State
        self._active_strategies: Dict[str, bool] = {}
        self._risk_limits: Dict[str, float] = {
            "max_position_pct": 5.0,
            "stop_loss_pct": 8.0,
            "take_profit_pct": 30.0,
            "daily_loss_limit": 1000.0,
            "max_drawdown_pct": 15.0,
        }
        self._alerts: List[Dict[str, Any]] = []

    async def execute(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a voice command intent.

        Args:
            intent: Parsed intent from VoiceCommandParser

        Returns:
            Response dictionary with success, response, and optional data
        """
        intent_type = intent.get("intent", "unknown")
        confidence = intent.get("confidence", 0.0)
        params = intent.get("params", {})
        confirmed = intent.get("confirmed", False)

        # Check confidence level
        if confidence < 0.5 and intent_type != "unknown":
            return {
                "success": True,
                "response": f"I'm not quite sure what you mean. Did you want me to handle {intent_type.replace('_', ' ')}? Please confirm or try again.",
                "requires_confirmation": True,
            }

        # Get handler
        handler = self.handlers.get(intent_type, self._handle_unknown)

        try:
            result = await handler(params, confirmed)
            return result
        except Exception as e:
            logger.error(f"Voice command error: {e}")
            return {
                "success": False,
                "response": "Sorry, I encountered an error processing that request. Please try again.",
                "error": str(e),
            }

    # =========================================================================
    # Market Briefing Handlers
    # =========================================================================

    async def _handle_morning_briefing(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Generate morning market briefing."""
        try:
            data = await self._get_market_data()

            # Format natural response
            sol_change = data.get("sol_24h_change", 0)
            sol_direction = "up" if sol_change > 0 else "down" if sol_change < 0 else "flat"

            response = f"Good morning. Here's your market briefing. "
            response += f"SOL is trading at {data.get('sol_price', 0):.2f} dollars, "
            response += f"{sol_direction} {abs(sol_change):.1f} percent in the last 24 hours. "

            if "btc_price" in data:
                btc_change = data.get("btc_24h_change", 0)
                response += f"Bitcoin is at {data.get('btc_price', 0):,.0f} dollars, "
                response += f"{'up' if btc_change > 0 else 'down'} {abs(btc_change):.1f} percent. "

            # Positions summary
            positions = data.get("total_positions", 0)
            if positions > 0:
                pnl = data.get("pnl_24h", 0)
                response += f"You have {positions} open positions with "
                response += f"{'a gain' if pnl > 0 else 'a loss'} of {abs(pnl):.2f} dollars today."
            else:
                response += "You have no open positions."

            return {
                "success": True,
                "response": response,
                "data": data,
            }

        except Exception as e:
            logger.error(f"Morning briefing error: {e}")
            return {
                "success": False,
                "response": "Sorry, I couldn't get the market data right now. Please try again in a moment.",
                "error": str(e),
            }

    # =========================================================================
    # Strategy Control Handlers
    # =========================================================================

    async def _handle_strategy_control(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Handle strategy activation/deactivation."""
        action = params.get("action", "")
        strategy = params.get("strategy", "")

        # Validate strategy
        if strategy not in VALID_STRATEGIES:
            available = ", ".join(sorted(VALID_STRATEGIES))
            return {
                "success": False,
                "response": f"I don't recognize the {strategy} strategy. Available strategies are: {available}.",
            }

        # Execute action
        if action == "activate":
            success = await self._set_strategy_state(strategy, True)
            if success:
                self._active_strategies[strategy] = True
                return {
                    "success": True,
                    "response": f"Done. The {strategy.replace('_', ' ')} strategy is now activated.",
                }
        elif action == "deactivate":
            success = await self._set_strategy_state(strategy, False)
            if success:
                self._active_strategies[strategy] = False
                return {
                    "success": True,
                    "response": f"Done. The {strategy.replace('_', ' ')} strategy has been deactivated.",
                }

        return {
            "success": False,
            "response": f"I couldn't {action} the {strategy} strategy. Please try again.",
        }

    async def _handle_strategy_status(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Report on active strategies."""
        active = [s for s, v in self._active_strategies.items() if v]

        if not active:
            return {
                "success": True,
                "response": "No strategies are currently active.",
            }

        strategies_str = ", ".join(s.replace("_", " ") for s in active)
        return {
            "success": True,
            "response": f"Currently active strategies: {strategies_str}.",
        }

    # =========================================================================
    # Risk Management Handlers
    # =========================================================================

    async def _handle_risk_adjustment(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Handle risk limit adjustments."""
        # Get the parameter being adjusted
        for param_name, value in params.items():
            if param_name in RISK_LIMITS:
                min_val, max_val = RISK_LIMITS[param_name]

                # Validate value
                if value < min_val or value > max_val:
                    return {
                        "success": False,
                        "response": f"That value is outside the safe range. {param_name.replace('_', ' ')} should be between {min_val} and {max_val}.",
                    }

                # Check if aggressive
                if param_name == "max_position_pct" and value > 15:
                    return {
                        "success": False,
                        "response": f"A {value} percent max position is very aggressive. I'd recommend staying under 15 percent. Are you sure?",
                        "requires_confirmation": True,
                    }

                # Update
                success = await self._update_risk_limit(param_name, value)
                if success:
                    self._risk_limits[param_name] = value
                    param_display = param_name.replace("_", " ")
                    return {
                        "success": True,
                        "response": f"Done. {param_display.capitalize()} has been set to {value}{'%' if 'pct' in param_name else ' dollars'}.",
                    }

        return {
            "success": False,
            "response": "I couldn't update the risk settings. Please specify which limit you want to change.",
        }

    async def _handle_risk_query(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Return current risk limits."""
        limits = await self._get_risk_limits()

        response = "Here are your current risk limits. "
        response += f"Max position size: {limits.get('max_position_pct', 5)} percent. "
        response += f"Stop loss: {limits.get('stop_loss_pct', 8)} percent. "
        response += f"Take profit: {limits.get('take_profit_pct', 30)} percent. "
        response += f"Daily loss limit: {limits.get('daily_loss_limit', 1000):.0f} dollars."

        return {
            "success": True,
            "response": response,
            "data": limits,
        }

    # =========================================================================
    # Alert Handlers
    # =========================================================================

    async def _handle_price_alert(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Create a price alert."""
        token = params.get("token", "").upper()
        price = params.get("price", 0)
        direction = params.get("direction", "at")

        if not token or not price:
            return {
                "success": False,
                "response": "Please specify a token and price for the alert.",
            }

        alert = await self._create_price_alert(token, price, direction)

        direction_text = "reaches" if direction == "at" else f"goes {direction}"
        return {
            "success": True,
            "response": f"Done. I'll alert you when {token} {direction_text} {price:.8g} dollars.",
            "data": alert,
        }

    async def _handle_list_alerts(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """List active alerts."""
        alerts = await self._get_alerts()

        if not alerts:
            return {
                "success": True,
                "response": "You don't have any active price alerts.",
            }

        response = f"You have {len(alerts)} active alert{'s' if len(alerts) > 1 else ''}. "
        for i, alert in enumerate(alerts[:3]):  # Limit to 3 for voice
            token = alert.get("token", "")
            price = alert.get("price", 0)
            direction = alert.get("direction", "at")
            response += f"{token} {direction} {price:.8g} dollars. "

        if len(alerts) > 3:
            response += f"And {len(alerts) - 3} more."

        return {
            "success": True,
            "response": response,
            "data": {"alerts": alerts},
        }

    async def _handle_cancel_alert(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Cancel a price alert."""
        token = params.get("token", "").upper()

        if not token:
            return {
                "success": False,
                "response": "Please specify which token's alert to cancel.",
            }

        success = await self._cancel_alert(token)

        if success:
            return {
                "success": True,
                "response": f"Done. The alert for {token} has been canceled.",
            }
        else:
            return {
                "success": False,
                "response": f"I couldn't find an active alert for {token}.",
            }

    # =========================================================================
    # Position Query Handlers
    # =========================================================================

    async def _handle_position_query(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Query positions."""
        token = params.get("token")

        if token:
            # Specific token query
            position = await self._get_position(token)
            if not position:
                return {
                    "success": True,
                    "response": f"You don't have any {token} position.",
                }

            pnl = position.get("pnl_pct", 0)
            pnl_text = f"up {pnl:.1f}" if pnl > 0 else f"down {abs(pnl):.1f}"
            response = f"Your {token} position: {position.get('amount', 0):.4g} tokens "
            response += f"worth {position.get('value_usd', 0):.2f} dollars, "
            response += f"{pnl_text} percent."

            return {
                "success": True,
                "response": response,
                "data": position,
            }

        # All positions
        positions = await self._get_positions()

        if not positions:
            return {
                "success": True,
                "response": "You don't have any open positions right now.",
            }

        response = f"You have {len(positions)} open position{'s' if len(positions) > 1 else ''}. "
        total_value = sum(p.get("value_usd", 0) for p in positions)
        response += f"Total value: {total_value:.2f} dollars. "

        # Top 3 positions
        sorted_positions = sorted(positions, key=lambda x: x.get("value_usd", 0), reverse=True)
        for pos in sorted_positions[:3]:
            token = pos.get("token", "")
            pnl = pos.get("pnl_pct", 0)
            response += f"{token}: {'up' if pnl > 0 else 'down'} {abs(pnl):.1f} percent. "

        return {
            "success": True,
            "response": response,
            "data": {"positions": positions},
        }

    # =========================================================================
    # Market Data Handlers
    # =========================================================================

    async def _handle_price_query(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Query token price."""
        token = params.get("token", "").upper()

        if not token:
            return {
                "success": False,
                "response": "Which token would you like the price for?",
            }

        price_data = await self._get_token_price(token)

        if not price_data:
            return {
                "success": False,
                "response": f"Sorry, I couldn't get the price for {token}.",
            }

        price = price_data.get("price", 0)
        change = price_data.get("change_24h", 0)
        change_text = f"up {change:.1f}" if change > 0 else f"down {abs(change):.1f}"

        # Format price based on magnitude
        if price >= 1:
            price_str = f"{price:.2f}"
        else:
            price_str = f"{price:.8g}"

        response = f"{token} is trading at {price_str} dollars, {change_text} percent in 24 hours."

        return {
            "success": True,
            "response": response,
            "data": price_data,
        }

    async def _handle_market_overview(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """General market overview."""
        overview = await self._get_market_overview()

        fear_greed = overview.get("fear_greed_index", 50)
        sentiment = "greedy" if fear_greed > 55 else "fearful" if fear_greed < 45 else "neutral"

        response = f"The market is looking {sentiment}. "
        response += f"Fear and greed index is at {fear_greed}. "

        trending = overview.get("trending", [])
        if trending:
            response += f"Top trending tokens: {', '.join(trending[:3])}."

        return {
            "success": True,
            "response": response,
            "data": overview,
        }

    # =========================================================================
    # Trade Execution Handlers
    # =========================================================================

    async def _handle_trade_command(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Handle trade execution commands."""
        action = params.get("action", "")
        token = params.get("token", "").upper()
        amount = params.get("amount")
        percentage = params.get("percentage")

        if not token:
            return {
                "success": False,
                "response": "Which token would you like to trade?",
            }

        # Build confirmation message
        if action == "buy":
            if amount:
                confirm_msg = f"Buy {amount:.2f} dollars worth of {token}"
            else:
                confirm_msg = f"Buy {token}"
        elif action == "sell":
            if percentage:
                confirm_msg = f"Sell {percentage:.0f} percent of your {token}"
            else:
                confirm_msg = f"Sell all of your {token}"
        elif action == "close":
            confirm_msg = f"Close your entire {token} position"
        else:
            return {
                "success": False,
                "response": f"I don't understand the trade action '{action}'.",
            }

        # Require confirmation for trades
        if not confirmed:
            return {
                "success": True,
                "response": f"{confirm_msg}. Should I proceed? Say yes to confirm.",
                "requires_confirmation": True,
            }

        # Execute trade
        result = await self._execute_trade(params)

        if result.get("success"):
            return {
                "success": True,
                "response": f"Done. {action.capitalize()} order executed for {token}.",
                "data": result,
            }
        else:
            return {
                "success": False,
                "response": f"The {action} order failed. {result.get('error', 'Please try again.')}",
            }

    async def _handle_unknown(
        self,
        params: Dict[str, Any],
        confirmed: bool
    ) -> Dict[str, Any]:
        """Handle unknown commands."""
        return {
            "success": False,
            "response": "I didn't understand that command. You can ask me for a morning briefing, check prices, view your positions, or set alerts.",
        }

    # =========================================================================
    # Data Access Methods (to be overridden or mocked)
    # =========================================================================

    async def _get_market_data(self) -> Dict[str, Any]:
        """Get market data for briefing."""
        # Try to get real data
        try:
            # Import market data sources
            from core.birdeye import BirdeyeClient

            client = BirdeyeClient()
            sol_data = await client.get_token_price("So11111111111111111111111111111111111111112")

            return {
                "sol_price": sol_data.get("price", 0),
                "sol_24h_change": sol_data.get("priceChange24h", 0),
                "btc_price": 95000,  # Placeholder
                "btc_24h_change": 1.5,
                "total_positions": 0,
                "portfolio_value": 0,
                "pnl_24h": 0,
            }
        except Exception as e:
            logger.debug(f"Could not get live market data: {e}")
            # Return placeholder data
            return {
                "sol_price": 180.0,
                "sol_24h_change": 2.5,
                "btc_price": 95000,
                "btc_24h_change": 1.0,
                "total_positions": 0,
                "portfolio_value": 0,
                "pnl_24h": 0,
            }

    async def _set_strategy_state(self, strategy: str, active: bool) -> bool:
        """Set strategy activation state."""
        # Placeholder - would integrate with strategy manager
        return True

    async def _update_risk_limit(self, param: str, value: float) -> bool:
        """Update a risk limit."""
        # Placeholder - would integrate with risk manager
        return True

    async def _get_risk_limits(self) -> Dict[str, float]:
        """Get current risk limits."""
        return self._risk_limits.copy()

    async def _create_price_alert(
        self,
        token: str,
        price: float,
        direction: str
    ) -> Dict[str, Any]:
        """Create a price alert."""
        alert = {
            "id": f"alert_{len(self._alerts) + 1}",
            "token": token,
            "price": price,
            "direction": direction,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._alerts.append(alert)
        return alert

    async def _get_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts."""
        return self._alerts.copy()

    async def _cancel_alert(self, token: str) -> bool:
        """Cancel an alert by token."""
        for i, alert in enumerate(self._alerts):
            if alert.get("token") == token:
                self._alerts.pop(i)
                return True
        return False

    async def _get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        # Placeholder - would integrate with position manager
        return []

    async def _get_position(self, token: str) -> Optional[Dict[str, Any]]:
        """Get specific position."""
        # Placeholder
        return None

    async def _get_token_price(self, token: str) -> Optional[Dict[str, Any]]:
        """Get token price data."""
        try:
            from core.birdeye import BirdeyeClient

            client = BirdeyeClient()

            # Map common names to addresses
            TOKEN_ADDRESSES = {
                "SOL": "So11111111111111111111111111111111111111112",
                # Add more as needed
            }

            address = TOKEN_ADDRESSES.get(token.upper())
            if address:
                data = await client.get_token_price(address)
                return {
                    "token": token,
                    "price": data.get("price", 0),
                    "change_24h": data.get("priceChange24h", 0),
                    "volume_24h": data.get("volume24h", 0),
                }
        except Exception as e:
            logger.debug(f"Could not get price for {token}: {e}")

        # Return placeholder
        return {
            "token": token,
            "price": 180.50,
            "change_24h": 5.2,
            "volume_24h": 1500000000,
        }

    async def _get_market_overview(self) -> Dict[str, Any]:
        """Get market overview data."""
        return {
            "btc_dominance": 52.5,
            "total_market_cap": 3500000000000,
            "fear_greed_index": 65,
            "trending": ["SOL", "BONK", "WIF"],
        }

    async def _execute_trade(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade."""
        # Placeholder - would integrate with trading engine
        return {
            "success": True,
            "tx_signature": "placeholder_tx",
        }
