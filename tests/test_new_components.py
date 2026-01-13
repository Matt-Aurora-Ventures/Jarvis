#!/usr/bin/env python3
"""
JARVIS New Components Test Suite

Tests all newly added components:
- LLM providers and router
- Autonomous web agent
- Proactive suggestions
- System tray
- State sync

Run: python -m pytest tests/test_new_components.py -v
"""

import asyncio
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ============================================================================
# LLM Provider Tests
# ============================================================================

class TestLLMProviders:
    """Tests for the unified LLM provider system."""

    def test_imports(self):
        """Test that all LLM components import correctly."""
        from core.llm import (
            LLMProvider,
            LLMConfig,
            LLMResponse,
            Message,
            UnifiedLLM,
            get_default_configs,
        )
        assert LLMProvider.OLLAMA is not None
        assert LLMProvider.GROQ is not None
        assert LLMProvider.XAI is not None

    def test_config_creation(self):
        """Test LLMConfig creation."""
        from core.llm import LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.GROQ,
            model="llama-3.3-70b-versatile",
            api_key="test-key",
            priority=1,
        )
        assert config.provider == LLMProvider.GROQ
        assert config.model == "llama-3.3-70b-versatile"
        assert config.priority == 1

    def test_message_creation(self):
        """Test Message dataclass."""
        from core.llm import Message

        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    @pytest.mark.asyncio
    async def test_unified_llm_init(self):
        """Test UnifiedLLM initialization."""
        from core.llm import UnifiedLLM, LLMConfig, LLMProvider

        llm = UnifiedLLM()

        # Add a mock provider
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="test-model",
        )
        llm.add_provider(config)

        assert LLMProvider.OLLAMA in llm.providers

    def test_default_configs(self):
        """Test default configuration loading from env."""
        from core.llm import get_default_configs

        configs = get_default_configs()
        # Should at least have Ollama (always added)
        assert len(configs) >= 1
        assert any(c.provider.value == "ollama" for c in configs)


class TestLLMRouter:
    """Tests for the LLM router."""

    def test_task_types(self):
        """Test TaskType enum."""
        from core.llm import TaskType

        assert TaskType.TRADING is not None
        assert TaskType.CHAT is not None
        assert TaskType.PRIVATE is not None

    def test_routing_rules(self):
        """Test routing rule configuration."""
        from core.llm.router import DEFAULT_RULES, TaskType

        assert TaskType.TRADING in DEFAULT_RULES
        assert TaskType.PRIVATE in DEFAULT_RULES

        # Private should prefer Ollama
        private_rule = DEFAULT_RULES[TaskType.PRIVATE]
        from core.llm import LLMProvider
        assert LLMProvider.OLLAMA in private_rule.preferred_providers

    @pytest.mark.asyncio
    async def test_router_init(self):
        """Test LLMRouter initialization."""
        from core.llm import LLMRouter

        router = LLMRouter()
        assert router.rules is not None
        assert len(router.rules) > 0


# ============================================================================
# Autonomous Web Agent Tests
# ============================================================================

class TestAutonomousWebAgent:
    """Tests for the autonomous web research agent."""

    def test_imports(self):
        """Test that web agent imports correctly."""
        from core.autonomous_web_agent import (
            AutonomousWebAgent,
            ResearchTopic,
            KnowledgeEntry,
            get_research_agent,
        )
        assert AutonomousWebAgent is not None

    def test_research_topic(self):
        """Test ResearchTopic dataclass."""
        from core.autonomous_web_agent import ResearchTopic

        topic = ResearchTopic(
            topic="Bitcoin analysis",
            priority=8,
            category="crypto",
            keywords=["bitcoin", "btc"],
        )
        assert topic.topic == "Bitcoin analysis"
        assert topic.priority == 8
        assert "bitcoin" in topic.keywords

    def test_knowledge_entry(self):
        """Test KnowledgeEntry dataclass."""
        from core.autonomous_web_agent import KnowledgeEntry

        entry = KnowledgeEntry(
            id="test123",
            topic="crypto",
            title="Test Entry",
            summary="A test summary",
            source_url="https://example.com",
            source_name="Test Source",
            extracted_at=datetime.now().isoformat(),
            confidence=0.8,
            category="crypto",
        )
        assert entry.id == "test123"
        assert entry.confidence == 0.8

    def test_agent_initialization(self):
        """Test agent creation."""
        from core.autonomous_web_agent import AutonomousWebAgent

        agent = AutonomousWebAgent()
        assert agent.sources is not None
        assert len(agent.sources) > 0

    def test_add_topic(self):
        """Test adding research topics."""
        from core.autonomous_web_agent import AutonomousWebAgent

        agent = AutonomousWebAgent()
        agent.add_topic("Solana DeFi", priority=7, category="crypto")

        assert len(agent.topic_queue) > 0
        topic = agent.get_next_topic()
        assert topic is not None


# ============================================================================
# Proactive Suggestion Tests
# ============================================================================

