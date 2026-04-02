"""
Custom Telegram bot filters for Jarvis.

This module provides reusable message filters for:
- Admin authorization
- Chat type filtering (private, group, supergroup, channel)
- Message content patterns (commands, mentions, tokens)
- User-based filters (subscribers, verified users)
- Spam detection patterns
- Media type filtering
- Rate limiting filters

Usage:
    from tg_bot.filters import AdminFilter, TokenMentionFilter
    from telegram.ext import MessageHandler

    app.add_handler(MessageHandler(AdminFilter(), handle_admin_message))
    app.add_handler(MessageHandler(TokenMentionFilter(), handle_token_message))
"""

import logging
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Pattern, Set, Union

from telegram import Message, Update
from telegram.ext.filters import MessageFilter, UpdateFilter

logger = logging.getLogger(__name__)


# ============================================================================
# Base Filter Classes
# ============================================================================

class BaseMessageFilter(MessageFilter, ABC):
    """
    Abstract base class for custom message filters.

    Subclasses must implement the `filter` method that returns
    True if the message should be processed, False otherwise.
    """

    def __init__(self, name: str = None):
        """Initialize filter with optional name for debugging."""
        super().__init__(name=name or self.__class__.__name__)

    @abstractmethod
    def filter(self, message: Message) -> bool:
        """
        Determine if message passes the filter.

        Args:
            message: Telegram Message object

        Returns:
            True if message should be processed, False otherwise
        """
        pass


class BaseUpdateFilter(UpdateFilter, ABC):
    """
    Abstract base class for custom update filters.

    Works on the Update object level, not just Message.
    """

    def __init__(self, name: str = None):
        """Initialize filter with optional name for debugging."""
        super().__init__(name=name or self.__class__.__name__)

    @abstractmethod
    def filter(self, update: Update) -> bool:
        """
        Determine if update passes the filter.

        Args:
            update: Telegram Update object

        Returns:
            True if update should be processed, False otherwise
        """
        pass


# ============================================================================
# Admin Filters
# ============================================================================

class AdminFilter(BaseMessageFilter):
    """
    Filter that only allows messages from admin users.

    Admin IDs are loaded from environment variable TELEGRAM_ADMIN_IDS.
    """

    def __init__(self, admin_ids: Set[int] = None):
        """
        Initialize admin filter.

        Args:
            admin_ids: Set of admin user IDs. If None, loads from environment.
        """
        super().__init__("AdminFilter")
        self._admin_ids = admin_ids if admin_ids is not None else self._load_admin_ids()

    @staticmethod
    def _load_admin_ids() -> Set[int]:
        """Load admin IDs from environment variable."""
        ids_str = os.environ.get("TELEGRAM_ADMIN_IDS", "")
        if not ids_str:
            return set()
        ids = set()
        for id_str in ids_str.split(","):
            id_str = id_str.strip()
            if id_str.isdigit():
                ids.add(int(id_str))
        return ids

    @property
    def admin_ids(self) -> Set[int]:
        """Return set of admin IDs."""
        return self._admin_ids

    def add_admin(self, user_id: int) -> None:
        """Add an admin ID at runtime."""
        self._admin_ids.add(user_id)

    def remove_admin(self, user_id: int) -> None:
        """Remove an admin ID at runtime."""
        self._admin_ids.discard(user_id)

    def filter(self, message: Message) -> bool:
        """Check if message is from an admin user."""
        if not message.from_user:
            return False
        return message.from_user.id in self._admin_ids


class AdminOrOwnerFilter(BaseMessageFilter):
    """
    Filter that allows messages from admins or chat owners.

    Useful for group moderation commands.
    """

    def __init__(self, admin_ids: Set[int] = None):
        """Initialize filter with admin IDs."""
        super().__init__("AdminOrOwnerFilter")
        self._admin_filter = AdminFilter(admin_ids)

    def filter(self, message: Message) -> bool:
        """Check if message is from admin or chat owner."""
        if not message.from_user:
            return False

        # Check bot admin status
        if self._admin_filter.filter(message):
            return True

        # Check if user is chat owner/admin (group context)
        if message.chat and message.chat.type in ("group", "supergroup"):
            # Would need async call to check chat member status
            # For sync filter, we only check bot admin list
            pass

        return False


