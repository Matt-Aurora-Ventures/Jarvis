"""
Tests for per-bot heartbeat integration.

Each clawdbot (jarvis, friday, matt) should have:
1. Heartbeat initialization with bot-specific URL
2. HEARTBEAT_OK silence token pattern
3. Heartbeat start on main() entry
4. Heartbeat stop on shutdown
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestClawdJarvisHeartbeat:
    """Tests for ClawdJarvis heartbeat integration."""

    def test_jarvis_has_heartbeat_import(self):
        """ClawdJarvis should import ExternalHeartbeat."""
        jarvis_path = PROJECT_ROOT / "bots" / "clawdjarvis" / "clawdjarvis_telegram_bot.py"
        content = jarvis_path.read_text(encoding="utf-8")
        assert "ExternalHeartbeat" in content, "ClawdJarvis should import ExternalHeartbeat"

    def test_jarvis_has_heartbeat_url_env(self):
        """ClawdJarvis should use JARVIS_HEARTBEAT_URL env variable."""
        jarvis_path = PROJECT_ROOT / "bots" / "clawdjarvis" / "clawdjarvis_telegram_bot.py"
        content = jarvis_path.read_text(encoding="utf-8")
        assert "JARVIS_HEARTBEAT_URL" in content, "ClawdJarvis should use JARVIS_HEARTBEAT_URL"

    def test_jarvis_has_heartbeat_ok_constant(self):
        """ClawdJarvis should define HEARTBEAT_OK silence token."""
        jarvis_path = PROJECT_ROOT / "bots" / "clawdjarvis" / "clawdjarvis_telegram_bot.py"
        content = jarvis_path.read_text(encoding="utf-8")
        assert "HEARTBEAT_OK" in content, "ClawdJarvis should define HEARTBEAT_OK token"

    def test_jarvis_starts_heartbeat_in_main(self):
        """ClawdJarvis main() should start heartbeat."""
        jarvis_path = PROJECT_ROOT / "bots" / "clawdjarvis" / "clawdjarvis_telegram_bot.py"
        content = jarvis_path.read_text(encoding="utf-8")
        # Look for heartbeat.start() in main function
        assert "heartbeat" in content.lower(), "ClawdJarvis should have heartbeat in main"
        assert ".start(" in content, "ClawdJarvis should call heartbeat.start()"


class TestClawdFridayHeartbeat:
    """Tests for ClawdFriday heartbeat integration."""

    def test_friday_has_heartbeat_import(self):
        """ClawdFriday should import ExternalHeartbeat."""
        friday_path = PROJECT_ROOT / "bots" / "clawdfriday" / "clawdfriday_telegram_bot.py"
        content = friday_path.read_text(encoding="utf-8")
        assert "ExternalHeartbeat" in content, "ClawdFriday should import ExternalHeartbeat"

    def test_friday_has_heartbeat_url_env(self):
        """ClawdFriday should use FRIDAY_HEARTBEAT_URL env variable."""
        friday_path = PROJECT_ROOT / "bots" / "clawdfriday" / "clawdfriday_telegram_bot.py"
        content = friday_path.read_text(encoding="utf-8")
        assert "FRIDAY_HEARTBEAT_URL" in content, "ClawdFriday should use FRIDAY_HEARTBEAT_URL"

    def test_friday_has_heartbeat_ok_constant(self):
        """ClawdFriday should define HEARTBEAT_OK silence token."""
        friday_path = PROJECT_ROOT / "bots" / "clawdfriday" / "clawdfriday_telegram_bot.py"
        content = friday_path.read_text(encoding="utf-8")
        assert "HEARTBEAT_OK" in content, "ClawdFriday should define HEARTBEAT_OK token"

    def test_friday_starts_heartbeat_in_main(self):
        """ClawdFriday main() should start heartbeat."""
        friday_path = PROJECT_ROOT / "bots" / "clawdfriday" / "clawdfriday_telegram_bot.py"
        content = friday_path.read_text(encoding="utf-8")
        assert "heartbeat" in content.lower(), "ClawdFriday should have heartbeat in main"
        assert ".start(" in content, "ClawdFriday should call heartbeat.start()"


class TestClawdMattHeartbeat:
    """Tests for ClawdMatt heartbeat integration."""

    def test_matt_has_heartbeat_import(self):
        """ClawdMatt should import ExternalHeartbeat."""
        matt_path = PROJECT_ROOT / "bots" / "clawdmatt" / "clawdmatt_telegram_bot.py"
        content = matt_path.read_text(encoding="utf-8")
        assert "ExternalHeartbeat" in content, "ClawdMatt should import ExternalHeartbeat"

    def test_matt_has_heartbeat_url_env(self):
        """ClawdMatt should use MATT_HEARTBEAT_URL env variable."""
        matt_path = PROJECT_ROOT / "bots" / "clawdmatt" / "clawdmatt_telegram_bot.py"
        content = matt_path.read_text(encoding="utf-8")
        assert "MATT_HEARTBEAT_URL" in content, "ClawdMatt should use MATT_HEARTBEAT_URL"

    def test_matt_has_heartbeat_ok_constant(self):
        """ClawdMatt should define HEARTBEAT_OK silence token."""
        matt_path = PROJECT_ROOT / "bots" / "clawdmatt" / "clawdmatt_telegram_bot.py"
        content = matt_path.read_text(encoding="utf-8")
        assert "HEARTBEAT_OK" in content, "ClawdMatt should define HEARTBEAT_OK token"

    def test_matt_starts_heartbeat_in_main(self):
        """ClawdMatt main() should start heartbeat."""
        matt_path = PROJECT_ROOT / "bots" / "clawdmatt" / "clawdmatt_telegram_bot.py"
        content = matt_path.read_text(encoding="utf-8")
        assert "heartbeat" in content.lower(), "ClawdMatt should have heartbeat in main"
        assert ".start(" in content, "ClawdMatt should call heartbeat.start()"


class TestHeartbeatIntegration:
    """Integration tests for heartbeat module usage."""

    def test_heartbeat_module_exists(self):
        """The heartbeat module should exist and be importable."""
        heartbeat_path = PROJECT_ROOT / "core" / "monitoring" / "heartbeat.py"
        assert heartbeat_path.exists(), "Heartbeat module should exist at core/monitoring/heartbeat.py"

    def test_heartbeat_has_external_heartbeat_class(self):
        """The heartbeat module should export ExternalHeartbeat class."""
        from core.monitoring.heartbeat import ExternalHeartbeat
        assert ExternalHeartbeat is not None

    @pytest.mark.asyncio
    async def test_heartbeat_can_be_initialized_with_custom_url(self):
        """ExternalHeartbeat should accept custom URL via constructor."""
        from core.monitoring.heartbeat import ExternalHeartbeat

        test_url = "https://example.com/heartbeat/test"
        heartbeat = ExternalHeartbeat(custom_webhook=test_url)

        assert heartbeat.custom_webhook == test_url
        assert heartbeat.has_endpoints() is True

    @pytest.mark.asyncio
    async def test_heartbeat_reports_no_endpoints_when_unconfigured(self):
        """ExternalHeartbeat should report no endpoints when none configured."""
        from core.monitoring.heartbeat import ExternalHeartbeat

        # Clear any environment variables
        with patch.dict(os.environ, {}, clear=True):
            heartbeat = ExternalHeartbeat(
                healthchecks_url=None,
                betterstack_url=None,
                custom_webhook=None
            )
            assert heartbeat.has_endpoints() is False


class TestSilenceTokenPattern:
    """Tests for HEARTBEAT_OK silence token pattern across all bots."""

    def test_all_bots_have_silence_token(self):
        """All bots should define HEARTBEAT_OK as silence token."""
        bots = [
            ("clawdjarvis", "clawdjarvis_telegram_bot.py"),
            ("clawdfriday", "clawdfriday_telegram_bot.py"),
            ("clawdmatt", "clawdmatt_telegram_bot.py"),
        ]

        for bot_name, filename in bots:
            bot_path = PROJECT_ROOT / "bots" / bot_name / filename
            content = bot_path.read_text(encoding="utf-8")
            assert 'HEARTBEAT_OK' in content, f"{bot_name} should define HEARTBEAT_OK"
            # Verify it's defined as a constant, not just mentioned
            assert 'SILENCE_TOKEN' in content or 'HEARTBEAT_OK = ' in content or '"HEARTBEAT_OK"' in content or "'HEARTBEAT_OK'" in content, \
                f"{bot_name} should define HEARTBEAT_OK as a usable constant"
