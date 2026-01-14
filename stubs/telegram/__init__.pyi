# Type stubs for python-telegram-bot
from typing import Any, Optional, List, Dict, Callable, Union, Awaitable

class Bot:
    def __init__(self, token: str) -> None: ...
    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional["ReplyMarkup"] = None,
        **kwargs: Any
    ) -> "Message": ...
    async def get_me(self) -> "User": ...

class Update:
    update_id: int
    message: Optional["Message"]
    callback_query: Optional["CallbackQuery"]
    effective_user: Optional["User"]
    effective_chat: Optional["Chat"]

class Message:
    message_id: int
    date: Any  # datetime
    chat: "Chat"
    from_user: Optional["User"]
    text: Optional[str]

    async def reply_text(
        self,
        text: str,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> "Message": ...

class User:
    id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    is_bot: bool

class Chat:
    id: int
    type: str
    title: Optional[str]
    username: Optional[str]

class CallbackQuery:
    id: str
    data: Optional[str]
    message: Optional[Message]
    from_user: User

    async def answer(self, text: Optional[str] = None, **kwargs: Any) -> bool: ...

class ReplyMarkup: ...

class InlineKeyboardMarkup(ReplyMarkup):
    def __init__(self, inline_keyboard: List[List["InlineKeyboardButton"]]) -> None: ...

class InlineKeyboardButton:
    def __init__(
        self,
        text: str,
        callback_data: Optional[str] = None,
        url: Optional[str] = None,
        **kwargs: Any
    ) -> None: ...

class CommandHandler:
    def __init__(
        self,
        command: str,
        callback: Callable[..., Awaitable[None]],
        **kwargs: Any
    ) -> None: ...

class MessageHandler:
    def __init__(
        self,
        filters: Any,
        callback: Callable[..., Awaitable[None]],
        **kwargs: Any
    ) -> None: ...

class CallbackQueryHandler:
    def __init__(
        self,
        callback: Callable[..., Awaitable[None]],
        pattern: Optional[str] = None,
        **kwargs: Any
    ) -> None: ...

class Application:
    @classmethod
    def builder(cls) -> "ApplicationBuilder": ...
    def add_handler(self, handler: Any) -> None: ...
    async def run_polling(self) -> None: ...

class ApplicationBuilder:
    def token(self, token: str) -> "ApplicationBuilder": ...
    def build(self) -> Application: ...

class ContextTypes:
    DEFAULT_TYPE: Any
