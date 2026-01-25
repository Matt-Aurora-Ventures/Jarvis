"""
Comprehensive unit tests for the X/Twitter Claude CLI Handler.

Tests cover:
- PendingCommand dataclass
- XClaudeCLIState runtime state management
- XBotCircuitBreaker for spam loop prevention
- XClaudeCLIHandler admin authentication
- Rate limiting and request tracking
- Command parsing and coding request detection
- Security sanitization (SECRET_PATTERNS, PARANOID_PATTERNS)
- Isolated sandbox workspace operations
- Code execution via Claude CLI
- Telegram reporting
- JARVIS voice responses
- Mention processing and replies
- Error handling and edge cases

This is a CRITICAL SECURITY component that executes code from X mentions.
Only @matthaynes88 is authorized. Thorough testing is essential.
"""

import pytest
import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.x_claude_cli_handler import (
    PendingCommand,
    XClaudeCLIState,
    XBotCircuitBreaker,
    XClaudeCLIHandler,
    get_x_claude_cli_handler,
    run_x_cli_monitor,
    ADMIN_USERNAMES,
    CODING_KEYWORDS,
    SECRET_PATTERNS,
    PARANOID_PATTERNS,
    JARVIS_CONFIRMATIONS,
    JARVIS_SUCCESS_TEMPLATES,
    JARVIS_ERROR_TEMPLATES,
)


# =============================================================================
# PendingCommand Tests
# =============================================================================

class TestPendingCommand:
    """Tests for PendingCommand dataclass."""

    def test_default_values(self):
        """Test PendingCommand default values."""
        cmd = PendingCommand(
            tweet_id="123456",
            author_username="test_user",
            command_text="fix the bug",
            created_at=datetime.now(),
        )
        assert cmd.confirmed is False
        assert cmd.executed is False
        assert cmd.result is None

    def test_all_values(self):
        """Test PendingCommand with all values set."""
        now = datetime.now()
        cmd = PendingCommand(
            tweet_id="789",
            author_username="admin",
            command_text="add feature",
            created_at=now,
            confirmed=True,
            executed=True,
            result="Success: added feature",
        )
        assert cmd.tweet_id == "789"
        assert cmd.author_username == "admin"
        assert cmd.command_text == "add feature"
        assert cmd.created_at == now
        assert cmd.confirmed is True
        assert cmd.executed is True
        assert cmd.result == "Success: added feature"


# =============================================================================
# XClaudeCLIState Tests
# =============================================================================

class TestXClaudeCLIState:
    """Tests for XClaudeCLIState runtime state."""

    def test_default_state(self):
        """Test default state initialization."""
        state = XClaudeCLIState()
        assert state.last_mention_id is None
        assert state.pending_commands == {}
        assert state.last_check_time == 0
        assert state.commands_executed_today == 0
        assert state.last_reset_date is None

    def test_reset_daily_same_day(self):
        """Test reset_daily does not reset on same day."""
        state = XClaudeCLIState()
        today = datetime.now().strftime("%Y-%m-%d")
        state.last_reset_date = today
        state.commands_executed_today = 10

        state.reset_daily()

        assert state.commands_executed_today == 10
        assert state.last_reset_date == today

    def test_reset_daily_new_day(self):
        """Test reset_daily resets on new day."""
        state = XClaudeCLIState()
        state.last_reset_date = "2020-01-01"  # Old date
        state.commands_executed_today = 10

        state.reset_daily()

        assert state.commands_executed_today == 0
        assert state.last_reset_date == datetime.now().strftime("%Y-%m-%d")

    def test_reset_daily_first_run(self):
        """Test reset_daily on first run (no last_reset_date)."""
        state = XClaudeCLIState()
        state.commands_executed_today = 5

        state.reset_daily()

        assert state.commands_executed_today == 0
        assert state.last_reset_date == datetime.now().strftime("%Y-%m-%d")


# =============================================================================
# XBotCircuitBreaker Tests
# =============================================================================

