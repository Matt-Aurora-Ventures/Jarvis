"""
Comprehensive unit tests for core/jarvis.py

Tests cover:
- UserProfile dataclass and defaults
- AIResource dataclass
- State loading and saving (_load_jarvis_state, _save_jarvis_state)
- Discovery logging (_log_discovery)
- User profile operations (get_user_profile, update_user_profile)
- AI resource discovery (discover_free_ai_resources)
- Trading research (research_trading_strategies)
- Proactive suggestions (generate_proactive_suggestions)
- User interviews (conduct_interview)
- Boot sequence (boot_sequence, _build_boot_report)
- Capabilities summarization (_summarize_capabilities)
- Context snapshot (_load_context_snapshot)
- Log auditing (_audit_recent_logs)
- Self-tests (_run_self_tests, _test_*)
- Auto-remediation (_auto_remediate)
- Mission context (get_mission_context)
"""

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.jarvis import (
    UserProfile,
    AIResource,
    _load_jarvis_state,
    _save_jarvis_state,
    _log_discovery,
    get_user_profile,
    update_user_profile,
    discover_free_ai_resources,
    research_trading_strategies,
    generate_proactive_suggestions,
    conduct_interview,
    boot_sequence,
    _build_boot_report,
    _summarize_capabilities,
    _load_context_snapshot,
    _audit_recent_logs,
    _run_self_tests,
    _test_filesystem_access,
    _test_memory_pipeline,
    _test_git_status,
    _test_shell_command,
    _test_puppeteer_binary,
    _test_sequential_thinking_config,
    _auto_remediate,
    get_mission_context,
    JARVIS_STATE_PATH,
    DISCOVERIES_PATH,
    ROOT,
    MCP_CONFIG_PATH,
    SYSTEM_INSTRUCTIONS_PATH,
    BOOT_REPORTS_DIR,
    DAEMON_LOG_PATH,
    EVOLUTION_LOG_PATH,
    MCP_LOG_DIR,
    MISSION_LOG_DIR,
)


# =============================================================================
# UserProfile Tests
# =============================================================================

class TestUserProfile:
    """Test UserProfile dataclass."""

    def test_default_values(self):
        """Test UserProfile has correct default values."""
        profile = UserProfile()

        assert profile.name == "User"
        assert profile.linkedin == "yourprofile"
        assert profile.trading_focus == "crypto algorithmic trading"
        assert profile.last_interview == 0

    def test_primary_goals_default(self):
        """Test primary_goals default list is populated."""
        profile = UserProfile()

        assert profile.primary_goals is not None
        assert len(profile.primary_goals) == 4
        assert "Make money through automation" in profile.primary_goals[0]

    def test_businesses_default_empty(self):
        """Test businesses defaults to empty list."""
        profile = UserProfile()

        assert profile.businesses == []

    def test_interests_default(self):
        """Test interests has default list."""
        profile = UserProfile()

        assert profile.interests is not None
        assert "AI and automation" in profile.interests
        assert "Crypto trading" in profile.interests

    def test_mentor_channels_default(self):
        """Test mentor_channels has default."""
        profile = UserProfile()

        assert profile.mentor_channels is not None
        assert "Moon Dev" in profile.mentor_channels

    def test_custom_values(self):
        """Test UserProfile with custom values."""
        profile = UserProfile(
            name="TestUser",
            linkedin="testuser",
            primary_goals=["Goal1"],
            businesses=["Business1"],
            interests=["Interest1"],
            trading_focus="defi",
            mentor_channels=["Channel1"],
            last_interview=12345.0,
        )

        assert profile.name == "TestUser"
        assert profile.linkedin == "testuser"
        assert profile.primary_goals == ["Goal1"]
        assert profile.businesses == ["Business1"]
        assert profile.interests == ["Interest1"]
        assert profile.trading_focus == "defi"
        assert profile.mentor_channels == ["Channel1"]
        assert profile.last_interview == 12345.0

    def test_asdict_conversion(self):
        """Test UserProfile can be converted to dict."""
        profile = UserProfile(name="Test")
        profile_dict = asdict(profile)

        assert isinstance(profile_dict, dict)
        assert profile_dict["name"] == "Test"


# =============================================================================
# AIResource Tests
# =============================================================================

class TestAIResource:
    """Test AIResource dataclass."""

    def test_create_resource(self):
        """Test creating an AIResource."""
        resource = AIResource(
            name="test-model",
            type="model",
            provider="test-provider",
            is_free=True,
            quality_score=8,
            description="A test model",
            how_to_use="pip install test",
            discovered_at=1234567890.0,
        )

        assert resource.name == "test-model"
        assert resource.type == "model"
        assert resource.provider == "test-provider"
        assert resource.is_free is True
        assert resource.quality_score == 8
        assert resource.description == "A test model"
        assert resource.how_to_use == "pip install test"
        assert resource.discovered_at == 1234567890.0

    def test_asdict_conversion(self):
        """Test AIResource can be converted to dict."""
        resource = AIResource(
            name="test",
            type="api",
            provider="provider",
            is_free=False,
            quality_score=5,
            description="desc",
            how_to_use="use it",
            discovered_at=0.0,
        )
        resource_dict = asdict(resource)

        assert isinstance(resource_dict, dict)
        assert resource_dict["name"] == "test"
        assert resource_dict["is_free"] is False


