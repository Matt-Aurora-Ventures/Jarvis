"""
Tests for bots/shared/__init__.py comprehensive module exports.

TDD: Tests written FIRST before implementation.
Tests verify that:
1. All expected modules are exportable (or gracefully fail)
2. get_available_modules() returns correct loaded modules
3. Version info is accessible
4. Missing modules don't crash imports
"""

import pytest


class TestSharedPackageExports:
    """Test the bots.shared package exports."""

    def test_package_imports_without_crash(self):
        """Package should import without raising exceptions."""
        try:
            import bots.shared
            assert True
        except Exception as e:
            pytest.fail(f"Package import crashed: {e}")

    def test_version_is_accessible(self):
        """Package should expose __version__."""
        from bots.shared import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        assert __version__ == "2.0.0"

    def test_all_dunder_is_list(self):
        """Package should have __all__ as a list."""
        import bots.shared

        assert hasattr(bots.shared, "__all__")
        assert isinstance(bots.shared.__all__, list)

    def test_get_available_modules_function_exists(self):
        """Package should expose get_available_modules function."""
        from bots.shared import get_available_modules

        assert callable(get_available_modules)

    def test_get_available_modules_returns_dict(self):
        """get_available_modules should return a dictionary."""
        from bots.shared import get_available_modules

        result = get_available_modules()

        assert isinstance(result, dict)
        assert "loaded" in result
        assert "failed" in result

    def test_get_available_modules_loaded_is_list(self):
        """get_available_modules loaded field should be a list."""
        from bots.shared import get_available_modules

        result = get_available_modules()

        assert isinstance(result["loaded"], list)
        assert isinstance(result["failed"], list)


class TestExistingModuleExports:
    """Test exports from existing, confirmed modules."""

    def test_computer_capabilities_exports(self):
        """Computer capabilities functions should be exportable."""
        from bots.shared import (
            browse_web,
            control_computer,
            send_telegram_web,
            read_telegram_web,
            check_remote_status,
            get_capabilities_prompt,
            COMPUTER_CAPABILITIES_PROMPT,
        )

        assert callable(browse_web)
        assert callable(control_computer)
        assert callable(send_telegram_web)
        assert callable(read_telegram_web)
        assert callable(check_remote_status)
        assert callable(get_capabilities_prompt)
        assert isinstance(COMPUTER_CAPABILITIES_PROMPT, str)

    def test_life_control_commands_export(self):
        """Life control commands should be exportable if available."""
        try:
            from bots.shared import register_life_commands
            assert callable(register_life_commands)
        except ImportError:
            pytest.skip("life_control_commands not fully available")

    def test_coordination_exports(self):
        """Coordination module exports should be available."""
        from bots.shared import (
            BotCoordinator,
            BotRole,
            TaskPriority,
            TaskStatus,
            CoordinationTask,
            BotMessage,
            BotStatus,
            get_coordinator,
        )

        assert BotCoordinator is not None
        assert BotRole is not None
        assert TaskPriority is not None
        assert TaskStatus is not None
        assert CoordinationTask is not None
        assert BotMessage is not None
        assert BotStatus is not None
        assert callable(get_coordinator)