# ============================================================================
# Chat Type Filters
# ============================================================================

class PrivateChatFilter(BaseMessageFilter):
    """Filter for private/DM chats only."""

    def __init__(self):
        super().__init__("PrivateChatFilter")

    def filter(self, message: Message) -> bool:
        """Check if message is from a private chat."""
        if not message.chat:
            return False
        return message.chat.type == "private"


class GroupChatFilter(BaseMessageFilter):
    """Filter for group chats only (regular groups, not supergroups)."""

    def __init__(self):
        super().__init__("GroupChatFilter")

    def filter(self, message: Message) -> bool:
        """Check if message is from a group chat."""
        if not message.chat:
            return False
        return message.chat.type == "group"


class SupergroupFilter(BaseMessageFilter):
    """Filter for supergroup chats only."""

    def __init__(self):
        super().__init__("SupergroupFilter")

    def filter(self, message: Message) -> bool:
        """Check if message is from a supergroup."""
        if not message.chat:
            return False
        return message.chat.type == "supergroup"


class AnyGroupFilter(BaseMessageFilter):
    """Filter for any group chat (group or supergroup)."""

    def __init__(self):
        super().__init__("AnyGroupFilter")

    def filter(self, message: Message) -> bool:
        """Check if message is from any group chat."""
        if not message.chat:
            return False
        return message.chat.type in ("group", "supergroup")


class ChannelFilter(BaseMessageFilter):
    """Filter for channel messages only."""

    def __init__(self):
        super().__init__("ChannelFilter")

    def filter(self, message: Message) -> bool:
        """Check if message is from a channel."""
        if not message.chat:
            return False
        return message.chat.type == "channel"


class SpecificChatFilter(BaseMessageFilter):
    """Filter for messages from specific chat IDs."""

    def __init__(self, chat_ids: Union[int, Set[int], List[int]]):
        """
        Initialize with specific chat IDs.

        Args:
            chat_ids: Single chat ID or collection of chat IDs
        """
        super().__init__("SpecificChatFilter")
        if isinstance(chat_ids, int):
            self._chat_ids = {chat_ids}
        else:
            self._chat_ids = set(chat_ids)

    @property
    def chat_ids(self) -> Set[int]:
        """Return set of allowed chat IDs."""
        return self._chat_ids

    def add_chat(self, chat_id: int) -> None:
        """Add a chat ID at runtime."""
        self._chat_ids.add(chat_id)

    def remove_chat(self, chat_id: int) -> None:
        """Remove a chat ID at runtime."""
        self._chat_ids.discard(chat_id)

    def filter(self, message: Message) -> bool:
        """Check if message is from an allowed chat."""
        if not message.chat:
            return False
        return message.chat.id in self._chat_ids


# ============================================================================
# Command Filters
# ============================================================================

class CommandPrefixFilter(BaseMessageFilter):
    """Filter for messages starting with a command prefix."""

    def __init__(self, prefix: str = "/"):
        """
        Initialize with command prefix.

        Args:
            prefix: Command prefix character(s), default "/"
        """
        super().__init__("CommandPrefixFilter")
        self._prefix = prefix

    @property
    def prefix(self) -> str:
        """Return the command prefix."""
        return self._prefix

    def filter(self, message: Message) -> bool:
        """Check if message starts with command prefix."""
        if not message.text:
            return False
        return message.text.strip().startswith(self._prefix)


