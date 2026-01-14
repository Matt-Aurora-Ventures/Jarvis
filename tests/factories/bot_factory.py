"""
Bot Factory

Factory classes for generating bot-related test data
for Telegram and Twitter integrations.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .base import BaseFactory, RandomData, SequenceGenerator


@dataclass
class TelegramUser:
    """Telegram user model for testing."""
    id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    is_bot: bool
    language_code: Optional[str]


class TelegramUserFactory(BaseFactory[TelegramUser]):
    """Factory for Telegram users."""

    @classmethod
    def _build(
        cls,
        id: Optional[int] = None,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_bot: bool = False,
        language_code: str = "en",
        **kwargs
    ) -> TelegramUser:
        """Build a TelegramUser instance."""
        seq = SequenceGenerator.next("tg_user")

        return TelegramUser(
            id=id or RandomData.telegram_id(),
            username=username or f"user{seq}",
            first_name=first_name or RandomData.choice(["Alice", "Bob", "Charlie"]),
            last_name=last_name,
            is_bot=is_bot,
            language_code=language_code,
        )


@dataclass
class TelegramChat:
    """Telegram chat model for testing."""
    id: int
    type: str
    title: Optional[str]
    username: Optional[str]


class TelegramChatFactory(BaseFactory[TelegramChat]):
    """Factory for Telegram chats."""

    @classmethod
    def _build(
        cls,
        id: Optional[int] = None,
        type: str = "private",
        title: Optional[str] = None,
        username: Optional[str] = None,
        **kwargs
    ) -> TelegramChat:
        """Build a TelegramChat instance."""
        return TelegramChat(
            id=id or RandomData.telegram_id(),
            type=type,
            title=title,
            username=username,
        )


@dataclass
class TelegramMessage:
    """Telegram message model for testing."""
    message_id: int
    date: datetime
    chat: TelegramChat
    from_user: TelegramUser
    text: Optional[str]
    reply_to_message: Optional['TelegramMessage']


class TelegramMessageFactory(BaseFactory[TelegramMessage]):
    """Factory for Telegram messages."""

    @classmethod
    def _build(
        cls,
        message_id: Optional[int] = None,
        date: Optional[datetime] = None,
        chat: Optional[TelegramChat] = None,
        from_user: Optional[TelegramUser] = None,
        text: Optional[str] = None,
        reply_to_message: Optional[TelegramMessage] = None,
        **kwargs
    ) -> TelegramMessage:
        """Build a TelegramMessage instance."""
        return TelegramMessage(
            message_id=message_id or SequenceGenerator.next("tg_message"),
            date=date or datetime.utcnow(),
            chat=chat or TelegramChatFactory.build(),
            from_user=from_user or TelegramUserFactory.build(),
            text=text or "/help",
            reply_to_message=reply_to_message,
        )


@dataclass
class TelegramUpdate:
    """Telegram update model for testing."""
    update_id: int
    message: Optional[TelegramMessage]
    callback_query: Optional[Dict[str, Any]]
    edited_message: Optional[TelegramMessage]


class TelegramUpdateFactory(BaseFactory[TelegramUpdate]):
    """Factory for Telegram updates."""

    @classmethod
    def _build(
        cls,
        update_id: Optional[int] = None,
        message: Optional[TelegramMessage] = None,
        callback_query: Optional[Dict[str, Any]] = None,
        edited_message: Optional[TelegramMessage] = None,
        text: Optional[str] = None,
        **kwargs
    ) -> TelegramUpdate:
        """Build a TelegramUpdate instance."""
        # If text is provided, create a message with that text
        if message is None and text is not None:
            message = TelegramMessageFactory.build(text=text)
        elif message is None:
            message = TelegramMessageFactory.build()

        return TelegramUpdate(
            update_id=update_id or SequenceGenerator.next("tg_update"),
            message=message,
            callback_query=callback_query,
            edited_message=edited_message,
        )


class CommandUpdateFactory(TelegramUpdateFactory):
    """Factory for command updates."""

    @classmethod
    def _build(cls, command: str = "/help", **kwargs) -> TelegramUpdate:
        kwargs.setdefault('text', command)
        return super()._build(**kwargs)


# Twitter factories

@dataclass
class TwitterUser:
    """Twitter user model for testing."""
    id: str
    username: str
    name: str
    followers_count: int
    verified: bool


class TwitterUserFactory(BaseFactory[TwitterUser]):
    """Factory for Twitter users."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        username: Optional[str] = None,
        name: Optional[str] = None,
        followers_count: Optional[int] = None,
        verified: bool = False,
        **kwargs
    ) -> TwitterUser:
        """Build a TwitterUser instance."""
        seq = SequenceGenerator.next("twitter_user")

        return TwitterUser(
            id=id or RandomData.twitter_id(),
            username=username or f"user{seq}",
            name=name or RandomData.full_name(),
            followers_count=followers_count or RandomData.integer(100, 100000),
            verified=verified,
        )


