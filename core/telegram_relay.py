"""
Telegram ↔ Claude Code Relay.

Bidirectional message bridge that allows controlling Claude Code from Telegram.
Automatically sanitizes sensitive information before transmission.
"""

import json
import re
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


# Sensitive patterns to redact
SENSITIVE_PATTERNS = [
    # API keys and tokens
    (r'sk-ant-[a-zA-Z0-9\-_]{20,}', '[ANTHROPIC_API_KEY]'),
    (r'xai-[a-zA-Z0-9]{20,}', '[XAI_API_KEY]'),
    (r'\d{10}:AA[a-zA-Z0-9\-_]{33}', '[TELEGRAM_BOT_TOKEN]'),
    (r'bags_prod_[a-zA-Z0-9\-_]{20,}', '[BAGS_API_KEY]'),

    # Private keys and seeds
    (r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b', '[SOLANA_PRIVATE_KEY]'),
    (r'[a-f0-9]{64}', '[PRIVATE_KEY_HEX]'),

    # Passwords and credentials (generic patterns)
    (r'(?i)\bpassword\b\s*[:=]\s*\S+', '[PASSWORD]'),
    (r'(?i)\bjarvis_wallet_password\b\s*[:=]\s*\S+', '[WALLET_PASSWORD]'),
    (r'(?i)\bvps_password\b\s*[:=]\s*\S+', '[VPS_PASSWORD]'),

    # IP addresses
    (r'\b\d{1,3}(?:\.\d{1,3}){3}\b', '[IP_ADDRESS]'),

    # File paths (local machine)
    (r'[A-Za-z]:\\Users\\[^\\]+\\', '[LOCAL_PATH]\\'),
    (r'/home/[^/]+/', '[VPS_PATH]/'),
]


@dataclass
class RelayMessage:
    """A message in the relay queue."""
    id: str
    direction: str  # "telegram_to_claude" or "claude_to_telegram"
    user_id: int
    username: Optional[str]
    content: str
    timestamp: str
    processed: bool = False
    response_id: Optional[str] = None  # Links request to response


class TelegramRelay:
    """
    Manages bidirectional message relay between Telegram and Claude Code.

    Architecture:
    - Telegram writes to: data/claude_relay/inbox.jsonl (telegram_to_claude)
    - Claude reads from: inbox.jsonl
    - Claude writes to: data/claude_relay/outbox.jsonl (claude_to_telegram)
    - Telegram reads from: outbox.jsonl
    """

    def __init__(self, relay_dir: Optional[Path] = None):
        if relay_dir is None:
            # Default to project root/data/claude_relay
            project_root = Path(__file__).resolve().parents[1]
            relay_dir = project_root / "data" / "claude_relay"

        self.relay_dir = relay_dir
        self.inbox = relay_dir / "inbox.jsonl"
        self.outbox = relay_dir / "outbox.jsonl"

        # Ensure directory exists
        self.relay_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_content(self, content: str) -> str:
        """Remove sensitive information from content."""
        sanitized = content

        for pattern, replacement in SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized)

        return sanitized

    def send_from_telegram(
        self,
        content: str,
        user_id: int,
        username: Optional[str] = None
    ) -> str:
        """
        Send a message from Telegram to Claude Code.

        Returns:
            Message ID for tracking response.
        """
        import uuid

        message = RelayMessage(
            id=str(uuid.uuid4()),
            direction="telegram_to_claude",
            user_id=user_id,
            username=username,
            content=content,  # Don't sanitize incoming - Claude needs full context
            timestamp=datetime.now(timezone.utc).isoformat(),
            processed=False
        )

        # Append to inbox
        with open(self.inbox, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(message)) + '\n')

        return message.id

    def get_pending_messages(self) -> List[RelayMessage]:
        """Get all unprocessed messages from Telegram."""
        if not self.inbox.exists():
            return []

        messages = []
        with open(self.inbox, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    msg = RelayMessage(**data)
                    if not msg.processed:
                        messages.append(msg)
                except (json.JSONDecodeError, TypeError):
                    continue

        return messages

    def mark_processed(self, message_id: str):
        """Mark a message as processed."""
        if not self.inbox.exists():
            return

        # Read all messages
        messages = []
        with open(self.inbox, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get('id') == message_id:
                        data['processed'] = True
                    messages.append(data)
                except json.JSONDecodeError:
                    continue

        # Write back
        with open(self.inbox, 'w', encoding='utf-8') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

    def send_response_to_telegram(
        self,
        content: str,
        request_id: str,
        user_id: int,
        username: Optional[str] = None
    ) -> str:
        """
        Send a response from Claude Code to Telegram.
        Automatically sanitizes sensitive content.

        Returns:
            Response message ID.
        """
        import uuid

        # CRITICAL: Sanitize before sending to Telegram
        sanitized_content = self.sanitize_content(content)

        message = RelayMessage(
            id=str(uuid.uuid4()),
            direction="claude_to_telegram",
            user_id=user_id,
            username=username,
            content=sanitized_content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            processed=False,
            response_id=request_id
        )

        # Append to outbox
        with open(self.outbox, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(message)) + '\n')

        return message.id

    def get_responses_for_telegram(self) -> List[RelayMessage]:
        """Get all unprocessed responses for Telegram."""
        if not self.outbox.exists():
            return []

        messages = []
        with open(self.outbox, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    msg = RelayMessage(**data)
                    if not msg.processed:
                        messages.append(msg)
                except (json.JSONDecodeError, TypeError):
                    continue

        return messages

    def mark_response_sent(self, response_id: str):
        """Mark a response as sent to Telegram."""
        if not self.outbox.exists():
            return

        # Read all messages
        messages = []
        with open(self.outbox, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get('id') == response_id:
                        data['processed'] = True
                    messages.append(data)
                except json.JSONDecodeError:
                    continue

        # Write back
        with open(self.outbox, 'w', encoding='utf-8') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

    def cleanup_old_messages(self, days: int = 7):
        """Remove messages older than specified days."""
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        for filepath in [self.inbox, self.outbox]:
            if not filepath.exists():
                continue

            # Read and filter
            kept_messages = []
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        timestamp = datetime.fromisoformat(data.get('timestamp', ''))
                        if timestamp > cutoff:
                            kept_messages.append(data)
                    except (json.JSONDecodeError, ValueError):
                        continue

            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                for msg in kept_messages:
                    f.write(json.dumps(msg) + '\n')


# Singleton instance
_relay: Optional[TelegramRelay] = None


def get_relay() -> TelegramRelay:
    """Get the global relay instance."""
    global _relay
    if _relay is None:
        _relay = TelegramRelay()
    return _relay