class SpecificCommandFilter(BaseMessageFilter):
    """Filter for specific command(s)."""

    def __init__(self, commands: Union[str, List[str]], case_sensitive: bool = False):
        """
        Initialize with specific commands.

        Args:
            commands: Single command or list of commands (without leading /)
            case_sensitive: Whether to match case-sensitively
        """
        super().__init__("SpecificCommandFilter")
        if isinstance(commands, str):
            commands = [commands]
        self._case_sensitive = case_sensitive
        if case_sensitive:
            self._commands = set(commands)
        else:
            self._commands = {cmd.lower() for cmd in commands}

    @property
    def commands(self) -> Set[str]:
        """Return set of commands."""
        return self._commands

    def filter(self, message: Message) -> bool:
        """Check if message is a specific command."""
        if not message.text:
            return False
        text = message.text.strip()
        if not text.startswith("/"):
            return False

        # Extract command (handle @botname suffix)
        parts = text[1:].split()
        if not parts:
            return False
        cmd = parts[0].split("@")[0]

        if not self._case_sensitive:
            cmd = cmd.lower()

        return cmd in self._commands


class NotCommandFilter(BaseMessageFilter):
    """Filter for messages that are NOT commands."""

    def __init__(self, prefix: str = "/"):
        """Initialize with command prefix to exclude."""
        super().__init__("NotCommandFilter")
        self._prefix = prefix

    def filter(self, message: Message) -> bool:
        """Check if message is not a command."""
        if not message.text:
            return True  # Non-text messages are not commands
        return not message.text.strip().startswith(self._prefix)


# ============================================================================
# Content Pattern Filters
# ============================================================================

class RegexFilter(BaseMessageFilter):
    """Filter messages matching a regex pattern."""

    def __init__(self, pattern: Union[str, Pattern], flags: int = 0):
        """
        Initialize with regex pattern.

        Args:
            pattern: Regex pattern string or compiled pattern
            flags: Regex flags (e.g., re.IGNORECASE)
        """
        super().__init__("RegexFilter")
        if isinstance(pattern, str):
            self._pattern = re.compile(pattern, flags)
        else:
            self._pattern = pattern

    @property
    def pattern(self) -> Pattern:
        """Return the compiled regex pattern."""
        return self._pattern

    def filter(self, message: Message) -> bool:
        """Check if message text matches pattern."""
        if not message.text:
            return False
        return bool(self._pattern.search(message.text))


class ContainsTextFilter(BaseMessageFilter):
    """Filter messages containing specific text."""

    def __init__(self, text: str, case_sensitive: bool = False):
        """
        Initialize with text to search for.

        Args:
            text: Text to search for in messages
            case_sensitive: Whether to match case-sensitively
        """
        super().__init__("ContainsTextFilter")
        self._case_sensitive = case_sensitive
        self._text = text if case_sensitive else text.lower()

    @property
    def search_text(self) -> str:
        """Return the search text."""
        return self._text

    def filter(self, message: Message) -> bool:
        """Check if message contains the text."""
        if not message.text:
            return False
        msg_text = message.text if self._case_sensitive else message.text.lower()
        return self._text in msg_text


class StartsWithFilter(BaseMessageFilter):
    """Filter messages starting with specific text."""

    def __init__(self, prefix: str, case_sensitive: bool = False):
        """
        Initialize with prefix text.

        Args:
            prefix: Text that message should start with
            case_sensitive: Whether to match case-sensitively
        """
        super().__init__("StartsWithFilter")
        self._case_sensitive = case_sensitive
        self._prefix = prefix if case_sensitive else prefix.lower()

    @property
    def prefix(self) -> str:
        """Return the prefix text."""
        return self._prefix

    def filter(self, message: Message) -> bool:
        """Check if message starts with the prefix."""
        if not message.text:
            return False
        text = message.text if self._case_sensitive else message.text.lower()
        return text.startswith(self._prefix)


class EndsWithFilter(BaseMessageFilter):
    """Filter messages ending with specific text."""

    def __init__(self, suffix: str, case_sensitive: bool = False):
        """
        Initialize with suffix text.

        Args:
            suffix: Text that message should end with
            case_sensitive: Whether to match case-sensitively
        """
        super().__init__("EndsWithFilter")
        self._case_sensitive = case_sensitive
        self._suffix = suffix if case_sensitive else suffix.lower()

    def filter(self, message: Message) -> bool:
        """Check if message ends with the suffix."""
        if not message.text:
            return False
        text = message.text if self._case_sensitive else message.text.lower()
        return text.endswith(self._suffix)


