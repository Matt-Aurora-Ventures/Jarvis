"""
Secure Terminal Handler for Telegram.

Allows admin to execute terminal commands via Telegram.
CRITICAL: Sanitizes ALL output to never expose keys/secrets.

Only @matthaynes88 (admin) can use this.
"""

import asyncio
import logging
import os
import re
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns to detect and redact secrets
SECRET_PATTERNS = [
    # API Keys
    (r'sk-ant-[a-zA-Z0-9\-_]+', '[REDACTED_ANTHROPIC_KEY]'),
    (r'xai-[a-zA-Z0-9\-_]+', '[REDACTED_XAI_KEY]'),
    (r'sk-[a-zA-Z0-9\-_]{20,}', '[REDACTED_API_KEY]'),

    # Tokens
    (r'[0-9]+:[A-Za-z0-9_-]{35,}', '[REDACTED_BOT_TOKEN]'),
    (r'AAAA[A-Za-z0-9%_-]{30,}', '[REDACTED_BEARER_TOKEN]'),

    # Private keys / Keypairs (base58/base64)
    (r'[1-9A-HJ-NP-Za-km-z]{87,88}', '[REDACTED_PRIVATE_KEY]'),
    (r'-----BEGIN[^-]+-----[^-]+-----END[^-]+-----', '[REDACTED_PEM_KEY]'),

    # Passwords in env files
    (r'(PASSWORD|SECRET|KEY|TOKEN)=\S+', r'\1=[REDACTED]'),
    (r'(password|secret|key|token)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),

    # Wallet addresses with balances (keep address, hide if in sensitive context)
    (r'(private_key|secret_key|mnemonic)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),

    # Common secret formats
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'[a-f0-9]{64}', '[REDACTED_HEX_SECRET]'),  # 256-bit hex keys

    # Connection strings
    (r'postgresql://[^\s]+', '[REDACTED_DB_URL]'),
    (r'mongodb(\+srv)?://[^\s]+', '[REDACTED_DB_URL]'),
    (r'redis://[^\s]+', '[REDACTED_DB_URL]'),
]

# Commands that are too dangerous
BLOCKED_COMMANDS = [
    'rm -rf /',
    'rm -rf /*',
    'format',
    'mkfs',
    ':(){:|:&};:',  # fork bomb
    'dd if=',
    '> /dev/sd',
    'chmod -R 777 /',
    'curl | bash',
    'wget | bash',
]

# Files that should never be read/output
SENSITIVE_FILES = [
    '.env',
    'keypair',
    'secret',
    'password',
    'credentials',
    'private',
    '.pem',
    '.key',
]


class TerminalHandler:
    """Secure terminal command execution for Telegram."""

    def __init__(self, admin_user_ids: list[int] = None):
        admin_str = os.environ.get("TELEGRAM_ADMIN_IDS", "")
        self.admin_ids = admin_user_ids or [
            int(x.strip()) for x in admin_str.split(",") if x.strip().isdigit()
        ]
        self.working_dir = os.environ.get(
            "JARVIS_WORKING_DIR",
            r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
        )

    def is_admin(self, user_id: int) -> bool:
        """Check if user is authorized to run commands."""
        return user_id in self.admin_ids

    def sanitize_output(self, text: str) -> str:
        """Remove ALL sensitive information from output."""
        if not text:
            return text

        sanitized = text

        # Apply all redaction patterns
        for pattern, replacement in SECRET_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        # Extra safety: redact anything that looks like an API key
        # Long alphanumeric strings (40+ chars) that aren't file paths
        sanitized = re.sub(
            r'(?<![/\\])[A-Za-z0-9+/]{40,}(?![/\\])',
            '[REDACTED_LONG_SECRET]',
            sanitized
        )

        return sanitized

    def is_safe_command(self, command: str) -> Tuple[bool, str]:
        """Check if command is safe to execute."""
        cmd_lower = command.lower().strip()

        # Check blocked commands
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return False, f"Blocked: dangerous command pattern '{blocked}'"

        # Check if trying to read sensitive files
        if any(keyword in cmd_lower for keyword in ['cat ', 'type ', 'more ', 'less ', 'head ', 'tail ']):
            for sensitive in SENSITIVE_FILES:
                if sensitive in cmd_lower:
                    return False, f"Blocked: cannot read sensitive files containing '{sensitive}'"

        # Check for env dump attempts
        if cmd_lower in ['env', 'set', 'printenv', 'export']:
            return False, "Blocked: environment variable dump not allowed"

        if 'echo $' in cmd_lower or 'echo %' in cmd_lower:
            return False, "Blocked: environment variable echo not allowed"

        return True, "OK"

    async def execute(self, command: str, user_id: int) -> str:
        """Execute a terminal command safely."""
        # Auth check
        if not self.is_admin(user_id):
            logger.warning(f"Unauthorized terminal attempt by user {user_id}")
            return "Access denied. Terminal commands are admin-only."

        # Safety check
        is_safe, reason = self.is_safe_command(command)
        if not is_safe:
            logger.warning(f"Blocked unsafe command from {user_id}: {command[:50]}")
            return f"Command blocked: {reason}"

        try:
            # Execute with timeout
            logger.info(f"Executing command for admin {user_id}: {command[:50]}...")

            # Set up environment with proper HOME for Windows compatibility
            env = os.environ.copy()
            env['HOME'] = os.path.expanduser('~')
            if 'USERPROFILE' not in env:
                env['USERPROFILE'] = os.path.expanduser('~')

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                process.kill()
                return "Command timed out (30s limit)"

            # Combine output
            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += "\n[stderr]\n" + stderr.decode('utf-8', errors='replace')

            # Sanitize before returning
            sanitized = self.sanitize_output(output)

            # Truncate if too long for Telegram
            if len(sanitized) > 4000:
                sanitized = sanitized[:3900] + "\n\n[... output truncated ...]"

            return sanitized or "(no output)"

        except Exception as e:
            logger.error(f"Terminal execution error: {e}")
            return f"Execution error: {str(e)}"


# Singleton instance
_handler: Optional[TerminalHandler] = None


def get_terminal_handler() -> TerminalHandler:
    global _handler
    if _handler is None:
        _handler = TerminalHandler()
    return _handler