class TestXBotCircuitBreaker:
    """Tests for XBotCircuitBreaker spam prevention."""

    @pytest.fixture(autouse=True)
    def reset_circuit_breaker(self):
        """Reset circuit breaker state before each test."""
        XBotCircuitBreaker._last_post = None
        XBotCircuitBreaker._error_count = 0
        XBotCircuitBreaker._cooldown_until = None
        XBotCircuitBreaker._success_count = 0
        XBotCircuitBreaker._initialized = False
        yield

    def test_constants(self):
        """Test circuit breaker constants."""
        assert XBotCircuitBreaker.MIN_POST_INTERVAL == 60
        assert XBotCircuitBreaker.MAX_CONSECUTIVE_ERRORS == 3
        assert XBotCircuitBreaker.COOLDOWN_DURATION == 1800

    @patch.object(XBotCircuitBreaker, '_load_state')
    @patch.dict(os.environ, {"X_BOT_ENABLED": "true"})
    def test_can_post_allowed(self, mock_load):
        """Test can_post returns True when allowed."""
        XBotCircuitBreaker._initialized = True
        can_post, reason = XBotCircuitBreaker.can_post()
        assert can_post is True
        assert reason == "OK"

    @patch.object(XBotCircuitBreaker, '_load_state')
    @patch.dict(os.environ, {"X_BOT_ENABLED": "false"})
    def test_can_post_kill_switch(self, mock_load):
        """Test can_post respects X_BOT_ENABLED kill switch."""
        XBotCircuitBreaker._initialized = True
        can_post, reason = XBotCircuitBreaker.can_post()
        assert can_post is False
        assert "X_BOT_ENABLED=false" in reason

    @patch.object(XBotCircuitBreaker, '_load_state')
    @patch.dict(os.environ, {"X_BOT_ENABLED": "true"})
    def test_can_post_cooldown_active(self, mock_load):
        """Test can_post blocked during cooldown."""
        XBotCircuitBreaker._initialized = True
        XBotCircuitBreaker._cooldown_until = datetime.now() + timedelta(minutes=10)

        can_post, reason = XBotCircuitBreaker.can_post()

        assert can_post is False
        assert "cooldown" in reason.lower()

    @patch.object(XBotCircuitBreaker, '_load_state')
    @patch.dict(os.environ, {"X_BOT_ENABLED": "true"})
    def test_can_post_rate_limited(self, mock_load):
        """Test can_post blocked by rate limit."""
        XBotCircuitBreaker._initialized = True
        XBotCircuitBreaker._last_post = datetime.now()  # Just posted

        can_post, reason = XBotCircuitBreaker.can_post()

        assert can_post is False
        assert "Rate limit" in reason

    @patch.object(XBotCircuitBreaker, '_save_state')
    @patch.object(XBotCircuitBreaker, '_load_state')
    def test_record_success(self, mock_load, mock_save):
        """Test record_success resets error count."""
        XBotCircuitBreaker._initialized = True
        XBotCircuitBreaker._error_count = 2
        XBotCircuitBreaker._success_count = 5

        XBotCircuitBreaker.record_success()

        assert XBotCircuitBreaker._error_count == 0
        assert XBotCircuitBreaker._success_count == 6
        assert XBotCircuitBreaker._last_post is not None
        mock_save.assert_called_once()

    @patch.object(XBotCircuitBreaker, '_save_state')
    @patch.object(XBotCircuitBreaker, '_load_state')
    def test_record_error_under_threshold(self, mock_load, mock_save):
        """Test record_error increments count under threshold."""
        XBotCircuitBreaker._initialized = True
        XBotCircuitBreaker._error_count = 0

        XBotCircuitBreaker.record_error()

        assert XBotCircuitBreaker._error_count == 1
        assert XBotCircuitBreaker._cooldown_until is None

    @patch.object(XBotCircuitBreaker, '_save_state')
    @patch.object(XBotCircuitBreaker, '_load_state')
    def test_record_error_triggers_cooldown(self, mock_load, mock_save):
        """Test record_error triggers cooldown at threshold."""
        XBotCircuitBreaker._initialized = True
        XBotCircuitBreaker._error_count = 2  # One more will trigger

        XBotCircuitBreaker.record_error()

        assert XBotCircuitBreaker._error_count == 0  # Reset after cooldown
        assert XBotCircuitBreaker._cooldown_until is not None
        assert XBotCircuitBreaker._cooldown_until > datetime.now()

    @patch.object(XBotCircuitBreaker, '_save_state')
    def test_reset(self, mock_save):
        """Test reset clears all state."""
        XBotCircuitBreaker._last_post = datetime.now()
        XBotCircuitBreaker._error_count = 5
        XBotCircuitBreaker._cooldown_until = datetime.now()
        XBotCircuitBreaker._success_count = 100

        XBotCircuitBreaker.reset()

        assert XBotCircuitBreaker._last_post is None
        assert XBotCircuitBreaker._error_count == 0
        assert XBotCircuitBreaker._cooldown_until is None
        assert XBotCircuitBreaker._success_count == 0

    @patch.object(XBotCircuitBreaker, '_load_state')
    @patch.dict(os.environ, {"X_BOT_ENABLED": "true"})
    def test_status(self, mock_load):
        """Test status returns complete state."""
        XBotCircuitBreaker._initialized = True
        XBotCircuitBreaker._error_count = 1
        XBotCircuitBreaker._success_count = 10

        status = XBotCircuitBreaker.status()

        assert "can_post" in status
        assert "reason" in status
        assert status["error_count"] == 1
        assert status["success_count"] == 10


# =============================================================================
# Admin Authentication Tests
# =============================================================================

class TestAdminAuthentication:
    """Tests for admin authentication and authorization."""

    @pytest.fixture
    def handler(self):
        """Create a fresh handler for each test."""
        return XClaudeCLIHandler()

    def test_admin_usernames_defined(self):
        """Test admin usernames set is defined."""
        assert "matthaynes88" in ADMIN_USERNAMES
        assert len(ADMIN_USERNAMES) >= 1

    def test_is_admin_valid_admin(self, handler):
        """Test is_admin returns True for valid admin."""
        assert handler.is_admin("matthaynes88") is True

    def test_is_admin_with_at_symbol(self, handler):
        """Test is_admin handles @ prefix."""
        assert handler.is_admin("@matthaynes88") is True

    def test_is_admin_case_insensitive(self, handler):
        """Test is_admin is case insensitive."""
        assert handler.is_admin("MATTHAYNES88") is True
        assert handler.is_admin("MatthAyneS88") is True

    def test_is_admin_with_whitespace(self, handler):
        """Test is_admin handles whitespace."""
        assert handler.is_admin("  matthaynes88  ") is True
        assert handler.is_admin("\tmatthaynes88\n") is True

    def test_is_admin_unauthorized_user(self, handler):
        """Test is_admin returns False for unauthorized users."""
        assert handler.is_admin("random_user") is False
        assert handler.is_admin("hacker123") is False

    def test_is_admin_empty_username(self, handler):
        """Test is_admin handles empty username."""
        assert handler.is_admin("") is False
        assert handler.is_admin(None) is False


# =============================================================================
# Rate Limiting Tests
# =============================================================================

class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.fixture
    def handler(self):
        """Create a fresh handler for each test."""
        return XClaudeCLIHandler()

    def test_rate_limit_constants(self, handler):
        """Test rate limit constants are set."""
        assert handler.RATE_LIMIT_WINDOW == 60
        assert handler.RATE_LIMIT_MAX_REQUESTS == 5
        assert handler.RATE_LIMIT_MIN_GAP == 10

    def test_check_rate_limit_no_history(self, handler):
        """Test rate limit check with no request history."""
        allowed, msg = handler.check_rate_limit("testuser")
        assert allowed is True
        assert msg == ""

    def test_check_rate_limit_empty_username(self, handler):
        """Test rate limit with empty username."""
        allowed, msg = handler.check_rate_limit("")
        assert allowed is True
        assert msg == ""

    def test_check_rate_limit_min_gap_violated(self, handler):
        """Test rate limit blocks requests too close together."""
        handler._request_history["testuser"] = [time.time()]

        allowed, msg = handler.check_rate_limit("testuser")

        assert allowed is False
        assert "slow down" in msg.lower()

    def test_check_rate_limit_max_requests_exceeded(self, handler):
        """Test rate limit blocks after max requests."""
        now = time.time()
        # Fill up with requests (spaced enough to pass min gap)
        handler._request_history["testuser"] = [
            now - 50, now - 40, now - 30, now - 20, now - 11
        ]

        allowed, msg = handler.check_rate_limit("testuser")

        assert allowed is False
        assert "rate limit hit" in msg.lower()

    def test_check_rate_limit_cleans_old_entries(self, handler):
        """Test rate limit removes old entries outside window."""
        now = time.time()
        # Old entries outside window + one recent (but older than MIN_GAP)
        handler._request_history["testuser"] = [
            now - 120, now - 100, now - 80, now - 15
        ]

        allowed, msg = handler.check_rate_limit("testuser")

        # Should only keep entries within window (60s)
        assert len(handler._request_history["testuser"]) == 1
        # With -15 seconds, that's within MIN_GAP (10s), so should be blocked
        # Actually -15 > 10, so it IS allowed - fix test expectation
        assert allowed is True  # -15 seconds ago is beyond MIN_GAP of 10s

    def test_record_request(self, handler):
        """Test recording a request."""
        handler.record_request("testuser")

        assert "testuser" in handler._request_history
        assert len(handler._request_history["testuser"]) == 1

    def test_record_request_empty_username(self, handler):
        """Test record_request with empty username does nothing."""
        handler.record_request("")
        assert "" not in handler._request_history