# ============================================================================
# Token/Address Filters
# ============================================================================

# Solana address pattern: Base58, 32-44 characters
SOLANA_ADDRESS_PATTERN = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

# Token ticker pattern: $ followed by 2-10 alphanumeric chars
TOKEN_TICKER_PATTERN = re.compile(r'\$[A-Za-z0-9]{2,10}\b')


class TokenAddressFilter(BaseMessageFilter):
    """Filter for messages containing Solana token addresses."""

    def __init__(self, pattern: Pattern = None):
        """
        Initialize with optional custom pattern.

        Args:
            pattern: Custom regex pattern for addresses
        """
        super().__init__("TokenAddressFilter")
        self._pattern = pattern or SOLANA_ADDRESS_PATTERN

    def filter(self, message: Message) -> bool:
        """Check if message contains a token address."""
        if not message.text:
            return False
        return bool(self._pattern.search(message.text))

    def extract_addresses(self, message: Message) -> List[str]:
        """Extract all token addresses from message."""
        if not message.text:
            return []
        return self._pattern.findall(message.text)


class TokenTickerFilter(BaseMessageFilter):
    """Filter for messages containing token tickers ($SYMBOL)."""

    def __init__(self, pattern: Pattern = None):
        """
        Initialize with optional custom pattern.

        Args:
            pattern: Custom regex pattern for tickers
        """
        super().__init__("TokenTickerFilter")
        self._pattern = pattern or TOKEN_TICKER_PATTERN

    def filter(self, message: Message) -> bool:
        """Check if message contains a token ticker."""
        if not message.text:
            return False
        return bool(self._pattern.search(message.text))

    def extract_tickers(self, message: Message) -> List[str]:
        """Extract all token tickers from message."""
        if not message.text:
            return []
        return self._pattern.findall(message.text)


class TokenMentionFilter(BaseMessageFilter):
    """Filter for messages mentioning tokens (address or ticker)."""

    def __init__(self):
        super().__init__("TokenMentionFilter")
        self._address_filter = TokenAddressFilter()
        self._ticker_filter = TokenTickerFilter()

    def filter(self, message: Message) -> bool:
        """Check if message mentions any token."""
        return (
            self._address_filter.filter(message) or
            self._ticker_filter.filter(message)
        )


# ============================================================================
# User Filters
# ============================================================================

class SpecificUserFilter(BaseMessageFilter):
    """Filter for messages from specific users."""

    def __init__(self, user_ids: Union[int, Set[int], List[int]]):
        """
        Initialize with specific user IDs.

        Args:
            user_ids: Single user ID or collection of user IDs
        """
        super().__init__("SpecificUserFilter")
        if isinstance(user_ids, int):
            self._user_ids = {user_ids}
        else:
            self._user_ids = set(user_ids)

    @property
    def user_ids(self) -> Set[int]:
        """Return set of allowed user IDs."""
        return self._user_ids

    def add_user(self, user_id: int) -> None:
        """Add a user ID at runtime."""
        self._user_ids.add(user_id)

    def remove_user(self, user_id: int) -> None:
        """Remove a user ID at runtime."""
        self._user_ids.discard(user_id)

    def filter(self, message: Message) -> bool:
        """Check if message is from an allowed user."""
        if not message.from_user:
            return False
        return message.from_user.id in self._user_ids


class UsernameFilter(BaseMessageFilter):
    """Filter for messages from users with specific usernames."""

    def __init__(self, usernames: Union[str, Set[str], List[str]], case_sensitive: bool = False):
        """
        Initialize with specific usernames.

        Args:
            usernames: Single username or collection of usernames
            case_sensitive: Whether to match usernames case-sensitively
        """
        super().__init__("UsernameFilter")
        if isinstance(usernames, str):
            usernames = [usernames]
        self._case_sensitive = case_sensitive
        # Remove @ prefix if present
        if case_sensitive:
            self._usernames = {u.lstrip("@") for u in usernames}
        else:
            self._usernames = {u.lstrip("@").lower() for u in usernames}

    @property
    def usernames(self) -> Set[str]:
        """Return set of allowed usernames."""
        return self._usernames

    def filter(self, message: Message) -> bool:
        """Check if message is from a user with allowed username."""
        if not message.from_user or not message.from_user.username:
            return False
        username = message.from_user.username
        if not self._case_sensitive:
            username = username.lower()
        return username in self._usernames


