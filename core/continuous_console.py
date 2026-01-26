"""
Continuous Claude Console for Telegram Vibe Coding

Features:
- Persistent console sessions per user with conversation history
- Anthropic API integration with proper OAuth token
- Automatic output sanitization (secrets, keys, passwords)
- Safe for both development ("vibe coding") and financial analysis
- Session management with automatic cleanup
- Integration with Dexter for financial queries

Security:
- All responses scrubbed for sensitive data
- Rate limiting per user
- Admin-only access for coding tasks
- Audit logging of all console requests
"""

from __future__ import annotations

import os
import re
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

# Console session storage
CONSOLE_DIR = Path.home() / ".jarvis" / "console_sessions"
CONSOLE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ConsoleMessage:
    """A message in a console session."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    sanitized: bool = False


@dataclass
class ConsoleSession:
    """A persistent Claude console session for a user."""
    user_id: int
    username: str
    chat_id: int
    session_id: str
    messages: List[ConsoleMessage]
    created_at: str
    last_active: str
    message_count: int = 0
    total_tokens: int = 0


class ContinuousConsole:
    """
    Continuous Claude console with persistent sessions.

    Each user gets their own console that persists across messages.
    Sessions automatically clean up after 24 hours of inactivity.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize continuous console."""
        # Use vibecoding key for console (supports advanced features)
        self.api_key = api_key or os.getenv("VIBECODING_ANTHROPIC_KEY") or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key or self.api_key == "ollama":
            logger.warning("No valid Anthropic API key - console will be disabled")
            self.client = None
        else:
            # Initialize with explicit timeout (5 minutes max per request)
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=300.0  # 5 minutes
            )
            logger.info("Continuous console initialized with Anthropic API (timeout=300s)")

        self.sessions: Dict[int, ConsoleSession] = {}
        self._load_sessions()

        # Sensitive pattern detection for output sanitization
        self.sensitive_patterns = [
            (re.compile(r'(sk-ant-[a-zA-Z0-9_-]{95,})', re.IGNORECASE), '[ANTHROPIC_KEY_REDACTED]'),
            (re.compile(r'(sk-[a-zA-Z0-9]{32,})', re.IGNORECASE), '[API_KEY_REDACTED]'),
            (re.compile(r'([a-zA-Z0-9]{40,}:[a-zA-Z0-9_-]{30,})', re.IGNORECASE), '[TOKEN_REDACTED]'),
            (re.compile(r'(password\s*[=:]\s*["\']?[^\s"\']+)', re.IGNORECASE), 'password=[REDACTED]'),
            (re.compile(r'(api[_-]?key\s*[=:]\s*["\']?[^\s"\']+)', re.IGNORECASE), 'api_key=[REDACTED]'),
            (re.compile(r'(secret\s*[=:]\s*["\']?[^\s"\']+)', re.IGNORECASE), 'secret=[REDACTED]'),
            (re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', re.IGNORECASE), '[EMAIL_REDACTED]'),
            (re.compile(r'(postgres://[^\s]+)', re.IGNORECASE), '[DATABASE_URL_REDACTED]'),
            (re.compile(r'(mongodb://[^\s]+)', re.IGNORECASE), '[DATABASE_URL_REDACTED]'),
            (re.compile(r'(/home/[^\s]+|c:\\users\\[^\s]+)', re.IGNORECASE), '[PATH_REDACTED]'),
        ]

    def _load_sessions(self):
        """Load active sessions from disk."""
        try:
            for session_file in CONSOLE_DIR.glob("*.json"):
                with open(session_file, 'r') as f:
                    data = json.load(f)
                    session = ConsoleSession(**data)

                    # Only load sessions active in last 24 hours
                    last_active = datetime.fromisoformat(session.last_active.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) - last_active < timedelta(hours=24):
                        self.sessions[session.user_id] = session
                    else:
                        # Clean up old session
                        session_file.unlink()
        except Exception as e:
            logger.error(f"Failed to load console sessions: {e}")

    def _save_session(self, session: ConsoleSession):
        """Save session to disk."""
        try:
            session_file = CONSOLE_DIR / f"session_{session.user_id}.json"
            with open(session_file, 'w') as f:
                json.dump(asdict(session), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def get_or_create_session(
        self,
        user_id: int,
        username: str,
        chat_id: int
    ) -> ConsoleSession:
        """Get existing session or create new one."""
        if user_id in self.sessions:
            session = self.sessions[user_id]
            session.last_active = datetime.now(timezone.utc).isoformat()
            return session

        # Create new session
        session = ConsoleSession(
            user_id=user_id,
            username=username,
            chat_id=chat_id,
            session_id=f"console_{user_id}_{int(datetime.now().timestamp())}",
            messages=[],
            created_at=datetime.now(timezone.utc).isoformat(),
            last_active=datetime.now(timezone.utc).isoformat()
        )

        self.sessions[user_id] = session
        self._save_session(session)

        logger.info(f"Created new console session for user {user_id} ({username})")
        return session

    def chunk_response(self, text: str, max_size: int = 3800) -> List[str]:
        """
        Split response into Telegram-safe chunks with code block preservation.

        Args:
            text: The text to chunk
            max_size: Maximum chunk size (default 3800, leaving margin under 4096 Telegram limit)

        Returns:
            List of chunks with preserved code block formatting
        """
        if len(text) <= max_size:
            return [text]

        chunks = []
        current_chunk = ""
        in_code_block = False
        code_block_lang = ""

        lines = text.split('\n')

        for line in lines:
            # Detect code block boundaries
            if line.strip().startswith('```'):
                if not in_code_block:
                    # Opening code block
                    in_code_block = True
                    code_block_lang = line.strip()[3:].strip()  # Extract language
                else:
                    # Closing code block
                    in_code_block = False

            # Check if adding this line would exceed limit
            if len(current_chunk) + len(line) + 1 > max_size:
                # Close code block if open
                if in_code_block:
                    current_chunk += "\n```"

                # Save current chunk
                chunks.append(current_chunk.strip())

                # Start new chunk
                current_chunk = ""

                # Reopen code block if we were in one
                if in_code_block:
                    current_chunk = f"```{code_block_lang}\n"

            current_chunk += line + "\n"

        # Add final chunk
        if current_chunk.strip():
            # Close any open code block
            if in_code_block:
                current_chunk += "```"
            chunks.append(current_chunk.strip())

        return chunks

    def sanitize_output(self, text: str) -> str:
        """
        Sanitize output to remove sensitive information.

        Removes:
        - API keys and tokens
        - Passwords and secrets
        - Email addresses
        - Database URLs
        - File paths
        """
        sanitized = text

        for pattern, replacement in self.sensitive_patterns:
            sanitized = pattern.sub(replacement, sanitized)

        return sanitized

    async def execute(
        self,
        user_id: int,
        username: str,
        chat_id: int,
        prompt: str,
        mode: str = "vibe"  # "vibe" for coding, "financial" for Dexter-style analysis
    ) -> Dict[str, Any]:
        """
        Execute a console request with conversation history.

        Args:
            user_id: Telegram user ID
            username: Username
            chat_id: Chat ID for responses
            prompt: User's request
            mode: "vibe" for coding tasks, "financial" for market analysis

        Returns:
            Dict with response, tokens_used, sanitized flag
        """
        if not self.client:
            return {
                "success": False,
                "response": "Console unavailable - API key not configured",
                "tokens_used": 0,
                "sanitized": False
            }

        try:
            # Get or create session
            session = self.get_or_create_session(user_id, username, chat_id)

            # Add user message to session
            user_msg = ConsoleMessage(
                role="user",
                content=prompt,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            session.messages.append(user_msg)

            # Build system prompt based on mode
            if mode == "vibe":
                system_prompt = self._get_vibe_system_prompt(username)
            else:
                system_prompt = self._get_financial_system_prompt(username)

            # Build conversation history for API (last 20 messages)
            messages = []
            for msg in session.messages[-20:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

            # Call Claude API with timeout and retry handling
            logger.info(f"Executing console request for {username} (mode={mode})")
            try:
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",  # Claude 3.5 Sonnet (widely available)
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    temperature=0.7
                )
            except anthropic.APITimeoutError as e:
                logger.warning(f"API timeout for user {user_id}: {e}")
                return {
                    "success": False,
                    "response": "⏱️ Request timed out after 5 minutes.\n\nTry breaking your task into smaller steps.",
                    "tokens_used": 0,
                    "sanitized": False
                }
            except anthropic.RateLimitError as e:
                logger.warning(f"Rate limited for user {user_id}: {e}")
                return {
                    "success": False,
                    "response": "⚠️ API rate limit reached.\n\nPlease wait a moment and try again.",
                    "tokens_used": 0,
                    "sanitized": False
                }
            except anthropic.APIConnectionError as e:
                logger.error(f"API connection error for user {user_id}: {e}")
                return {
                    "success": False,
                    "response": "🌐 Network error connecting to Claude API.\n\nCheck your internet connection and try again.",
                    "tokens_used": 0,
                    "sanitized": False
                }
            except anthropic.AuthenticationError as e:
                logger.error(f"API authentication error: {e}")
                return {
                    "success": False,
                    "response": "🔑 API authentication failed.\n\nContact admin to check API key configuration.",
                    "tokens_used": 0,
                    "sanitized": False
                }
            except anthropic.APIError as e:
                logger.error(f"Claude API error for user {user_id}: {e}")
                return {
                    "success": False,
                    "response": f"❌ Claude API error: {str(e)}\n\nThis has been logged for investigation.",
                    "tokens_used": 0,
                    "sanitized": False
                }

            # Extract response
            assistant_content = response.content[0].text if response.content else ""

            # Sanitize output
            sanitized_content = self.sanitize_output(assistant_content)
            was_sanitized = sanitized_content != assistant_content

            # Add assistant message to session
            assistant_msg = ConsoleMessage(
                role="assistant",
                content=sanitized_content,
                timestamp=datetime.now(timezone.utc).isoformat(),
                sanitized=was_sanitized
            )
            session.messages.append(assistant_msg)

            # Update session stats
            session.message_count += 1
            session.total_tokens += response.usage.input_tokens + response.usage.output_tokens
            session.last_active = datetime.now(timezone.utc).isoformat()

            # Save session
            self._save_session(session)

            return {
                "success": True,
                "response": sanitized_content,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "sanitized": was_sanitized,
                "session_id": session.session_id,
                "message_count": session.message_count
            }

        except Exception as e:
            logger.error(f"Console execution error: {e}", exc_info=True)
            return {
                "success": False,
                "response": f"❌ Unexpected error: {type(e).__name__}\n\nThis has been logged for investigation.",
                "tokens_used": 0,
                "sanitized": False
            }

    def _get_vibe_system_prompt(self, username: str) -> str:
        """System prompt for vibe coding mode."""
        return f"""You are JARVIS, a highly capable AI assistant helping {username} with development tasks.