class TestProactiveSuggestions:
    """Tests for the proactive suggestion system."""

    def test_imports(self):
        """Test that proactive module imports correctly."""
        from core.proactive import (
            Suggestion,
            SuggestionCategory,
            Priority,
            TriggerType,
            get_suggestion_engine,
        )
        assert Suggestion is not None
        assert SuggestionCategory.BRIEFING is not None

    def test_suggestion_creation(self):
        """Test Suggestion dataclass."""
        from core.proactive import Suggestion, SuggestionCategory, Priority, TriggerType

        suggestion = Suggestion(
            id="test123",
            category=SuggestionCategory.ALERT,
            priority=Priority.HIGH,
            title="Test Alert",
            content="This is a test alert",
            trigger_type=TriggerType.TIME,
        )
        assert suggestion.title == "Test Alert"
        assert suggestion.priority == Priority.HIGH
        assert not suggestion.is_expired()

    def test_suggestion_expiry(self):
        """Test suggestion expiration."""
        from core.proactive import Suggestion, SuggestionCategory, Priority, TriggerType

        # Create expired suggestion
        suggestion = Suggestion(
            id="expired",
            category=SuggestionCategory.ALERT,
            priority=Priority.LOW,
            title="Expired",
            content="Expired content",
            trigger_type=TriggerType.TIME,
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert suggestion.is_expired()

    def test_engine_initialization(self):
        """Test ProactiveSuggestionEngine initialization."""
        from core.proactive import ProactiveSuggestionEngine

        engine = ProactiveSuggestionEngine()
        assert engine.triggers is not None
        assert len(engine.triggers) > 0  # Default triggers

    def test_add_price_alert(self):
        """Test adding price alert trigger."""
        from core.proactive import ProactiveSuggestionEngine

        engine = ProactiveSuggestionEngine()
        initial_count = len(engine.triggers)

        engine.add_price_alert("BTC", 100000, "above")
        assert len(engine.triggers) == initial_count + 1

    def test_add_scheduled_reminder(self):
        """Test adding scheduled reminder."""
        from core.proactive import ProactiveSuggestionEngine

        engine = ProactiveSuggestionEngine()
        engine.add_scheduled_reminder(
            "Test Reminder",
            "Test message",
            times=[time(9, 0)],
        )
        # Should have added a new trigger
        assert any(t.name == "reminder_Test Reminder" for t in engine.triggers)


# ============================================================================
# System Tray Tests
# ============================================================================

class TestSystemTray:
    """Tests for the system tray UI."""

    def test_imports(self):
        """Test that system tray imports correctly."""
        from core.system_tray import (
            JarvisSystemTray,
            TrayState,
            CrossSystemStateSync,
            get_tray,
            get_state_sync,
        )
        assert JarvisSystemTray is not None

    def test_tray_state(self):
        """Test TrayState dataclass."""
        from core.system_tray import TrayState

        state = TrayState()
        assert not state.voice_enabled
        assert not state.daemon_running

        state.voice_enabled = True
        assert state.voice_enabled

    def test_state_sync_init(self):
        """Test CrossSystemStateSync initialization."""
        from core.system_tray import CrossSystemStateSync

        sync = CrossSystemStateSync()
        assert sync._state is not None
        assert 'components' in sync._state

    def test_state_sync_context(self):
        """Test setting and getting context."""
        from core.system_tray import CrossSystemStateSync

        sync = CrossSystemStateSync()
        sync.set_context("test_key", "test_value")
        assert sync.get_context("test_key") == "test_value"
        assert sync.get_context("nonexistent", "default") == "default"

    def test_state_sync_components(self):
        """Test component registration."""
        from core.system_tray import CrossSystemStateSync

        sync = CrossSystemStateSync()
        sync.register_component("test_component", "running")

        components = sync.get_all_components()
        assert "test_component" in components
        assert components["test_component"]["status"] == "running"

        sync.unregister_component("test_component")
        assert "test_component" not in sync.get_all_components()


# ============================================================================
# Integration Tests
# ============================================================================

class TestComponentIntegration:
    """Tests for component integration."""

    def test_daemon_imports(self):
        """Test that jarvis_daemon imports all components."""
        # This tests that all components can be imported together
        try:
            from core.system_tray import get_state_sync, get_tray
            from core.llm import get_llm
            from core.autonomous_web_agent import get_research_agent
            from core.proactive import get_suggestion_engine
            success = True
        except ImportError as e:
            success = False
            print(f"Import failed: {e}")

        assert success

    @pytest.mark.asyncio
    async def test_llm_with_router(self):
        """Test LLM and router work together."""
        from core.llm import UnifiedLLM, LLMRouter

        llm = UnifiedLLM()
        router = LLMRouter(llm)

        # Router should have the LLM
        assert router._llm == llm

    def test_suggestion_to_tray_notification(self):
        """Test suggestion can be formatted for tray."""
        from core.proactive import Suggestion, SuggestionCategory, Priority, TriggerType

        suggestion = Suggestion(
            id="test",
            category=SuggestionCategory.ALERT,
            priority=Priority.HIGH,
            title="Test Title",
            content="Test Content",
            trigger_type=TriggerType.EVENT,
        )

        # Convert to dict for notification
        data = suggestion.to_dict()
        assert "title" in data
        assert "content" in data
        assert data["title"] == "Test Title"


# ============================================================================
# Quick Smoke Test
# ============================================================================

def test_smoke():
    """Basic smoke test that all modules load."""
    print("\n=== JARVIS New Components Smoke Test ===\n")

    modules = [
        ("core.llm", "LLM Providers"),
        ("core.llm.router", "LLM Router"),
        ("core.autonomous_web_agent", "Web Research Agent"),
        ("core.proactive", "Proactive Suggestions"),
        ("core.system_tray", "System Tray"),
    ]

    all_passed = True
    for module_path, name in modules:
        try:
            __import__(module_path)
            print(f"[OK] {name} ({module_path})")
        except Exception as e:
            print(f"[FAIL] {name} ({module_path}): {e}")
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("All components loaded successfully!")
    else:
        print("Some components failed to load.")

    assert all_passed


if __name__ == "__main__":
    # Run quick smoke test
    test_smoke()

    # Run full test suite
    print("\n\nRunning full test suite...\n")
    pytest.main([__file__, "-v", "--tb=short"])