class BotFilter(BaseMessageFilter):
    """Filter for messages from bots."""

    def __init__(self, allow_bots: bool = True, name: str = None):
        """
        Initialize bot filter.

        Args:
            allow_bots: If True, only bot messages pass. If False, only non-bot messages pass.
            name: Optional filter name
        """
        super().__init__(name or "BotFilter")
        self._allow_bots = allow_bots

    def filter(self, message: Message) -> bool:
        """Check if message is from a bot (or not)."""
        if not message.from_user:
            return False
        is_bot = message.from_user.is_bot
        return is_bot if self._allow_bots else not is_bot


class NotBotFilter(BotFilter):
    """Filter for messages NOT from bots (human users only)."""

    def __init__(self):
        super().__init__(allow_bots=False, name="NotBotFilter")


# ============================================================================
# Mention Filters
# ============================================================================

class BotMentionFilter(BaseMessageFilter):
    """Filter for messages that mention the bot."""

    def __init__(self, bot_username: str = None):
        """
        Initialize with bot username.

        Args:
            bot_username: Bot's username (without @). If None, tries to get from env.
        """
        super().__init__("BotMentionFilter")
        self._bot_username = bot_username or os.environ.get("BOT_USERNAME", "")

    @property
    def bot_username(self) -> str:
        """Return bot username."""
        return self._bot_username

    def set_bot_username(self, username: str) -> None:
        """Set bot username at runtime."""
        self._bot_username = username.lstrip("@")

    def filter(self, message: Message) -> bool:
        """Check if message mentions the bot."""
        if not self._bot_username:
            return False

        # Check text mentions
        if message.text:
            mention = f"@{self._bot_username}"
            if mention.lower() in message.text.lower():
                return True

        # Check entities for user mentions
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mention_text = message.text[entity.offset:entity.offset + entity.length]
                    if mention_text.lower() == f"@{self._bot_username.lower()}":
                        return True

        return False


class ReplyToBotFilter(BaseMessageFilter):
    """Filter for messages that are replies to the bot."""

    def __init__(self, bot_id: int = None):
        """
        Initialize with bot ID.

        Args:
            bot_id: Bot's user ID. If None, cannot filter.
        """
        super().__init__("ReplyToBotFilter")
        self._bot_id = bot_id

    @property
    def bot_id(self) -> Optional[int]:
        """Return bot ID."""
        return self._bot_id

    def set_bot_id(self, bot_id: int) -> None:
        """Set bot ID at runtime."""
        self._bot_id = bot_id

    def filter(self, message: Message) -> bool:
        """Check if message is a reply to the bot."""
        if not self._bot_id:
            return False
        if not message.reply_to_message:
            return False
        if not message.reply_to_message.from_user:
            return False
        return message.reply_to_message.from_user.id == self._bot_id


# ============================================================================
# Spam Detection Filters
# ============================================================================

@dataclass
class SpamConfig:
    """Configuration for spam detection."""
    max_emojis: int = 10
    max_caps_ratio: float = 0.7
    min_caps_length: int = 20
    blocked_patterns: List[str] = field(default_factory=list)
    suspicious_urls: List[str] = field(default_factory=lambda: [
        "bit.ly", "tinyurl", "t.co", "goo.gl",
        "discord.gg", "t.me/joinchat"
    ])