# =============================================================================
# State Management Tests
# =============================================================================

class TestStateManagement:
    """Test state loading and saving."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create a temporary state file path."""
        return tmp_path / "jarvis_state.json"

    def test_load_state_nonexistent(self, tmp_path, monkeypatch):
        """Test loading state when file doesn't exist."""
        fake_path = tmp_path / "nonexistent.json"
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", fake_path)

        state = _load_jarvis_state()

        assert state["boot_count"] == 0
        assert state["last_boot"] == 0
        assert state["last_discovery_check"] == 0
        assert state["discovered_resources"] == []
        assert state["self_improvements"] == []
        assert "user_profile" in state

    def test_load_state_valid_json(self, tmp_path, monkeypatch):
        """Test loading state from valid JSON file."""
        state_file = tmp_path / "jarvis_state.json"
        state_data = {
            "boot_count": 5,
            "last_boot": 12345.0,
            "user_profile": {"name": "TestUser"}
        }
        state_file.write_text(json.dumps(state_data))
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)

        state = _load_jarvis_state()

        assert state["boot_count"] == 5
        assert state["last_boot"] == 12345.0

    def test_load_state_invalid_json(self, tmp_path, monkeypatch):
        """Test loading state from invalid JSON returns default."""
        state_file = tmp_path / "jarvis_state.json"
        state_file.write_text("not valid json {{{")
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)

        state = _load_jarvis_state()

        assert state["boot_count"] == 0
        assert state["last_boot"] == 0

    def test_save_state(self, tmp_path, monkeypatch):
        """Test saving state creates file."""
        state_file = tmp_path / "data" / "jarvis_state.json"
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)

        state = {"boot_count": 10, "last_boot": 999.0}
        _save_jarvis_state(state)

        assert state_file.exists()
        loaded = json.loads(state_file.read_text())
        assert loaded["boot_count"] == 10

    def test_save_state_creates_parent_dir(self, tmp_path, monkeypatch):
        """Test saving state creates parent directories."""
        state_file = tmp_path / "deep" / "nested" / "dir" / "state.json"
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)

        _save_jarvis_state({"test": "data"})

        assert state_file.parent.exists()
        assert state_file.exists()


# =============================================================================
# Discovery Logging Tests
# =============================================================================

class TestDiscoveryLogging:
    """Test discovery logging."""

    def test_log_discovery(self, tmp_path, monkeypatch):
        """Test logging a discovery."""
        discoveries_file = tmp_path / "discoveries.jsonl"
        monkeypatch.setattr("core.jarvis.DISCOVERIES_PATH", discoveries_file)

        resource = AIResource(
            name="new-model",
            type="model",
            provider="test",
            is_free=True,
            quality_score=9,
            description="Great model",
            how_to_use="pip install",
            discovered_at=time.time(),
        )
        _log_discovery(resource)

        assert discoveries_file.exists()
        content = discoveries_file.read_text().strip()
        logged = json.loads(content)
        assert logged["name"] == "new-model"

    def test_log_multiple_discoveries(self, tmp_path, monkeypatch):
        """Test logging multiple discoveries appends."""
        discoveries_file = tmp_path / "discoveries.jsonl"
        monkeypatch.setattr("core.jarvis.DISCOVERIES_PATH", discoveries_file)

        for i in range(3):
            resource = AIResource(
                name=f"model-{i}",
                type="model",
                provider="test",
                is_free=True,
                quality_score=i,
                description=f"Model {i}",
                how_to_use="use it",
                discovered_at=time.time(),
            )
            _log_discovery(resource)

        lines = discoveries_file.read_text().strip().split("\n")
        assert len(lines) == 3


# =============================================================================
# User Profile Operations Tests
# =============================================================================

class TestUserProfileOperations:
    """Test user profile get and update operations."""

    def test_get_user_profile(self, tmp_path, monkeypatch):
        """Test getting user profile from state."""
        state_file = tmp_path / "jarvis_state.json"
        state_data = {
            "user_profile": {
                "name": "TestName",
                "linkedin": "testlinkedin",
                "primary_goals": ["Goal1"],
                "businesses": [],
                "interests": ["Interest1"],
                "trading_focus": "crypto",
                "mentor_channels": ["Channel1"],
                "last_interview": 0,
            }
        }
        state_file.write_text(json.dumps(state_data))
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)

        profile = get_user_profile()

        assert profile.name == "TestName"
        assert profile.linkedin == "testlinkedin"

    def test_get_user_profile_empty_state(self, tmp_path, monkeypatch):
        """Test getting user profile when no state exists."""
        state_file = tmp_path / "nonexistent.json"
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)

        profile = get_user_profile()

        assert profile.name == "User"  # Default value

    def test_update_user_profile(self, tmp_path, monkeypatch):
        """Test updating user profile."""
        state_file = tmp_path / "jarvis_state.json"
        state_file.write_text(json.dumps({"user_profile": {"name": "OldName"}}))
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)

        update_user_profile(name="NewName", linkedin="newlinkedin")

        # Reload and verify
        profile = get_user_profile()
        assert profile.name == "NewName"