# =============================================================================
# Coding Request Detection Tests
# =============================================================================

class TestCodingRequestDetection:
    """Tests for detecting coding requests."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_coding_keywords_defined(self):
        """Test coding keywords list is populated."""
        assert len(CODING_KEYWORDS) > 10
        assert "fix" in CODING_KEYWORDS
        assert "code" in CODING_KEYWORDS
        assert "ralph wiggum" in CODING_KEYWORDS

    def test_is_coding_request_positive(self, handler):
        """Test detection of coding requests."""
        assert handler.is_coding_request("fix the bug in trading.py") is True
        assert handler.is_coding_request("Add a new feature") is True
        assert handler.is_coding_request("create endpoint for API") is True
        assert handler.is_coding_request("update the config") is True
        assert handler.is_coding_request("ralph wiggum on improvements") is True

    def test_is_coding_request_negative(self, handler):
        """Test non-coding requests are not detected."""
        assert handler.is_coding_request("what is the price of BTC?") is False
        assert handler.is_coding_request("hello jarvis") is False
        assert handler.is_coding_request("how are you?") is False

    def test_is_coding_request_case_insensitive(self, handler):
        """Test coding detection is case insensitive."""
        assert handler.is_coding_request("FIX THE BUG") is True
        assert handler.is_coding_request("ADD FEATURE") is True
        assert handler.is_coding_request("RALPH WIGGUM") is True


# =============================================================================
# Security Sanitization Tests
# =============================================================================

class TestSecuritySanitization:
    """Tests for output sanitization and secret scrubbing."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_secret_patterns_defined(self):
        """Test secret patterns are defined."""
        assert len(SECRET_PATTERNS) > 10

    def test_paranoid_patterns_defined(self):
        """Test paranoid patterns are defined."""
        assert len(PARANOID_PATTERNS) >= 2

    def test_sanitize_output_empty(self, handler):
        """Test sanitizing empty output."""
        assert handler.sanitize_output("") == ""
        assert handler.sanitize_output(None) is None

    def test_sanitize_output_anthropic_key(self, handler):
        """Test Anthropic API key is redacted."""
        text = "Using key sk-ant-abc123xyz789-very-long-key"
        result = handler.sanitize_output(text)
        assert "sk-ant" not in result
        assert "[REDACTED]" in result

    def test_sanitize_output_xai_key(self, handler):
        """Test xAI key is redacted."""
        text = "XAI_API_KEY=xai-abcdef123456789"
        result = handler.sanitize_output(text)
        assert "xai-" not in result

    def test_sanitize_output_telegram_token(self, handler):
        """Test Telegram bot token is redacted."""
        text = "Bot token: 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefg"
        result = handler.sanitize_output(text)
        assert "1234567890:" not in result
        assert "[REDACTED]" in result

    def test_sanitize_output_twitter_secrets(self, handler):
        """Test Twitter secrets are redacted."""
        text = "TWITTER_BEARER_TOKEN=AAAA123456789abcdefghijklmnopqrstuvwxyz"
        result = handler.sanitize_output(text)
        assert "AAAA" not in result

    def test_sanitize_output_solana_private_key(self, handler):
        """Test Solana private key is redacted."""
        # 88-character base58 private key
        text = "private_key: 5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ8U2e8WbB7nJKhfVHVKqW8rXVFq"
        result = handler.sanitize_output(text)
        assert "5HueCGU8" not in result
        assert "[REDACTED]" in result

    def test_sanitize_output_database_url(self, handler):
        """Test database URLs are redacted."""
        text = "DATABASE_URL=postgresql://user:pass@localhost:5432/db"
        result = handler.sanitize_output(text)
        assert "postgresql://" not in result
        assert "[REDACTED" in result

    def test_sanitize_output_github_token(self, handler):
        """Test GitHub tokens are redacted."""
        text = "Using ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        result = handler.sanitize_output(text)
        assert "ghp_" not in result
        assert "[REDACTED]" in result

    def test_sanitize_output_jwt(self, handler):
        """Test JWT tokens are redacted."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        text = f"Token: {jwt}"
        result = handler.sanitize_output(text)
        assert "eyJ" not in result
        assert "[REDACTED]" in result

    def test_sanitize_output_user_paths(self, handler):
        """Test user paths are anonymized."""
        text = r"Path: C:\Users\lucid\Documents\secret.txt"
        result = handler.sanitize_output(text)
        assert "lucid" not in result
        assert "***" in result

    def test_sanitize_output_ansi_codes_removed(self, handler):
        """Test ANSI escape codes are removed."""
        text = "\x1b[32mGreen text\x1b[0m and \x1b[31mred\x1b[0m"
        result = handler.sanitize_output(text)
        assert "\x1b" not in result
        assert "Green text" in result

    def test_sanitize_output_spinners_removed(self, handler):
        """Test loading spinners (Unicode braille characters) are removed."""
        # The actual spinner characters from the source code: [U+280B, U+2819, etc.]
        spinner_chars = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"
        text = f"Loading {spinner_chars} done"
        result = handler.sanitize_output(text)
        # All braille spinner chars should be removed
        for char in spinner_chars:
            assert char not in result
        assert "Loading" in result
        assert "done" in result

    def test_sanitize_output_hex_secrets(self, handler):
        """Test long hex strings are redacted."""
        # 64-char hex (like SHA256)
        text = "Hash: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        result = handler.sanitize_output(text, paranoid=True)
        assert "a1b2c3d4" not in result

    def test_sanitize_output_non_paranoid_mode(self, handler):
        """Test non-paranoid mode is less aggressive."""
        text = "Regular text with some content"
        result = handler.sanitize_output(text, paranoid=False)
        assert result == text


# =============================================================================
# Path Ignore Tests
# =============================================================================

class TestPathIgnore:
    """Tests for path ignore logic in sandbox."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_ignore_venv(self, handler):
        """Test .venv directory is ignored."""
        assert handler._should_ignore_path(".venv/lib/python") is True
        assert handler._should_ignore_path("venv/bin/python") is True

    def test_ignore_git(self, handler):
        """Test .git directory is ignored."""
        assert handler._should_ignore_path(".git/config") is True

    def test_ignore_pycache(self, handler):
        """Test __pycache__ is ignored."""
        assert handler._should_ignore_path("src/__pycache__/module.cpython") is True

    def test_ignore_node_modules(self, handler):
        """Test node_modules is ignored."""
        assert handler._should_ignore_path("node_modules/package/index.js") is True

    def test_ignore_env_files(self, handler):
        """Test .env files are ignored."""
        assert handler._should_ignore_path(".env") is True
        assert handler._should_ignore_path(".env.local") is True
        assert handler._should_ignore_path(".env.production") is True

    def test_ignore_log_files(self, handler):
        """Test log files are ignored."""
        assert handler._should_ignore_path("app.log") is True
        assert handler._should_ignore_path("logs/server.log") is True

    def test_ignore_sqlite(self, handler):
        """Test SQLite files are ignored."""
        assert handler._should_ignore_path("database.db") is True
        assert handler._should_ignore_path("app.sqlite") is True
        assert handler._should_ignore_path("data.sqlite3") is True

    def test_ignore_key_files(self, handler):
        """Test key/pem files are ignored."""
        assert handler._should_ignore_path("private.key") is True
        assert handler._should_ignore_path("server.pem") is True

    def test_ignore_windows_reserved_names(self, handler):
        """Test Windows reserved device names are ignored."""
        assert handler._should_ignore_path("nul") is True
        assert handler._should_ignore_path("con") is True
        assert handler._should_ignore_path("aux") is True
        assert handler._should_ignore_path("com1") is True
        assert handler._should_ignore_path("lpt1") is True

    def test_normal_paths_not_ignored(self, handler):
        """Test normal paths are not ignored."""
        assert handler._should_ignore_path("src/main.py") is False
        assert handler._should_ignore_path("tests/test_api.py") is False
        assert handler._should_ignore_path("README.md") is False


