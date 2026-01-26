"""
FSM Router for State-Based Message Handling.

Routes incoming messages to handlers based on current FSM state.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from tg_bot.fsm.context import FSMContext
from tg_bot.fsm.states import FSMState

logger = logging.getLogger(__name__)


class FSMRouter:
    """
    Routes messages to handlers based on FSM state.

    Usage:
        router = FSMRouter()

        @router.on(TradingStates.waiting_for_token)
        async def handle_token(update, context, fsm):
            # Process token input
            ...

        # In message handler
        result = await router.dispatch(update, fsm_context)
    """

    def __init__(self):
        """Initialize router."""
        self._handlers: Dict[FSMState, List[Callable]] = {}
        self._fallback_handler: Optional[Callable] = None

    def register(
        self,
        state: FSMState,
        handler: Callable,
    ) -> None:
        """
        Register a handler for a state.

        Args:
            state: FSM state to handle
            handler: Handler function
        """
        if state not in self._handlers:
            self._handlers[state] = []

        self._handlers[state].append(handler)
        logger.debug(f"Registered handler for state {state}")

    def on(self, state: FSMState) -> Callable:
        """
        Decorator to register a handler for a state.

        Usage:
            @router.on(TradingStates.waiting_for_token)
            async def handle_token(update, context, fsm):
                ...
        """
        def decorator(handler: Callable) -> Callable:
            self.register(state, handler)
            return handler
        return decorator

    def set_fallback(self, handler: Callable) -> None:
        """
        Set fallback handler for unmatched states.

        Args:
            handler: Fallback handler function
        """
        self._fallback_handler = handler

    def fallback(self) -> Callable:
        """
        Decorator to set fallback handler.

        Usage:
            @router.fallback()
            async def handle_fallback(update, context, fsm):
                ...
        """
        def decorator(handler: Callable) -> Callable:
            self.set_fallback(handler)
            return handler
        return decorator

    async def dispatch(
        self,
        update: Any,
        fsm_context: FSMContext,
        telegram_context: Optional[Any] = None,
    ) -> Optional[Any]:
        """
        Dispatch update to appropriate handler based on state.

        Args:
            update: Telegram Update
            fsm_context: FSM context for the user
            telegram_context: Optional telegram CallbackContext

        Returns:
            Handler result or None if no matching handler
        """
        # Get current state
        state = await fsm_context.get_state()

        if state is None:
            # No active state - try fallback
            if self._fallback_handler:
                return await self._fallback_handler(update, telegram_context, fsm_context)
            return None

        # Find handlers for state
        handlers = self._handlers.get(state, [])

        if not handlers:
            # No handlers for state - try fallback
            if self._fallback_handler:
                return await self._fallback_handler(update, telegram_context, fsm_context)

            logger.warning(f"No handler registered for state {state}")
            return None

        # Call first matching handler (could extend to try all)
        handler = handlers[0]
        try:
            return await handler(update, telegram_context, fsm_context)
        except Exception as e:
            logger.error(f"Error in FSM handler for {state}: {e}")
            raise

    def get_states(self) -> List[FSMState]:
        """Get list of all registered states."""
        return list(self._handlers.keys())


# Global router instance
_trading_router: Optional[FSMRouter] = None


def get_trading_router() -> FSMRouter:
    """Get the global trading router instance."""
    global _trading_router
    if _trading_router is None:
        _trading_router = FSMRouter()
    return _trading_router


__all__ = ["FSMRouter", "get_trading_router"]
