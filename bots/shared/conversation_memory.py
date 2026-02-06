"""
Conversation Memory Module for ClawdBots.

Provides persistent conversation memory that enables:
- Per-user conversation history storage
- Context retrieval for LLM prompts
- Memory summarization for long conversations
- Automatic memory limits and expiration
- Cross-bot memory sharing

Usage in any ClawdBot:
    from bots.shared.conversation_memory import (
        add_message,
        get_conversation_history,
        get_context_for_prompt,
        summarize_conversation,
        clear_memory,
        share_memory,
    )

    # Add a message to the conversation
    add_message("jarvis", "user123", "user", "Hello, how are you?")
    add_message("jarvis", "user123", "assistant", "I'm doing great!")

    # Get conversation history
    history = get_conversation_history("jarvis", "user123", limit=20)

    # Get formatted context for LLM prompt
    context = get_context_for_prompt("jarvis", "user123", max_tokens=2000)

    # Share memory between bots
    share_memory("jarvis", "friday", "user123")

Storage:
    /root/clawdbots/memory/{bot_name}/{user_id}.json

Memory Management:
    - Max 100 messages per conversation
    - Auto-summarize when approaching limit
    - Expire inactive conversations after 7 days
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Default memory directory (can be overridden)
DEFAULT_MEMORY_DIR = os.environ.get(
    "CLAWDBOT_MEMORY_DIR",
    "/root/clawdbots/memory",
)


@dataclass
class MemoryConfig:
    """Configuration for conversation memory behavior."""

    max_messages: int = 100
    max_context_tokens: int = 2000
    expiry_days: int = 7
    auto_summarize_threshold: int = 80  # Summarize when reaching this % of max


@dataclass
class Message:
    """A single message in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def token_count(self) -> int:
        """Estimate token count (roughly 4 characters per token)."""
        return max(1, len(self.content) // 4)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Deserialize message from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
        )


@dataclass
class ConversationSummary:
    """Summary of older conversation messages."""

    content: str
    message_count: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize summary to dictionary."""
        return {
            "content": self.content,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSummary":
        """Deserialize summary from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        return cls(
            content=data["content"],
            message_count=data["message_count"],
            created_at=created_at,
        )