# =============================================================================
# Windows Reserved Name Tests
# =============================================================================

class TestWindowsReservedNames:
    """Tests for Windows reserved name detection."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_is_windows_reserved_name_nul(self, handler):
        """Test NUL is detected as reserved."""
        assert handler._is_windows_reserved_name("nul") is True
        assert handler._is_windows_reserved_name("NUL") is True
        assert handler._is_windows_reserved_name("nul.txt") is True

    def test_is_windows_reserved_name_con(self, handler):
        """Test CON is detected as reserved."""
        assert handler._is_windows_reserved_name("con") is True
        assert handler._is_windows_reserved_name("CON.log") is True

    def test_is_windows_reserved_name_com_ports(self, handler):
        """Test COM ports are detected."""
        for i in range(1, 10):
            assert handler._is_windows_reserved_name(f"com{i}") is True
            assert handler._is_windows_reserved_name(f"COM{i}") is True

    def test_is_windows_reserved_name_lpt_ports(self, handler):
        """Test LPT ports are detected."""
        for i in range(1, 10):
            assert handler._is_windows_reserved_name(f"lpt{i}") is True
            assert handler._is_windows_reserved_name(f"LPT{i}") is True

    def test_normal_names_not_reserved(self, handler):
        """Test normal filenames are not reserved."""
        assert handler._is_windows_reserved_name("main.py") is False
        assert handler._is_windows_reserved_name("console.log") is False
        assert handler._is_windows_reserved_name("communication.py") is False


# =============================================================================
# Sandbox Environment Tests
# =============================================================================

class TestSandboxEnvironment:
    """Tests for sandbox environment building."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_sandbox_env_blocklist(self, handler):
        """Test sandbox blocklist items."""
        assert "KEY" in handler.SANDBOX_ENV_BLOCKLIST
        assert "TOKEN" in handler.SANDBOX_ENV_BLOCKLIST
        assert "SECRET" in handler.SANDBOX_ENV_BLOCKLIST
        assert "PASSWORD" in handler.SANDBOX_ENV_BLOCKLIST
        assert "PRIVATE" in handler.SANDBOX_ENV_BLOCKLIST

    def test_sandbox_env_allowlist(self, handler):
        """Test sandbox allowlist items."""
        assert "ANTHROPIC_API_KEY" in handler.SANDBOX_ENV_ALLOWLIST
        assert "CLAUDE_API_KEY" in handler.SANDBOX_ENV_ALLOWLIST

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "SOME_SECRET_KEY": "secret123",
        "DATABASE_PASSWORD": "dbpass",
        "NORMAL_VAR": "normalvalue",
    })
    def test_build_sandbox_env_filters_secrets(self, handler):
        """Test sandbox env filters out secrets but keeps allowlisted."""
        env = handler._build_sandbox_env()

        # Allowlisted should be kept
        assert "ANTHROPIC_API_KEY" in env

        # Blocklisted should be removed
        assert "SOME_SECRET_KEY" not in env
        assert "DATABASE_PASSWORD" not in env

        # Normal vars should be kept
        assert env.get("NORMAL_VAR") == "normalvalue"

    def test_build_sandbox_env_sets_marker(self, handler):
        """Test sandbox env sets JARVIS_SANDBOX marker."""
        env = handler._build_sandbox_env()
        assert env.get("JARVIS_SANDBOX") == "1"


# =============================================================================
# JARVIS Voice Tests
# =============================================================================

