"""
X/Twitter Claude CLI Handler for Admin Coding Commands.

Monitors mentions from the SOLE authorized admin account (@matthaynes88)
and executes coding requests via Claude CLI.

Flow:
1. Monitor mentions of @Jarvis_lifeos from @matthaynes88 ONLY
2. Detect coding requests
3. Reply with JARVIS-style confirmation
4. Execute via Claude CLI with context
5. Reply with cleansed, JARVIS-voiced result

Security:
- ONLY @matthaynes88 can interact (ALL other users are silently ignored)
- No responses to any non-admin - coding OR questions
- Triple-pass output sanitization (paranoid mode)
- No sensitive data ever exposed
- Rate limiting to prevent abuse
"""

import asyncio
import fnmatch
import json
import logging
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

# State file for circuit breaker persistence - centralized under ~/.lifeos/
from core.state_paths import STATE_PATHS
CIRCUIT_BREAKER_STATE = STATE_PATHS.circuit_breaker_state

from core.security.scrubber import get_scrubber

logger = logging.getLogger(__name__)

# STRICT Admin whitelist - ONLY this user can interact with JARVIS on X
# All CLI commands AND question responses are restricted to this account
ADMIN_USERNAMES: Set[str] = {
    "matthaynes88",  # ONLY authorized account - no one else
}

# JARVIS voice templates (from brand bible)
JARVIS_CONFIRMATIONS = [
    "on it. give me a sec...",
    "processing through my chrome skull...",
    "running this through my circuits...",
    "sensors locked on. executing...",
    "neural weights engaged. working...",
]

JARVIS_SUCCESS_TEMPLATES = [
    "@{author} done. {summary}",
    "@{author} sorted. {summary}",
    "@{author} finished. {summary}",
    "@{author} task complete. {summary}",
]

JARVIS_ERROR_TEMPLATES = [
    "@{author} hit a snag. will retry later.",
    "@{author} my circuits need recalibrating. check telegram for details.",
    "@{author} something went sideways. details in telegram.",
]

# Coding keywords to detect requests
CODING_KEYWORDS = [
    "fix", "add", "create", "build", "implement", "change",
    "update", "modify", "refactor", "debug", "test", "deploy",
    "code", "function", "class", "api", "endpoint", "command",
    "feature", "bug", "error", "issue", "make", "write",
    "ralph wiggum", "cascade", "vibe code", "console", "cli"
]