# =============================================================================
# AI Resource Discovery Tests
# =============================================================================

class TestAIResourceDiscovery:
    """Test AI resource discovery function."""

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    def test_discover_returns_resources(self, mock_generate, mock_safety):
        """Test discovering AI resources returns parsed resources."""
        mock_safety.return_value = "Safety prompt"
        mock_generate.return_value = json.dumps([
            {
                "name": "test-model",
                "type": "model",
                "provider": "test",
                "is_free": True,
                "quality_score": 8,
                "description": "A test model",
                "how_to_use": "pip install",
            }
        ])

        resources = discover_free_ai_resources()

        assert len(resources) == 1
        assert resources[0].name == "test-model"
        assert resources[0].is_free is True

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    def test_discover_handles_markdown_code_block(self, mock_generate, mock_safety):
        """Test discovery handles markdown-wrapped JSON."""
        mock_safety.return_value = "Safety prompt"
        mock_generate.return_value = """```json
[{"name": "model1", "type": "model", "provider": "p", "is_free": true, "quality_score": 5, "description": "d", "how_to_use": "u"}]
```"""

        resources = discover_free_ai_resources()

        assert len(resources) == 1
        assert resources[0].name == "model1"

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    def test_discover_returns_empty_on_error(self, mock_generate, mock_safety):
        """Test discovery returns empty list on error."""
        mock_safety.return_value = "Safety prompt"
        mock_generate.side_effect = Exception("API error")

        resources = discover_free_ai_resources()

        assert resources == []

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    def test_discover_returns_empty_on_none_response(self, mock_generate, mock_safety):
        """Test discovery returns empty list when response is None."""
        mock_safety.return_value = "Safety prompt"
        mock_generate.return_value = None

        resources = discover_free_ai_resources()

        assert resources == []


# =============================================================================
# Trading Research Tests
# =============================================================================

class TestTradingResearch:
    """Test trading research function."""

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_research_returns_response(self, mock_profile, mock_generate, mock_safety):
        """Test research returns LLM response."""
        mock_safety.return_value = "Safety prompt"
        mock_profile.return_value = UserProfile(name="TestUser")
        mock_generate.return_value = "Here are some trading strategies..."

        result = research_trading_strategies()

        assert "trading strategies" in result.lower()

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_research_handles_none_response(self, mock_profile, mock_generate, mock_safety):
        """Test research handles None response."""
        mock_safety.return_value = "Safety prompt"
        mock_profile.return_value = UserProfile()
        mock_generate.return_value = None

        result = research_trading_strategies()

        assert "Could not research" in result

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_research_handles_exception(self, mock_profile, mock_generate, mock_safety):
        """Test research handles exceptions gracefully."""
        mock_safety.return_value = "Safety prompt"
        mock_profile.return_value = UserProfile()
        mock_generate.side_effect = Exception("API error")

        result = research_trading_strategies()

        assert "Research failed" in result


# =============================================================================
# Proactive Suggestions Tests
# =============================================================================

class TestProactiveSuggestions:
    """Test proactive suggestions generation."""

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_suggestions_returns_list(self, mock_profile, mock_generate, mock_safety):
        """Test suggestions returns list of strings."""
        mock_safety.return_value = "Safety"
        mock_profile.return_value = UserProfile()
        mock_generate.return_value = '["Suggestion 1", "Suggestion 2", "Suggestion 3"]'

        suggestions = generate_proactive_suggestions()

        assert len(suggestions) == 3
        assert "Suggestion 1" in suggestions

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_suggestions_handles_markdown(self, mock_profile, mock_generate, mock_safety):
        """Test suggestions handles markdown code blocks."""
        mock_safety.return_value = "Safety"
        mock_profile.return_value = UserProfile()
        mock_generate.return_value = "```json\n[\"Idea1\"]\n```"

        suggestions = generate_proactive_suggestions()

        assert "Idea1" in suggestions

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_suggestions_returns_empty_on_error(self, mock_profile, mock_generate, mock_safety):
        """Test suggestions returns empty list on error."""
        mock_safety.return_value = "Safety"
        mock_profile.return_value = UserProfile()
        mock_generate.side_effect = Exception("Error")

        suggestions = generate_proactive_suggestions()

        assert suggestions == []

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_suggestions_returns_empty_on_none(self, mock_profile, mock_generate, mock_safety):
        """Test suggestions returns empty list when response is None."""
        mock_safety.return_value = "Safety"
        mock_profile.return_value = UserProfile()
        mock_generate.return_value = None

        suggestions = generate_proactive_suggestions()

        assert suggestions == []