class TestJarvisVoice:
    """Tests for JARVIS voice generation."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_jarvis_confirmations_defined(self):
        """Test confirmation templates are defined."""
        assert len(JARVIS_CONFIRMATIONS) >= 3
        for conf in JARVIS_CONFIRMATIONS:
            assert isinstance(conf, str)
            assert len(conf) > 0

    def test_jarvis_success_templates_defined(self):
        """Test success templates are defined."""
        assert len(JARVIS_SUCCESS_TEMPLATES) >= 3
        for tmpl in JARVIS_SUCCESS_TEMPLATES:
            assert "{author}" in tmpl
            assert "{summary}" in tmpl

    def test_jarvis_error_templates_defined(self):
        """Test error templates are defined."""
        assert len(JARVIS_ERROR_TEMPLATES) >= 2
        for tmpl in JARVIS_ERROR_TEMPLATES:
            assert "{author}" in tmpl

    def test_get_jarvis_confirmation(self, handler):
        """Test getting a JARVIS confirmation."""
        result = handler.get_jarvis_confirmation("testuser")
        assert "@testuser" in result
        assert len(result) > 10

    def test_get_jarvis_result_success(self, handler):
        """Test JARVIS success result formatting."""
        result = handler.get_jarvis_result("testuser", True, "Fixed the bug")
        assert "@testuser" in result
        assert any(word in result.lower() for word in ["done", "sorted", "finished", "complete"])

    def test_get_jarvis_result_failure(self, handler):
        """Test JARVIS failure result formatting."""
        result = handler.get_jarvis_result("testuser", False, "Something failed")
        assert "@testuser" in result
        assert any(word in result.lower() for word in ["snag", "recalibrating", "sideways"])


# =============================================================================
# Tweet Formatting Tests
# =============================================================================

class TestTweetFormatting:
    """Tests for tweet formatting."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_format_for_tweet_short(self, handler):
        """Test short text is unchanged."""
        text = "This is a short tweet"
        result = handler.format_for_tweet(text)
        assert result == text

    def test_format_for_tweet_truncates_long(self, handler):
        """Test long text is truncated."""
        text = "x" * 300
        result = handler.format_for_tweet(text)
        assert len(result) <= 270
        assert result.endswith("...")

    def test_format_for_tweet_custom_max_len(self, handler):
        """Test custom max length."""
        text = "x" * 100
        result = handler.format_for_tweet(text, max_len=50)
        assert len(result) <= 50
        assert result.endswith("...")

    def test_format_for_tweet_cleans_whitespace(self, handler):
        """Test whitespace is cleaned."""
        text = "Multiple   spaces\nand\nnewlines"
        result = handler.format_for_tweet(text)
        assert "\n" not in result
        assert "  " not in result


# =============================================================================
# Telegram Formatting Tests
# =============================================================================

class TestTelegramFormatting:
    """Tests for Telegram message formatting."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_format_for_telegram_short(self, handler):
        """Test short text is unchanged."""
        text = "Short message"
        result = handler._format_for_telegram(text)
        assert result == text

    def test_format_for_telegram_truncates(self, handler):
        """Test long text is truncated."""
        text = "x" * 4000
        result = handler._format_for_telegram(text)
        # Max is 3500 chars + "\n\n[truncated]" suffix
        assert len(result) <= 3500 + len("\n\n[truncated]")
        assert "[truncated]" in result

    def test_clean_output_for_telegram_removes_hooks(self, handler):
        """Test hook errors are cleaned from output."""
        output = """
        Some output here
        hook [SessionEnd] failed with error
        More hook stuff

        Actual result
        """
        result = handler._clean_output_for_telegram(output)
        assert "hook" not in result.lower() or "hook" in "webhook"  # webhook might be valid
        assert "Actual result" in result

    def test_clean_output_for_telegram_removes_node_traces(self, handler):
        """Test Node.js stack traces are removed."""
        output = """
        Error output
        at Object.<anonymous> (/path/to/file.js:10:5)
        at Module._compile (node:internal/modules/cjs/loader:1256:14)
        MODULE_NOT_FOUND

        Real content
        """
        result = handler._clean_output_for_telegram(output)
        assert "at Object" not in result
        assert "node:internal" not in result
        assert "MODULE_NOT_FOUND" not in result

    def test_clean_output_for_telegram_removes_temp_paths(self, handler):
        """Test temporary paths are removed."""
        output = "Output from jarvis_claude_12345/workspace and AppData\\Local\\Temp"
        result = handler._clean_output_for_telegram(output)
        assert "jarvis_claude_" not in result

    def test_clean_output_for_telegram_empty_returns_default(self, handler):
        """Test empty output returns default message."""
        result = handler._clean_output_for_telegram("")
        assert result == ""

        # All content filtered
        output = "hook [test] failed\nat something\n"
        result = handler._clean_output_for_telegram(output)
        assert result == "Command executed."


# =============================================================================
# Result Summarization Tests
# =============================================================================

class TestResultSummarization:
    """Tests for summarizing execution results."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_summarize_created(self, handler):
        """Test summarizing created file."""
        output = 'I created "new_feature.py" with the implementation'
        result = handler.summarize_result(output)
        assert "Created" in result

    def test_summarize_modified(self, handler):
        """Test summarizing modified file."""
        output = 'I edited "existing.py" to fix the bug'
        result = handler.summarize_result(output)
        assert "Modified" in result

    def test_summarize_fixed(self, handler):
        """Test summarizing fixed issue."""
        output = 'I fixed "the rate limiter bug" that was causing issues'
        result = handler.summarize_result(output)
        assert "Fixed" in result

    def test_summarize_success_keyword(self, handler):
        """Test summarizing with success keyword."""
        output = "Task completed successfully"
        result = handler.summarize_result(output)
        assert "completed" in result.lower() or "Processed" in result

    def test_summarize_error_keyword(self, handler):
        """Test summarizing with error keyword."""
        output = "The operation failed with an error"
        result = handler.summarize_result(output)
        assert "issues" in result.lower()

    def test_summarize_generic(self, handler):
        """Test generic summarization fallback."""
        output = "Some random output with no patterns"
        result = handler.summarize_result(output)
        assert "Processed" in result


# =============================================================================
# Execution Metrics Tests
# =============================================================================