class SpamFilter(BaseMessageFilter):
    """Filter for spam messages."""

    def __init__(self, config: SpamConfig = None):
        """
        Initialize spam filter.

        Args:
            config: SpamConfig for detection parameters
        """
        super().__init__("SpamFilter")
        self._config = config or SpamConfig()
        self._emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F700-\U0001F77F"  # alchemical
            "\U0001F780-\U0001F7FF"  # geometric shapes
            "\U0001F800-\U0001F8FF"  # arrows
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # chess symbols
            "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended
            "\U00002702-\U000027B0"  # dingbats
            "]+",
            flags=re.UNICODE
        )

    @property
    def config(self) -> SpamConfig:
        """Return spam config."""
        return self._config

    def filter(self, message: Message) -> bool:
        """Check if message appears to be spam."""
        if not message.text:
            return False

        text = message.text

        # Check emoji count
        emojis = self._emoji_pattern.findall(text)
        total_emojis = sum(len(e) for e in emojis)
        if total_emojis > self._config.max_emojis:
            return True

        # Check caps ratio (for longer messages)
        if len(text) >= self._config.min_caps_length:
            alpha_chars = [c for c in text if c.isalpha()]
            if alpha_chars:
                upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                if upper_ratio > self._config.max_caps_ratio:
                    return True

        # Check blocked patterns
        text_lower = text.lower()
        for pattern in self._config.blocked_patterns:
            if pattern.lower() in text_lower:
                return True

        # Check suspicious URLs
        for url in self._config.suspicious_urls:
            if url.lower() in text_lower:
                return True

        return False


class NotSpamFilter(BaseMessageFilter):
    """Filter for non-spam messages."""

    def __init__(self, config: SpamConfig = None):
        """Initialize with spam config."""
        super().__init__("NotSpamFilter")
        self._spam_filter = SpamFilter(config)

    def filter(self, message: Message) -> bool:
        """Check if message is NOT spam."""
        return not self._spam_filter.filter(message)


# ============================================================================
# Rate Limiting Filters
# ============================================================================

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    messages_per_window: int = 5
    window_seconds: float = 60.0
    per_user: bool = True
    per_chat: bool = False


class RateLimitFilter(BaseMessageFilter):
    """Filter that rate limits messages."""

    def __init__(self, config: RateLimitConfig = None):
        """
        Initialize rate limit filter.

        Args:
            config: RateLimitConfig for rate limiting parameters
        """
        super().__init__("RateLimitFilter")
        self._config = config or RateLimitConfig()
        self._timestamps: dict[str, List[float]] = {}

    @property
    def config(self) -> RateLimitConfig:
        """Return rate limit config."""
        return self._config

    def reset(self) -> None:
        """Reset all rate limit tracking."""
        self._timestamps.clear()

    def _get_key(self, message: Message) -> str:
        """Generate rate limit key from message."""
        parts = []
        if self._config.per_user and message.from_user:
            parts.append(f"u{message.from_user.id}")
        if self._config.per_chat and message.chat:
            parts.append(f"c{message.chat.id}")
        return ":".join(parts) if parts else "global"

    def _cleanup_old(self, key: str, now: float) -> None:
        """Remove timestamps outside the window."""
        if key not in self._timestamps:
            return
        cutoff = now - self._config.window_seconds
        self._timestamps[key] = [t for t in self._timestamps[key] if t > cutoff]

    def filter(self, message: Message) -> bool:
        """
        Check if message is within rate limit.

        Returns True if message should be processed (within limit),
        False if rate limited (should be dropped).
        """
        now = time.time()
        key = self._get_key(message)

        self._cleanup_old(key, now)

        if key not in self._timestamps:
            self._timestamps[key] = []

        # Check if within limit
        if len(self._timestamps[key]) >= self._config.messages_per_window:
            return False  # Rate limited

        # Record this message
        self._timestamps[key].append(now)
        return True


# ============================================================================
# Media Type Filters
# ============================================================================