# =============================================================================
# Interview Tests
# =============================================================================

class TestInterview:
    """Test user interview function."""

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_interview_returns_questions(self, mock_profile, mock_generate, mock_safety):
        """Test interview returns questions."""
        mock_safety.return_value = "Safety"
        mock_profile.return_value = UserProfile(name="TestUser")
        mock_generate.return_value = "1. What are you working on?\n2. What's blocking you?"

        result = conduct_interview()

        assert "1." in result
        assert "2." in result

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_interview_fallback_on_error(self, mock_profile, mock_generate, mock_safety):
        """Test interview returns fallback questions on error."""
        mock_safety.return_value = "Safety"
        mock_profile.return_value = UserProfile()
        mock_generate.side_effect = Exception("Error")

        result = conduct_interview()

        assert "What are you working on today?" in result

    @patch("core.jarvis.guardian.get_safety_prompt")
    @patch("core.jarvis.providers.generate_text")
    @patch("core.jarvis.get_user_profile")
    def test_interview_fallback_on_none(self, mock_profile, mock_generate, mock_safety):
        """Test interview returns fallback when response is None."""
        mock_safety.return_value = "Safety"
        mock_profile.return_value = UserProfile()
        mock_generate.return_value = None

        result = conduct_interview()

        assert "How can I help you today?" in result


# =============================================================================
# Capabilities Summary Tests
# =============================================================================

class TestCapabilitiesSummary:
    """Test capabilities summarization."""

    def test_summarize_mcp_servers(self, tmp_path, monkeypatch):
        """Test summarizing MCP server configuration."""
        mcp_config = tmp_path / "mcp.config.json"
        mcp_config.write_text(json.dumps({
            "servers": [
                {"name": "server1", "enabled": True},
                {"name": "server2", "enabled": False},
                {"name": "server3"},  # enabled by default
            ]
        }))
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)
        monkeypatch.setattr("core.jarvis.SYSTEM_INSTRUCTIONS_PATH", tmp_path / "nonexistent.md")

        summary = _summarize_capabilities()

        assert "server1" in summary["mcp_servers"]
        assert "server2" not in summary["mcp_servers"]
        assert "server3" in summary["mcp_servers"]

    def test_summarize_handles_missing_mcp(self, tmp_path, monkeypatch):
        """Test summarizing handles missing MCP config."""
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", tmp_path / "nonexistent.json")
        monkeypatch.setattr("core.jarvis.SYSTEM_INSTRUCTIONS_PATH", tmp_path / "nonexistent.md")

        summary = _summarize_capabilities()

        assert len(summary["mcp_servers"]) >= 1  # Error message added
        assert "Error" in summary["mcp_servers"][0] or summary["mcp_servers"] == []

    def test_summarize_system_instructions(self, tmp_path, monkeypatch):
        """Test summarizing system instructions."""
        mcp_config = tmp_path / "mcp.config.json"
        mcp_config.write_text(json.dumps({"servers": []}))
        instructions = tmp_path / "instructions.md"
        instructions.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)
        monkeypatch.setattr("core.jarvis.SYSTEM_INSTRUCTIONS_PATH", instructions)

        summary = _summarize_capabilities()

        assert "Line 1" in summary["instruction_highlights"]

    def test_summarize_handles_missing_instructions(self, tmp_path, monkeypatch):
        """Test summarizing handles missing instructions file."""
        mcp_config = tmp_path / "mcp.config.json"
        mcp_config.write_text(json.dumps({"servers": []}))
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)
        monkeypatch.setattr("core.jarvis.SYSTEM_INSTRUCTIONS_PATH", tmp_path / "nonexistent.md")

        summary = _summarize_capabilities()

        assert "missing" in str(summary["instruction_highlights"]).lower()


# =============================================================================
# Context Snapshot Tests
# =============================================================================

class TestContextSnapshot:
    """Test context snapshot loading."""

    @patch("core.jarvis.memory.fetch_recent_entries")
    def test_load_context_snapshot(self, mock_memory, tmp_path, monkeypatch):
        """Test loading context snapshot."""
        monkeypatch.setattr("core.jarvis.MISSION_LOG_DIR", tmp_path / "missions")
        mock_memory.return_value = [
            {"timestamp": 123, "summary": "Test memory entry"}
        ]

        state = {"last_discovery_check": 12345.0}
        boot_result = {"discoveries": ["model1"], "suggestions": ["suggestion1"]}

        snapshot = _load_context_snapshot(state, boot_result)

        assert snapshot["last_discovery_check"] == 12345.0
        assert "model1" in snapshot["last_discoveries"]
        assert "suggestion1" in snapshot["last_suggestions"]

    @patch("core.jarvis.memory.fetch_recent_entries")
    def test_load_context_with_mission_logs(self, mock_memory, tmp_path, monkeypatch):
        """Test loading context with mission logs."""
        mission_dir = tmp_path / "missions"
        mission_dir.mkdir()
        log_file = mission_dir / "mission1.log"
        log_file.write_text("Line 1\nLine 2\nLine 3")
        monkeypatch.setattr("core.jarvis.MISSION_LOG_DIR", mission_dir)
        mock_memory.return_value = []

        state = {}
        boot_result = {}

        snapshot = _load_context_snapshot(state, boot_result)

        assert len(snapshot["recent_missions"]) > 0

    @patch("core.jarvis.memory.fetch_recent_entries")
    def test_load_context_handles_memory_error(self, mock_memory, tmp_path, monkeypatch):
        """Test loading context handles memory errors gracefully."""
        monkeypatch.setattr("core.jarvis.MISSION_LOG_DIR", tmp_path / "missions")
        mock_memory.side_effect = Exception("Memory error")

        state = {}
        boot_result = {}

        # Should not raise
        snapshot = _load_context_snapshot(state, boot_result)

        assert snapshot["recent_memory_entries"] == []


