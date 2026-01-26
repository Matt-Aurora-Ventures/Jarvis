"""
FSM Middleware for Telegram Bot.

Injects FSM context into handlers for easy state management.
"""

import logging
from typing import Any, Callable, Optional

from tg_bot.fsm.context import FSMContext
from tg_bot.fsm.storage import RedisFSMStorage, get_fsm_storage

logger = logging.getLogger(__name__)


class FSMMiddleware:
    """
    Middleware that injects FSMContext into handler context.

    Usage:
        # In bot setup
        storage = get_fsm_storage()
        middleware = FSMMiddleware(storage)

        # Register with application
        app.add_handler(TypeHandler(Update, middleware.pre_process), group=-2)

        # In handlers
        async def my_handler(update, context):
            fsm: FSMContext = context.user_data.get("fsm")
            state = await fsm.get_state()
    """

    def __init__(self, storage: Optional[RedisFSMStorage] = None):
        """
        Initialize middleware.

        Args:
            storage: FSM storage instance (uses singleton if not provided)
        """
        self.storage = storage or get_fsm_storage()

    async def __call__(
        self,
        handler: Callable,
        update: Any,
        context: Any
    ) -> Any:
        """
        Process update through middleware.

        Injects FSMContext into context.user_data["fsm"] before
        calling the handler.

        Args:
            handler: The handler function to call
            update: Telegram Update object
            context: Telegram CallbackContext

        Returns:
            Handler result
        """
        # Get user and chat IDs
        user_id = None
        chat_id = None

        if hasattr(update, 'effective_user') and update.effective_user:
            user_id = update.effective_user.id

        if hasattr(update, 'effective_chat') and update.effective_chat:
            chat_id = update.effective_chat.id
        elif hasattr(update, 'message') and update.message:
            chat_id = update.message.chat_id

        # Inject FSM context if we have user/chat IDs
        if user_id is not None and chat_id is not None:
            fsm_ctx = FSMContext(
                storage=self.storage,
                user_id=user_id,
                chat_id=chat_id,
            )

            # Ensure user_data exists
            if not hasattr(context, 'user_data'):
                context.user_data = {}
            elif context.user_data is None:
                context.user_data = {}

            context.user_data["fsm"] = fsm_ctx

        # Call the handler
        return await handler(update, context)

    async def pre_process(self, update: Any, context: Any) -> None:
        """
        Pre-process hook for python-telegram-bot.

        Injects FSMContext into context.user_data.

        Args:
            update: Telegram Update
            context: Telegram CallbackContext
        """
        # Get user and chat IDs
        user_id = None
        chat_id = None

        if hasattr(update, 'effective_user') and update.effective_user:
            user_id = update.effective_user.id

        if hasattr(update, 'effective_chat') and update.effective_chat:
            chat_id = update.effective_chat.id
        elif hasattr(update, 'message') and update.message:
            chat_id = update.message.chat_id

        # Inject FSM context if we have user/chat IDs
        if user_id is not None and chat_id is not None:
            fsm_ctx = FSMContext(
                storage=self.storage,
                user_id=user_id,
                chat_id=chat_id,
            )

            # Ensure user_data exists
            if not hasattr(context, 'user_data'):
                context.user_data = {}
            elif context.user_data is None:
                context.user_data = {}

            context.user_data["fsm"] = fsm_ctx


def get_fsm_context(context: Any) -> Optional[FSMContext]:
    """
    Helper to get FSMContext from handler context.

    Args:
        context: Telegram CallbackContext

    Returns:
        FSMContext or None if not available
    """
    if hasattr(context, 'user_data') and context.user_data:
        return context.user_data.get("fsm")
    return None


__all__ = ["FSMMiddleware", "get_fsm_context"]