class MediaFilter(BaseMessageFilter):
    """Filter for messages with media attachments."""

    def __init__(
        self,
        photos: bool = True,
        videos: bool = True,
        audio: bool = True,
        documents: bool = True,
        animations: bool = True,
        stickers: bool = True,
        voice: bool = True,
        video_notes: bool = True,
        name: str = None
    ):
        """
        Initialize media filter.

        Args:
            photos: Allow photo messages
            videos: Allow video messages
            audio: Allow audio messages
            documents: Allow document messages
            animations: Allow animation/GIF messages
            stickers: Allow sticker messages
            voice: Allow voice messages
            video_notes: Allow video note (circle video) messages
            name: Optional filter name
        """
        super().__init__(name or "MediaFilter")
        self._photos = photos
        self._videos = videos
        self._audio = audio
        self._documents = documents
        self._animations = animations
        self._stickers = stickers
        self._voice = voice
        self._video_notes = video_notes

    def filter(self, message: Message) -> bool:
        """Check if message has allowed media type."""
        if self._photos and message.photo:
            return True
        if self._videos and message.video:
            return True
        if self._audio and message.audio:
            return True
        if self._documents and message.document:
            return True
        if self._animations and message.animation:
            return True
        if self._stickers and message.sticker:
            return True
        if self._voice and message.voice:
            return True
        if self._video_notes and message.video_note:
            return True
        return False


class PhotoFilter(MediaFilter):
    """Filter for photo messages only."""

    def __init__(self):
        super().__init__(
            photos=True, videos=False, audio=False, documents=False,
            animations=False, stickers=False, voice=False, video_notes=False,
            name="PhotoFilter"
        )


class VideoFilter(MediaFilter):
    """Filter for video messages only."""

    def __init__(self):
        super().__init__(
            photos=False, videos=True, audio=False, documents=False,
            animations=False, stickers=False, voice=False, video_notes=False,
            name="VideoFilter"
        )


class DocumentFilter(MediaFilter):
    """Filter for document messages only."""

    def __init__(self):
        super().__init__(
            photos=False, videos=False, audio=False, documents=True,
            animations=False, stickers=False, voice=False, video_notes=False,
            name="DocumentFilter"
        )


class AnimationFilter(MediaFilter):
    """Filter for animation/GIF messages only."""

    def __init__(self):
        super().__init__(
            photos=False, videos=False, audio=False, documents=False,
            animations=True, stickers=False, voice=False, video_notes=False,
            name="AnimationFilter"
        )


class StickerFilter(MediaFilter):
    """Filter for sticker messages only."""

    def __init__(self):
        super().__init__(
            photos=False, videos=False, audio=False, documents=False,
            animations=False, stickers=True, voice=False, video_notes=False,
            name="StickerFilter"
        )


class VoiceFilter(MediaFilter):
    """Filter for voice messages only."""

    def __init__(self):
        super().__init__(
            photos=False, videos=False, audio=False, documents=False,
            animations=False, stickers=False, voice=True, video_notes=False,
            name="VoiceFilter"
        )


class NoMediaFilter(BaseMessageFilter):
    """Filter for text-only messages (no media)."""

    def __init__(self):
        super().__init__("NoMediaFilter")

    def filter(self, message: Message) -> bool:
        """Check if message has no media attachments."""
        return (
            not message.photo and
            not message.video and
            not message.audio and
            not message.document and
            not message.animation and
            not message.sticker and
            not message.voice and
            not message.video_note
        )


# ============================================================================
# Composite Filters
# ============================================================================

class AndFilter(BaseMessageFilter):
    """Filter that requires ALL child filters to pass."""

    def __init__(self, *filters: BaseMessageFilter):
        """
        Initialize with child filters.

        Args:
            filters: Variable number of filters that must all pass
        """
        super().__init__("AndFilter")
        self._filters = list(filters)

    @property
    def filters(self) -> List[BaseMessageFilter]:
        """Return list of child filters."""
        return self._filters

    def add_filter(self, f: BaseMessageFilter) -> None:
        """Add a filter to the AND chain."""
        self._filters.append(f)

    def filter(self, message: Message) -> bool:
        """Check if ALL child filters pass."""
        return all(f.filter(message) for f in self._filters)


class OrFilter(BaseMessageFilter):
    """Filter that requires ANY child filter to pass."""

    def __init__(self, *filters: BaseMessageFilter):
        """
        Initialize with child filters.

        Args:
            filters: Variable number of filters where any one can pass
        """
        super().__init__("OrFilter")
        self._filters = list(filters)

    @property
    def filters(self) -> List[BaseMessageFilter]:
        """Return list of child filters."""
        return self._filters

    def add_filter(self, f: BaseMessageFilter) -> None:
        """Add a filter to the OR chain."""
        self._filters.append(f)

    def filter(self, message: Message) -> bool:
        """Check if ANY child filter passes."""
        return any(f.filter(message) for f in self._filters)


