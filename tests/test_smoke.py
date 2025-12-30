"""Smoke tests for LifeOS core functionality.

These tests verify that essential modules load and basic functions work.
They don't require external services or API keys.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestConfigLoading:
    """Test configuration system."""

    def test_config_loads(self):
        """Config module loads without error."""
        from core import config
        cfg = config.load_config()
        assert isinstance(cfg, dict)

    def test_config_has_sections(self):
        """Config has expected sections."""
        from core import config
        cfg = config.load_config()
        # At minimum, config should have some structure
        assert cfg is not None


class TestMemory:
    """Test memory system."""

    def test_memory_imports(self):
        """Memory module loads."""
        from core import memory
        assert hasattr(memory, "get_recent_entries")
        assert hasattr(memory, "get_factual_entries")
        assert hasattr(memory, "summarize_entries")

    def test_memory_factual_filter(self):
        """Factual entries exclude assistant outputs."""
        from core import memory
        # This should not raise
        entries = memory.get_factual_entries()
        assert isinstance(entries, list)
        # All entries should NOT be assistant sources
        for entry in entries:
            assert entry.get("source") != "voice_chat_assistant"

    def test_memory_cap_computation(self):
        """Adaptive cap computes without error."""
        from core import memory
        cap = memory.compute_adaptive_cap(update_state=False)
        assert isinstance(cap, int)
        assert cap >= 50  # min_cap
        assert cap <= 300  # max_cap


class TestProviders:
    """Test AI provider system."""

    def test_providers_import(self):
        """Providers module loads."""
        from core import providers
        assert hasattr(providers, "generate_text")
        assert hasattr(providers, "check_provider_health")
        assert hasattr(providers, "get_provider_summary")

    def test_provider_health_check(self):
        """Provider health check runs without error."""
        from core import providers
        health = providers.check_provider_health()
        assert isinstance(health, dict)
        # Should have at least one provider key
        assert len(health) > 0

    def test_provider_summary(self):
        """Provider summary generates."""
        from core import providers
        summary = providers.get_provider_summary()
        assert isinstance(summary, str)
        assert "Provider" in summary or "provider" in summary.lower()


class TestState:
    """Test state management."""

    def test_state_imports(self):
        """State module loads."""
        from core import state
        assert hasattr(state, "read_state")
        assert hasattr(state, "update_state")
        assert hasattr(state, "is_running")

    def test_state_read(self):
        """State can be read."""
        from core import state
        current = state.read_state()
        assert isinstance(current, dict)


class TestSafety:
    """Test safety system."""

    def test_safety_imports(self):
        """Safety module loads."""
        from core import safety
        assert hasattr(safety, "SafetyContext")
        assert hasattr(safety, "allow_action")

    def test_safety_context_creation(self):
        """SafetyContext can be created."""
        from core import safety
        ctx = safety.SafetyContext(apply=False, dry_run=True)
        assert ctx.dry_run is True


class TestVoice:
    """Test voice system (non-interactive parts only)."""

    def test_voice_imports(self):
        """Voice module loads."""
        from core import voice
        assert hasattr(voice, "check_voice_health")
        assert hasattr(voice, "get_voice_doctor_summary")
        assert hasattr(voice, "parse_command")

    def test_voice_health_check(self):
        """Voice health check runs."""
        from core import voice
        health = voice.check_voice_health()
        assert isinstance(health, dict)
        assert "microphone" in health
        assert "stt" in health
        assert "tts" in health

    def test_voice_doctor_summary(self):
        """Voice doctor summary generates."""
        from core import voice
        summary = voice.get_voice_doctor_summary()
        assert isinstance(summary, str)
        assert "Voice Pipeline" in summary

    def test_command_parsing(self):
        """Voice commands parse correctly."""
        from core import voice
        # Test known commands
        cmd = voice.parse_command("status")
        assert cmd is not None
        assert cmd.action == "status"

        cmd = voice.parse_command("stop listening")
        assert cmd is not None
        assert cmd.action == "listening_off"

        cmd = voice.parse_command("shutdown")
        assert cmd is not None
        assert cmd.action == "shutdown"

        # Unknown command returns None
        cmd = voice.parse_command("random gibberish xyz")
        assert cmd is None


class TestConversation:
    """Test conversation system."""

    def test_conversation_imports(self):
        """Conversation module loads."""
        from core import conversation
        assert hasattr(conversation, "generate_response")

    def test_support_prompts(self):
        """Support prompt selection works."""
        from core import conversation
        # This is an internal function but we can test it
        text, ids = conversation._support_prompts("tell me about crypto trading")
        # Should return tuple of (str, list)
        assert isinstance(text, str)
        assert isinstance(ids, list)


class TestErrorRecovery:
    """Test error recovery system."""

    def test_error_recovery_imports(self):
        """Error recovery module loads."""
        from core import error_recovery
        assert hasattr(error_recovery, "ErrorRecord")
        assert hasattr(error_recovery, "ErrorRecoveryManager")

    def test_recovery_manager_creation(self):
        """Recovery manager can be created."""
        from core import error_recovery
        manager = error_recovery.ErrorRecoveryManager()
        assert manager is not None


class TestCLI:
    """Test CLI structure."""

    def test_cli_imports(self):
        """CLI module loads."""
        from core import cli
        assert hasattr(cli, "build_parser")
        assert hasattr(cli, "main")

    def test_parser_builds(self):
        """CLI parser builds without error."""
        from core import cli
        parser = cli.build_parser()
        assert parser is not None


class TestSecrets:
    """Test secrets handling (without exposing secrets)."""

    def test_secrets_imports(self):
        """Secrets module loads."""
        from core import secrets
        assert hasattr(secrets, "list_configured_keys")

    def test_key_listing(self):
        """Key listing works."""
        from core import secrets
        keys = secrets.list_configured_keys()
        assert isinstance(keys, dict)
        # Should have standard key names
        assert "groq" in keys
        assert "gemini" in keys
        assert "openai" in keys
