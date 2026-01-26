"""
FSM State Definitions for Telegram Bot.

Defines all conversation states for trading, wallet, portfolio, and settings flows.
States are compatible with aiogram-style FSM patterns but work with python-telegram-bot.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class StateBase:
    """Base class for FSM state groups."""

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.name}"

    def __repr__(self) -> str:
        return str(self)


class TradingStates(Enum):
    """
    States for trading flows (buy/sell/swap).

    Flow: waiting_for_token -> waiting_for_amount -> setting_slippage
          -> setting_tp_sl -> waiting_for_confirmation -> (execute/cancel)
    """

    # Token selection
    waiting_for_token = "trading:waiting_for_token"

    # Amount input
    waiting_for_amount = "trading:waiting_for_amount"

    # Trade confirmation
    waiting_for_confirmation = "trading:waiting_for_confirmation"

    # Risk settings
    setting_slippage = "trading:setting_slippage"
    setting_tp_sl = "trading:setting_tp_sl"

    # Execution
    executing_trade = "trading:executing_trade"

    def __str__(self) -> str:
        return f"TradingStates:{self.name}"


class WalletStates(Enum):
    """
    States for wallet management flows.

    Flow: viewing_balance -> selecting_wallet -> (withdraw flow)
    """

    viewing_balance = "wallet:viewing_balance"
    selecting_wallet = "wallet:selecting_wallet"
    confirming_withdraw = "wallet:confirming_withdraw"
    entering_withdraw_amount = "wallet:entering_withdraw_amount"
    entering_withdraw_address = "wallet:entering_withdraw_address"

    def __str__(self) -> str:
        return f"WalletStates:{self.name}"


class PortfolioStates(Enum):
    """
    States for portfolio management flows.

    Flow: viewing_positions -> selecting_position -> (close/modify)
    """

    viewing_positions = "portfolio:viewing_positions"
    selecting_position = "portfolio:selecting_position"
    closing_position = "portfolio:closing_position"
    modifying_tp_sl = "portfolio:modifying_tp_sl"

    def __str__(self) -> str:
        return f"PortfolioStates:{self.name}"


class SettingsStates(Enum):
    """
    States for user settings flows.

    Flow: main_menu -> (edit specific setting) -> main_menu
    """

    main_menu = "settings:main_menu"
    editing_slippage = "settings:editing_slippage"
    editing_default_tp = "settings:editing_default_tp"
    editing_default_sl = "settings:editing_default_sl"
    editing_notifications = "settings:editing_notifications"

    def __str__(self) -> str:
        return f"SettingsStates:{self.name}"


# Type alias for any FSM state
FSMState = Union[TradingStates, WalletStates, PortfolioStates, SettingsStates, None]


@dataclass
class SessionData:
    """
    Session data for FSM flows.

    Stores all context needed for a user's current conversation flow.
    Supports serialization to/from dict for Redis persistence.
    """

    # Identity (required)
    user_id: int
    chat_id: int

    # Wallet context (isolated per session)
    wallet_address: Optional[str] = None

    # Trade context
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    amount: Optional[float] = None
    slippage: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None

    # Position context (for closing/modifying)
    position_id: Optional[str] = None

    # Withdraw context
    withdraw_address: Optional[str] = None
    withdraw_amount: Optional[float] = None

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Previous messages for cleanup
    message_ids: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Create from dictionary."""
        # Handle missing fields for backwards compatibility
        defaults = {
            "wallet_address": None,
            "token_address": None,
            "token_symbol": None,
            "amount": None,
            "slippage": None,
            "take_profit": None,
            "stop_loss": None,
            "position_id": None,
            "withdraw_address": None,
            "withdraw_amount": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message_ids": [],
        }

        # Merge defaults with provided data
        merged = {**defaults, **data}

        return cls(
            user_id=merged["user_id"],
            chat_id=merged["chat_id"],
            wallet_address=merged["wallet_address"],
            token_address=merged["token_address"],
            token_symbol=merged["token_symbol"],
            amount=merged["amount"],
            slippage=merged["slippage"],
            take_profit=merged["take_profit"],
            stop_loss=merged["stop_loss"],
            position_id=merged["position_id"],
            withdraw_address=merged["withdraw_address"],
            withdraw_amount=merged["withdraw_amount"],
            created_at=merged["created_at"],
            updated_at=merged["updated_at"],
            message_ids=merged["message_ids"],
        )

    def update(self, **kwargs) -> "SessionData":
        """Update fields and return self."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self

    def clear_trade_context(self) -> "SessionData":
        """Clear trade-specific fields."""
        self.token_address = None
        self.token_symbol = None
        self.amount = None
        self.slippage = None
        self.take_profit = None
        self.stop_loss = None
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self

    def clear_withdraw_context(self) -> "SessionData":
        """Clear withdraw-specific fields."""
        self.withdraw_address = None
        self.withdraw_amount = None
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self


# Valid state transitions for each state type
_VALID_TRANSITIONS: Dict[Optional[FSMState], Set[Optional[FSMState]]] = {
    # From idle/None
    None: {
        TradingStates.waiting_for_token,
        WalletStates.viewing_balance,
        PortfolioStates.viewing_positions,
        SettingsStates.main_menu,
    },

    # Trading flow transitions
    TradingStates.waiting_for_token: {
        TradingStates.waiting_for_amount,
        None,  # Cancel
    },
    TradingStates.waiting_for_amount: {
        TradingStates.setting_slippage,
        TradingStates.waiting_for_confirmation,  # Skip slippage if using defaults
        TradingStates.waiting_for_token,  # Go back
        None,
    },
    TradingStates.setting_slippage: {
        TradingStates.setting_tp_sl,
        TradingStates.waiting_for_confirmation,  # Skip TP/SL if using defaults
        TradingStates.waiting_for_amount,  # Go back
        None,
    },
    TradingStates.setting_tp_sl: {
        TradingStates.waiting_for_confirmation,
        TradingStates.setting_slippage,  # Go back
        None,
    },
    TradingStates.waiting_for_confirmation: {
        TradingStates.executing_trade,
        TradingStates.setting_tp_sl,  # Go back
        TradingStates.waiting_for_amount,  # Edit amount
        None,
    },
    TradingStates.executing_trade: {
        None,  # Complete
    },

    # Wallet flow transitions
    WalletStates.viewing_balance: {
        WalletStates.selecting_wallet,
        WalletStates.entering_withdraw_amount,
        None,
    },
    WalletStates.selecting_wallet: {
        WalletStates.viewing_balance,
        None,
    },
    WalletStates.entering_withdraw_amount: {
        WalletStates.entering_withdraw_address,
        WalletStates.viewing_balance,
        None,
    },
    WalletStates.entering_withdraw_address: {
        WalletStates.confirming_withdraw,
        WalletStates.entering_withdraw_amount,
        None,
    },
    WalletStates.confirming_withdraw: {
        WalletStates.viewing_balance,
        None,
    },

    # Portfolio flow transitions
    PortfolioStates.viewing_positions: {
        PortfolioStates.selecting_position,
        None,
    },
    PortfolioStates.selecting_position: {
        PortfolioStates.closing_position,
        PortfolioStates.modifying_tp_sl,
        PortfolioStates.viewing_positions,
        None,
    },
    PortfolioStates.closing_position: {
        PortfolioStates.viewing_positions,
        PortfolioStates.selecting_position,
        None,
    },
    PortfolioStates.modifying_tp_sl: {
        PortfolioStates.selecting_position,
        PortfolioStates.viewing_positions,
        None,
    },

    # Settings flow transitions
    SettingsStates.main_menu: {
        SettingsStates.editing_slippage,
        SettingsStates.editing_default_tp,
        SettingsStates.editing_default_sl,
        SettingsStates.editing_notifications,
        None,
    },
    SettingsStates.editing_slippage: {
        SettingsStates.main_menu,
        None,
    },
    SettingsStates.editing_default_tp: {
        SettingsStates.main_menu,
        None,
    },
    SettingsStates.editing_default_sl: {
        SettingsStates.main_menu,
        None,
    },
    SettingsStates.editing_notifications: {
        SettingsStates.main_menu,
        None,
    },
}


def is_valid_transition(from_state: Optional[FSMState], to_state: Optional[FSMState]) -> bool:
    """
    Check if a state transition is valid.

    Args:
        from_state: Current state (None = idle)
        to_state: Target state (None = return to idle)

    Returns:
        True if transition is valid
    """
    # Self-transition is always valid
    if from_state == to_state:
        return True

    # Check transition table
    valid_targets = _VALID_TRANSITIONS.get(from_state, set())
    return to_state in valid_targets


def parse_state_string(state_str: str) -> Optional[FSMState]:
    """
    Parse a state string back to a state enum.

    Args:
        state_str: String like "TradingStates:waiting_for_token"

    Returns:
        The corresponding FSMState or None
    """
    if not state_str or state_str == "None":
        return None

    try:
        class_name, state_name = state_str.split(":", 1)

        if class_name == "TradingStates":
            return TradingStates[state_name]
        elif class_name == "WalletStates":
            return WalletStates[state_name]
        elif class_name == "PortfolioStates":
            return PortfolioStates[state_name]
        elif class_name == "SettingsStates":
            return SettingsStates[state_name]

    except (ValueError, KeyError):
        pass

    return None


__all__ = [
    "TradingStates",
    "WalletStates",
    "PortfolioStates",
    "SettingsStates",
    "FSMState",
    "SessionData",
    "is_valid_transition",
    "parse_state_string",
]
