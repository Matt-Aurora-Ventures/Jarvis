"""
Integration tests for Self-Improving Core integrations.

Tests cover:
- Integration layer (singleton orchestrator, context enrichment)
- Conversation integration
- Daemon integration
- API endpoints
- Scheduler
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        os.unlink(db_path)
    except Exception:
        pass


class TestIntegrationLayerDirect:
    """Tests for the integration layer using direct orchestrator."""

    def test_orchestrator_creates_successfully(self, temp_db):
        """Test orchestrator can be created with temp db."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator

        orch = SelfImprovingOrchestrator(db_path=temp_db)
        assert orch is not None
        assert orch.memory is not None
        assert orch.trust is not None
        orch.close()

    def test_context_building(self, temp_db):
        """Test context building works."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator

        orch = SelfImprovingOrchestrator(db_path=temp_db)

        context = orch.build_response_context("test query")

        assert "query" in context
        assert context["query"] == "test query"

        orch.close()

    def test_record_interaction(self, temp_db):
        """Test recording interactions."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator

        orch = SelfImprovingOrchestrator(db_path=temp_db)

        interaction_id = orch.record_interaction(
            user_input="Hello",
            jarvis_response="Hi there!",
            session_id="test_session",
        )

        assert interaction_id > 0

        orch.close()

    def test_health_check(self, temp_db):
        """Test health check."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator

        orch = SelfImprovingOrchestrator(db_path=temp_db)

        health = orch.health_check()

        assert health["memory"]
        assert health["trust"]
        assert health["reflexion"]

        orch.close()

    def test_trust_operations(self, temp_db):
        """Test trust level operations."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator
        from core.self_improving.trust.ladder import TrustLevel

        orch = SelfImprovingOrchestrator(db_path=temp_db)

        # Initially should be STRANGER (0)
        level = orch.get_trust_level("test_domain")
        assert level == TrustLevel.STRANGER

        # Record success
        orch.trust.record_success("test_domain")

        orch.close()


class TestConversationIntegration:
    """Tests for conversation.py integration."""

    def test_self_improving_import_available(self):
        """Test that self-improving can be imported."""
        try:
            from core.self_improving import integration as self_improving
            available = True
        except ImportError:
            available = False

        assert available, "Self-improving integration should be importable"

    def test_conversation_has_self_improving_flag(self):
        """Test that conversation has SELF_IMPROVING_ENABLED flag."""
        from core import conversation

        assert hasattr(conversation, "SELF_IMPROVING_ENABLED")

    def test_record_conversation_turn_has_session_id(self):
        """Test that _record_conversation_turn has session_id parameter."""
        from core import conversation
        import inspect

        sig = inspect.signature(conversation._record_conversation_turn)
        params = list(sig.parameters.keys())

        assert "session_id" in params, "_record_conversation_turn should have session_id parameter"


class TestDaemonIntegration:
    """Tests for daemon.py integration."""

    def test_daemon_has_self_improving_flag(self):
        """Test that daemon has SELF_IMPROVING_AVAILABLE flag."""
        from core import daemon

        assert hasattr(daemon, "SELF_IMPROVING_AVAILABLE")


class TestAPIIntegration:
    """Tests for API server integration."""

    def test_brain_endpoints_defined(self):
        """Test that brain endpoints are defined in API server."""
        try:
            from core import api_server

            handler_class = api_server.JarvisAPIHandler

            assert hasattr(handler_class, "_handle_brain_stats")
            assert hasattr(handler_class, "_handle_brain_health")
            assert hasattr(handler_class, "_handle_brain_trust")
        except ModuleNotFoundError as e:
            pytest.skip(f"Optional dependency missing: {e}")

    def test_self_improving_available_in_api(self):
        """Test that SELF_IMPROVING_AVAILABLE is defined."""
        try:
            from core import api_server

            assert hasattr(api_server, "SELF_IMPROVING_AVAILABLE")
        except ModuleNotFoundError as e:
            pytest.skip(f"Optional dependency missing: {e}")


class TestTelegramIntegration:
    """Tests for Telegram bot integration."""

    def test_brain_command_in_bot_source(self):
        """Test that brain command is defined in bot.py source."""
        from pathlib import Path

        bot_path = Path(__file__).parent.parent / "tg_bot" / "bot.py"

        if not bot_path.exists():
            pytest.skip("Telegram bot file not found")

        content = bot_path.read_text()

        assert "async def brain" in content, "Bot should have brain command"
        assert "SELF_IMPROVING_AVAILABLE" in content, "Bot should have SELF_IMPROVING_AVAILABLE flag"
        assert 'CommandHandler("brain"' in content, "Bot should register brain command handler"


class TestSchedulerIntegration:
    """Tests for scheduler integration."""

    def test_scheduler_creation(self, temp_db):
        """Test scheduler can be created."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator
        from core.self_improving.scheduler import SelfImprovingScheduler

        orch = SelfImprovingOrchestrator(temp_db)
        scheduler = SelfImprovingScheduler(orch)

        assert scheduler is not None
        assert scheduler.orchestrator is orch

        orch.close()

    def test_scheduler_status(self, temp_db):
        """Test scheduler status."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator
        from core.self_improving.scheduler import SelfImprovingScheduler

        orch = SelfImprovingOrchestrator(temp_db)
        scheduler = SelfImprovingScheduler(orch)

        status = scheduler.get_status()

        assert "running" in status
        assert "apscheduler_available" in status

        orch.close()


class TestEndToEndFlow:
    """End-to-end integration tests."""

    def test_full_learning_flow(self, temp_db):
        """Test complete learning flow from conversation to memory."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator

        orch = SelfImprovingOrchestrator(db_path=temp_db)

        # 1. Build context before response
        context = orch.build_response_context("How do I use Python?")
        assert "query" in context

        # 2. Record the conversation
        interaction_id = orch.record_interaction(
            user_input="How do I use Python?",
            jarvis_response="Python is a versatile programming language...",
            session_id="test_e2e",
        )
        assert interaction_id > 0

        # 3. Get stats to verify storage
        stats = orch.get_stats()
        assert "memory" in stats
        assert stats["memory"]["interactions_count"] >= 1

        orch.close()

    def test_trust_progression_flow(self, temp_db):
        """Test trust level progression through successes."""
        from core.self_improving.orchestrator import SelfImprovingOrchestrator
        from core.self_improving.trust.ladder import TrustLevel

        orch = SelfImprovingOrchestrator(db_path=temp_db)

        # Start at STRANGER
        initial_level = orch.get_trust_level("test_domain")
        assert initial_level == TrustLevel.STRANGER

        # Record many successes
        for _ in range(20):
            orch.trust.record_success("test_domain")

        # Should have progressed
        new_level = orch.get_trust_level("test_domain")
        assert new_level >= TrustLevel.ACQUAINTANCE

        orch.close()


class TestIntegrationModule:
    """Tests for the integration module functions."""

    def test_format_context_for_prompt_exists(self):
        """Test format_context_for_prompt function exists."""
        from core.self_improving import integration

        assert hasattr(integration, "format_context_for_prompt")

    def test_enrich_context_exists(self):
        """Test enrich_context function exists."""
        from core.self_improving import integration

        assert hasattr(integration, "enrich_context")

    def test_record_conversation_exists(self):
        """Test record_conversation function exists."""
        from core.self_improving import integration

        assert hasattr(integration, "record_conversation")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
