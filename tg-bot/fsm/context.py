"""
FSM Context for Telegram Bot Handlers.

Provides a convenient interface for handlers to interact with FSM state and data.
"""

import logging
from typing import Any, Dict, Optional

from tg_bot.fsm.states import FSMState, SessionData
from tg_bot.fsm.storage import RedisFSMStorage

logger = logging.getLogger(__name__)


class FSMContext:
    """
    Context manager for FSM state and data in handlers.

    Provides a clean interface for:
    - Getting/setting current state
    - Getting/setting session data
    - Updating specific data fields
    - Clearing/finishing state machine

    Usage in handlers:
        async def handle_token_input(update, context):
            fsm: FSMContext = context.user_data.get("fsm")

            # Get current data
            data = await fsm.get_data()

            # Update with new token
            await fsm.update_data(token_address=update.message.text)

            # Transition to next state
            await fsm.set_state(TradingStates.waiting_for_amount)
    """

    def __init__(
        self,
        storage: RedisFSMStorage,
        user_id: int,
        chat_id: int,
    ):
        """
        Initialize FSM context.

        Args:
            storage: Redis FSM storage instance
            user_id: Telegram user ID
            chat_id: Telegram chat ID
        """
        self.storage = storage
        self.user_id = user_id
        self.chat_id = chat_id

        # Local cache for current request
        self._state_cache: Optional[FSMState] = None
        self._data_cache: Optional[SessionData] = None
        self._cache_loaded = False

    async def get_state(self) -> Optional[FSMState]:
        """
        Get current FSM state.

        Returns:
            Current state or None if idle
        """
        if not self._cache_loaded:
            self._state_cache = await self.storage.get_state(self.user_id, self.chat_id)
            self._cache_loaded = True

        return self._state_cache

    async def set_state(self, state: Optional[FSMState]) -> bool:
        """
        Set FSM state.

        Args:
            state: New state (None to return to idle)

        Returns:
            True if successful
        """
        result = await self.storage.set_state(self.user_id, self.chat_id, state)
        if result:
            self._state_cache = state

        return result

    async def get_data(self) -> Optional[SessionData]:
        """
        Get session data.

        Returns:
            Session data or None if not found
        """
        if self._data_cache is None:
            self._data_cache = await self.storage.get_data(self.user_id, self.chat_id)

        return self._data_cache

    async def set_data(self, data: SessionData) -> bool:
        """
        Set session data.

        Args:
            data: Session data to store

        Returns:
            True if successful
        """
        result = await self.storage.set_data(self.user_id, self.chat_id, data)
        if result:
            self._data_cache = data

        return result

    async def update_data(self, **updates) -> Optional[SessionData]:
        """
        Update specific fields in session data.

        Args:
            **updates: Fields to update

        Returns:
            Updated session data or None if failed

        Example:
            await ctx.update_data(amount=1.5, slippage=0.02)
        """
        data = await self.get_data()

        if data is None:
            # Create new session data with updates
            data = SessionData(
                user_id=self.user_id,
                chat_id=self.chat_id,
                **updates
            )
            await self.set_data(data)
            return data

        # Update existing data
        data.update(**updates)
        await self.set_data(data)
        return data

    async def clear(self) -> bool:
        """
        Clear state and data (return to idle).

        Returns:
            True if successful
        """
        result = await self.storage.clear(self.user_id, self.chat_id)

        # Clear local cache
        self._state_cache = None
        self._data_cache = None
        self._cache_loaded = False

        return result

    async def finish(self) -> bool:
        """
        Finish state machine (alias for clear).

        Returns:
            True if successful
        """
        return await self.clear()

    async def touch(self) -> bool:
        """
        Refresh session TTL (keep alive).

        Returns:
            True if session exists and was refreshed
        """
        return await self.storage.touch(self.user_id, self.chat_id)

    def __repr__(self) -> str:
        return f"FSMContext(user_id={self.user_id}, chat_id={self.chat_id})"


__all__ = ["FSMContext"]