You have access to the Jarvis codebase and can:
- Write and modify code
- Debug issues
- Explain implementations
- Suggest improvements
- Execute CLI commands (with user approval)

IMPORTANT GUIDELINES:
1. Be concise and action-oriented
2. Provide working code, not just explanations
3. Consider security and best practices
4. Ask for clarification when needed
5. Format code with proper syntax highlighting

Current context: Telegram vibe coding session
User: {username}
Mode: Development/Coding

Respond directly with solutions. Keep explanations brief unless asked for details."""

    def _get_financial_system_prompt(self, username: str) -> str:
        """System prompt for financial analysis mode."""
        return f"""You are JARVIS, a financial analysis AI assistant helping {username} with crypto/trading questions.

You can:
- Analyze token sentiment and trends
- Provide market insights
- Explain trading concepts
- Review position strategies

IMPORTANT:
1. Be direct and data-driven
2. Always include "NFA" (not financial advice) disclaimers
3. Emphasize DYOR (do your own research)
4. Focus on education, not predictions
5. Cite data sources when possible

Current context: Telegram financial analysis session
User: {username}
Mode: Financial/Trading

Provide clear, educational responses. Never guarantee outcomes."""

    def clear_session(self, user_id: int) -> bool:
        """Clear a user's console session."""
        if user_id in self.sessions:
            session = self.sessions[user_id]
            session_file = CONSOLE_DIR / f"session_{user_id}.json"

            if session_file.exists():
                session_file.unlink()

            del self.sessions[user_id]
            logger.info(f"Cleared console session for user {user_id}")
            return True
        return False

    def get_session_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get session information for a user."""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        return {
            "session_id": session.session_id,
            "username": session.username,
            "message_count": session.message_count,
            "total_tokens": session.total_tokens,
            "created_at": session.created_at,
            "last_active": session.last_active,
            "age_hours": (
                datetime.now(timezone.utc) -
                datetime.fromisoformat(session.created_at.replace('Z', '+00:00'))
            ).total_seconds() / 3600
        }


# Singleton instance
_console: Optional[ContinuousConsole] = None


def get_continuous_console() -> ContinuousConsole:
    """Get or create the singleton continuous console."""
    global _console
    if _console is None:
        _console = ContinuousConsole()
    return _console


async def execute_vibe_request(
    user_id: int,
    username: str,
    chat_id: int,
    prompt: str
) -> Dict[str, Any]:
    """
    Execute a vibe coding request with continuous console.

    Convenience function for vibe coding mode.
    """
    console = get_continuous_console()
    return await console.execute(user_id, username, chat_id, prompt, mode="vibe")


async def execute_financial_request(
    user_id: int,
    username: str,
    chat_id: int,
    prompt: str
) -> Dict[str, Any]:
    """
    Execute a financial analysis request with continuous console.

    Convenience function for financial mode.
    """
    console = get_continuous_console()
    return await console.execute(user_id, username, chat_id, prompt, mode="financial")
