"""
Test Fixtures for ClawdBot Testing

Provides pre-built fixture functions for common test data.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import random
import string


def _random_string(length: int = 8) -> str:
    """Generate a random string."""
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def _random_int(min_val: int = 100000000, max_val: int = 999999999) -> int:
    """Generate a random integer."""
    return random.randint(min_val, max_val)


# User Fixtures

def sample_user(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    first_name: str = "Test",
    last_name: str = "User",
    is_bot: bool = False,
    language_code: str = "en",
    is_premium: bool = False,
) -> Dict[str, Any]:
    """
    Create a sample Telegram user fixture.

    Usage:
        user = sample_user(username="alice")
        user = sample_user(user_id=12345, first_name="Bob")
    """
    return {
        "id": user_id or _random_int(),
        "username": username or f"user_{_random_string(6)}",
        "first_name": first_name,
        "last_name": last_name,
        "is_bot": is_bot,
        "language_code": language_code,
        "is_premium": is_premium,
    }


def sample_admin_user(**kwargs) -> Dict[str, Any]:
    """Create a sample admin user fixture."""
    kwargs.setdefault("username", "admin")
    kwargs.setdefault("first_name", "Admin")
    return sample_user(**kwargs)


def sample_bot_user(**kwargs) -> Dict[str, Any]:
    """Create a sample bot user fixture."""
    kwargs.setdefault("is_bot", True)
    kwargs.setdefault("username", "test_bot")
    kwargs.setdefault("first_name", "Test Bot")
    return sample_user(**kwargs)


# Message Fixtures

def sample_message(
    text: str = "Hello, bot!",
    user: Optional[Dict] = None,
    chat: Optional[Dict] = None,
    message_id: Optional[int] = None,
    reply_to_message: Optional[Dict] = None,
    entities: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Create a sample Telegram message fixture.

    Usage:
        msg = sample_message("/help")
        msg = sample_message("Hello!", user=sample_user(username="alice"))
    """
    if user is None:
        user = sample_user()

    if chat is None:
        chat = sample_chat(chat_id=user["id"])

    # Auto-generate command entities
    if entities is None and text.startswith("/"):
        space_idx = text.find(" ")
        cmd_end = space_idx if space_idx > 0 else len(text)
        entities = [{
            "type": "bot_command",
            "offset": 0,
            "length": cmd_end,
        }]

    return {
        "message_id": message_id or _random_int(1, 100000),
        "date": int(datetime.utcnow().timestamp()),
        "chat": chat,
        "from": user,
        "text": text,
        "reply_to_message": reply_to_message,
        "entities": entities or [],
    }


def sample_command_message(
    command: str,
    args: str = "",
    **kwargs
) -> Dict[str, Any]:
    """
    Create a sample command message.

    Usage:
        msg = sample_command_message("/help")
        msg = sample_command_message("/review", args="My message text")
    """
    text = f"{command} {args}".strip() if args else command
    return sample_message(text=text, **kwargs)