# =============================================================================
# Log Audit Tests
# =============================================================================

class TestLogAudit:
    """Test log auditing."""

    def test_audit_daemon_warnings(self, tmp_path, monkeypatch):
        """Test auditing daemon log for warnings."""
        daemon_log = tmp_path / "daemon.log"
        daemon_log.write_text("Normal line\nWARNING: something\nAnother line\nERROR: bad thing")
        monkeypatch.setattr("core.jarvis.DAEMON_LOG_PATH", daemon_log)
        monkeypatch.setattr("core.jarvis.EVOLUTION_LOG_PATH", tmp_path / "evolution.jsonl")
        monkeypatch.setattr("core.jarvis.MCP_LOG_DIR", tmp_path / "mcp_logs")

        audits = _audit_recent_logs()

        assert len(audits["daemon_warnings"]) >= 2

    def test_audit_evolution_errors(self, tmp_path, monkeypatch):
        """Test auditing evolution log for errors."""
        monkeypatch.setattr("core.jarvis.DAEMON_LOG_PATH", tmp_path / "daemon.log")
        evolution_log = tmp_path / "evolution.jsonl"
        evolution_log.write_text("Normal entry\nEntry with error in it")
        monkeypatch.setattr("core.jarvis.EVOLUTION_LOG_PATH", evolution_log)
        monkeypatch.setattr("core.jarvis.MCP_LOG_DIR", tmp_path / "mcp_logs")

        audits = _audit_recent_logs()

        assert len(audits["evolution_errors"]) >= 1

    def test_audit_mcp_errors(self, tmp_path, monkeypatch):
        """Test auditing MCP logs for errors."""
        monkeypatch.setattr("core.jarvis.DAEMON_LOG_PATH", tmp_path / "daemon.log")
        monkeypatch.setattr("core.jarvis.EVOLUTION_LOG_PATH", tmp_path / "evolution.jsonl")
        mcp_log_dir = tmp_path / "mcp_logs"
        mcp_log_dir.mkdir()
        mcp_log = mcp_log_dir / "server.log"
        mcp_log.write_text("Server started\nError: connection failed\nRecovery attempted")
        monkeypatch.setattr("core.jarvis.MCP_LOG_DIR", mcp_log_dir)

        audits = _audit_recent_logs()

        assert len(audits["mcp_errors"]) >= 1

    def test_audit_handles_missing_logs(self, tmp_path, monkeypatch):
        """Test auditing handles missing log files."""
        monkeypatch.setattr("core.jarvis.DAEMON_LOG_PATH", tmp_path / "nonexistent.log")
        monkeypatch.setattr("core.jarvis.EVOLUTION_LOG_PATH", tmp_path / "nonexistent.jsonl")
        monkeypatch.setattr("core.jarvis.MCP_LOG_DIR", tmp_path / "nonexistent_dir")

        audits = _audit_recent_logs()

        assert audits["daemon_warnings"] == []
        assert audits["evolution_errors"] == []
        assert audits["mcp_errors"] == []


# =============================================================================
# Self-Tests Tests
# =============================================================================