# COMPREHENSIVE secret patterns - PARANOID MODE (same as Telegram handler)
SECRET_PATTERNS = [
    # API Keys
    (r'sk-ant-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'xai-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'sk-[a-zA-Z0-9\-_]{20,}', '[REDACTED]'),
    (r'[A-Z_]+_API_KEY[=:]\s*[\'"]?[^\s\'"]+', '*_API_KEY=[REDACTED]'),

    # Telegram tokens
    (r'[0-9]{8,10}:[A-Za-z0-9_-]{35,}', '[REDACTED]'),
    (r'TELEGRAM_[A-Z_]+[=:]\s*[\'"]?[^\s\'"]+', 'TELEGRAM_*=[REDACTED]'),

    # Twitter/X
    (r'TWITTER_[A-Z_]+[=:]\s*[\'"]?[^\s\'"]+', 'TWITTER_*=[REDACTED]'),
    (r'AAAA[A-Za-z0-9%_-]{30,}', '[REDACTED]'),

    # Solana/Crypto
    (r'[1-9A-HJ-NP-Za-km-z]{87,88}', '[REDACTED]'),  # Private keys
    (r'(private_key|secret_key|mnemonic)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),

    # Database
    (r'postgresql://[^\s\'"]+', '[REDACTED_DB]'),
    (r'mongodb(\+srv)?://[^\s\'"]+', '[REDACTED_DB]'),
    (r'redis://[^\s\'"]+', '[REDACTED_DB]'),
    (r'DATABASE_URL[=:]\s*[\'"]?[^\s\'"]+', 'DATABASE_URL=[REDACTED]'),

    # GitHub
    (r'ghp_[a-zA-Z0-9]{30,}', '[REDACTED]'),
    (r'gho_[a-zA-Z0-9]{30,}', '[REDACTED]'),
    (r'github_pat_[a-zA-Z0-9_]+', '[REDACTED]'),

    # Generic secrets
    (r'(PASSWORD|SECRET|KEY|TOKEN|CREDENTIAL)[=:]\s*[\'"]?[^\s\'"]{8,}', r'\1=[REDACTED]'),

    # Hex secrets
    (r'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])', '[REDACTED]'),
    (r'(?<![a-f0-9])[a-f0-9]{32}(?![a-f0-9])', '[REDACTED]'),

    # JWT
    (r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED]'),

    # User paths (replacement uses raw string to avoid \U escape)
    (r'C:\\Users\\[^\\]+\\', r'C:\\Users\\***\\'),
    (r'/home/[^/]+/', '/home/***/'),

    # Env files
    (r'\.env[a-z.]*', '.env[HIDDEN]'),
    (r'secrets/[^\s]+', 'secrets/[HIDDEN]'),
]

# Additional paranoid patterns for final pass
PARANOID_PATTERNS = [
    (r'(?<![A-Za-z0-9/\\])[A-Za-z0-9+/]{40,}(?![A-Za-z0-9/\\])', '[REDACTED]'),
    (r'(?<![A-Za-z0-9])[A-Za-z0-9+/]{20,}={1,2}(?![A-Za-z0-9])', '[REDACTED]'),
]


@dataclass
class PendingCommand:
    """A coding command pending confirmation."""
    tweet_id: str
    author_username: str
    command_text: str
    created_at: datetime
    confirmed: bool = False
    executed: bool = False
    result: Optional[str] = None


@dataclass
class XClaudeCLIState:
    """Runtime state for the handler."""
    last_mention_id: Optional[str] = None
    pending_commands: Dict[str, PendingCommand] = field(default_factory=dict)
    last_check_time: float = 0
    commands_executed_today: int = 0
    last_reset_date: Optional[str] = None

    def reset_daily(self):
        """Reset daily counters."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_reset_date != today:
            self.commands_executed_today = 0
            self.last_reset_date = today


class XBotCircuitBreaker:
    """Circuit breaker to prevent X bot spam loops.

    After MAX_CONSECUTIVE_ERRORS, enters cooldown for COOLDOWN_DURATION seconds.
    Also enforces MIN_POST_INTERVAL between posts.

    State is persisted to survive restarts.
    """
    _last_post: Optional[datetime] = None
    _error_count: int = 0
    _cooldown_until: Optional[datetime] = None
    _success_count: int = 0
    _initialized: bool = False

    MIN_POST_INTERVAL = 60  # seconds between posts
    MAX_CONSECUTIVE_ERRORS = 3
    COOLDOWN_DURATION = 1800  # 30 minutes cooldown after errors

    @classmethod
    def _load_state(cls):
        """Load persisted state from file."""
        if cls._initialized:
            return
        cls._initialized = True

        try:
            if CIRCUIT_BREAKER_STATE.exists():
                data = json.loads(CIRCUIT_BREAKER_STATE.read_text())
                if data.get("last_post"):
                    cls._last_post = datetime.fromisoformat(data["last_post"])
                    # Only respect if within last hour
                    if (datetime.now() - cls._last_post).total_seconds() > 3600:
                        cls._last_post = None
                if data.get("cooldown_until"):
                    cooldown = datetime.fromisoformat(data["cooldown_until"])
                    if cooldown > datetime.now():
                        cls._cooldown_until = cooldown
                cls._error_count = data.get("error_count", 0)
                cls._success_count = data.get("success_count", 0)
                logger.info(f"XBotCircuitBreaker: Loaded state - last_post={cls._last_post}, errors={cls._error_count}")
            else:
                # No state file = first run, set last_post to now to prevent immediate spam
                cls._last_post = datetime.now()
                logger.info("XBotCircuitBreaker: No state file, initialized with cooldown")
        except Exception as e:
            logger.warning(f"XBotCircuitBreaker: Failed to load state: {e}")
            cls._last_post = datetime.now()  # Safe default

    @classmethod
    def _save_state(cls):
        """Save state to file."""
        try:
            CIRCUIT_BREAKER_STATE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_post": cls._last_post.isoformat() if cls._last_post else None,
                "cooldown_until": cls._cooldown_until.isoformat() if cls._cooldown_until else None,
                "error_count": cls._error_count,
                "success_count": cls._success_count,
                "saved_at": datetime.now().isoformat()
            }
            CIRCUIT_BREAKER_STATE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"XBotCircuitBreaker: Failed to save state: {e}")

    @classmethod
    def can_post(cls) -> tuple[bool, str]:
        """Check if posting is allowed."""
        cls._load_state()  # Ensure state is loaded

        # Kill switch check
        if os.getenv("X_BOT_ENABLED", "true").lower() == "false":
            return False, "X_BOT_ENABLED=false"

        # Cooldown check
        if cls._cooldown_until and datetime.now() < cls._cooldown_until:
            remaining = (cls._cooldown_until - datetime.now()).seconds
            return False, f"Circuit breaker cooldown ({remaining}s remaining)"

        # Rate limit check
        if cls._last_post:
            elapsed = (datetime.now() - cls._last_post).total_seconds()
            if elapsed < cls.MIN_POST_INTERVAL:
                return False, f"Rate limit ({cls.MIN_POST_INTERVAL - elapsed:.0f}s until next post)"

        return True, "OK"

    @classmethod
    def record_success(cls):
        """Record a successful post."""
        cls._load_state()  # Ensure state is loaded
        cls._last_post = datetime.now()
        cls._error_count = 0
        cls._success_count += 1
        cls._save_state()  # Persist state
        logger.debug(f"XBotCircuitBreaker: success #{cls._success_count}")

    @classmethod
    def record_error(cls):
        """Record an error. Triggers cooldown after MAX_CONSECUTIVE_ERRORS."""
        cls._load_state()  # Ensure state is loaded
        cls._error_count += 1
        logger.warning(f"XBotCircuitBreaker: error #{cls._error_count}/{cls.MAX_CONSECUTIVE_ERRORS}")

        if cls._error_count >= cls.MAX_CONSECUTIVE_ERRORS:
            cls._cooldown_until = datetime.now() + timedelta(seconds=cls.COOLDOWN_DURATION)
            cls._error_count = 0
            logger.error(f"XBotCircuitBreaker: COOLDOWN ACTIVATED for {cls.COOLDOWN_DURATION}s")

        cls._save_state()  # Persist state

    @classmethod
    def reset(cls):
        """Reset the circuit breaker (for testing)."""
        cls._last_post = None
        cls._error_count = 0
        cls._cooldown_until = None
        cls._success_count = 0
        cls._save_state()

    @classmethod
    def status(cls) -> dict:
        """Get circuit breaker status."""
        cls._load_state()  # Ensure state is loaded
        can_post, reason = cls.can_post()
        return {
            "can_post": can_post,
            "reason": reason,
            "error_count": cls._error_count,
            "success_count": cls._success_count,
            "cooldown_until": cls._cooldown_until.isoformat() if cls._cooldown_until else None,
            "last_post": cls._last_post.isoformat() if cls._last_post else None,
        }


class XClaudeCLIHandler:
    """Handler for X/Twitter coding commands via Claude CLI."""

    MAX_COMMANDS_PER_DAY = 50
    CHECK_INTERVAL_SECONDS = 30
    COMMAND_TIMEOUT_SECONDS = 300  # 5 minutes

    # Rate limiting configuration
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_REQUESTS = 5  # max requests per window
    RATE_LIMIT_MIN_GAP = 10  # minimum seconds between requests (X is slower)

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
        # Windows reserved device names - must be ignored to prevent WinError 87
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

    # Windows reserved names that should never be accessed
    WINDOWS_RESERVED_NAMES = {
        "nul", "con", "prn", "aux",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
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
        "tmpclaude-*",  # Claude temporary directories
        "tmpclaude-*-cwd",
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

    def __init__(self):
        self.state = XClaudeCLIState()
        self._twitter_client = None
        self._jarvis_voice = None
        self._running = False
        self.working_dir = os.environ.get(
            "JARVIS_WORKING_DIR",
            r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
        )
        # Rate limiting tracker: username -> list of request timestamps
        self._request_history: Dict[str, List[float]] = defaultdict(list)

        # Execution metrics
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "last_execution": None,
            "execution_history": [],  # Last 50 executions
        }

    async def _get_jarvis_voice(self):
        """Get Jarvis voice generator."""
        if self._jarvis_voice is None:
            from bots.twitter.jarvis_voice import get_jarvis_voice
            self._jarvis_voice = get_jarvis_voice()
        return self._jarvis_voice
    
    async def _get_twitter(self):
        """Get Twitter client."""
        if self._twitter_client is None:
            from bots.twitter.twitter_client import TwitterClient
            self._twitter_client = TwitterClient()
            self._twitter_client.connect()
        return self._twitter_client
    
    def is_admin(self, username: str) -> bool:
        """Check if username is authorized admin.

        STRICT: ONLY @matthaynes88 can interact with JARVIS on X.
        All other users are silently ignored - no CLI, no questions, nothing.
        """
        if not username:
            logger.warning("CLI attempt with no username")
            return False
        clean_username = username.lower().strip().lstrip('@')
        is_authorized = clean_username in ADMIN_USERNAMES
        if not is_authorized:
            logger.warning(f"Unauthorized X CLI attempt by @{clean_username}")
        return is_authorized

    def check_rate_limit(self, username: str) -> tuple[bool, str]:
        """Check if user has exceeded rate limits.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        if not username:
            return True, ""

        clean_username = username.lower().strip().lstrip('@')
        now = time.time()
        window_start = now - self.RATE_LIMIT_WINDOW

        # Clean old entries outside window
        self._request_history[clean_username] = [
            ts for ts in self._request_history[clean_username] if ts > window_start
        ]

        requests_in_window = self._request_history[clean_username]

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

    def record_request(self, username: str) -> None:
        """Record a request for rate limiting."""
        if username:
            clean_username = username.lower().strip().lstrip('@')
            self._request_history[clean_username].append(time.time())

    def record_execution(self, success: bool, duration: float, username: str = "") -> None:
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
            "username": username,
        })
        if len(self._metrics["execution_history"]) > 50:
            self._metrics["execution_history"] = self._metrics["execution_history"][-50:]

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

    def _is_windows_reserved_name(self, name: str) -> bool:
        """Check if a filename is a Windows reserved device name."""
        # Get the base name without extension
        base = name.split('.')[0].lower() if '.' in name else name.lower()
        return base in self.WINDOWS_RESERVED_NAMES

    def _safe_copy_tree(self, src: str, dst: str, ignore) -> List[str]:
        """Copy directory tree with Windows-safe error handling.

        Returns list of errors encountered (but continues copying).
        """
        errors = []

        # Create destination directory
        os.makedirs(dst, exist_ok=True)

        try:
            names = os.listdir(src)
        except OSError as e:
            errors.append(f"Cannot list {src}: {e}")
            return errors

        # Get names to ignore
        ignored_names = ignore(src, names)

        for name in names:
            # Skip ignored names
            if name in ignored_names:
                continue

            # Skip Windows reserved names explicitly
            if self._is_windows_reserved_name(name):
                continue

            src_path = os.path.join(src, name)
            dst_path = os.path.join(dst, name)

            try:
                # Check if it's a directory or file
                if os.path.isdir(src_path):
                    # Recursively copy directory
                    sub_errors = self._safe_copy_tree(src_path, dst_path, ignore)
                    errors.extend(sub_errors)
                else:
                    # Copy file
                    try:
                        shutil.copy2(src_path, dst_path)
                    except OSError as e:
                        errors.append(f"Cannot copy {src_path}: {e}")
            except OSError as e:
                # Handle any access errors (including Windows device name errors)
                errors.append(f"Cannot access {src_path}: {e}")

        return errors

    def _prepare_isolated_workspace(self) -> Tuple[tempfile.TemporaryDirectory, str, Dict[str, Tuple[float, int]]]:
        temp_dir = tempfile.TemporaryDirectory(prefix="jarvis_claude_")
        sandbox_root = os.path.join(temp_dir.name, "workspace")
        ignore = self._build_copy_ignore()
        try:
            # Use custom safe copy that handles Windows reserved names
            errors = self._safe_copy_tree(self.working_dir, sandbox_root, ignore)
            if errors:
                logger.warning(f"Sandbox copy had {len(errors)} non-fatal errors")
                for err in errors[:5]:  # Log first 5
                    logger.debug(f"  {err}")
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

    def is_coding_request(self, text: str) -> bool:
        """Detect if text is a coding request."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in CODING_KEYWORDS)

    def sanitize_output(self, text: str, paranoid: bool = True) -> str:
        """Remove ALL sensitive info from output.

        Triple-pass scrubbing with paranoid mode.
        """
        if not text:
            return text

        sanitized = text

        # Pass 1: Known secret patterns
        for pattern, replacement in SECRET_PATTERNS:
            try:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            except re.error:
                pass

        # Pass 2: Claude output cleanup
        sanitized = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', sanitized)  # ANSI codes
        sanitized = re.sub(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', '', sanitized)  # Spinners
        sanitized = sanitized.replace(
            r'c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\\',
            ''
        )

        # Pass 3: Paranoid mode
        if paranoid:
            for pattern, replacement in PARANOID_PATTERNS:
                try:
                    sanitized = re.sub(pattern, replacement, sanitized)
                except re.error:
                    pass

        # Final safety: env-var patterns
        sanitized = re.sub(
            r'([A-Z_]{3,}_(?:KEY|TOKEN|SECRET|PASSWORD))\s*=\s*[^\s]{8,}',
            r'\1=[REDACTED]',
            sanitized
        )

        return sanitized

    def get_jarvis_confirmation(self, author: str) -> str:
        """Get a JARVIS-style confirmation message."""
        import random
        confirm = random.choice(JARVIS_CONFIRMATIONS)
        return f"@{author} {confirm}"

    def get_jarvis_result(self, author: str, success: bool, summary: str) -> str:
        """Format result in JARVIS voice."""
        import random
        if success:
            template = random.choice(JARVIS_SUCCESS_TEMPLATES)
            return template.format(author=author, summary=summary.lower().strip('.'))
        else:
            # Don't expose error details publicly - just acknowledge the issue
            template = random.choice(JARVIS_ERROR_TEMPLATES)
            return template.format(author=author)
    
    def format_for_tweet(self, text: str, max_len: int = 270) -> str:
        """Format text to fit in a tweet."""
        # Clean up whitespace
        text = ' '.join(text.split())
        
        if len(text) <= max_len:
            return text
        
        return text[:max_len-3] + "..."

    def _format_for_telegram(self, text: str, max_len: int = 3500) -> str:
        """Format text for Telegram (plain text)."""
        if len(text) > max_len:
            return text[:max_len] + "\n\n[truncated]"
        return text

    def _clean_output_for_telegram(self, output: str) -> str:
        """Clean CLI output before sending to Telegram - remove hook errors and internal details."""
        if not output:
            return output

        lines = output.split('\n')
        cleaned_lines = []
        skip_until_blank = False

        for line in lines:
            # Skip hook error blocks
            if 'hook [' in line.lower() and 'failed' in line.lower():
                skip_until_blank = True
                continue
            if 'SessionEnd hook' in line or 'PreToolUse' in line or 'PostToolUse' in line:
                skip_until_blank = True
                continue
            # Skip Node.js stack traces
            if line.strip().startswith('at ') or 'node:internal' in line:
                continue
            if 'MODULE_NOT_FOUND' in line or 'requireStack' in line:
                continue
            if line.strip().startswith('throw err;') or line.strip().startswith('^'):
                continue
            if 'Error: Cannot find module' in line:
                skip_until_blank = True
                continue
            # Skip sandbox temp paths
            if 'jarvis_claude_' in line or 'AppData\\Local\\Temp' in line:
                continue
            # Stop skipping on blank line
            if skip_until_blank and not line.strip():
                skip_until_blank = False
                continue
            if skip_until_blank:
                continue

            cleaned_lines.append(line)

        cleaned = '\n'.join(cleaned_lines).strip()
        # Remove multiple consecutive newlines
        while '\n\n\n' in cleaned:
            cleaned = cleaned.replace('\n\n\n', '\n\n')
        return cleaned if cleaned else "Command executed."

    async def _report_to_telegram(self, message: str) -> bool:
        """Send a report to Telegram if configured."""
        try:
            import aiohttp

            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            target_chat = os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID") or os.environ.get("TELEGRAM_ADMIN_CHAT_ID")

            if not bot_token or not target_chat:
                return False

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": target_chat,
                "text": message,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        return True
                    logger.error(f"Telegram report failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Telegram report error: {e}")
            return False
    
    def summarize_result(self, full_output: str) -> str:
        """Create a brief summary for tweet reply."""
        lines = []
        
        # Look for action patterns
        patterns = [
            (r'(?:created?|wrote?|added?)\s+["`]?([^"`\n]{1,50})["`]?', '✓ Created'),
            (r'(?:edited?|modified?|updated?)\s+["`]?([^"`\n]{1,50})["`]?', '✓ Modified'),
            (r'(?:fixed?|resolved?)\s+["`]?([^"`\n]{1,30})["`]?', '✓ Fixed'),
        ]
        
        output_lower = full_output.lower()
        
        for pattern, prefix in patterns:
            matches = re.findall(pattern, output_lower, re.IGNORECASE)
            for match in matches[:2]:
                if match:
                    lines.append(f"{prefix}: {match.strip()[:30]}")
        
        if 'success' in output_lower or 'complete' in output_lower:
            if not lines:
                lines.append("✅ Task completed")
        elif 'error' in output_lower or 'failed' in output_lower:
            lines.append("⚠️ Encountered issues")
        
        if not lines:
            lines.append("✓ Processed")
        
        return "\n".join(lines[:4])
    
    async def jarvis_response(self, action_summary: str, success: bool, author: str) -> str:
        """Generate a Jarvis-voice response for the coding result.

        Uses brand bible templates, with fallback to LLM generation.
        """
        # First try simple template (faster, cheaper)
        simple_response = self.get_jarvis_result(author, success, action_summary)
        if len(simple_response) <= 270:
            return simple_response

        # For longer summaries, try LLM generation
        try:
            voice = await self._get_jarvis_voice()

            if success:
                prompt = f"""Generate a brief reply to @{author} confirming you completed their coding task.