@dataclass
class Tweet:
    """Tweet model for testing."""
    id: str
    text: str
    author: TwitterUser
    created_at: datetime
    in_reply_to_user_id: Optional[str]
    referenced_tweets: List[Dict[str, str]]
    public_metrics: Dict[str, int]


class TweetFactory(BaseFactory[Tweet]):
    """Factory for tweets."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        text: Optional[str] = None,
        author: Optional[TwitterUser] = None,
        created_at: Optional[datetime] = None,
        in_reply_to_user_id: Optional[str] = None,
        referenced_tweets: Optional[List[Dict[str, str]]] = None,
        public_metrics: Optional[Dict[str, int]] = None,
        **kwargs
    ) -> Tweet:
        """Build a Tweet instance."""
        return Tweet(
            id=id or str(SequenceGenerator.next("tweet")),
            text=text or "Test tweet content #crypto",
            author=author or TwitterUserFactory.build(),
            created_at=created_at or datetime.utcnow(),
            in_reply_to_user_id=in_reply_to_user_id,
            referenced_tweets=referenced_tweets or [],
            public_metrics=public_metrics or {
                "retweet_count": RandomData.integer(0, 100),
                "reply_count": RandomData.integer(0, 50),
                "like_count": RandomData.integer(0, 500),
                "quote_count": RandomData.integer(0, 20),
            },
        )


@dataclass
class TwitterMention:
    """Twitter mention model for testing."""
    id: str
    text: str
    author_id: str
    author_username: str
    created_at: datetime


class TwitterMentionFactory(BaseFactory[TwitterMention]):
    """Factory for Twitter mentions."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        text: Optional[str] = None,
        author_id: Optional[str] = None,
        author_username: Optional[str] = None,
        created_at: Optional[datetime] = None,
        **kwargs
    ) -> TwitterMention:
        """Build a TwitterMention instance."""
        seq = SequenceGenerator.next("mention")

        return TwitterMention(
            id=id or str(seq),
            text=text or "@jarvis_bot what's the SOL price?",
            author_id=author_id or RandomData.twitter_id(),
            author_username=author_username or f"user{seq}",
            created_at=created_at or datetime.utcnow(),
        )


# Bot event factories

@dataclass
class BotEvent:
    """Bot event model for testing."""
    id: str
    bot_type: str
    event_type: str
    user_id: str
    data: Dict[str, Any]
    created_at: datetime


class BotEventFactory(BaseFactory[BotEvent]):
    """Factory for bot events."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        bot_type: str = "telegram",
        event_type: str = "message",
        user_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        **kwargs
    ) -> BotEvent:
        """Build a BotEvent instance."""
        return BotEvent(
            id=id or RandomData.uuid(),
            bot_type=bot_type,
            event_type=event_type,
            user_id=user_id or str(RandomData.telegram_id()),
            data=data or {},
            created_at=created_at or datetime.utcnow(),
        )