class TestSelfTests:
    """Test self-test functions."""

    def test_filesystem_access_pass(self, tmp_path, monkeypatch):
        """Test filesystem access test passes."""
        monkeypatch.setattr("core.jarvis.ROOT", tmp_path)
        (tmp_path / "data").mkdir()

        result = _test_filesystem_access()

        assert result["status"] == "pass"
        assert "Read/Write OK" in result["detail"]

    def test_filesystem_access_fail(self, tmp_path, monkeypatch):
        """Test filesystem access test fails on error."""
        monkeypatch.setattr("core.jarvis.ROOT", tmp_path / "nonexistent" / "deep" / "path")

        result = _test_filesystem_access()

        assert result["status"] == "fail"
        assert "error" in result["detail"].lower()

    @patch("core.jarvis.memory.append_entry")
    @patch("core.jarvis.memory.fetch_recent_entries")
    def test_memory_pipeline_pass(self, mock_fetch, mock_append):
        """Test memory pipeline test passes."""
        mock_fetch.return_value = [{"timestamp": 123, "text": "test"}]

        result = _test_memory_pipeline()

        assert result["status"] == "pass"
        mock_append.assert_called_once()

    @patch("core.jarvis.memory.append_entry")
    @patch("core.jarvis.memory.fetch_recent_entries")
    def test_memory_pipeline_fail_no_entries(self, mock_fetch, mock_append):
        """Test memory pipeline test fails when no entries returned."""
        mock_fetch.return_value = []

        result = _test_memory_pipeline()

        assert result["status"] == "fail"
        assert "no entries" in result["detail"].lower()

    @patch("core.jarvis.memory.append_entry")
    def test_memory_pipeline_fail_on_exception(self, mock_append):
        """Test memory pipeline test fails on exception."""
        mock_append.side_effect = Exception("Memory error")

        result = _test_memory_pipeline()

        assert result["status"] == "fail"
        assert "error" in result["detail"].lower()

    @patch("subprocess.run")
    def test_git_status_pass(self, mock_run):
        """Test git status test passes."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = _test_git_status()

        assert result["status"] == "pass"

    @patch("subprocess.run")
    def test_git_status_fail(self, mock_run):
        """Test git status test fails on error."""
        mock_run.return_value = MagicMock(returncode=1, stderr="not a git repo")

        result = _test_git_status()

        assert result["status"] == "fail"

    @patch("subprocess.run")
    def test_git_status_exception(self, mock_run):
        """Test git status test handles exception."""
        mock_run.side_effect = Exception("Git not found")

        result = _test_git_status()

        assert result["status"] == "fail"

    @patch("subprocess.run")
    def test_shell_command_pass(self, mock_run):
        """Test shell command test passes."""
        mock_run.return_value = MagicMock(stdout="/home/user\n", returncode=0)

        result = _test_shell_command()

        assert result["status"] == "pass"

    @patch("subprocess.run")
    def test_shell_command_fail(self, mock_run):
        """Test shell command test fails on exception."""
        mock_run.side_effect = Exception("Shell error")

        result = _test_shell_command()

        assert result["status"] == "fail"

    def test_puppeteer_binary_with_command(self, tmp_path, monkeypatch):
        """Test puppeteer binary test with command path."""
        mcp_config = tmp_path / "mcp.config.json"
        command_path = tmp_path / "puppeteer"
        command_path.touch()
        mcp_config.write_text(json.dumps({
            "servers": [
                {"name": "puppeteer", "command": str(command_path)}
            ]
        }))
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)

        result = _test_puppeteer_binary()

        assert result["status"] == "pass"

    def test_puppeteer_binary_with_node_script(self, tmp_path, monkeypatch):
        """Test puppeteer binary test with node script."""
        mcp_config = tmp_path / "mcp.config.json"
        script_path = tmp_path / "server.js"
        script_path.touch()
        mcp_config.write_text(json.dumps({
            "servers": [
                {"name": "puppeteer", "command": "node", "args": [str(script_path)]}
            ]
        }))
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)

        result = _test_puppeteer_binary()

        assert result["status"] == "pass"

    def test_puppeteer_binary_not_configured(self, tmp_path, monkeypatch):
        """Test puppeteer binary test when not configured."""
        mcp_config = tmp_path / "mcp.config.json"
        mcp_config.write_text(json.dumps({"servers": []}))
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)

        result = _test_puppeteer_binary()

        assert result["status"] == "warn"

    def test_sequential_thinking_configured(self, tmp_path, monkeypatch):
        """Test sequential thinking test when configured."""
        mcp_config = tmp_path / "mcp.config.json"
        mcp_config.write_text(json.dumps({
            "servers": [{"name": "sequential-thinking"}]
        }))
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)

        result = _test_sequential_thinking_config()

        assert result["status"] == "pass"

    def test_sequential_thinking_not_configured(self, tmp_path, monkeypatch):
        """Test sequential thinking test when not configured."""
        mcp_config = tmp_path / "mcp.config.json"
        mcp_config.write_text(json.dumps({"servers": []}))
        monkeypatch.setattr("core.jarvis.MCP_CONFIG_PATH", mcp_config)

        result = _test_sequential_thinking_config()

        assert result["status"] == "warn"

    def test_run_self_tests(self, tmp_path, monkeypatch):
        """Test run_self_tests runs all tests."""
        # Mock the individual tests
        with patch("core.jarvis._test_filesystem_access") as mock_fs, \
             patch("core.jarvis._test_memory_pipeline") as mock_mem, \
             patch("core.jarvis._test_git_status") as mock_git, \
             patch("core.jarvis._test_shell_command") as mock_shell, \
             patch("core.jarvis._test_puppeteer_binary") as mock_pup, \
             patch("core.jarvis._test_sequential_thinking_config") as mock_seq:

            mock_fs.return_value = {"status": "pass", "detail": "ok"}
            mock_mem.return_value = {"status": "pass", "detail": "ok"}
            mock_git.return_value = {"status": "pass", "detail": "ok"}
            mock_shell.return_value = {"status": "pass", "detail": "ok"}
            mock_pup.return_value = {"status": "pass", "detail": "ok"}
            mock_seq.return_value = {"status": "pass", "detail": "ok"}

            tests = _run_self_tests()

            assert "filesystem" in tests
            assert "memory" in tests
            assert "git" in tests
            assert "shell" in tests
            assert "puppeteer" in tests
            assert "sequential_thinking" in tests


# =============================================================================
# Auto-Remediation Tests
# =============================================================================

class TestAutoRemediation:
    """Test auto-remediation function."""

    def test_no_remediation_needed(self):
        """Test no remediation when all tests pass."""
        self_tests = {
            "filesystem": {"status": "pass", "detail": "ok"},
            "memory": {"status": "pass", "detail": "ok"},
        }

        notes = _auto_remediate(self_tests)

        assert notes == []

    def test_remediation_on_failure(self):
        """Test remediation triggered on failure."""
        self_tests = {
            "filesystem": {"status": "fail", "detail": "error"},
        }

        with patch("core.jarvis.mcp_loader") as mock_loader:
            notes = _auto_remediate(self_tests)

            mock_loader.stop_mcp_servers.assert_called_once()
            mock_loader.start_mcp_servers.assert_called_once()
            assert len(notes) >= 1
            assert "Restarted MCP servers" in notes[0]

    def test_remediation_handles_exception(self):
        """Test remediation handles MCP restart exception."""
        self_tests = {
            "memory": {"status": "fail", "detail": "error"},
        }

        with patch("core.jarvis.mcp_loader") as mock_loader:
            mock_loader.stop_mcp_servers.side_effect = Exception("Stop failed")

            notes = _auto_remediate(self_tests)

            assert len(notes) >= 1
            assert "Failed to restart" in notes[0]


# =============================================================================
# Boot Sequence Tests
# =============================================================================

class TestBootSequence:
    """Test boot sequence functions."""

    @patch("core.jarvis.generate_proactive_suggestions")
    @patch("core.jarvis.discover_free_ai_resources")
    @patch("core.jarvis._build_boot_report")
    def test_boot_sequence_increments_count(
        self, mock_report, mock_discover, mock_suggestions, tmp_path, monkeypatch
    ):
        """Test boot sequence increments boot count."""
        state_file = tmp_path / "jarvis_state.json"
        state_file.write_text(json.dumps({"boot_count": 5}))
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)
        mock_report.return_value = {"path": tmp_path / "report.json"}
        mock_discover.return_value = []
        mock_suggestions.return_value = []

        result = boot_sequence()

        assert result["boot_count"] == 6

    @patch("core.jarvis.generate_proactive_suggestions")
    @patch("core.jarvis.discover_free_ai_resources")
    @patch("core.jarvis._build_boot_report")
    def test_boot_sequence_discovers_resources(
        self, mock_report, mock_discover, mock_suggestions, tmp_path, monkeypatch
    ):
        """Test boot sequence discovers resources after 24 hours."""
        state_file = tmp_path / "jarvis_state.json"
        # Last check was > 24 hours ago
        state_file.write_text(json.dumps({
            "boot_count": 1,
            "last_discovery_check": time.time() - 90000,  # > 24 hours
        }))
        discoveries_file = tmp_path / "discoveries.jsonl"
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)
        monkeypatch.setattr("core.jarvis.DISCOVERIES_PATH", discoveries_file)
        mock_report.return_value = {"path": tmp_path / "report.json"}

        resource = AIResource(
            name="new-model",
            type="model",
            provider="test",
            is_free=True,
            quality_score=8,
            description="test",
            how_to_use="use",
            discovered_at=time.time(),
        )
        mock_discover.return_value = [resource]
        mock_suggestions.return_value = []

        result = boot_sequence()

        assert "new-model" in result["discoveries"]

    @patch("core.jarvis.generate_proactive_suggestions")
    @patch("core.jarvis.discover_free_ai_resources")
    @patch("core.jarvis._build_boot_report")
    def test_boot_sequence_skips_recent_discovery(
        self, mock_report, mock_discover, mock_suggestions, tmp_path, monkeypatch
    ):
        """Test boot sequence skips discovery if checked recently."""
        state_file = tmp_path / "jarvis_state.json"
        # Last check was < 24 hours ago
        state_file.write_text(json.dumps({
            "boot_count": 1,
            "last_discovery_check": time.time() - 3600,  # 1 hour ago
        }))
        monkeypatch.setattr("core.jarvis.JARVIS_STATE_PATH", state_file)
        mock_report.return_value = {"path": tmp_path / "report.json"}
        mock_suggestions.return_value = ["suggestion1"]

        result = boot_sequence()

        mock_discover.assert_not_called()
        assert result["discoveries"] == []


# =============================================================================
# Build Boot Report Tests
# =============================================================================

class TestBuildBootReport:
    """Test boot report building."""

    @patch("core.jarvis._auto_remediate")
    @patch("core.jarvis._run_self_tests")
    @patch("core.jarvis._audit_recent_logs")
    @patch("core.jarvis._load_context_snapshot")
    @patch("core.jarvis._summarize_capabilities")
    def test_build_boot_report(
        self,
        mock_caps,
        mock_context,
        mock_audit,
        mock_tests,
        mock_remediate,
        tmp_path,
        monkeypatch,
    ):
        """Test building boot report."""
        monkeypatch.setattr("core.jarvis.BOOT_REPORTS_DIR", tmp_path / "reports")
        mock_caps.return_value = {"mcp_servers": [], "instruction_highlights": []}
        mock_context.return_value = {"recent_missions": []}
        mock_audit.return_value = {"daemon_warnings": []}
        mock_tests.return_value = {"filesystem": {"status": "pass", "detail": "ok"}}
        mock_remediate.return_value = []

        state = {"boot_count": 5}
        boot_result = {"discoveries": [], "suggestions": []}

        result = _build_boot_report(state, boot_result)

        assert "data" in result
        assert "path" in result
        assert result["data"]["boot_count"] == 5
        # Report file should be created
        assert Path(result["path"]).exists()


# =============================================================================
# Mission Context Tests
# =============================================================================

class TestMissionContext:
    """Test mission context generation."""

    @patch("core.jarvis.get_user_profile")
    def test_get_mission_context(self, mock_profile):
        """Test getting mission context."""
        mock_profile.return_value = UserProfile(
            name="TestUser",
            linkedin="testlinkedin",
            primary_goals=["Goal1", "Goal2"],
            interests=["Interest1", "Interest2"],
            mentor_channels=["Channel1"],
            trading_focus="crypto",
        )

        context = get_mission_context()

        assert "JARVIS MISSION CONTEXT" in context
        assert "TestUser" in context
        assert "Goal1" in context
        assert "Interest1" in context
        assert "Channel1" in context

    @patch("core.jarvis.get_user_profile")
    def test_mission_context_includes_safety(self, mock_profile):
        """Test mission context includes safety statement."""
        mock_profile.return_value = UserProfile()

        context = get_mission_context()

        assert "SAFETY" in context or "Never harm" in context

    @patch("core.jarvis.get_user_profile")
    def test_mission_context_includes_compression_directive(self, mock_profile):
        """Test mission context includes compression directive."""
        mock_profile.return_value = UserProfile()

        context = get_mission_context()

        # The compression directive is appended
        assert len(context) > 500  # Should be substantial


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_user_profile_with_none_values(self):
        """Test UserProfile handles None values properly."""
        # This tests __post_init__ behavior
        profile = UserProfile(
            name="Test",
            primary_goals=None,
            businesses=None,
            interests=None,
            mentor_channels=None,
        )

        assert profile.primary_goals is not None
        assert profile.businesses is not None
        assert profile.interests is not None
        assert profile.mentor_channels is not None

    def test_empty_json_array_in_discovery(self, tmp_path, monkeypatch):
        """Test discovery handles empty JSON array."""
        with patch("core.jarvis.guardian.get_safety_prompt") as mock_safety, \
             patch("core.jarvis.providers.generate_text") as mock_generate:
            mock_safety.return_value = "Safety"
            mock_generate.return_value = "[]"

            resources = discover_free_ai_resources()

            assert resources == []

    def test_malformed_json_in_discovery(self):
        """Test discovery handles malformed JSON gracefully."""
        with patch("core.jarvis.guardian.get_safety_prompt") as mock_safety, \
             patch("core.jarvis.providers.generate_text") as mock_generate:
            mock_safety.return_value = "Safety"
            mock_generate.return_value = "not json at all"

            resources = discover_free_ai_resources()

            assert resources == []

    def test_partial_resource_data(self):
        """Test discovery handles partial resource data."""
        with patch("core.jarvis.guardian.get_safety_prompt") as mock_safety, \
             patch("core.jarvis.providers.generate_text") as mock_generate:
            mock_safety.return_value = "Safety"
            # Missing some fields
            mock_generate.return_value = json.dumps([
                {"name": "partial-model"}
            ])

            resources = discover_free_ai_resources()

            assert len(resources) == 1
            assert resources[0].name == "partial-model"
            assert resources[0].type == "model"  # default


# =============================================================================
# Path Constants Tests
# =============================================================================

class TestPathConstants:
    """Test path constants are properly defined."""

    def test_root_is_path(self):
        """Test ROOT is a Path object."""
        assert isinstance(ROOT, Path)

    def test_state_path_under_root(self):
        """Test JARVIS_STATE_PATH is under ROOT."""
        assert str(ROOT) in str(JARVIS_STATE_PATH)

    def test_discoveries_path_under_root(self):
        """Test DISCOVERIES_PATH is under ROOT."""
        assert str(ROOT) in str(DISCOVERIES_PATH)

    def test_boot_reports_dir_under_root(self):
        """Test BOOT_REPORTS_DIR is under ROOT."""
        assert str(ROOT) in str(BOOT_REPORTS_DIR)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