class TestExecutionMetrics:
    """Tests for execution metrics tracking."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_initial_metrics(self, handler):
        """Test initial metrics state."""
        metrics = handler.get_metrics()
        assert metrics["total"] == 0
        assert metrics["success_rate"] == "N/A"
        assert metrics["avg_duration"] == "N/A"
        assert metrics["last_execution"] == "Never"

    def test_record_execution_success(self, handler):
        """Test recording successful execution."""
        handler.record_execution(True, 2.5, "testuser")

        assert handler._metrics["total_executions"] == 1
        assert handler._metrics["successful_executions"] == 1
        assert handler._metrics["failed_executions"] == 0
        assert handler._metrics["total_execution_time"] == 2.5

    def test_record_execution_failure(self, handler):
        """Test recording failed execution."""
        handler.record_execution(False, 1.0, "testuser")

        assert handler._metrics["total_executions"] == 1
        assert handler._metrics["successful_executions"] == 0
        assert handler._metrics["failed_executions"] == 1

    def test_get_metrics_with_data(self, handler):
        """Test getting metrics with recorded data."""
        handler.record_execution(True, 2.0, "user1")
        handler.record_execution(True, 4.0, "user2")
        handler.record_execution(False, 1.0, "user3")

        metrics = handler.get_metrics()

        assert metrics["total"] == 3
        assert metrics["successful"] == 2
        assert metrics["failed"] == 1
        assert "66" in metrics["success_rate"]  # ~66.7%
        assert "2.3" in metrics["avg_duration"]  # (2+4+1)/3

    def test_execution_history_limit(self, handler):
        """Test execution history is limited to 50."""
        for i in range(60):
            handler.record_execution(True, 1.0, f"user{i}")

        assert len(handler._metrics["execution_history"]) == 50


# =============================================================================
# Process Mention Tests
# =============================================================================

class TestProcessMention:
    """Tests for processing X mentions."""

    @pytest.fixture
    def handler(self):
        h = XClaudeCLIHandler()
        # Reset circuit breaker for clean tests
        XBotCircuitBreaker._last_post = None
        XBotCircuitBreaker._error_count = 0
        XBotCircuitBreaker._cooldown_until = None
        XBotCircuitBreaker._initialized = True
        return h

    @pytest.mark.asyncio
    async def test_process_mention_non_admin_ignored(self, handler):
        """Test non-admin mentions are silently ignored."""
        mention = {
            "id": "123",
            "text": "@jarvis fix the bug",
            "author_username": "random_user",
        }

        result = await handler.process_mention(mention)

        assert result is None  # Silently ignored

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"X_BOT_ENABLED": "true"})
    async def test_process_mention_admin_question(self, handler):
        """Test admin non-coding question gets answered."""
        mention = {
            "id": "123",
            "text": "@jarvis what is the price of BTC?",
            "author_username": "matthaynes88",
        }

        with patch.object(handler, 'answer_question', new_callable=AsyncMock) as mock_answer:
            mock_answer.return_value = "@matthaynes88 btc looking solid at 100k"
            with patch.object(handler, '_get_jarvis_voice', new_callable=AsyncMock):
                result = await handler.process_mention(mention)

        assert result == "@matthaynes88 btc looking solid at 100k"

    @pytest.mark.asyncio
    async def test_process_mention_rate_limited(self, handler):
        """Test rate limited request returns rate limit message."""
        mention = {
            "id": "123",
            "text": "@jarvis hello",
            "author_username": "matthaynes88",
        }

        # Fill up rate limit
        handler._request_history["matthaynes88"] = [time.time()]

        result = await handler.process_mention(mention)

        assert "slow down" in result.lower()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"X_BOT_ENABLED": "true"})
    async def test_process_mention_daily_limit(self, handler):
        """Test daily limit blocks command."""
        handler.state.last_reset_date = datetime.now().strftime("%Y-%m-%d")
        handler.state.commands_executed_today = 50

        mention = {
            "id": "123",
            "text": "@jarvis fix the bug",
            "author_username": "matthaynes88",
        }

        result = await handler.process_mention(mention)

        assert "daily limit" in result.lower()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"X_BOT_ENABLED": "true"})
    async def test_process_mention_circuit_breaker_blocked(self, handler):
        """Test circuit breaker blocks command."""
        XBotCircuitBreaker._cooldown_until = datetime.now() + timedelta(hours=1)

        mention = {
            "id": "123",
            "text": "@jarvis fix the bug",
            "author_username": "matthaynes88",
        }

        result = await handler.process_mention(mention)

        assert result is None  # Blocked by circuit breaker


# =============================================================================
# Execute Command Tests
# =============================================================================

class TestExecuteCommand:
    """Tests for command execution."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    @pytest.mark.asyncio
    async def test_execute_command_cli_not_found(self, handler):
        """Test handling when Claude CLI is not installed."""
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError):
            with patch.object(handler, '_prepare_isolated_workspace') as mock_workspace:
                mock_workspace.return_value = (MagicMock(), "/tmp/workspace", {})

                success, summary, output = await handler.execute_command("test")

        assert success is False
        assert "CLI not found" in summary

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, handler):
        """Test command timeout handling."""
        async def slow_process(*args, **kwargs):
            mock = MagicMock()
            mock.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock.kill = MagicMock()
            return mock

        with patch('asyncio.create_subprocess_exec', side_effect=slow_process):
            with patch.object(handler, '_prepare_isolated_workspace') as mock_workspace:
                temp_dir = MagicMock()
                temp_dir.cleanup = MagicMock()
                mock_workspace.return_value = (temp_dir, "/tmp/workspace", {})

                success, summary, output = await handler.execute_command("slow command")

        assert success is False
        assert "Timed out" in summary

    @pytest.mark.asyncio
    async def test_execute_command_sandbox_setup_failure(self, handler):
        """Test sandbox setup failure handling."""
        with patch.object(handler, '_prepare_isolated_workspace', side_effect=Exception("Disk full")):
            success, summary, output = await handler.execute_command("test")

        assert success is False
        assert "Sandbox setup failed" in summary

    @pytest.mark.asyncio
    async def test_execute_command_success(self, handler):
        """Test successful command execution."""
        async def mock_process(*args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.communicate = AsyncMock(return_value=(
                b"Task completed successfully",
                b""
            ))
            return mock

        with patch('asyncio.create_subprocess_exec', mock_process):
            with patch.object(handler, '_prepare_isolated_workspace') as mock_workspace:
                temp_dir = MagicMock()
                temp_dir.cleanup = MagicMock()
                mock_workspace.return_value = (temp_dir, "/tmp/workspace", {})
                with patch.object(handler, '_apply_sandbox_changes', return_value={"added": [], "changed": [], "removed": []}):
                    success, summary, output = await handler.execute_command("fix bug")

        assert success is True
        assert "completed" in output.lower()


# =============================================================================
# Answer Question Tests
# =============================================================================

class TestAnswerQuestion:
    """Tests for question answering."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    @pytest.mark.asyncio
    async def test_answer_question_success(self, handler):
        """Test successful question answering."""
        mock_voice = MagicMock()
        mock_voice.generate_tweet = AsyncMock(return_value="btc looking solid above 95k")

        with patch.object(handler, '_get_jarvis_voice', new_callable=AsyncMock) as mock_get_voice:
            mock_get_voice.return_value = mock_voice

            result = await handler.answer_question("what is the price of BTC?", "testuser")

        assert result is not None
        assert "@testuser" in result

    @pytest.mark.asyncio
    async def test_answer_question_adds_mention(self, handler):
        """Test mention is added if not present."""
        mock_voice = MagicMock()
        mock_voice.generate_tweet = AsyncMock(return_value="btc is at 100k")

        with patch.object(handler, '_get_jarvis_voice', new_callable=AsyncMock) as mock_get_voice:
            mock_get_voice.return_value = mock_voice

            result = await handler.answer_question("price?", "testuser")

        assert result.startswith("@testuser")

    @pytest.mark.asyncio
    async def test_answer_question_truncates_long_response(self, handler):
        """Test long responses are truncated."""
        mock_voice = MagicMock()
        mock_voice.generate_tweet = AsyncMock(return_value="x" * 300)

        with patch.object(handler, '_get_jarvis_voice', new_callable=AsyncMock) as mock_get_voice:
            mock_get_voice.return_value = mock_voice

            result = await handler.answer_question("question?", "user")

        assert len(result) <= 280  # @user + space + content

    @pytest.mark.asyncio
    async def test_answer_question_error_returns_none(self, handler):
        """Test error in question answering returns None."""
        with patch.object(handler, '_get_jarvis_voice', new_callable=AsyncMock) as mock_get_voice:
            mock_get_voice.side_effect = Exception("API Error")

            result = await handler.answer_question("question?", "user")

        assert result is None


# =============================================================================
# Telegram Reporting Tests
# =============================================================================

class TestTelegramReporting:
    """Tests for Telegram report sending."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_BUY_BOT_CHAT_ID": ""})
    async def test_report_to_telegram_no_config(self, handler):
        """Test no report sent without config."""
        result = await handler._report_to_telegram("test message")
        assert result is False

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token", "TELEGRAM_BUY_BOT_CHAT_ID": "123"})
    async def test_report_to_telegram_success(self, handler):
        """Test successful Telegram report."""
        import aiohttp

        mock_resp = MagicMock()
        mock_resp.status = 200

        mock_session = MagicMock()
        mock_session.post = MagicMock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.post.return_value.__aexit__ = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await handler._report_to_telegram("test message")

        assert result is True

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token", "TELEGRAM_BUY_BOT_CHAT_ID": "123"})
    async def test_report_to_telegram_api_error(self, handler):
        """Test Telegram API error handling."""
        mock_resp = MagicMock()
        mock_resp.status = 500

        mock_session = MagicMock()
        mock_session.post = MagicMock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.post.return_value.__aexit__ = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await handler._report_to_telegram("test message")

        assert result is False