def sample_reply_message(
    text: str,
    original_message: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Create a sample reply message.

    Usage:
        original = sample_message("First message")
        reply = sample_reply_message("Reply text", original)
    """
    return sample_message(
        text=text,
        reply_to_message=original_message,
        **kwargs
    )


# Chat Fixtures

def sample_chat(
    chat_id: Optional[int] = None,
    chat_type: str = "private",
    title: Optional[str] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a sample Telegram chat fixture.

    Usage:
        chat = sample_chat(chat_type="group", title="Test Group")
    """
    return {
        "id": chat_id or _random_int(),
        "type": chat_type,
        "title": title,
        "username": username,
    }


def sample_group_chat(**kwargs) -> Dict[str, Any]:
    """Create a sample group chat fixture."""
    kwargs.setdefault("chat_type", "group")
    kwargs.setdefault("title", f"Test Group {_random_string(4)}")
    return sample_chat(**kwargs)


def sample_supergroup_chat(**kwargs) -> Dict[str, Any]:
    """Create a sample supergroup chat fixture."""
    kwargs.setdefault("chat_type", "supergroup")
    kwargs.setdefault("title", f"Test Supergroup {_random_string(4)}")
    return sample_chat(**kwargs)


# Callback Query Fixtures

def sample_callback(
    data: str,
    user: Optional[Dict] = None,
    message: Optional[Dict] = None,
    callback_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a sample callback query fixture.

    Usage:
        callback = sample_callback("action:confirm")
    """
    if user is None:
        user = sample_user()

    if message is None:
        message = sample_message("Button message", user=user)

    return {
        "id": callback_id or str(_random_int()),
        "from": user,
        "message": message,
        "chat_instance": str(message["chat"]["id"]),
        "data": data,
    }


# Conversation Fixtures

def sample_conversation(
    user: Optional[Dict] = None,
    message_count: int = 4,
    include_bot_responses: bool = True,
) -> Dict[str, Any]:
    """
    Create a sample conversation fixture.

    Usage:
        conv = sample_conversation(message_count=6)
    """
    if user is None:
        user = sample_user()

    chat = sample_chat(chat_id=user["id"])
    messages = []

    for i in range(message_count):
        if i % 2 == 0:
            # User message
            messages.append({
                "role": "user",
                "content": f"User message {i + 1}",
                "message": sample_message(f"User message {i + 1}", user=user, chat=chat),
            })
        elif include_bot_responses:
            # Bot response
            messages.append({
                "role": "assistant",
                "content": f"Bot response {i + 1}",
                "message": None,  # Bot responses don't have a message object
            })

    return {
        "id": f"conv_{_random_string(8)}",
        "user": user,
        "chat": chat,
        "messages": messages,
        "started_at": datetime.utcnow().isoformat(),
        "is_active": True,
    }


def sample_jarvis_conversation(**kwargs) -> Dict[str, Any]:
    """Create a sample Jarvis bot conversation."""
    conv = sample_conversation(**kwargs)
    conv["bot"] = "clawdjarvis"
    conv["messages"][0]["message"]["text"] = "/jarvis What can you do?"
    return conv


def sample_friday_conversation(**kwargs) -> Dict[str, Any]:
    """Create a sample Friday bot conversation."""
    conv = sample_conversation(**kwargs)
    conv["bot"] = "clawdfriday"
    conv["messages"][0]["message"]["text"] = "/email Partnership | Let's work together"
    return conv


def sample_matt_conversation(**kwargs) -> Dict[str, Any]:
    """Create a sample Matt bot conversation."""
    conv = sample_conversation(**kwargs)
    conv["bot"] = "clawdmatt"
    conv["messages"][0]["message"]["text"] = "/review Check out our amazing product!"
    return conv


# Config Fixtures

def sample_config(
    bot_name: str = "testbot",
    bot_token: str = "123456:ABC-DEF",
    admin_ids: Optional[List[int]] = None,
    features: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """
    Create a sample bot configuration fixture.

    Usage:
        config = sample_config(bot_name="clawdjarvis")
    """
    return {
        "bot_name": bot_name,
        "bot_token": bot_token,
        "admin_ids": admin_ids or [123456789],
        "features": features or {
            "llm_enabled": True,
            "logging_enabled": True,
            "rate_limiting": True,
        },
        "rate_limits": {
            "messages_per_minute": 20,
            "commands_per_minute": 10,
        },
        "llm_config": {
            "model": "grok-3",
            "temperature": 0.7,
            "max_tokens": 1024,
        },
    }


def sample_jarvis_config(**kwargs) -> Dict[str, Any]:
    """Create sample ClawdJarvis configuration."""
    kwargs.setdefault("bot_name", "clawdjarvis")
    config = sample_config(**kwargs)
    config["features"]["computer_control"] = True
    config["features"]["skill_system"] = True
    return config


def sample_friday_config(**kwargs) -> Dict[str, Any]:
    """Create sample ClawdFriday configuration."""
    kwargs.setdefault("bot_name", "clawdfriday")
    config = sample_config(**kwargs)
    config["features"]["email_analysis"] = True
    config["features"]["draft_generation"] = True
    return config


def sample_matt_config(**kwargs) -> Dict[str, Any]:
    """Create sample ClawdMatt configuration."""
    kwargs.setdefault("bot_name", "clawdmatt")
    config = sample_config(**kwargs)
    config["features"]["pr_review"] = True
    config["features"]["content_filtering"] = True
    return config


# Update Fixtures

def sample_update(
    message: Optional[Dict] = None,
    callback_query: Optional[Dict] = None,
    update_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a sample Telegram update fixture.

    Usage:
        update = sample_update(message=sample_message("/help"))
    """
    return {
        "update_id": update_id or _random_int(1, 1000000),
        "message": message,
        "callback_query": callback_query,
        "edited_message": None,
        "channel_post": None,
    }


def sample_message_update(text: str = "Hello", **kwargs) -> Dict[str, Any]:
    """Create a sample message update."""
    return sample_update(message=sample_message(text, **kwargs))


def sample_callback_update(data: str, **kwargs) -> Dict[str, Any]:
    """Create a sample callback update."""
    return sample_update(callback_query=sample_callback(data, **kwargs))


# Email Fixtures (for ClawdFriday)

def sample_email(
    subject: str = "Test Subject",
    body: str = "Test email body content.",
    sender: str = "sender@example.com",
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a sample email fixture.

    Usage:
        email = sample_email(subject="Partnership Inquiry")
    """
    return {
        "subject": subject,
        "body": body,
        "sender": sender,
        "received_at": datetime.utcnow().isoformat(),
        "category": category,
        "is_read": False,
    }


def sample_business_email(**kwargs) -> Dict[str, Any]:
    """Create a sample business inquiry email."""
    kwargs.setdefault("subject", "Business Opportunity")
    kwargs.setdefault("body", "We'd like to discuss a potential business opportunity...")
    kwargs.setdefault("category", "business_inquiry")
    return sample_email(**kwargs)


def sample_support_email(**kwargs) -> Dict[str, Any]:
    """Create a sample support request email."""
    kwargs.setdefault("subject", "Need Help")
    kwargs.setdefault("body", "I'm having an issue with...")
    kwargs.setdefault("category", "technical_support")
    return sample_email(**kwargs)


# PR Review Fixtures (for ClawdMatt)

def sample_pr_content(
    text: str = "Check out our new feature!",
    tone: str = "professional",
) -> Dict[str, Any]:
    """
    Create a sample PR content fixture.

    Usage:
        content = sample_pr_content(text="Amazing results!")
    """
    return {
        "text": text,
        "tone": tone,
        "word_count": len(text.split()),
        "created_at": datetime.utcnow().isoformat(),
    }


def sample_approved_content(**kwargs) -> Dict[str, Any]:
    """Create sample content that would be approved."""
    kwargs.setdefault("text", "We're excited to share our latest update.")
    kwargs.setdefault("tone", "professional")
    return sample_pr_content(**kwargs)


def sample_blocked_content(**kwargs) -> Dict[str, Any]:
    """Create sample content that would be blocked."""
    kwargs.setdefault("text", "This damn thing is f*cking amazing!")
    kwargs.setdefault("tone", "inappropriate")
    return sample_pr_content(**kwargs)


def sample_needs_revision_content(**kwargs) -> Dict[str, Any]:
    """Create sample content that needs revision."""
    kwargs.setdefault("text", "We're the best in the industry, 100% guaranteed!")
    kwargs.setdefault("tone", "overpromising")
    return sample_pr_content(**kwargs)
