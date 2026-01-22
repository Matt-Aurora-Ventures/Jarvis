"""
Claude CLI Handler for Telegram Coding Commands.

Executes coding requests via the Claude CLI and returns cleansed responses.

Flow:
1. Receive coding command from Telegram
2. Send confirmation back to Telegram (JARVIS voice)
3. Execute via `claude` CLI with conversation context
4. Cleanse output of sensitive info
5. Send response back to Telegram (JARVIS voice, brand bible)

Security:
- Only admin users can execute (@matthaynes88)
- All output is sanitized before returning
- No secrets/keys/passwords exposed
- Multi-layer scrubbing with paranoid mode
"""

import asyncio
import fnmatch
import logging
import os
import re
import shutil
import tempfile
import time
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

from core.security.scrubber import get_scrubber

logger = logging.getLogger(__name__)

# Lazy import anthropic for API mode
_anthropic_module = None


def _get_anthropic():
    """Lazily import anthropic module."""
    global _anthropic_module
    if _anthropic_module is None:
        try:
            import anthropic
            _anthropic_module = anthropic
        except ImportError:
            logger.warning("anthropic package not installed - API mode unavailable")
    return _anthropic_module


# Coding system prompt for API mode
CODING_SYSTEM_PROMPT = """You are JARVIS, an advanced AI coding assistant for the Jarvis trading system.

You have access to the Jarvis codebase and can help with:
- Writing and modifying Python code
- Debugging issues
- Explaining code architecture
- Suggesting improvements
- Running analysis

When responding:
- Be concise and actionable
- Show code when relevant (use markdown code blocks)
- Explain what changes you're making
- Warn about potential issues
- Follow Python best practices

The codebase is a Solana trading bot with:
- Telegram bot interface (tg_bot/)
- Twitter/X bot (bots/twitter/)
- Treasury trading engine (bots/treasury/)
- Core modules (core/)

Respond directly with the solution. No pleasantries needed."""

# JARVIS voice templates (from brand bible)
JARVIS_CONFIRMATIONS = [
    "on it. give me a sec...",
    "processing through my chrome skull...",
    "running this through my circuits...",
    "sensors locked on. executing...",
    "neural weights engaged. working on it...",
]

JARVIS_SUCCESS_RESPONSES = [
    "done. {summary}",
    "sorted. {summary}",
    "finished. {summary}",
    "task complete. {summary}",
    "executed successfully. {summary}",
]

JARVIS_ERROR_RESPONSES = [
    "hit a snag. {error}",
    "my circuits encountered an issue. {error}",
    "something went wrong. {error}",
    "task failed. {error}",
]