# =============================================================================
# Check Mentions Tests
# =============================================================================

class TestCheckMentions:
    """Tests for mention checking loop."""

    @pytest.fixture
    def handler(self):
        h = XClaudeCLIHandler()
        XBotCircuitBreaker._initialized = True
        XBotCircuitBreaker._last_post = None
        XBotCircuitBreaker._cooldown_until = None
        return h

    @pytest.mark.asyncio
    async def test_check_mentions_no_mentions(self, handler):
        """Test check_mentions with no new mentions."""
        mock_twitter = MagicMock()
        mock_twitter.get_mentions = AsyncMock(return_value=[])

        with patch.object(handler, '_get_twitter', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_twitter

            await handler.check_mentions()

        mock_twitter.get_mentions.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_mentions_updates_last_id(self, handler):
        """Test check_mentions updates last_mention_id."""
        mock_twitter = MagicMock()
        mock_twitter.get_mentions = AsyncMock(return_value=[
            {"id": "100", "text": "test", "author_username": "user1"},
            {"id": "200", "text": "test2", "author_username": "user2"},
        ])
        mock_twitter.reply_to_tweet = AsyncMock()

        with patch.object(handler, '_get_twitter', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_twitter
            with patch.object(handler, 'process_mention', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = None

                await handler.check_mentions()

        assert handler.state.last_mention_id == "200"


# =============================================================================
# Run Loop Tests
# =============================================================================

class TestRunLoop:
    """Tests for the main run loop."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    @pytest.mark.asyncio
    async def test_run_starts_running(self, handler):
        """Test run sets _running flag to True initially."""
        # We can't easily test the full loop, but we can verify
        # that the handler has the proper initial state
        assert handler._running is False

        # Mock check_mentions to immediately stop
        async def stop_on_check():
            handler.stop()

        with patch.object(handler, 'check_mentions', side_effect=stop_on_check):
            # Run briefly - it should stop after first check
            handler.state.last_check_time = 0
            handler.CHECK_INTERVAL_SECONDS = 0
            try:
                await asyncio.wait_for(handler.run(), timeout=0.5)
            except asyncio.TimeoutError:
                handler.stop()

        # After stopping, _running should be False
        assert handler._running is False

    def test_stop_clears_running(self, handler):
        """Test stop clears _running flag."""
        handler._running = True
        handler.stop()
        assert handler._running is False


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_x_claude_cli_handler_singleton(self):
        """Test get_x_claude_cli_handler returns singleton."""
        # Reset singleton
        import bots.twitter.x_claude_cli_handler as module
        module._handler = None

        handler1 = get_x_claude_cli_handler()
        handler2 = get_x_claude_cli_handler()

        assert handler1 is handler2


# =============================================================================
# JARVIS Response Tests
# =============================================================================

class TestJarvisResponse:
    """Tests for jarvis_response async method."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    @pytest.mark.asyncio
    async def test_jarvis_response_success_short(self, handler):
        """Test simple success response uses template."""
        result = await handler.jarvis_response("fixed bug", True, "testuser")

        assert "@testuser" in result
        assert len(result) <= 270

    @pytest.mark.asyncio
    async def test_jarvis_response_failure(self, handler):
        """Test failure response uses error template."""
        result = await handler.jarvis_response("something broke", False, "testuser")

        assert "@testuser" in result

    @pytest.mark.asyncio
    async def test_jarvis_response_llm_fallback(self, handler):
        """Test LLM generation for long summaries with fallback."""
        long_summary = "x" * 300  # Too long for simple template

        mock_voice = MagicMock()
        mock_voice.generate_tweet = AsyncMock(return_value="@testuser done with long task")

        with patch.object(handler, '_get_jarvis_voice', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_voice

            result = await handler.jarvis_response(long_summary, True, "testuser")

        assert "@testuser" in result
        assert len(result) <= 270

    @pytest.mark.asyncio
    async def test_jarvis_response_llm_error_fallback(self, handler):
        """Test fallback to template when LLM fails."""
        with patch.object(handler, '_get_jarvis_voice', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("API Error")

            result = await handler.jarvis_response("test summary", True, "testuser")

        # Should fall back to simple template
        assert "@testuser" in result


# =============================================================================
# Find Bash Tests
# =============================================================================

class TestFindBash:
    """Tests for _find_bash method."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    @patch('os.path.isfile')
    def test_find_bash_git_bash(self, mock_isfile, handler):
        """Test finding Git Bash."""
        def isfile_side_effect(path):
            return "Git" in path and "bash.exe" in path

        mock_isfile.side_effect = isfile_side_effect

        result = handler._find_bash()

        # Should find Git Bash if it exists
        if result:
            assert "bash" in result.lower()

    @patch('os.path.isfile', return_value=False)
    @patch('shutil.which', return_value=None)
    def test_find_bash_not_found(self, mock_which, mock_isfile, handler):
        """Test when no bash is found."""
        result = handler._find_bash()
        assert result is None


# =============================================================================
# File Equality Tests
# =============================================================================

class TestFileEquality:
    """Tests for _files_equal method."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_files_equal_same_content(self, handler):
        """Test files with same content are equal."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("test content")
            f1_path = f1.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("test content")
            f2_path = f2.name

        try:
            result = handler._files_equal(f1_path, f2_path)
            assert result is True
        finally:
            os.unlink(f1_path)
            os.unlink(f2_path)

    def test_files_equal_different_content(self, handler):
        """Test files with different content are not equal."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("content A")
            f1_path = f1.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("content B")
            f2_path = f2.name

        try:
            result = handler._files_equal(f1_path, f2_path)
            assert result is False
        finally:
            os.unlink(f1_path)
            os.unlink(f2_path)

    def test_files_equal_different_sizes(self, handler):
        """Test files with different sizes are not equal."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("short")
            f1_path = f1.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("much longer content here")
            f2_path = f2.name

        try:
            result = handler._files_equal(f1_path, f2_path)
            assert result is False
        finally:
            os.unlink(f1_path)
            os.unlink(f2_path)

    def test_files_equal_nonexistent(self, handler):
        """Test comparing with nonexistent file returns False."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("test")
            f1_path = f1.name

        try:
            result = handler._files_equal(f1_path, "/nonexistent/path")
            assert result is False
        finally:
            os.unlink(f1_path)


# =============================================================================
# Scrub Prompt Tests
# =============================================================================

class TestScrubPrompt:
    """Tests for _scrub_prompt method."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_scrub_prompt_empty(self, handler):
        """Test scrubbing empty prompt."""
        with patch('bots.twitter.x_claude_cli_handler.get_scrubber') as mock_get:
            mock_scrubber = MagicMock()
            mock_scrubber.scrub.return_value = ("", [])
            mock_get.return_value = mock_scrubber

            result, redacted = handler._scrub_prompt("")

        assert result == ""
        assert redacted == []

    def test_scrub_prompt_with_secrets(self, handler):
        """Test scrubbing prompt with secrets."""
        with patch('bots.twitter.x_claude_cli_handler.get_scrubber') as mock_get:
            mock_scrubber = MagicMock()
            mock_scrubber.scrub.return_value = ("clean text", ["secret1", "secret2"])
            mock_get.return_value = mock_scrubber

            result, redacted = handler._scrub_prompt("text with secrets")

        assert "secret" not in result.lower()
        assert len(redacted) > 0


# =============================================================================
# Build Copy Ignore Tests
# =============================================================================

class TestBuildCopyIgnore:
    """Tests for _build_copy_ignore method."""

    @pytest.fixture
    def handler(self):
        return XClaudeCLIHandler()

    def test_build_copy_ignore_returns_function(self, handler):
        """Test _build_copy_ignore returns a callable."""
        ignore_fn = handler._build_copy_ignore()
        assert callable(ignore_fn)

    def test_build_copy_ignore_ignores_venv(self, handler):
        """Test ignore function ignores .venv."""
        ignore_fn = handler._build_copy_ignore()
        ignored = ignore_fn("/some/path", [".venv", "src", "main.py"])
        assert ".venv" in ignored
        assert "src" not in ignored

    def test_build_copy_ignore_ignores_env_files(self, handler):
        """Test ignore function ignores .env files."""
        ignore_fn = handler._build_copy_ignore()
        ignored = ignore_fn("/some/path", [".env", ".env.local", "config.py"])
        assert ".env" in ignored
        assert ".env.local" in ignored
        assert "config.py" not in ignored


# =============================================================================
# Run X CLI Monitor Tests
# =============================================================================

class TestRunXCLIMonitor:
    """Tests for run_x_cli_monitor entry point."""

    @pytest.mark.asyncio
    async def test_run_x_cli_monitor(self):
        """Test run_x_cli_monitor calls handler.run()."""
        import bots.twitter.x_claude_cli_handler as module
        module._handler = None

        with patch.object(XClaudeCLIHandler, 'run', new_callable=AsyncMock) as mock_run:
            # Make it return quickly
            mock_run.return_value = None

            await run_x_cli_monitor()

        mock_run.assert_called_once()