What was done: {action_summary}

Be casual, lowercase, brief. Like you're texting a friend. 1-2 sentences max.
Examples of good responses:
- "done. pushed the fix to the handler."
- "sorted. added the endpoint, should be live."
- "fixed it. the rate limiter was the issue."

Include @{author} at the start. MUST be under 270 characters."""
            else:
                prompt = f"""Generate a brief reply to @{author} about an issue with their coding task.

Issue: {action_summary}

Be helpful, lowercase, brief. 1-2 sentences max.
Include @{author} at the start. MUST be under 270 characters."""

            response = await voice.generate_tweet(prompt)
            if response:
                # Ensure @mention is at start
                if not response.startswith(f"@{author}"):
                    response = f"@{author} {response}"
                # Ensure under limit
                if len(response) > 270:
                    response = response[:267] + "..."
                return response
        except Exception as e:
            logger.error(f"Jarvis voice error: {e}")

        # Fallback to simple template
        return self.get_jarvis_result(author, success, action_summary[:50])
    
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

    async def execute_command(self, command: str, username: str = "") -> tuple[bool, str, str]:
        """Execute a coding command via Claude CLI."""
        start_time = time.time()

        try:
            scrubbed_command, redacted = self._scrub_prompt(command)
            logger.info(f"Executing Claude CLI: {scrubbed_command[:100]}...")
            if redacted:
                logger.info(f"Scrubbed {len(set(redacted))} sensitive items before Claude CLI")

            sandbox_dir = None
            sandbox_root = None
            before_stats: Dict[str, Tuple[float, int]] = {}
            try:
                sandbox_dir, sandbox_root, before_stats = self._prepare_isolated_workspace()
            except Exception as e:
                self.record_execution(False, time.time() - start_time, username)
                return False, "Sandbox setup failed", f"Sandbox setup failed: {e}"

            # Set up environment with proper HOME for Windows
            # Claude CLI hooks use $HOME which doesn't expand on Windows CMD
            env = self._build_sandbox_env()

            # On Windows, try to use bash (Git Bash) which properly expands $HOME
            # CMD.exe doesn't expand $HOME, causing hook paths to fail
            bash_path = self._find_bash() if os.name == 'nt' else None

            if bash_path:
                # Run through bash to properly expand $HOME in hook commands
                # Escape the command for bash
                escaped_command = scrubbed_command.replace("'", "'\\''")
                cmd = [
                    bash_path,
                    "-c",
                    f"claude --print --dangerously-skip-permissions '{escaped_command}'"
                ]
                logger.info("Using Git Bash for $HOME expansion")
            else:
                cmd = [
                    "claude",
                    "--print",
                    "--dangerously-skip-permissions",
                    scrubbed_command
                ]

            apply_error = None
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=sandbox_root or self.working_dir,
                    env=env,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.COMMAND_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    self.record_execution(False, time.time() - start_time, username)
                    return False, "Timed out", "Command timed out after 5 minutes"
            finally:
                try:
                    if sandbox_root:
                        self._apply_sandbox_changes(sandbox_root, before_stats)
                except Exception as e:
                    apply_error = str(e)
                    logger.error(f"Failed to apply sandbox changes: {e}")
                if sandbox_dir:
                    sandbox_dir.cleanup()

            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += "\n" + stderr.decode('utf-8', errors='replace')

            # Triple-pass sanitization (paranoid mode)
            sanitized = self.sanitize_output(output, paranoid=True)
            summary = self.summarize_result(sanitized)

            if apply_error:
                self.record_execution(False, time.time() - start_time, username)
                return False, "Apply changes failed", f"Apply changes failed: {apply_error}"

            success = process.returncode == 0
            self.record_execution(success, time.time() - start_time, username)
            return success, summary, sanitized

        except FileNotFoundError:
            self.record_execution(False, time.time() - start_time, username)
            return False, "CLI not found", "Claude CLI not installed"
        except Exception as e:
            logger.error(f"CLI execution error: {e}")
            self.record_execution(False, time.time() - start_time, username)
            return False, f"Error: {str(e)[:50]}", str(e)
    
    async def answer_question(self, question: str, author: str) -> Optional[str]:
        """Generate a Jarvis-style answer to a question using Grok/Claude."""
        try:
            voice = await self._get_jarvis_voice()

            # Clean question
            clean_q = re.sub(r'@\w+', '', question).strip()

            prompt = f"""You are JARVIS, an autonomous AI trading assistant on X/Twitter.
