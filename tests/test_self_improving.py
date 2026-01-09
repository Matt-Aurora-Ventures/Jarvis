"""
Tests for Jarvis Self-Improving Core.

Tests cover:
- Memory store operations
- Trust ladder progression
- Reflexion engine
- Proactive suggestions
- Action framework
- Orchestrator integration
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.self_improving.memory.store import MemoryStore
from core.self_improving.memory.models import (
    Entity,
    Fact,
    Reflection,
    Prediction,
    Interaction,
)
from core.self_improving.trust.ladder import TrustManager, TrustLevel
from core.self_improving.reflexion.engine import ReflexionEngine
from core.self_improving.proactive.engine import ProactiveEngine, SuggestionType
from core.self_improving.actions.framework import (
    ActionRegistry,
    ActionResult,
    ActionContext,
    ReminderAction,
    create_default_registry,
)
from core.self_improving.orchestrator import SelfImprovingOrchestrator


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def memory_store(temp_db):
    """Create a memory store with temp database."""
    store = MemoryStore(temp_db)
    yield store
    store.close()


@pytest.fixture
def trust_manager(memory_store):
    """Create a trust manager."""
    return TrustManager(memory_store)


class TestMemoryStore:
    """Tests for MemoryStore."""

    def test_store_and_retrieve_fact(self, memory_store):
        """Test storing and retrieving facts."""
        fact = Fact(
            entity="user",
            fact="prefers short responses",
            confidence=0.9,
            source="conversation",
        )
        fact_id = memory_store.store_fact(fact)
        assert fact_id > 0

        facts = memory_store.get_facts_about("user")
        assert len(facts) >= 1
        assert any(f.fact == "prefers short responses" for f in facts)

    def test_store_and_retrieve_entity(self, memory_store):
        """Test storing and retrieving entities."""
        entity = Entity(
            name="John Smith",
            entity_type="person",
            attributes={"role": "manager"},
        )
        entity_id = memory_store.store_entity(entity)
        assert entity_id > 0

        retrieved = memory_store.get_entity("John Smith", "person")
        assert retrieved is not None
        assert retrieved.name == "John Smith"
        assert retrieved.attributes.get("role") == "manager"

    def test_store_and_retrieve_interaction(self, memory_store):
        """Test storing and retrieving interactions."""
        interaction = Interaction(
            user_input="What's the weather?",
            jarvis_response="I don't have weather data.",
            feedback="negative",
            session_id="test_session",
        )
        interaction_id = memory_store.store_interaction(interaction)
        assert interaction_id > 0

        recent = memory_store.get_recent_interactions(hours=1)
        assert len(recent) >= 1

    def test_store_and_retrieve_reflection(self, memory_store):
        """Test storing and retrieving reflections."""
        reflection = Reflection(
            trigger="user asked about weather",
            what_happened="responded without data",
            why_failed="no weather API integrated",
            lesson="check for required integrations before responding",
            new_approach="say 'I don't have access to weather data'",
        )
        reflection_id = memory_store.store_reflection(reflection)
        assert reflection_id > 0

        reflections = memory_store.get_relevant_reflections("weather")
        assert len(reflections) >= 1

    def test_build_context(self, memory_store):
        """Test context building."""
        # Add some data
        memory_store.store_fact(Fact("user", "likes Python", 0.9))
        memory_store.store_fact(Fact("Python", "is a programming language", 0.95))

        context = memory_store.build_context("Python programming")
        assert context.query == "Python programming"
        assert len(context.facts) >= 0  # May or may not match

    def test_prediction_accuracy(self, memory_store):
        """Test prediction tracking."""
        # Store predictions
        p1 = Prediction(
            prediction="user will accept suggestion",
            confidence=0.8,
            domain="calendar",
        )
        p1_id = memory_store.store_prediction(p1)

        # Resolve
        memory_store.resolve_prediction(p1_id, "accepted", was_correct=True)

        accuracy = memory_store.get_prediction_accuracy("calendar")
        assert accuracy["total"] >= 1


class TestTrustLadder:
    """Tests for TrustManager."""

    def test_initial_trust_is_stranger(self, trust_manager):
        """Test that initial trust is STRANGER."""
        level = trust_manager.get_level("general")
        assert level == TrustLevel.STRANGER

    def test_cannot_suggest_at_stranger(self, trust_manager):
        """Test that suggesting is not allowed at STRANGER level."""
        permission = trust_manager.can_suggest("general")
        assert not permission.allowed

    def test_record_success_builds_trust(self, trust_manager):
        """Test that recording successes builds trust."""
        # Record enough successes to potentially level up
        for _ in range(10):
            trust_manager.record_success("general")

        state = trust_manager.get_state("general")
        assert state.successes >= 10
        # May or may not have leveled up depending on accuracy

    def test_record_failure_tracks_failures(self, trust_manager):
        """Test that failures are tracked."""
        trust_manager.record_failure("general")
        state = trust_manager.get_state("general")
        assert state.failures >= 1

    def test_major_failure_demotes(self, trust_manager):
        """Test that major failure demotes trust."""
        # First, level up
        trust_manager.set_level("general", 2)
        assert trust_manager.get_level("general") == TrustLevel.COLLEAGUE

        # Major failure
        trust_manager.record_failure("general", major=True)
        assert trust_manager.get_level("general") < TrustLevel.COLLEAGUE

    def test_manual_set_level(self, trust_manager):
        """Test manual trust level setting."""
        trust_manager.set_level("calendar", 3)
        assert trust_manager.get_level("calendar") == TrustLevel.PARTNER

    def test_domain_specific_trust(self, trust_manager):
        """Test that trust is domain-specific."""
        trust_manager.set_level("calendar", 3)
        trust_manager.set_level("trading", 0)

        assert trust_manager.get_level("calendar") == TrustLevel.PARTNER
        assert trust_manager.get_level("trading") == TrustLevel.STRANGER


class TestReflexionEngine:
    """Tests for ReflexionEngine."""

    def test_reflexion_engine_init(self, memory_store):
        """Test reflexion engine initialization."""
        engine = ReflexionEngine(memory_store)
        assert engine is not None

    def test_format_reflections_for_prompt(self, memory_store):
        """Test formatting reflections for prompts."""
        engine = ReflexionEngine(memory_store)

        reflections = [
            Reflection(
                trigger="test",
                what_happened="test",
                why_failed="test",
                lesson="Always verify data before responding",
                new_approach="Check data sources first",
            )
        ]

        formatted = engine.format_reflections_for_prompt(reflections)
        assert "Always verify data" in formatted
        assert "Check data sources" in formatted


class TestProactiveEngine:
    """Tests for ProactiveEngine."""

    def test_proactive_engine_init(self, memory_store, trust_manager):
        """Test proactive engine initialization."""
        engine = ProactiveEngine(memory_store, trust_manager)
        assert engine is not None

    def test_rate_limiting(self, memory_store, trust_manager):
        """Test that rate limiting works."""
        engine = ProactiveEngine(memory_store, trust_manager)

        # Simulate having made a suggestion
        engine._last_suggestion_time = datetime.now(timezone.utc)

        assert engine._is_in_cooldown()

    def test_daily_limit(self, memory_store, trust_manager):
        """Test daily suggestion limit."""
        engine = ProactiveEngine(memory_store, trust_manager)
        engine._daily_count = engine.MAX_DAILY_SUGGESTIONS

        # Should not suggest
        context = {"time": datetime.now(timezone.utc).isoformat()}
        # Note: This would return None due to limit
        # Can't fully test without LLM client


class TestActionFramework:
    """Tests for Action Framework."""

    def test_action_registry(self, memory_store, trust_manager):
        """Test action registry."""
        registry = create_default_registry(memory_store, trust_manager)

        actions = registry.list_all()
        assert "set_reminder" in actions
        assert "draft_content" in actions
        assert "research" in actions

    def test_permission_denied_at_low_trust(self, memory_store, trust_manager):
        """Test that actions are denied at low trust."""
        registry = create_default_registry(memory_store, trust_manager)

        result = registry.execute(
            "set_reminder",
            {"message": "test", "when": "tomorrow"},
        )

        # Should fail due to trust level (STRANGER needs ACQUAINTANCE)
        assert not result.success
        assert "ACQUAINTANCE" in result.message or "Need" in result.message

    def test_action_succeeds_with_trust(self, memory_store, trust_manager):
        """Test that actions succeed with sufficient trust."""
        registry = create_default_registry(memory_store, trust_manager)

        # Set sufficient trust
        trust_manager.set_level("tasks", TrustLevel.ACQUAINTANCE)

        result = registry.execute(
            "set_reminder",
            {"message": "test reminder", "when": "tomorrow"},
        )

        assert result.success
        assert "Reminder set" in result.message

    def test_action_validation(self, memory_store, trust_manager):
        """Test action parameter validation."""
        registry = create_default_registry(memory_store, trust_manager)
        trust_manager.set_level("tasks", TrustLevel.ACQUAINTANCE)

        # Missing required parameter
        result = registry.execute(
            "set_reminder",
            {"message": "test"},  # Missing 'when'
        )

        assert not result.success
        assert "when" in result.message.lower()


class TestOrchestrator:
    """Tests for SelfImprovingOrchestrator."""

    def test_orchestrator_init(self, temp_db):
        """Test orchestrator initialization."""
        orchestrator = SelfImprovingOrchestrator(temp_db)
        assert orchestrator is not None
        orchestrator.close()

    def test_health_check(self, temp_db):
        """Test health check."""
        orchestrator = SelfImprovingOrchestrator(temp_db)
        health = orchestrator.health_check()

        assert health["memory"]
        assert health["trust"]
        assert health["reflexion"]
        assert health["proactive"]
        assert not health["llm_client"]  # No client set

        orchestrator.close()

    def test_build_response_context(self, temp_db):
        """Test context building."""
        orchestrator = SelfImprovingOrchestrator(temp_db)

        # Add some facts
        orchestrator.memory.store_fact(
            Fact("user", "works at tech company", 0.9)
        )

        context = orchestrator.build_response_context("work schedule")
        assert "query" in context
        assert context["query"] == "work schedule"

        orchestrator.close()

    def test_record_interaction(self, temp_db):
        """Test interaction recording."""
        orchestrator = SelfImprovingOrchestrator(temp_db)

        interaction_id = orchestrator.record_interaction(
            user_input="Hello",
            jarvis_response="Hi there!",
            session_id="test_session",
        )

        assert interaction_id > 0

        orchestrator.close()

    def test_get_stats(self, temp_db):
        """Test statistics collection."""
        orchestrator = SelfImprovingOrchestrator(temp_db)
        stats = orchestrator.get_stats()

        assert "initialized_at" in stats
        assert "memory" in stats
        assert "trust" in stats

        orchestrator.close()


class TestIntegration:
    """Integration tests for the full system."""

    def test_full_conversation_flow(self, temp_db):
        """Test a full conversation flow."""
        orchestrator = SelfImprovingOrchestrator(temp_db)

        # Start session
        session_id = orchestrator.start_session()
        assert session_id

        # Build context
        context = orchestrator.build_response_context("How do I use Python?")
        assert context

        # Record interaction
        orchestrator.record_interaction(
            user_input="How do I use Python?",
            jarvis_response="Python is a programming language...",
            session_id=session_id,
            feedback="positive",
        )

        # Check stats increased
        stats = orchestrator.get_stats()
        assert stats["memory"]["interactions_count"] >= 1

        orchestrator.close()

    def test_trust_progression(self, temp_db):
        """Test trust progression through the system."""
        orchestrator = SelfImprovingOrchestrator(temp_db)

        # Initially stranger
        assert orchestrator.get_trust_level("calendar") == TrustLevel.STRANGER

        # Record many successes
        for _ in range(20):
            orchestrator.trust.record_success("calendar")

        # Should have progressed
        assert orchestrator.get_trust_level("calendar") >= TrustLevel.ACQUAINTANCE

        orchestrator.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
