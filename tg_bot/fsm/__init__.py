"""
FSM (Finite State Machine) Module for Telegram Bot.

Provides session management with Redis persistence for conversational flows.

Features:
- State definitions for trading, wallet, portfolio, and settings flows
- Redis-backed persistence for state and session data
- Wallet-per-session isolation
- Automatic session cleanup (TTL-based)
- Session recovery on bot restart
- In-memory fallback when Redis is unavailable
- Context manager for easy handler integration
- State-based message routing
"""

from tg_bot.fsm.states import (
    TradingStates,
    WalletStates,
    PortfolioStates,
    SettingsStates,
    SessionData,
    FSMState,
    is_valid_transition,
    parse_state_string,
)

from tg_bot.fsm.storage import (
    RedisFSMStorage,
    get_fsm_storage,
    reset_fsm_storage,
)

from tg_bot.fsm.context import (
    FSMContext,
)

from tg_bot.fsm.middleware import (
    FSMMiddleware,
    get_fsm_context,
)

from tg_bot.fsm.router import (
    FSMRouter,
    get_trading_router,
)

__all__ = [
    # States
    "TradingStates",
    "WalletStates",
    "PortfolioStates",
    "SettingsStates",
    "SessionData",
    "FSMState",
    "is_valid_transition",
    "parse_state_string",
    # Storage
    "RedisFSMStorage",
    "get_fsm_storage",
    "reset_fsm_storage",
    # Context
    "FSMContext",
    # Middleware
    "FSMMiddleware",
    "get_fsm_context",
    # Router
    "FSMRouter",
    "get_trading_router",
]