@dataclass
class Conversation:
    """A conversation with a specific user."""

    messages: List[Message] = field(default_factory=list)
    summary: Optional[ConversationSummary] = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize conversation to dictionary."""
        data = {
            "messages": [m.to_dict() for m in self.messages],
            "last_activity": self.last_activity.isoformat(),
        }
        if self.summary:
            data["summary"] = self.summary.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        """Deserialize conversation from dictionary."""
        messages = [
            Message.from_dict(m)
            for m in data.get("messages", [])
        ]

        summary = None
        if "summary" in data and data["summary"]:
            summary = ConversationSummary.from_dict(data["summary"])

        last_activity = data.get("last_activity")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)
        elif last_activity is None:
            last_activity = datetime.now(timezone.utc)

        return cls(
            messages=messages,
            summary=summary,
            last_activity=last_activity,
        )


class ConversationMemory:
    """
    Manages conversation memory for a single bot.

    Each bot has its own memory namespace, and conversations are
    stored per-user in JSON files.
    """

    def __init__(
        self,
        bot_name: str,
        memory_dir: str = None,
        config: MemoryConfig = None,
    ):
        """
        Initialize conversation memory for a bot.

        Args:
            bot_name: Name of the bot (e.g., "jarvis", "friday", "matt")
            memory_dir: Directory for storing memory files
            config: Memory configuration (uses defaults if not provided)
        """
        self.bot_name = bot_name
        self.memory_dir = Path(memory_dir or DEFAULT_MEMORY_DIR)
        self.config = config or MemoryConfig()

        # Ensure bot's memory directory exists
        self.bot_dir = self.memory_dir / bot_name
        self.bot_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_file(self, user_id: str) -> Path:
        """Get the file path for a user's conversation."""
        # Sanitize user_id for filesystem
        safe_user_id = "".join(c for c in user_id if c.isalnum() or c in "-_")
        return self.bot_dir / f"{safe_user_id}.json"

    def _load_conversation(self, user_id: str) -> Conversation:
        """Load conversation from disk."""
        file_path = self._get_user_file(user_id)

        if not file_path.exists():
            return Conversation()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Conversation.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load conversation for {user_id}: {e}")
            return Conversation()

    def _save_conversation(self, user_id: str, conversation: Conversation) -> None:
        """Save conversation to disk."""
        file_path = self._get_user_file(user_id)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(conversation.to_dict(), f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save conversation for {user_id}: {e}")

    def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
    ) -> None:
        """
        Add a message to the conversation.

        Args:
            user_id: Unique identifier for the user
            role: "user" or "assistant"
            content: Message content
        """
        conversation = self._load_conversation(user_id)

        # Add new message
        message = Message(role=role, content=content)
        conversation.messages.append(message)
        conversation.last_activity = datetime.now(timezone.utc)

        # Check if we need to summarize (approaching limit)
        if len(conversation.messages) >= self.config.auto_summarize_threshold:
            self._auto_summarize(conversation)

        # Enforce max messages (after summarization attempt)
        if len(conversation.messages) > self.config.max_messages:
            # Keep only the most recent messages
            conversation.messages = conversation.messages[-self.config.max_messages:]

        self._save_conversation(user_id, conversation)

    def get_conversation_history(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Message]:
        """
        Get recent conversation history.

        Args:
            user_id: Unique identifier for the user
            limit: Maximum number of messages to return (default: 20)

        Returns:
            List of Message objects, most recent last
        """
        conversation = self._load_conversation(user_id)
        messages = conversation.messages

        if len(messages) <= limit:
            return messages

        return messages[-limit:]

    def get_context_for_prompt(
        self,
        user_id: str,
        max_tokens: int = None,
    ) -> str:
        """
        Generate context string for LLM prompt.

        Args:
            user_id: Unique identifier for the user
            max_tokens: Maximum tokens in context (default from config)

        Returns:
            Formatted context string including summary and recent messages
        """
        max_tokens = max_tokens or self.config.max_context_tokens
        conversation = self._load_conversation(user_id)

        context_parts = []
        total_tokens = 0

        # Include summary if available
        if conversation.summary:
            summary_text = f"[Previous conversation summary: {conversation.summary.content}]\n"
            summary_tokens = len(summary_text) // 4
            if summary_tokens < max_tokens:
                context_parts.append(summary_text)
                total_tokens += summary_tokens

        # Add recent messages in reverse order (most recent first for token budget)
        recent_messages = []
        for message in reversed(conversation.messages):
            msg_text = f"{message.role}: {message.content}\n"
            msg_tokens = message.token_count + 2  # Account for role prefix

            if total_tokens + msg_tokens > max_tokens:
                break

            recent_messages.append(msg_text)
            total_tokens += msg_tokens

        # Reverse to get chronological order
        recent_messages.reverse()
        context_parts.extend(recent_messages)

        return "".join(context_parts)

    def _auto_summarize(self, conversation: Conversation) -> None:
        """
        Automatically summarize older messages when approaching limit.

        This creates a summary of older messages and keeps only recent ones.
        """
        if len(conversation.messages) < self.config.auto_summarize_threshold:
            return

        # Determine how many messages to summarize
        messages_to_keep = self.config.auto_summarize_threshold // 2
        messages_to_summarize = conversation.messages[:-messages_to_keep]

        if not messages_to_summarize:
            return

        # Create a simple summary (can be enhanced with LLM later)
        topics = set()
        for msg in messages_to_summarize:
            # Extract potential topics (simple keyword extraction)
            words = msg.content.lower().split()
            for word in words:
                if len(word) > 4 and word.isalpha():
                    topics.add(word)

        # Build summary
        summary_content = f"Conversation covered topics: {', '.join(list(topics)[:10])}. "
        summary_content += f"Summarized {len(messages_to_summarize)} messages."

        # Update or create summary
        if conversation.summary:
            # Merge with existing summary
            summary_content = (
                f"{conversation.summary.content} "
                f"Additional: {summary_content}"
            )
            message_count = (
                conversation.summary.message_count + len(messages_to_summarize)
            )
        else:
            message_count = len(messages_to_summarize)

        conversation.summary = ConversationSummary(
            content=summary_content[:500],  # Limit summary length
            message_count=message_count,
        )

        # Keep only recent messages
        conversation.messages = conversation.messages[-messages_to_keep:]

    def summarize_conversation(self, user_id: str) -> Optional[ConversationSummary]:
        """
        Generate a summary of the conversation.

        Args:
            user_id: Unique identifier for the user

        Returns:
            ConversationSummary or None if no conversation exists
        """
        conversation = self._load_conversation(user_id)

        if not conversation.messages and not conversation.summary:
            return None

        # Create summary from all messages
        all_content = " ".join(m.content for m in conversation.messages)
        topics = set()
        words = all_content.lower().split()
        for word in words:
            if len(word) > 4 and word.isalpha():
                topics.add(word)

        summary_content = (
            f"Conversation about: {', '.join(list(topics)[:15])}."
        )

        if conversation.summary:
            summary_content = (
                f"{conversation.summary.content} "
                f"Recent: {summary_content}"
            )

        message_count = len(conversation.messages)
        if conversation.summary:
            message_count += conversation.summary.message_count

        return ConversationSummary(
            content=summary_content[:500],
            message_count=message_count,
        )

    def clear_memory(self, user_id: str) -> None:
        """
        Clear all memory for a user.

        Args:
            user_id: Unique identifier for the user
        """
        file_path = self._get_user_file(user_id)

        if file_path.exists():
            try:
                file_path.unlink()
            except IOError as e:
                logger.error(f"Failed to delete memory file for {user_id}: {e}")

    def expire_old_conversations(self) -> List[str]:
        """
        Expire conversations older than expiry_days.

        Returns:
            List of user IDs whose conversations were expired
        """
        expired = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.expiry_days)

        if not self.bot_dir.exists():
            return expired

        for file_path in self.bot_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                last_activity = data.get("last_activity")
                if isinstance(last_activity, str):
                    last_activity = datetime.fromisoformat(last_activity)
                else:
                    # If no last_activity, check file modification time
                    mtime = datetime.fromtimestamp(
                        file_path.stat().st_mtime,
                        tz=timezone.utc,
                    )
                    last_activity = mtime

                if last_activity < cutoff:
                    user_id = file_path.stem
                    file_path.unlink()
                    expired.append(user_id)
                    logger.info(f"Expired conversation for {user_id}")

            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error processing {file_path}: {e}")

        return expired

    def share_memory_to(
        self,
        target_bot: str,
        user_id: str,
        memory_dir: str = None,
    ) -> bool:
        """
        Share conversation memory to another bot.

        This copies the conversation context (as a summary) to the target bot's
        memory, allowing cross-bot context continuity.

        Args:
            target_bot: Name of the target bot
            user_id: User whose memory to share
            memory_dir: Memory directory (uses default if not provided)

        Returns:
            True if sharing was successful
        """
        conversation = self._load_conversation(user_id)

        if not conversation.messages and not conversation.summary:
            return False

        # Create target bot's memory instance
        target_memory = ConversationMemory(
            target_bot,
            memory_dir or str(self.memory_dir),
            self.config,
        )

        # Load target's existing conversation (if any)
        target_conv = target_memory._load_conversation(user_id)

        # Create a shared context message
        shared_content = f"[Context from {self.bot_name}] "
        if conversation.summary:
            shared_content += conversation.summary.content + " "

        # Add recent message summaries
        recent = conversation.messages[-5:]  # Last 5 messages
        if recent:
            msg_summaries = [f"{m.role}: {m.content[:50]}..." for m in recent]
            shared_content += "Recent: " + "; ".join(msg_summaries)

        # Add as a system message to target
        shared_message = Message(
            role="system",
            content=shared_content[:1000],  # Limit length
        )

        # Insert at beginning of target's messages
        target_conv.messages.insert(0, shared_message)
        target_conv.last_activity = datetime.now(timezone.utc)

        target_memory._save_conversation(user_id, target_conv)

        logger.info(f"Shared memory from {self.bot_name} to {target_bot} for {user_id}")
        return True


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