class TestNewModuleExports:
    """Test exports from new modules (may be missing during development)."""

    def test_self_healing_exports(self):
        """Self healing module exports should be available if module exists."""
        try:
            from bots.shared import (
                ProcessWatchdog,
                SelfHealingConfig,
            )
            assert ProcessWatchdog is not None
            assert SelfHealingConfig is not None
        except ImportError:
            # Module may not exist yet
            pytest.skip("self_healing module not yet available")

    def test_observability_exports(self):
        """Observability module exports should be available if module exists."""
        try:
            from bots.shared import ClawdBotObservability
            assert ClawdBotObservability is not None
        except ImportError:
            pytest.skip("observability module not yet available")

    def test_heartbeat_exports(self):
        """Heartbeat module exports should be available if module exists."""
        try:
            from bots.shared import HeartbeatManager
            assert HeartbeatManager is not None
        except ImportError:
            pytest.skip("heartbeat module not yet available")

    def test_campaign_orchestrator_exports(self):
        """Campaign orchestrator exports should be available if module exists."""
        try:
            from bots.shared import CampaignOrchestrator
            assert CampaignOrchestrator is not None
        except ImportError:
            pytest.skip("campaign_orchestrator module not yet available")

    def test_sleep_compute_exports(self):
        """Sleep compute exports should be available if module exists."""
        try:
            from bots.shared import SleepComputeScheduler
            assert SleepComputeScheduler is not None
        except ImportError:
            pytest.skip("sleep_compute module not yet available")

    def test_moltbook_exports(self):
        """Moltbook exports should be available if module exists."""
        try:
            from bots.shared import MoltbookClient
            assert MoltbookClient is not None
        except ImportError:
            pytest.skip("moltbook module not yet available")

    def test_personality_exports(self):
        """Personality exports should be available if module exists."""
        try:
            from bots.shared import PersonalityLoader
            assert PersonalityLoader is not None
        except ImportError:
            pytest.skip("personality module not yet available")

    def test_cost_tracker_exports(self):
        """Cost tracker exports should be available if module exists."""
        try:
            from bots.shared import CostTracker
            assert CostTracker is not None
        except ImportError:
            pytest.skip("cost_tracker module not yet available")

    def test_command_registry_exports(self):
        """Command registry exports should be available if module exists."""
        try:
            from bots.shared import CommandRegistry
            assert CommandRegistry is not None
        except ImportError:
            pytest.skip("command_registry module not yet available")

    def test_error_handler_exports(self):
        """Error handler exports should be available if module exists."""
        try:
            from bots.shared import ErrorHandler
            assert ErrorHandler is not None
        except ImportError:
            pytest.skip("error_handler module not yet available")

    def test_message_queue_exports(self):
        """Message queue exports should be available if module exists."""
        try:
            from bots.shared import MessageQueue
            assert MessageQueue is not None
        except ImportError:
            pytest.skip("message_queue module not yet available")

    def test_rate_limiter_exports(self):
        """Rate limiter exports should be available if module exists."""
        try:
            from bots.shared import RateLimiter
            assert RateLimiter is not None
        except ImportError:
            pytest.skip("rate_limiter module not yet available")

    def test_security_exports(self):
        """Security module exports should be available if module exists."""
        try:
            from bots.shared import SecurityManager
            assert SecurityManager is not None
        except ImportError:
            pytest.skip("security module not yet available")

    def test_state_manager_exports(self):
        """State manager exports should be available if module exists."""
        try:
            from bots.shared import StateManager
            assert StateManager is not None
        except ImportError:
            pytest.skip("state_manager module not yet available")

    def test_conversation_memory_exports(self):
        """Conversation memory exports should be available if module exists."""
        try:
            from bots.shared import ConversationMemory
            assert ConversationMemory is not None
        except ImportError:
            pytest.skip("conversation_memory module not yet available")

    def test_scheduler_exports(self):
        """Scheduler exports should be available if module exists."""
        try:
            from bots.shared import TaskScheduler
            assert TaskScheduler is not None
        except ImportError:
            pytest.skip("scheduler module not yet available")

    def test_user_preferences_exports(self):
        """User preferences exports should be available if module exists."""
        try:
            from bots.shared import UserPreferencesManager
            assert UserPreferencesManager is not None
        except ImportError:
            pytest.skip("user_preferences module not yet available")

    def test_analytics_exports(self):
        """Analytics exports should be available if module exists."""
        try:
            from bots.shared import AnalyticsCollector
            assert AnalyticsCollector is not None
        except ImportError:
            pytest.skip("analytics module not yet available")

    def test_webhook_handler_exports(self):
        """Webhook handler exports should be available if module exists."""
        try:
            from bots.shared import WebhookHandler
            assert WebhookHandler is not None
        except ImportError:
            pytest.skip("webhook_handler module not yet available")

    def test_feature_flags_exports(self):
        """Feature flags exports should be available if module exists."""
        try:
            from bots.shared import FeatureFlags
            assert FeatureFlags is not None
        except ImportError:
            pytest.skip("feature_flags module not yet available")

    def test_response_templates_exports(self):
        """Response templates exports should be available if module exists."""
        try:
            from bots.shared import ResponseTemplates
            assert ResponseTemplates is not None
        except ImportError:
            pytest.skip("response_templates module not yet available")

    def test_logging_utils_exports(self):
        """Logging utils exports should be available if module exists."""
        try:
            from bots.shared import setup_bot_logging
            assert callable(setup_bot_logging)
        except ImportError:
            pytest.skip("logging_utils module not yet available")


class TestGetAvailableModulesDetails:
    """Detailed tests for get_available_modules functionality."""

    def test_loaded_modules_includes_computer_capabilities(self):
        """Loaded modules should include computer_capabilities."""
        from bots.shared import get_available_modules

        result = get_available_modules()

        assert "computer_capabilities" in result["loaded"]

    def test_loaded_modules_includes_coordination(self):
        """Loaded modules should include coordination."""
        from bots.shared import get_available_modules

        result = get_available_modules()

        assert "coordination" in result["loaded"]

    def test_failed_modules_tracks_import_errors(self):
        """Failed modules should list modules that failed to import."""
        from bots.shared import get_available_modules

        result = get_available_modules()

        # At least the structure should exist
        assert isinstance(result["failed"], list)

    def test_get_available_modules_includes_count(self):
        """get_available_modules should include total counts."""
        from bots.shared import get_available_modules

        result = get_available_modules()

        assert "total_loaded" in result
        assert "total_failed" in result
        assert isinstance(result["total_loaded"], int)
        assert isinstance(result["total_failed"], int)
        assert result["total_loaded"] == len(result["loaded"])
        assert result["total_failed"] == len(result["failed"])


class TestGracefulDegradation:
    """Test that missing modules don't break the package."""

    def test_missing_module_doesnt_crash_import(self):
        """Importing bots.shared should work even if some modules are missing."""
        # This test verifies the try/except import pattern works
        import importlib
        import sys

        # Clear any cached imports
        if "bots.shared" in sys.modules:
            # Get current loaded count
            from bots.shared import get_available_modules
            result = get_available_modules()
            # Should have at least some loaded modules
            assert result["total_loaded"] >= 2  # computer_capabilities + coordination

    def test_all_exports_are_valid(self):
        """All items in __all__ should be importable from the package."""
        import bots.shared

        for name in bots.shared.__all__:
            assert hasattr(bots.shared, name), f"__all__ contains '{name}' but it's not accessible"