class NotFilter(BaseMessageFilter):
    """Filter that inverts another filter's result."""

    def __init__(self, inner_filter: BaseMessageFilter):
        """
        Initialize with filter to invert.

        Args:
            inner_filter: Filter whose result will be inverted
        """
        super().__init__("NotFilter")
        self._inner = inner_filter

    @property
    def inner_filter(self) -> BaseMessageFilter:
        """Return the inner filter."""
        return self._inner

    def filter(self, message: Message) -> bool:
        """Return inverse of inner filter result."""
        return not self._inner.filter(message)


# ============================================================================
# Callback Filter
# ============================================================================

class CallbackFilter(BaseMessageFilter):
    """Filter using a custom callback function."""

    def __init__(self, callback: Callable[[Message], bool], name: str = None):
        """
        Initialize with custom callback.

        Args:
            callback: Function that takes Message and returns bool
            name: Optional name for the filter
        """
        super().__init__(name or "CallbackFilter")
        self._callback = callback

    @property
    def callback(self) -> Callable[[Message], bool]:
        """Return the callback function."""
        return self._callback

    def filter(self, message: Message) -> bool:
        """Call the custom callback."""
        return self._callback(message)


# ============================================================================
# Factory Functions
# ============================================================================

def create_admin_filter(admin_ids: Set[int] = None) -> AdminFilter:
    """Factory function to create an admin filter."""
    return AdminFilter(admin_ids)


def create_chat_filter(chat_ids: Union[int, Set[int], List[int]]) -> SpecificChatFilter:
    """Factory function to create a specific chat filter."""
    return SpecificChatFilter(chat_ids)


def create_user_filter(user_ids: Union[int, Set[int], List[int]]) -> SpecificUserFilter:
    """Factory function to create a specific user filter."""
    return SpecificUserFilter(user_ids)


def create_command_filter(commands: Union[str, List[str]]) -> SpecificCommandFilter:
    """Factory function to create a specific command filter."""
    return SpecificCommandFilter(commands)


def create_regex_filter(pattern: str, flags: int = 0) -> RegexFilter:
    """Factory function to create a regex filter."""
    return RegexFilter(pattern, flags)


def create_rate_limit_filter(
    messages: int = 5,
    seconds: float = 60.0,
    per_user: bool = True,
    per_chat: bool = False
) -> RateLimitFilter:
    """Factory function to create a rate limit filter."""
    config = RateLimitConfig(
        messages_per_window=messages,
        window_seconds=seconds,
        per_user=per_user,
        per_chat=per_chat
    )
    return RateLimitFilter(config)


# ============================================================================
# Module-level filter instances (convenience)
# ============================================================================

# Chat type filters
PRIVATE_CHAT = PrivateChatFilter()
GROUP_CHAT = GroupChatFilter()
SUPERGROUP = SupergroupFilter()
ANY_GROUP = AnyGroupFilter()
CHANNEL = ChannelFilter()

# Content filters
HAS_TEXT = NotFilter(MediaFilter())
HAS_MEDIA = MediaFilter()
HAS_PHOTO = PhotoFilter()
HAS_VIDEO = VideoFilter()
HAS_DOCUMENT = DocumentFilter()
HAS_STICKER = StickerFilter()
HAS_ANIMATION = AnimationFilter()
HAS_VOICE = VoiceFilter()
NO_MEDIA = NoMediaFilter()

# Command filters
IS_COMMAND = CommandPrefixFilter()
NOT_COMMAND = NotCommandFilter()

# User filters
FROM_BOT = BotFilter(allow_bots=True)
FROM_HUMAN = NotBotFilter()

# Token filters
HAS_TOKEN_ADDRESS = TokenAddressFilter()
HAS_TOKEN_TICKER = TokenTickerFilter()
HAS_TOKEN_MENTION = TokenMentionFilter()