# Cache for memory instances
_memory_instances: Dict[str, ConversationMemory] = {}


def _get_memory(bot_name: str) -> ConversationMemory:
    """Get or create a memory instance for a bot."""
    if bot_name not in _memory_instances:
        _memory_instances[bot_name] = ConversationMemory(
            bot_name,
            DEFAULT_MEMORY_DIR,
        )
    return _memory_instances[bot_name]


def add_message(
    bot_name: str,
    user_id: str,
    role: str,
    content: str,
) -> None:
    """
    Add a message to a bot's conversation with a user.

    Args:
        bot_name: Name of the bot (e.g., "jarvis", "friday")
        user_id: Unique identifier for the user
        role: "user" or "assistant"
        content: Message content
    """
    memory = _get_memory(bot_name)
    memory.add_message(user_id, role, content)


def get_conversation_history(
    bot_name: str,
    user_id: str,
    limit: int = 20,
) -> List[Message]:
    """
    Get conversation history for a bot and user.

    Args:
        bot_name: Name of the bot
        user_id: Unique identifier for the user
        limit: Maximum messages to return

    Returns:
        List of Message objects
    """
    memory = _get_memory(bot_name)
    return memory.get_conversation_history(user_id, limit)


def get_context_for_prompt(
    bot_name: str,
    user_id: str,
    max_tokens: int = 2000,
) -> str:
    """
    Get formatted context for an LLM prompt.

    Args:
        bot_name: Name of the bot
        user_id: Unique identifier for the user
        max_tokens: Maximum tokens in context

    Returns:
        Formatted context string
    """
    memory = _get_memory(bot_name)
    return memory.get_context_for_prompt(user_id, max_tokens)


def summarize_conversation(
    bot_name: str,
    user_id: str,
) -> Optional[ConversationSummary]:
    """
    Summarize a conversation.

    Args:
        bot_name: Name of the bot
        user_id: Unique identifier for the user

    Returns:
        ConversationSummary or None
    """
    memory = _get_memory(bot_name)
    return memory.summarize_conversation(user_id)


def clear_memory(
    bot_name: str,
    user_id: str,
) -> None:
    """
    Clear all memory for a bot and user.

    Args:
        bot_name: Name of the bot
        user_id: Unique identifier for the user
    """
    memory = _get_memory(bot_name)
    memory.clear_memory(user_id)


def share_memory(
    from_bot: str,
    to_bot: str,
    user_id: str,
) -> bool:
    """
    Share memory from one bot to another.

    Args:
        from_bot: Source bot name
        to_bot: Target bot name
        user_id: User whose memory to share

    Returns:
        True if sharing was successful
    """
    memory = _get_memory(from_bot)
    return memory.share_memory_to(to_bot, user_id)