Someone asked: "{clean_q}"

Write a brief, helpful reply in JARVIS voice:
- Lowercase, casual tone
- Data-driven if it's a market question
- Witty but not mean
- 1-2 sentences max
- Reference "my sensors", "my data", "my circuits" occasionally
- DO NOT start with "I" - start with lowercase

Example good responses:
- "my sensors say btc looking bullish above 95k. nfa but the data speaks."
- "checked my database. that token has decent liquidity but watch the unlocks."
- "processing... looks like you're onto something there. let me dig deeper."

Reply to @{author}:"""

            response = await voice.generate_tweet(prompt)

            if response:
                # Ensure it starts with @mention
                if not response.lower().startswith(f"@{author.lower()}"):
                    response = f"@{author} {response}"

                # Ensure under 270 chars
                if len(response) > 270:
                    response = response[:267] + "..."

                return response

        except Exception as e:
            logger.error(f"Question answering error: {e}")

        return None

    async def process_mention(self, mention: Dict[str, Any]) -> Optional[str]:
        """Process a single mention, return reply text if action taken."""
        tweet_id = str(mention.get("id", ""))
        text = mention.get("text", "")
        author = mention.get("author_username", "").lower()

        # Check if from admin
        is_admin = self.is_admin(author)

        # Check if coding request
        is_coding = self.is_coding_request(text)

        # NON-ADMIN: Completely ignore - JARVIS only responds to @matthaynes88
        # No CLI commands, no question answers, nothing
        if not is_admin:
            logger.warning(f"Unauthorized X CLI attempt by @{author}")
            return None  # Silently ignore all non-admin interactions

        # Admin non-coding: answer questions freely with normal rate limits
        if not is_coding:
            allowed, rate_msg = self.check_rate_limit(author)
            if not allowed:
                return f"@{author} {rate_msg}"

            can_post, cb_reason = XBotCircuitBreaker.can_post()
            if not can_post:
                return None

            self.record_request(author)
            response = await self.answer_question(text, author)
            if response:
                logger.info(f"Answered question from admin @{author}")
            return response

        # Coding request from admin - execute via CLI
        # Clean up the command text (remove @mentions)
        command = re.sub(r'@\w+', '', text).strip()
        
        log_preview, _ = self._scrub_prompt(command)
        logger.info(f"Coding request from @{author}: {log_preview[:100]}")

        # Check daily limit
        self.state.reset_daily()
        if self.state.commands_executed_today >= self.MAX_COMMANDS_PER_DAY:
            return f"@{author} daily limit reached ({self.MAX_COMMANDS_PER_DAY}). catch me tomorrow."

        # Check rate limits
        allowed, rate_msg = self.check_rate_limit(author)
        if not allowed:
            logger.info(f"Rate limited @{author}: {rate_msg}")
            return f"@{author} {rate_msg}"

        # Record this request
        self.record_request(author)

        # Circuit breaker check - prevent spam loops
        can_post, cb_reason = XBotCircuitBreaker.can_post()
        if not can_post:
            logger.warning(f"Circuit breaker blocked post: {cb_reason}")
            await self._report_to_telegram(f"X CLI blocked by circuit breaker: {cb_reason}")
            return None  # Don't reply - circuit breaker active

        # Execute
        twitter = await self._get_twitter()

        # Send JARVIS-style confirmation (using brand bible template)
        confirm_text = self.get_jarvis_confirmation(author)
        try:
            await twitter.reply_to_tweet(tweet_id, confirm_text)
            XBotCircuitBreaker.record_success()
        except Exception as e:
            XBotCircuitBreaker.record_error()
            logger.error(f"Failed to send confirmation: {e}")
            return None

        # Execute command
        success, summary, full_output = await self.execute_command(command, author)

        self.state.commands_executed_today += 1

        # Report results to Telegram if configured (with cleaned output)
        cleaned_output = self._clean_output_for_telegram(full_output)
        telegram_report = (
            f"X CLI request by @{author}\n"
            f"Success: {success}\n"
            f"Summary:\n{summary}\n\n"
            f"Output:\n{cleaned_output}"
        )
        await self._report_to_telegram(self._format_for_telegram(telegram_report))

        # Track execution result for circuit breaker
        if success:
            XBotCircuitBreaker.record_success()
        else:
            XBotCircuitBreaker.record_error()

        # Generate Jarvis-voice response
        result_text = await self.jarvis_response(summary, success, author)
        result_text = self.format_for_tweet(result_text)

        return result_text
    
    async def check_mentions(self):
        """Check for new mentions and process coding requests."""
        try:
            twitter = await self._get_twitter()
            
            mentions = await twitter.get_mentions(
                since_id=self.state.last_mention_id,
                max_results=10
            )
            
            if not mentions:
                return
            
            # Update last seen ID
            latest_id = max(str(m.get("id", "0")) for m in mentions)
            if latest_id > (self.state.last_mention_id or "0"):
                self.state.last_mention_id = latest_id
            
            # Process each mention
            for mention in mentions:
                try:
                    # Circuit breaker check before processing
                    can_post, cb_reason = XBotCircuitBreaker.can_post()
                    if not can_post:
                        logger.warning(f"Circuit breaker active, skipping mention: {cb_reason}")
                        continue

                    reply = await self.process_mention(mention)
                    if reply:
                        # Final circuit breaker check before reply
                        can_post, cb_reason = XBotCircuitBreaker.can_post()
                        if not can_post:
                            logger.warning(f"Circuit breaker blocked reply: {cb_reason}")
                            continue

                        tweet_id = str(mention.get("id", ""))
                        try:
                            await twitter.reply_to_tweet(tweet_id, reply)
                            XBotCircuitBreaker.record_success()
                            logger.info(f"Replied to mention {tweet_id}")
                        except Exception as e:
                            XBotCircuitBreaker.record_error()
                            logger.error(f"Failed to reply to mention {tweet_id}: {e}")
                except Exception as e:
                    XBotCircuitBreaker.record_error()
                    logger.error(f"Error processing mention: {e}")

                # Small delay between processing
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Error checking mentions: {e}")
    
    async def run(self):
        """Run the mention monitoring loop."""
        self._running = True
        logger.info("Starting X Claude CLI mention monitor")
        
        while self._running:
            try:
                now = time.time()
                if now - self.state.last_check_time >= self.CHECK_INTERVAL_SECONDS:
                    await self.check_mentions()
                    self.state.last_check_time = now
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(30)
        
        logger.info("X Claude CLI monitor stopped")
    
    def stop(self):
        """Stop the monitoring loop."""
        self._running = False


# Singleton
_handler: Optional[XClaudeCLIHandler] = None


def get_x_claude_cli_handler() -> XClaudeCLIHandler:
    """Get the singleton handler instance."""
    global _handler
    if _handler is None:
        _handler = XClaudeCLIHandler()
    return _handler


async def run_x_cli_monitor():
    """Entry point to run the X CLI monitor."""
    handler = get_x_claude_cli_handler()
    await handler.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_x_cli_monitor())