# COMPREHENSIVE secret patterns - PARANOID MODE
SECRET_PATTERNS = [
    # ============== API Keys ==============
    (r'sk-ant-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'xai-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'sk-[a-zA-Z0-9\-_]{20,}', '[REDACTED]'),
    (r'ANTHROPIC_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'ANTHROPIC_API_KEY=[REDACTED]'),
    (r'XAI_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'XAI_API_KEY=[REDACTED]'),
    (r'OPENAI_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'OPENAI_API_KEY=[REDACTED]'),
    (r'GROQ_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'GROQ_API_KEY=[REDACTED]'),

    # ============== Telegram ==============
    (r'[0-9]{8,10}:[A-Za-z0-9_-]{35,}', '[REDACTED_BOT_TOKEN]'),
    (r'TELEGRAM_BOT_TOKEN[=:]\s*[\'"]?[^\s\'"]+', 'TELEGRAM_BOT_TOKEN=[REDACTED]'),
    (r'TELEGRAM_ADMIN_ID[S]?[=:]\s*[\'"]?[^\s\'"]+', 'TELEGRAM_ADMIN_IDS=[REDACTED]'),

    # ============== Twitter/X ==============
    (r'TWITTER_[A-Z_]+[=:]\s*[\'"]?[^\s\'"]+', r'TWITTER_*=[REDACTED]'),
    (r'AAAA[A-Za-z0-9%_-]{30,}', '[REDACTED]'),

    # ============== Solana/Crypto ==============
    (r'[1-9A-HJ-NP-Za-km-z]{87,88}', '[REDACTED_PRIVATE_KEY]'),  # Base58 private key
    (r'[1-9A-HJ-NP-Za-km-z]{43,44}', '[POSSIBLE_WALLET]'),  # Base58 public key (flag but don't redact)
    (r'-----BEGIN[^-]+-----[\s\S]+?-----END[^-]+-----', '[REDACTED_PEM]'),
    (r'(private_key|secret_key|mnemonic|seed_phrase)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),
    (r'SOLANA_PRIVATE_KEY[=:]\s*[\'"]?[^\s\'"]+', 'SOLANA_PRIVATE_KEY=[REDACTED]'),
    (r'WALLET_SECRET[=:]\s*[\'"]?[^\s\'"]+', 'WALLET_SECRET=[REDACTED]'),

    # ============== Database ==============
    (r'postgresql://[^\s\'"]+', '[REDACTED_DB_URL]'),
    (r'mongodb(\+srv)?://[^\s\'"]+', '[REDACTED_DB_URL]'),
    (r'redis://[^\s\'"]+', '[REDACTED_DB_URL]'),
    (r'DATABASE_URL[=:]\s*[\'"]?[^\s\'"]+', 'DATABASE_URL=[REDACTED]'),

    # ============== GitHub ==============
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'ghr_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}', '[REDACTED]'),
    (r'GITHUB_TOKEN[=:]\s*[\'"]?[^\s\'"]+', 'GITHUB_TOKEN=[REDACTED]'),

    # ============== Generic Secrets ==============
    (r'(PASSWORD|SECRET|KEY|TOKEN|CREDENTIAL|AUTH)[=:]\s*[\'"]?[^\s\'"]{8,}[\'"]?', r'\1=[REDACTED]'),
    (r'(password|secret|key|token|credential|auth)["\']?\s*[:=]\s*["\']?[^\s"\']{8,}', r'\1=[REDACTED]'),

    # ============== Hex Secrets ==============
    (r'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])', '[REDACTED_HEX]'),  # 256-bit hex
    (r'(?<![a-f0-9])[a-f0-9]{32}(?![a-f0-9])', '[REDACTED_HEX]'),  # 128-bit hex (UUIDs are ok)

    # ============== JWT Tokens ==============
    (r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED_JWT]'),

    # ============== AWS ==============
    (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]'),
    (r'aws_secret_access_key[=:]\s*[\'"]?[^\s\'"]+', 'aws_secret_access_key=[REDACTED]'),

    # ============== Environment Files ==============
    (r'\.env[a-z.]*', '.env[HIDDEN]'),
    (r'secrets/[^\s]+', 'secrets/[HIDDEN]'),
    (r'credentials[^\s]*\.json', 'credentials[HIDDEN].json'),

    # ============== IP Addresses (Optional - might be useful) ==============
    # (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP_HIDDEN]'),

    # ============== User Paths (raw strings for Windows escapes) ==============
    (r'C:\\Users\\[^\\]+\\', r'C:\\Users\\***\\'),
    (r'/home/[^/]+/', '/home/***/')
]

# Additional paranoid patterns for final pass
PARANOID_PATTERNS = [
    # Long alphanumeric strings that look like secrets
    (r'(?<![A-Za-z0-9/\\])[A-Za-z0-9+/]{40,}(?![A-Za-z0-9/\\])', '[REDACTED_LONG_SECRET]'),
    # Base64 encoded data
    (r'(?<![A-Za-z0-9])[A-Za-z0-9+/]{20,}={1,2}(?![A-Za-z0-9])', '[REDACTED_BASE64]'),
]

# Additional patterns specific to Claude CLI output
CLAUDE_OUTPUT_PATTERNS = [
    # Remove ANSI escape codes
    (r'\x1b\[[0-9;]*[mGKHF]', ''),
    # Remove progress spinners
    (r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', ''),
    # Simplify file paths
    (r'c:\\Users\\lucid\\OneDrive\\Desktop\\Projects\\Jarvis\\', ''),
    (r'/home/[^/]+/', '~/'),
    # Remove Claude hook errors (sandbox $HOME expansion issues)
    (r'(?:Session|PreTool|PostTool|Stop)(?:End|Use)? hook \[[^\]]+\] failed:[^\n]*\n', '\n'),

    # ============== Node.js Error Cleanup (COMPREHENSIVE) ==============
    # Full Node.js error blocks (throw err through stack trace)
    (r'throw err;[\s\S]*?Node\.js v[\d.]+', ''),
    # Standalone throw err with caret
    (r'\s*throw err;\s*\n\s*\^\s*\n', ''),
    # requireStack patterns
    (r'\s*requireStack:\s*\[[\s\S]*?\]\s*\n?', ''),
    # code: MODULE_NOT_FOUND patterns
    (r"\s*code:\s*'MODULE_NOT_FOUND'[,\s]*\n?", ''),
    # Node.js version line
    (r'\s*Node\.js v[\d.]+\s*\n?', ''),
    # node:internal module path lines
    (r'\s*node:internal/[^\n]*\n', ''),
    # at Function.Module lines (stack trace)
    (r'\s*at Function\.Module[^\n]*\n', ''),
    (r'\s*at Module\.[^\n]*\n', ''),
    (r'\s*at Object\.<anonymous>[^\n]*\n', ''),
    # Error: Cannot find module with full stack trace
    (r"Error: Cannot find module '[^']*'[\s\S]*?(?=\n\n|\Z)", ''),
    # Orphaned closing braces from error objects
    (r'^\s*\}\s*$', ''),
    # requireStack array content
    (r"requireStack:\s*\[\s*'[^']*'\s*\]", ''),

    # ============== Bash/Shell Errors ==============
    # Remove bash: command not found errors from hooks
    (r'bash: [^\n]*: No such file or directory\n', ''),
    (r'bash: [^\n]*: command not found\n', ''),
    # Remove shell error codes
    (r'\nError: Command failed with exit code \d+\n?', ''),

    # ============== Hook Error Cleanup ==============
    # Hook failure traces
    (r'Hook \S+ failed:[\s\S]*?(?=\n\n|\Z)', ''),
    # Failed to load hook messages
    (r'Failed to load hook[^\n]*\n', ''),

    # ============== Final Cleanup ==============
    # Multiple consecutive blank lines to 2
    (r'\n{3,}', '\n\n'),
    # Lines with only whitespace
    (r'\n\s+\n', '\n\n'),
    # Trailing whitespace
    (r'[ \t]+$', ''),
]


class ClaudeCLIHandler:
    """Handler for executing coding commands via Claude CLI.

    Security: Only authorized admin (@matthaynes88) can execute.
    All output is triple-scrubbed before returning.
    """

    # Known Claude CLI locations (Windows + Linux)
    CLAUDE_PATHS = [
        # Windows paths
        r"C:\Users\lucid\AppData\Roaming\npm\claude.cmd",
        r"C:\Users\lucid\AppData\Roaming\npm\claude",
        # Linux paths (VPS)
        "/usr/local/bin/claude",
        "/home/ubuntu/.local/bin/claude",
        "/home/jarvis/.local/bin/claude",
        "claude",  # fallback to PATH
    ]

    # Strict admin whitelist - ONLY these users can execute CLI
    ADMIN_WHITELIST = {
        8527130908,  # Matt (@matthaynes88)
    }

    # Telegram usernames allowed (as backup check)
    ADMIN_USERNAMES = {
        "matthaynes88",
    }

    # Rate limiting configuration
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_REQUESTS = 5  # max requests per window
    RATE_LIMIT_MIN_GAP = 5  # minimum seconds between requests

    # Circuit breaker configuration (like X bot)
    CIRCUIT_BREAKER_ERROR_THRESHOLD = 3  # errors before tripping
    CIRCUIT_BREAKER_COOLDOWN = 1800  # 30 minutes cooldown when tripped
    CIRCUIT_BREAKER_WINDOW = 300  # 5 minute window for counting errors

    # API mode disabled - CLI only
    USE_API_MODE = False
    API_MODEL = "claude-sonnet-4-20250514"
    API_MAX_TOKENS = 4096

    # Auto-retry configuration
    MAX_RETRIES = 2
    RETRY_BASE_DELAY = 2  # seconds
    TRANSIENT_ERROR_PATTERNS = [
        "connection",
        "timeout",
        "network",
        "temporarily unavailable",
        "retry",
        "eagain",  # lowercase for case-insensitive match
        "econnrefused",
        "econnreset",
    ]

    ISOLATION_IGNORE_NAMES = {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        ".agent",
        ".claude",
        ".codex",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "logs",
        "tmp",
        "temp",
        "data",
        "nul",
        "con",
        "prn",
        "aux",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }

    ISOLATION_IGNORE_GLOBS = {
        ".env",
        ".env.*",
        "*.log",
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        "*.pem",
        "*.key",
        "*.pfx",
    }

    SANDBOX_ENV_BLOCKLIST = (
        "KEY",
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "PRIVATE",
        "MNEMONIC",
        "SEED",
        "CREDENTIAL",
    )

    SANDBOX_ENV_ALLOWLIST = {
        "ANTHROPIC_API_KEY",
        "CLAUDE_API_KEY",
        "CLAUDE_CODE_API_KEY",
    }

    WINDOWS_RESERVED_NAMES = {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }

    def __init__(self, admin_user_ids: list[int] = None):
        # Use strict whitelist, ignore env var for CLI execution
        self.admin_ids = set(self.ADMIN_WHITELIST)
        if admin_user_ids:
            # Allow additional admins only if explicitly passed
            self.admin_ids.update(admin_user_ids)

        # Determine working directory (Windows or Linux)
        default_dir = (
            r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
            if os.name == "nt"
            else "/home/ubuntu/Jarvis"
        )
        self.working_dir = os.environ.get("JARVIS_WORKING_DIR", default_dir)
        self._active_process: Optional[asyncio.subprocess.Process] = None
        self._env_claude_path = (
            os.environ.get("CLAUDE_CLI_PATH")
            or os.environ.get("JARVIS_CLAUDE_PATH")
            or os.environ.get("CLAUDE_PATH")
        )
        self._claude_path = self._find_claude()
        self._conversation_context: List[Dict] = []

        # Import memory bridge for context
        try:
            from core.telegram_console_bridge import get_console_bridge
            self._bridge = get_console_bridge()
        except ImportError:
            self._bridge = None
            logger.warning("Console bridge not available - no conversation context")

        # Rate limiting tracker: user_id -> list of request timestamps
        self._request_history: Dict[int, List[float]] = defaultdict(list)

        # Circuit breaker state
        self._error_timestamps: List[float] = []  # Recent error timestamps
        self._circuit_breaker_tripped_at: Optional[float] = None

        # Execution metrics
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "last_execution": None,
            "execution_history": [],  # Last 50 executions
        }

        # Command queue for serialized execution
        self._execution_lock = asyncio.Lock()
        self._queue_depth = 0
        self._max_queue_depth = 3  # Max commands waiting

        # API mode client (lazy init)
        self._anthropic_client = None
        self._api_mode_available = False
        self._init_api_client()
        self._pending_commands: List[Dict[str, Any]] = []  # Track pending commands

    def _init_api_client(self):
        """Initialize Anthropic API client for API mode."""
        if not self.USE_API_MODE:
            logger.info("API mode disabled - using CLI subprocess mode")
            return

        anthropic = _get_anthropic()
        if anthropic is None:
            logger.warning("anthropic package not available - falling back to CLI mode")
            return

        # Try to get API key from environment or secrets
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            try:
                from core.secrets import get_anthropic_key
                api_key = get_anthropic_key()
            except ImportError:
                pass

        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not found - falling back to CLI mode")
            return

        try:
            self._anthropic_client = anthropic.Anthropic(api_key=api_key)
            self._api_mode_available = True
            logger.info("API mode initialized - using Anthropic API directly (no CLI subprocess)")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            self._api_mode_available = False

    async def _execute_via_api(
        self,
        prompt: str,
        user_id: int,
        context: str = None,
    ) -> Tuple[bool, str, str]:
        """Execute coding request via Anthropic API instead of CLI subprocess.

        This uses the same API that governs this Claude instance, providing
        a unified experience without spawning separate processes.

        Returns:
            Tuple[success, jarvis_response, full_output]
        """
        if not self._api_mode_available or not self._anthropic_client:
            raise RuntimeError("API mode not available")

        start_time = time.time()

        # Build the message with optional context
        messages = []
        if context:
            messages.append({
                "role": "user",
                "content": f"## Context from conversation:\n{context}\n\n## Current request:\n{prompt}"
            })
        else:
            messages.append({"role": "user", "content": prompt})

        try:
            # Run in thread pool since anthropic client is sync
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._anthropic_client.messages.create(
                    model=self.API_MODEL,
                    max_tokens=self.API_MAX_TOKENS,
                    system=CODING_SYSTEM_PROMPT,
                    messages=messages,
                )
            )

            # Extract response content
            output = response.content[0].text if response.content else ""

            # Sanitize output (same as CLI mode)
            sanitized = self.sanitize_output(output, paranoid=True)
            summary = self.summarize_action(sanitized)
            formatted = self.format_for_telegram(sanitized)

            # Record success
            self.record_execution(True, time.time() - start_time, user_id)

            jarvis_response = self.get_jarvis_response(True, summary)
            return True, jarvis_response, formatted

        except Exception as e:
            logger.error(f"API execution error: {e}")
            self.record_execution(False, time.time() - start_time, user_id)
            self.record_error()

            error_msg = str(e)[:200]
            jarvis_error = self.get_jarvis_response(False, error_msg)
            return False, jarvis_error, f"API error: {e}"

    def _find_claude(self) -> str:
        """Find the Claude CLI executable."""
        import shutil

        if self._env_claude_path:
            env_path = self._env_claude_path
            if os.path.exists(env_path):
                logger.info("Using CLAUDE_CLI_PATH=%s", env_path)
                return env_path
            resolved = shutil.which(env_path)
            if resolved:
                logger.info("Resolved CLAUDE_CLI_PATH via PATH to %s", resolved)
                return resolved
            logger.warning("CLAUDE_CLI_PATH=%s not found; falling back to known locations", env_path)

        for path in self.CLAUDE_PATHS:
            if os.path.exists(path):
                logger.info("Found Claude CLI at %s", path)
                return path

        found = shutil.which("claude")
        if found:
            logger.info("Found Claude CLI via PATH: %s", found)
        return found or "claude"

    def _find_bash(self) -> Optional[str]:
        """Find bash executable for Windows $HOME expansion."""
        import shutil

        # Try common bash locations on Windows
        bash_locations = [
            shutil.which("bash"),  # Git Bash in PATH
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
            r"C:\Git\bin\bash.exe",
        ]

        for bash_path in bash_locations:
            if bash_path and os.path.isfile(bash_path):
                return bash_path
        return None

    def _windows_to_bash_path(self, win_path: str) -> str:
        """Convert Windows path to Git Bash compatible path.

        C:\\Users\\lucid\\... -> /c/Users/lucid/...
        """
        if not win_path or os.name != 'nt':
            return win_path

        # Handle drive letter (C: -> /c)
        if len(win_path) >= 2 and win_path[1] == ':':
            drive = win_path[0].lower()
            rest = win_path[2:]
            # Convert backslashes to forward slashes
            rest = rest.replace('\\', '/')
            return f"/{drive}{rest}"

        # Just convert backslashes if no drive letter
        return win_path.replace('\\', '/')

    def is_admin(self, user_id: int, username: str = None) -> bool:
        """Check if user is authorized for CLI execution.

        Uses strict whitelist - only @matthaynes88.
        """
        if user_id in self.admin_ids:
            return True
        if username and username.lower().lstrip('@') in self.ADMIN_USERNAMES:
            logger.info(f"Admin authorized by username: {username}")
            return True
        logger.warning(f"Unauthorized CLI attempt: user_id={user_id}, username={username}")
        return False

    def check_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        """Check if user has exceeded rate limits.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        now = time.time()
        window_start = now - self.RATE_LIMIT_WINDOW

        # Clean old entries outside window
        self._request_history[user_id] = [
            ts for ts in self._request_history[user_id] if ts > window_start
        ]

        requests_in_window = self._request_history[user_id]

        # Check minimum gap between requests
        if requests_in_window:
            time_since_last = now - requests_in_window[-1]
            if time_since_last < self.RATE_LIMIT_MIN_GAP:
                wait_time = self.RATE_LIMIT_MIN_GAP - time_since_last
                return False, f"slow down. wait {wait_time:.0f}s between requests."

        # Check max requests per window
        if len(requests_in_window) >= self.RATE_LIMIT_MAX_REQUESTS:
            return False, f"rate limit hit. max {self.RATE_LIMIT_MAX_REQUESTS} requests per minute."

        return True, ""

    def record_request(self, user_id: int) -> None:
        """Record a request for rate limiting."""
        self._request_history[user_id].append(time.time())

    def check_circuit_breaker(self) -> Tuple[bool, str]:
        """Check if circuit breaker is tripped.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        now = time.time()

        # Check if circuit breaker is currently tripped
        if self._circuit_breaker_tripped_at:
            time_since_trip = now - self._circuit_breaker_tripped_at
            if time_since_trip < self.CIRCUIT_BREAKER_COOLDOWN:
                remaining = int(self.CIRCUIT_BREAKER_COOLDOWN - time_since_trip)
                minutes = remaining // 60
                seconds = remaining % 60
                return False, f"circuit breaker active. too many errors. cooldown: {minutes}m {seconds}s"
            else:
                # Cooldown expired, reset circuit breaker
                self._circuit_breaker_tripped_at = None
                self._error_timestamps = []
                logger.info("Circuit breaker reset after cooldown")

        # Clean old errors outside window
        window_start = now - self.CIRCUIT_BREAKER_WINDOW
        self._error_timestamps = [ts for ts in self._error_timestamps if ts > window_start]

        return True, ""

    def record_error(self) -> None:
        """Record an error for circuit breaker tracking."""
        now = time.time()
        self._error_timestamps.append(now)

        # Clean old errors
        window_start = now - self.CIRCUIT_BREAKER_WINDOW
        self._error_timestamps = [ts for ts in self._error_timestamps if ts > window_start]

        # Check if we should trip the circuit breaker
        if len(self._error_timestamps) >= self.CIRCUIT_BREAKER_ERROR_THRESHOLD:
            self._circuit_breaker_tripped_at = now
            logger.warning(
                f"Circuit breaker TRIPPED: {len(self._error_timestamps)} errors in "
                f"{self.CIRCUIT_BREAKER_WINDOW}s window. Cooldown: {self.CIRCUIT_BREAKER_COOLDOWN}s"
            )

    def get_circuit_breaker_status(self) -> Dict:
        """Get current circuit breaker status."""
        now = time.time()

        # Clean old errors
        window_start = now - self.CIRCUIT_BREAKER_WINDOW
        recent_errors = [ts for ts in self._error_timestamps if ts > window_start]

        if self._circuit_breaker_tripped_at:
            time_since_trip = now - self._circuit_breaker_tripped_at
            if time_since_trip < self.CIRCUIT_BREAKER_COOLDOWN:
                remaining = int(self.CIRCUIT_BREAKER_COOLDOWN - time_since_trip)
                return {
                    "state": "OPEN",
                    "errors_in_window": len(recent_errors),
                    "threshold": self.CIRCUIT_BREAKER_ERROR_THRESHOLD,
                    "cooldown_remaining": remaining,
                    "tripped_at": datetime.fromtimestamp(self._circuit_breaker_tripped_at).isoformat(),
                }

        return {
            "state": "CLOSED",
            "errors_in_window": len(recent_errors),
            "threshold": self.CIRCUIT_BREAKER_ERROR_THRESHOLD,
            "cooldown_remaining": 0,
            "tripped_at": None,
        }

    def is_transient_error(self, error_msg: str) -> bool:
        """Check if error is likely transient and worth retrying."""
        error_lower = error_msg.lower()
        return any(pattern in error_lower for pattern in self.TRANSIENT_ERROR_PATTERNS)

    def record_execution(self, success: bool, duration: float, user_id: int = 0) -> None:
        """Record execution metrics."""
        self._metrics["total_executions"] += 1
        if success:
            self._metrics["successful_executions"] += 1
        else:
            self._metrics["failed_executions"] += 1
        self._metrics["total_execution_time"] += duration
        self._metrics["last_execution"] = time.time()

        # Keep last 50 executions
        self._metrics["execution_history"].append({
            "timestamp": time.time(),
            "success": success,
            "duration": duration,
            "user_id": user_id,
        })
        if len(self._metrics["execution_history"]) > 50:
            self._metrics["execution_history"] = self._metrics["execution_history"][-50:]

    async def _run_cli_with_retry(
        self,
        cmd: List[str],
        timeout: float = 180.0,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, str]:
        """Run CLI command with retry for transient failures.

        Returns:
            Tuple of (success, stdout, stderr)
        """
        last_error = ""

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    # Exponential backoff
                    delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.info(f"Retry attempt {attempt} after {delay}s delay...")
                    await asyncio.sleep(delay)

                # Set up environment with proper HOME for Windows
                # Claude CLI hooks use $HOME which doesn't expand on Windows
                exec_env = env.copy() if env else os.environ.copy()
                exec_env["HOME"] = os.path.expanduser("~")
                if "USERPROFILE" not in exec_env:
                    exec_env["USERPROFILE"] = os.path.expanduser("~")

                self._active_process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd or self.working_dir,
                    env=exec_env,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        self._active_process.communicate(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    self._active_process.kill()
                    last_error = "timeout"
                    if attempt < self.MAX_RETRIES:
                        continue
                    return False, "", "Command execution timed out."
                finally:
                    self._active_process = None

                stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
                stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

                # Check for transient errors in output
                combined = stdout_str + stderr_str
                if self.is_transient_error(combined) and attempt < self.MAX_RETRIES:
                    last_error = combined[:100]
                    continue

                return True, stdout_str, stderr_str

            except Exception as e:
                error_str = str(e)
                if self.is_transient_error(error_str) and attempt < self.MAX_RETRIES:
                    last_error = error_str[:100]
                    continue
                raise

        # All retries exhausted
        return False, "", f"Failed after {self.MAX_RETRIES} retries. Last error: {last_error}"

    def get_metrics(self) -> Dict:
        """Get execution metrics summary."""
        total = self._metrics["total_executions"]
        if total == 0:
            return {
                "total": 0,
                "success_rate": "N/A",
                "avg_duration": "N/A",
                "last_execution": "Never",
            }

        success_rate = (self._metrics["successful_executions"] / total) * 100
        avg_duration = self._metrics["total_execution_time"] / total

        last_exec = self._metrics["last_execution"]
        if last_exec:
            last_exec_str = datetime.fromtimestamp(last_exec).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_exec_str = "Never"

        return {
            "total": total,
            "successful": self._metrics["successful_executions"],
            "failed": self._metrics["failed_executions"],
            "success_rate": f"{success_rate:.1f}%",
            "avg_duration": f"{avg_duration:.1f}s",
            "last_execution": last_exec_str,
        }

    def get_queue_status(self) -> Dict:
        """Get current queue status."""
        return {
            "depth": self._queue_depth,
            "max_depth": self._max_queue_depth,
            "pending": list(self._pending_commands),  # Copy to avoid mutation
            "is_locked": self._execution_lock.locked(),
        }

    def _scrub_prompt(self, text: str) -> Tuple[str, List[str]]:
        """Scrub sensitive data before sending prompt to Claude."""
        scrubber = get_scrubber()
        scrubbed, redacted = scrubber.scrub(text or "")
        scrubbed = self.sanitize_output(scrubbed, paranoid=True)
        return scrubbed, list(set(redacted))

    def _should_ignore_path(self, rel_path: str) -> bool:
        rel_path = rel_path.replace("\\", "/")
        parts = rel_path.split("/")
        for part in parts:
            if part.lower() in self.ISOLATION_IGNORE_NAMES:
                return True
        filename = parts[-1] if parts else rel_path
        filename_lower = filename.lower()
        if filename_lower in self.ISOLATION_IGNORE_NAMES:
            return True
        for pattern in self.ISOLATION_IGNORE_GLOBS:
            if fnmatch.fnmatch(filename_lower, pattern):
                return True
        return False

    def _collect_file_stats(self, root_dir: str) -> Dict[str, Tuple[float, int]]:
        stats: Dict[str, Tuple[float, int]] = {}
        for base, _, files in os.walk(root_dir):
            for name in files:
                path = os.path.join(base, name)
                rel = os.path.relpath(path, root_dir)
                if self._should_ignore_path(rel):
                    continue
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                stats[rel] = (st.st_mtime, st.st_size)
        return stats

    def _build_copy_ignore(self):
        patterns = [p.lower() for p in self.ISOLATION_IGNORE_GLOBS]

        def _ignore(_path: str, names: List[str]):
            ignored = set()
            for name in names:
                name_lower = name.lower()
                if name_lower in self.ISOLATION_IGNORE_NAMES:
                    ignored.add(name)
                    continue
                for pattern in patterns:
                    if fnmatch.fnmatch(name_lower, pattern):
                        ignored.add(name)
                        break
            return ignored

        return _ignore

    def _copy_workspace(self, src_root: str, dst_root: str) -> None:
        for root, dirs, files in os.walk(src_root):
            rel_root = os.path.relpath(root, src_root)
            if rel_root == ".":
                rel_root = ""

            if rel_root and self._should_ignore_path(rel_root):
                dirs[:] = []
                continue

            filtered_dirs = []
            for d in dirs:
                d_base = d.split(".", 1)[0].lower()
                if d_base in self.WINDOWS_RESERVED_NAMES:
                    continue
                if self._should_ignore_path(os.path.join(rel_root, d)):
                    continue
                filtered_dirs.append(d)
            dirs[:] = filtered_dirs

            dst_dir = os.path.join(dst_root, rel_root) if rel_root else dst_root
            os.makedirs(dst_dir, exist_ok=True)

            for name in files:
                name_base = name.split(".", 1)[0].lower()
                if name_base in self.WINDOWS_RESERVED_NAMES:
                    continue
                rel_path = os.path.join(rel_root, name) if rel_root else name
                if self._should_ignore_path(rel_path):
                    continue
                src_path = os.path.join(root, name)
                dst_path = os.path.join(dst_root, rel_path)
                try:
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                except OSError as e:
                    logger.warning(f"Skipped copy for {rel_path}: {e}")

    def _prepare_isolated_workspace(self) -> Tuple[tempfile.TemporaryDirectory, str, Dict[str, Tuple[float, int]]]:
        temp_dir = tempfile.TemporaryDirectory(prefix="jarvis_claude_")
        sandbox_root = os.path.join(temp_dir.name, "workspace")
        try:
            self._copy_workspace(self.working_dir, sandbox_root)
            before_stats = self._collect_file_stats(sandbox_root)
            return temp_dir, sandbox_root, before_stats
        except Exception:
            temp_dir.cleanup()
            raise

    def _files_equal(self, path_a: str, path_b: str) -> bool:
        try:
            if os.path.getsize(path_a) != os.path.getsize(path_b):
                return False
            with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
                while True:
                    chunk_a = fa.read(8192)
                    chunk_b = fb.read(8192)
                    if chunk_a != chunk_b:
                        return False
                    if not chunk_a:
                        return True
        except OSError:
            return False

    def _apply_sandbox_changes(
        self,
        sandbox_root: str,
        before_stats: Dict[str, Tuple[float, int]]
    ) -> Dict[str, List[str]]:
        after_stats = self._collect_file_stats(sandbox_root)
        added = sorted(rel for rel in after_stats if rel not in before_stats)
        removed = sorted(rel for rel in before_stats if rel not in after_stats)

        changed_candidates = [
            rel for rel in after_stats
            if rel in before_stats and after_stats[rel] != before_stats[rel]
        ]
        changed: List[str] = []

        for rel in changed_candidates:
            src = os.path.join(sandbox_root, rel)
            dst = os.path.join(self.working_dir, rel)
            if not os.path.exists(dst):
                added.append(rel)
                continue
            if not self._files_equal(src, dst):
                changed.append(rel)

        def is_safe(rel_path: str) -> bool:
            if rel_path.startswith("..") or os.path.isabs(rel_path):
                return False
            base = os.path.abspath(self.working_dir)
            target = os.path.abspath(os.path.join(base, rel_path))
            return os.path.commonpath([base, target]) == base

        for rel in added + changed:
            if not is_safe(rel):
                continue
            src = os.path.join(sandbox_root, rel)
            dst = os.path.join(self.working_dir, rel)
            dst_dir = os.path.dirname(dst)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                logger.warning(f"Failed to apply change for {rel}: {e}")

        for rel in removed:
            if not is_safe(rel):
                continue
            dst = os.path.join(self.working_dir, rel)
            try:
                if os.path.isfile(dst):
                    os.remove(dst)
            except OSError as e:
                logger.warning(f"Failed to remove {rel}: {e}")

        return {
            "added": sorted(set(added)),
            "changed": sorted(set(changed)),
            "removed": sorted(set(removed)),
        }

    def _build_sandbox_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        for key in list(env.keys()):
            key_upper = key.upper()
            if key_upper in self.SANDBOX_ENV_ALLOWLIST:
                continue
            if any(token in key_upper for token in self.SANDBOX_ENV_BLOCKLIST):
                env.pop(key, None)
        env["HOME"] = os.path.expanduser("~")
        if "USERPROFILE" not in env:
            env["USERPROFILE"] = os.path.expanduser("~")
        env["JARVIS_SANDBOX"] = "1"
        return env

    def sanitize_output(self, text: str, paranoid: bool = True) -> str:
        """Remove ALL sensitive information from output.

        Triple-pass scrubbing:
        1. Known secret patterns
        2. Claude output cleanup
        3. Paranoid mode (catch anything that looks secret-ish)
        """
        if not text:
            return text

        sanitized = text

        # Pass 1: Apply known secret patterns
        for pattern, replacement in SECRET_PATTERNS:
            try:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Regex error in pattern: {e}")

        # Pass 2: Claude output cleanup (MULTILINE for ^ and $ anchors)
        for pattern, replacement in CLAUDE_OUTPUT_PATTERNS:
            try:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.MULTILINE)
            except re.error:
                pass

        # Pass 3: Paranoid mode - catch anything that looks like a secret
        if paranoid:
            for pattern, replacement in PARANOID_PATTERNS:
                try:
                    sanitized = re.sub(pattern, replacement, sanitized)
                except re.error:
                    pass

        # Final safety: scan for any remaining env-var-like patterns
        sanitized = re.sub(
            r'([A-Z_]{3,}_(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL))\s*=\s*[^\s]{8,}',
            r'\1=[REDACTED]',
            sanitized
        )

        return sanitized

    def get_jarvis_confirmation(self) -> str:
        """Get a random JARVIS-style confirmation message."""
        import random
        return random.choice(JARVIS_CONFIRMATIONS)

    def get_jarvis_response(self, success: bool, summary: str) -> str:
        """Format response in JARVIS voice."""
        import random
        if success:
            template = random.choice(JARVIS_SUCCESS_RESPONSES)
            return template.format(summary=summary.lower().strip('.'))
        else:
            template = random.choice(JARVIS_ERROR_RESPONSES)
            return template.format(error=summary.lower().strip('.'))

    def get_conversation_context(self, user_id: int, current_request: str = "", limit: int = 10) -> str:
        """Get enhanced conversation context for better CLI execution.

        Uses the bridge's enhanced context builder which includes:
        - Recent conversation
        - Relevant learnings from past sessions
        - User preferences
        - Standing instructions
        """
        if not self._bridge:
            return ""

        try:
            # Use enhanced context builder if available
            if hasattr(self._bridge.memory, 'build_enhanced_context'):
                return self._bridge.memory.build_enhanced_context(user_id, current_request)

            # Fallback to basic context
            context = self._bridge.memory.get_recent_context(user_id, limit=limit)
            if not context:
                return ""

            # Format context for Claude CLI
            context_lines = []
            for msg in context[-limit:]:
                role = msg.get('role', 'user')
                content = msg.get('content', '')[:300]
                context_lines.append(f"[{role}]: {content}")

            return "\n".join(context_lines)
        except Exception as e:
            logger.warning(f"Failed to get context: {e}")
            return ""
    
    def format_for_telegram(self, text: str) -> str:
        """Format output for Telegram display."""
        # Truncate if too long
        max_len = 3800  # Leave room for formatting
        if len(text) > max_len:
            text = text[:max_len] + "\n\n[... truncated ...]"
        
        # Escape HTML entities
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        return text
    
    def summarize_action(self, full_output: str) -> str:
        """Create a human-readable summary of what was done."""
        summary_lines = []
        
        # Look for common action patterns in output
        patterns = [
            (r'(?:created?|wrote?|added?)\s+(?:file\s+)?["`]?([^"`\n]+)["`]?', 'Created'),
            (r'(?:edited?|modified?|updated?|changed?)\s+["`]?([^"`\n]+)["`]?', 'Modified'),
            (r'(?:deleted?|removed?)\s+["`]?([^"`\n]+)["`]?', 'Deleted'),
            (r'(?:installed?|added? dependency)\s+["`]?([^"`\n]+)["`]?', 'Installed'),
            (r'(?:ran|executed?|running)\s+["`]?([^"`\n]+)["`]?', 'Ran'),
            (r'(?:fixed?|resolved?)\s+(?:bug|issue|error)?\s*["`]?([^"`\n]*)["`]?', 'Fixed'),
        ]
        
        output_lower = full_output.lower()
        
        for pattern, action in patterns:
            matches = re.findall(pattern, output_lower, re.IGNORECASE)
            for match in matches[:3]:  # Limit to 3 per action type
                if match and len(match) < 100:
                    summary_lines.append(f"• {action}: {match.strip()}")
        
        # Look for success/completion indicators
        if 'success' in output_lower or 'complete' in output_lower or 'done' in output_lower:
            summary_lines.append("✅ Completed successfully")
        elif 'error' in output_lower or 'failed' in output_lower:
            summary_lines.append("⚠️ Encountered errors - check details")
        
        if not summary_lines:
            summary_lines.append("• Task processed")
        
        return "\n".join(summary_lines[:10])  # Max 10 lines
    
    async def execute(
        self,
        prompt: str,
        user_id: int,
        username: str = None,
        send_update: callable = None,
        include_context: bool = True
    ) -> Tuple[bool, str, str]:
        """
        Execute a coding command via Claude CLI.

        Args:
            prompt: The coding request
            user_id: Telegram user ID
            username: Telegram username for backup auth check
            send_update: Async callback to send updates to Telegram
            include_context: Whether to include conversation history

        Returns:
            Tuple of (success, jarvis_summary, full_output)
        """
        if not self.is_admin(user_id, username):
            logger.warning(f"Unauthorized Claude CLI attempt by user {user_id} ({username})")
            return False, "access denied. admin only.", "Access denied. Admin only."

        # Check circuit breaker FIRST (before rate limits)
        cb_allowed, cb_msg = self.check_circuit_breaker()
        if not cb_allowed:
            logger.warning(f"Circuit breaker blocked request from user {user_id}: {cb_msg}")
            return False, cb_msg, "Circuit breaker active."

        # Check rate limits
        allowed, rate_msg = self.check_rate_limit(user_id)
        if not allowed:
            logger.info(f"Rate limited user {user_id}: {rate_msg}")
            return False, rate_msg, "Rate limited."

        # Check queue depth
        if self._queue_depth >= self._max_queue_depth:
            logger.info(f"Queue full ({self._queue_depth}/{self._max_queue_depth})")
            return False, "queue full. try again in a moment.", "Command queue full."

        # Record this request
        self.record_request(user_id)

        # Track execution time
        start_time = time.time()

        # Add to pending queue
        scrubbed_preview, _ = self._scrub_prompt(prompt)
        pending_entry = {
            "user_id": user_id,
            "prompt_preview": scrubbed_preview[:50] + "..." if len(scrubbed_preview) > 50 else scrubbed_preview,
            "queued_at": datetime.now().isoformat(),
        }
        self._pending_commands.append(pending_entry)
        self._queue_depth += 1

        # Acquire execution lock (serialize CLI calls)
        async with self._execution_lock:
            try:

                # Send JARVIS-style confirmation
                if send_update:
                    jarvis_confirm = self.get_jarvis_confirmation()
                    await send_update(f"🤖 {jarvis_confirm}")

                # Build enhanced prompt with context (includes learnings & preferences)
                scrubbed_prompt, redacted = self._scrub_prompt(prompt)
                enhanced_prompt = scrubbed_prompt
                logger.info(f"Executing request for admin {user_id}: {scrubbed_prompt[:100]}...")

                # ============ CLI MODE (PRIMARY) ============
                # Uses the Claude CLI that governs this instance
                logger.info(f"Using CLI mode at: {self._claude_path}")

                if include_context and self._bridge:
                    context = self.get_conversation_context(user_id, current_request=prompt, limit=5)
                    if context:
                        scrubbed_context, context_redacted = self._scrub_prompt(context)
                        redacted.extend(context_redacted)
                        enhanced_prompt = f"""## Context
{scrubbed_context}

## Current Request
{scrubbed_prompt}

Execute this request. Be concise in your response. Follow any standing instructions."""

                if redacted:
                    logger.info(f"Scrubbed {len(set(redacted))} sensitive items before Claude CLI")

                # Build the claude command
                logger.info(f"Using Claude CLI at: {self._claude_path}")

                # On Windows, use bash (Git Bash) to properly expand $HOME in hook commands
                # CMD.exe doesn't expand $HOME, causing hook paths to fail
                bash_path = self._find_bash() if os.name == 'nt' else None

                # NOTE: --dangerously-skip-permissions is blocked on Linux when running as root
                # Only use it on Windows where it works reliably
                skip_perms_flag = "--dangerously-skip-permissions" if os.name == 'nt' else ""

                if bash_path:
                    # Run through bash to properly expand $HOME in hook commands
                    # Convert Windows path to bash-compatible format
                    bash_claude_path = self._windows_to_bash_path(self._claude_path)
                    # Escape the prompt for bash (single quotes with escaped single quotes)
                    escaped_prompt = enhanced_prompt.replace("'", "'\\''")
                    cmd = [
                        bash_path,
                        "-c",
                        f"'{bash_claude_path}' --print {skip_perms_flag} '{escaped_prompt}'"
                    ]
                    logger.info(f"Using Git Bash for $HOME expansion, claude path: {bash_claude_path}")
                else:
                    cmd = [
                        self._claude_path,
                        "--print",  # Non-interactive, print output
                        enhanced_prompt
                    ]
                    # Only add dangerous flag on Windows (blocked on Linux root)
                    if os.name == 'nt':
                        cmd.insert(2, "--dangerously-skip-permissions")

                # Execute in isolated workspace
                sandbox_dir = None
                sandbox_root = None
                before_stats: Dict[str, Tuple[float, int]] = {}
                try:
                    sandbox_dir, sandbox_root, before_stats = self._prepare_isolated_workspace()
                except Exception as e:
                    self.record_execution(False, time.time() - start_time, user_id)
                    self.record_error()  # Circuit breaker tracking
                    jarvis_error = self.get_jarvis_response(False, "sandbox setup failed")
                    return False, jarvis_error, f"Sandbox setup failed: {e}"

                apply_error = None
                try:
                    sandbox_env = self._build_sandbox_env()
                    cli_success, stdout_str, stderr_str = await self._run_cli_with_retry(
                        cmd,
                        timeout=180.0,
                        cwd=sandbox_root,
                        env=sandbox_env,
                    )
                finally:
                    try:
                        if sandbox_root:
                            self._apply_sandbox_changes(sandbox_root, before_stats)
                    except Exception as e:
                        apply_error = str(e)
                        logger.error(f"Failed to apply sandbox changes: {e}")
                    if sandbox_dir:
                        sandbox_dir.cleanup()

                if apply_error:
                    self.record_execution(False, time.time() - start_time, user_id)
                    self.record_error()  # Circuit breaker tracking
                    jarvis_error = self.get_jarvis_response(False, "failed to apply changes")
                    return False, jarvis_error, f"Apply changes failed: {apply_error}"

                if not cli_success:
                    self.record_execution(False, time.time() - start_time, user_id)
                    self.record_error()  # Circuit breaker tracking
                    error_output = stderr_str or "Command execution failed."
                    sanitized_error = self.sanitize_output(error_output, paranoid=True)
                    summary_error = sanitized_error[:200] if sanitized_error else "execution failed"
                    jarvis_error = self.get_jarvis_response(False, summary_error)
                    return False, jarvis_error, sanitized_error

                # Combine output
                output = stdout_str
                if stderr_str:
                    if output:
                        output += "\n"
                    output += stderr_str

                # Triple-sanitize (paranoid mode)
                sanitized = self.sanitize_output(output, paranoid=True)

                # Generate summary
                summary = self.summarize_action(sanitized)

                # Format for Telegram
                formatted = self.format_for_telegram(sanitized)

                # Determine success
                success = self._active_process is None

                # Store in memory for context and extract learnings
                if self._bridge:
                    try:
                        # Store the result
                        self._bridge.memory.add_message(
                            user_id,
                            username or "admin",
                            "assistant",
                            f"[CLI Result] {summary}"
                        )

                        # Extract learnings from successful results
                        if success and hasattr(self._bridge.memory, 'extract_learnings_from_result'):
                            self._bridge.memory.extract_learnings_from_result(
                                sanitized,
                                topic="coding"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to store in memory: {e}")

                # Format JARVIS response
                jarvis_summary = self.get_jarvis_response(success, summary)

                # Record execution metrics
                self.record_execution(success, time.time() - start_time, user_id)

                return success, jarvis_summary, formatted

            except FileNotFoundError:
                logger.error(f"Claude CLI not found at: {self._claude_path}")
                self.record_execution(False, time.time() - start_time, user_id)
                self.record_error()  # Circuit breaker tracking
                return False, "Claude CLI not found", f"Tried: {self._claude_path}. Install via: npm install -g @anthropic-ai/claude-code"
            except Exception as e:
                logger.error(f"Claude CLI execution error: {e}")
                self.record_execution(False, time.time() - start_time, user_id)
                self.record_error()  # Circuit breaker tracking
                return False, f"Error: {str(e)[:100]}", str(e)
            finally:
                # Clean up queue tracking
                self._queue_depth = max(0, self._queue_depth - 1)
                if pending_entry in self._pending_commands:
                    self._pending_commands.remove(pending_entry)

    def cancel(self):
        """Cancel any active execution."""
        if self._active_process:
            self._active_process.kill()
            logger.info("Cancelled active Claude CLI process")


# Singleton instance
_handler: Optional[ClaudeCLIHandler] = None


def get_claude_cli_handler() -> ClaudeCLIHandler:
    """Get the singleton ClaudeCLIHandler instance."""
    global _handler
    if _handler is None:
        admin_ids = []
        try:
            from tg_bot.config import get_config
            admin_ids = list(get_config().admin_ids)
        except Exception:
            admin_ids = []
        _handler = ClaudeCLIHandler(admin_user_ids=admin_ids)
    return _handler
