"""
Tests for SubAgent Manager - Clawdbot-style subagent tracking.

TDD Phase 1: Write failing tests that define expected behavior.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
import json


class TestSubAgentDataClass:
    """Test SubAgent dataclass."""

    def test_subagent_creation_with_required_fields(self):
        """SubAgent should be creatable with required fields."""
        from core.agents.manager import SubAgent

        agent = SubAgent(
            id="test-agent-001",
            session_id="tg:user123:main",
            subagent_type="scout",
            description="Explore codebase",
            prompt="Find all trading files",
        )

        assert agent.id == "test-agent-001"
        assert agent.session_id == "tg:user123:main"
        assert agent.subagent_type == "scout"
        assert agent.description == "Explore codebase"
        assert agent.prompt == "Find all trading files"
        assert agent.status == "pending"  # Default status
        assert agent.tokens_used == 0  # Default tokens

    def test_subagent_creation_with_all_fields(self):
        """SubAgent should support all optional fields."""
        from core.agents.manager import SubAgent

        now = datetime.now()
        agent = SubAgent(
            id="test-agent-002",
            session_id="tg:user123:main",
            subagent_type="kraken",
            description="Implement feature",
            prompt="Add user authentication",
            status="running",
            started_at=now,
            completed_at=None,
            tokens_used=15000,
            output_file="/path/to/output.md",
            error=None,
            metadata={"priority": "high", "tags": ["auth", "security"]},
        )

        assert agent.status == "running"
        assert agent.started_at == now
        assert agent.tokens_used == 15000
        assert agent.metadata["priority"] == "high"

    def test_subagent_status_values(self):
        """SubAgent status should accept valid values."""
        from core.agents.manager import SubAgent, AgentStatus

        assert AgentStatus.PENDING.value == "pending"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"
        assert AgentStatus.STOPPED.value == "stopped"


class TestSubAgentManager:
    """Test SubAgentManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh SubAgentManager instance."""
        from core.agents.manager import SubAgentManager
        return SubAgentManager()

    @pytest.fixture
    def sample_agent_data(self):
        """Sample agent registration data."""
        return {
            "agent_id": "a9495d1",
            "subagent_type": "scout",
            "description": "Capability gap analysis",
            "prompt": "Analyze the codebase for missing capabilities",
            "session_id": "tg:user123:main",
        }

    def test_register_agent(self, manager, sample_agent_data):
        """Manager should register new agents."""
        agent = manager.register_agent(**sample_agent_data)

        assert agent.id == "a9495d1"
        assert agent.subagent_type == "scout"
        assert agent.status == "pending"
        assert agent.session_id == "tg:user123:main"

    def test_register_agent_generates_id_if_not_provided(self, manager):
        """Manager should generate ID if not provided."""
        agent = manager.register_agent(
            subagent_type="kraken",
            description="Test task",
            prompt="Do something",
            session_id="tg:user456:main",
        )

        assert agent.id is not None
        assert len(agent.id) >= 7  # Short hash format

    def test_update_status_to_running(self, manager, sample_agent_data):
        """Manager should update agent status to running."""
        agent = manager.register_agent(**sample_agent_data)

        updated = manager.update_status(agent.id, "running")

        assert updated.status == "running"
        assert updated.started_at is not None

    def test_update_status_to_completed_with_tokens(self, manager, sample_agent_data):
        """Manager should update status to completed with token count."""
        agent = manager.register_agent(**sample_agent_data)
        manager.update_status(agent.id, "running")

        updated = manager.update_status(agent.id, "completed", tokens=45000)

        assert updated.status == "completed"
        assert updated.completed_at is not None
        assert updated.tokens_used == 45000

    def test_update_status_to_failed_with_error(self, manager, sample_agent_data):
        """Manager should update status to failed with error message."""
        agent = manager.register_agent(**sample_agent_data)
        manager.update_status(agent.id, "running")

        updated = manager.update_status(agent.id, "failed", error="Timeout exceeded")

        assert updated.status == "failed"
        assert updated.error == "Timeout exceeded"
        assert updated.completed_at is not None

    def test_get_agent_returns_agent(self, manager, sample_agent_data):
        """Manager should retrieve agent by ID."""
        manager.register_agent(**sample_agent_data)

        agent = manager.get_agent("a9495d1")

        assert agent is not None
        assert agent.id == "a9495d1"

    def test_get_agent_returns_none_for_unknown(self, manager):
        """Manager should return None for unknown agent ID."""
        agent = manager.get_agent("unknown-id")
        assert agent is None

    def test_list_agents_returns_all(self, manager):
        """Manager should list all agents."""
        manager.register_agent(
            agent_id="agent-1",
            subagent_type="scout",
            description="Task 1",
            prompt="Do task 1",
            session_id="session-1",
        )
        manager.register_agent(
            agent_id="agent-2",
            subagent_type="kraken",
            description="Task 2",
            prompt="Do task 2",
            session_id="session-1",
        )

        agents = manager.list_agents()

        assert len(agents) == 2

    def test_list_agents_filters_by_session(self, manager):
        """Manager should filter agents by session ID."""
        manager.register_agent(
            agent_id="agent-1",
            subagent_type="scout",
            description="Task 1",
            prompt="Do task 1",
            session_id="session-1",
        )
        manager.register_agent(
            agent_id="agent-2",
            subagent_type="kraken",
            description="Task 2",
            prompt="Do task 2",
            session_id="session-2",
        )

        agents = manager.list_agents(session_id="session-1")

        assert len(agents) == 1
        assert agents[0].session_id == "session-1"

    def test_list_agents_filters_by_status(self, manager):
        """Manager should filter agents by status."""
        manager.register_agent(
            agent_id="agent-1",
            subagent_type="scout",
            description="Task 1",
            prompt="Do task 1",
            session_id="session-1",
        )
        agent2 = manager.register_agent(
            agent_id="agent-2",
            subagent_type="kraken",
            description="Task 2",
            prompt="Do task 2",
            session_id="session-1",
        )
        manager.update_status("agent-2", "running")

        running_agents = manager.list_agents(status="running")

        assert len(running_agents) == 1
        assert running_agents[0].id == "agent-2"

    def test_get_agent_output(self, manager, sample_agent_data, temp_dir):
        """Manager should retrieve agent output from file."""
        output_file = temp_dir / "agent_output.md"
        output_file.write_text("# Agent Output\n\nThis is the result.")

        agent = manager.register_agent(**sample_agent_data)
        manager.update_status(agent.id, "running")
        manager.update_status(agent.id, "completed", output_file=str(output_file))

        output = manager.get_agent_output(agent.id)

        assert "Agent Output" in output
        assert "This is the result" in output

    def test_get_agent_output_returns_none_if_no_file(self, manager, sample_agent_data):
        """Manager should return None if no output file."""
        agent = manager.register_agent(**sample_agent_data)

        output = manager.get_agent_output(agent.id)

        assert output is None

    def test_stop_agent(self, manager, sample_agent_data):
        """Manager should stop a running agent."""
        agent = manager.register_agent(**sample_agent_data)
        manager.update_status(agent.id, "running")

        stopped = manager.stop_agent(agent.id)

        assert stopped is True
        updated = manager.get_agent(agent.id)
        assert updated.status == "stopped"

    def test_stop_agent_returns_false_if_not_running(self, manager, sample_agent_data):
        """Manager should return False if agent not running."""
        agent = manager.register_agent(**sample_agent_data)
        # Agent is in pending status, not running

        stopped = manager.stop_agent(agent.id)

        assert stopped is False

    def test_get_agent_log(self, manager, sample_agent_data, temp_dir):
        """Manager should retrieve agent execution log."""
        # Create a log file
        log_dir = temp_dir / "agent_logs"
        log_dir.mkdir()
        log_file = log_dir / "a9495d1.log"
        log_file.write_text("2024-01-01 10:00:00 - Starting agent\n2024-01-01 10:00:05 - Processing...")

        with patch('core.agents.manager.AGENT_LOGS_DIR', log_dir):
            agent = manager.register_agent(**sample_agent_data)

            log = manager.get_agent_log(agent.id)

        assert "Starting agent" in log
        assert "Processing" in log

    def test_get_session_summary(self, manager):
        """Manager should provide session summary stats."""
        # Register and update various agents
        manager.register_agent(
            agent_id="agent-1",
            subagent_type="scout",
            description="Task 1",
            prompt="Do task 1",
            session_id="session-1",
        )
        manager.update_status("agent-1", "running")
        manager.update_status("agent-1", "completed", tokens=15000)

        manager.register_agent(
            agent_id="agent-2",
            subagent_type="kraken",
            description="Task 2",
            prompt="Do task 2",
            session_id="session-1",
        )
        manager.update_status("agent-2", "running")
        manager.update_status("agent-2", "completed", tokens=27000)

        manager.register_agent(
            agent_id="agent-3",
            subagent_type="oracle",
            description="Task 3",
            prompt="Do task 3",
            session_id="session-1",
        )
        manager.update_status("agent-3", "running")

        manager.register_agent(
            agent_id="agent-4",
            subagent_type="spark",
            description="Task 4",
            prompt="Do task 4",
            session_id="session-1",
        )
        manager.update_status("agent-4", "running")
        manager.update_status("agent-4", "failed", error="Timeout")

        summary = manager.get_session_summary("session-1")

        assert summary["total"] == 4
        assert summary["running"] == 1
        assert summary["completed"] == 2
        assert summary["failed"] == 1
        assert summary["total_tokens"] == 42000


class TestSubAgentManagerPersistence:
    """Test SubAgentManager database persistence."""

    @pytest.fixture
    def db_manager(self, temp_dir):
        """Create a SubAgentManager with database persistence."""
        from core.agents.manager import SubAgentManager
        from core.memory.database import DatabaseManager
        from core.memory.config import MemoryConfig

        config = MemoryConfig(memory_root=temp_dir)
        db = DatabaseManager(config)
        return SubAgentManager(db=db)

    def test_persists_agent_to_database(self, db_manager):
        """Manager should persist agent to database."""
        agent = db_manager.register_agent(
            agent_id="persist-test-1",
            subagent_type="scout",
            description="Persisted task",
            prompt="Do something",
            session_id="persist-session",
        )

        # Retrieve from database
        retrieved = db_manager.get_agent("persist-test-1")

        assert retrieved is not None
        assert retrieved.id == "persist-test-1"
        assert retrieved.description == "Persisted task"

    def test_updates_persist_to_database(self, db_manager):
        """Manager should persist status updates to database."""
        db_manager.register_agent(
            agent_id="persist-test-2",
            subagent_type="kraken",
            description="Update test",
            prompt="Do something",
            session_id="persist-session",
        )

        db_manager.update_status("persist-test-2", "running")
        db_manager.update_status("persist-test-2", "completed", tokens=25000)

        retrieved = db_manager.get_agent("persist-test-2")

        assert retrieved.status == "completed"
        assert retrieved.tokens_used == 25000


class TestSubAgentManagerFormatting:
    """Test SubAgentManager output formatting."""

    @pytest.fixture
    def manager_with_agents(self):
        """Create manager with sample agents."""
        from core.agents.manager import SubAgentManager

        manager = SubAgentManager()

        # Running agents
        manager.register_agent(
            agent_id="a9495d1",
            subagent_type="scout",
            description="Capability gap analysis",
            prompt="Find gaps",
            session_id="tg:user123:main",
        )
        manager.update_status("a9495d1", "running")

        manager.register_agent(
            agent_id="aa9e6dd",
            subagent_type="kraken",
            description="Skill system impl",
            prompt="Implement skills",
            session_id="tg:user123:main",
        )
        manager.update_status("aa9e6dd", "running")

        # Completed agent
        manager.register_agent(
            agent_id="a123456",
            subagent_type="oracle",
            description="Research phase 1",
            prompt="Research auth",
            session_id="tg:user123:main",
        )
        manager.update_status("a123456", "running")
        manager.update_status("a123456", "completed", tokens=45000)

        # Failed agent
        manager.register_agent(
            agent_id="a345678",
            subagent_type="architect",
            description="API integration",
            prompt="Integrate API",
            session_id="tg:user123:main",
        )
        manager.update_status("a345678", "running")
        manager.update_status("a345678", "failed", error="timeout")

        return manager

    def test_format_agent_list(self, manager_with_agents):
        """Manager should format agent list for display."""
        output = manager_with_agents.format_agent_list("tg:user123:main")

        # Check header
        assert "Active Subagents" in output
        assert "tg:user123:main" in output

        # Check running section
        assert "RUNNING" in output
        assert "a9495d1" in output
        assert "Capability gap analysis" in output

        # Check completed section
        assert "COMPLETED" in output
        assert "a123456" in output
        assert "45K" in output  # Token count formatting

        # Check failed section
        assert "FAILED" in output
        assert "a345678" in output
        assert "timeout" in output

    def test_format_agent_info(self, manager_with_agents):
        """Manager should format detailed agent info."""
        info = manager_with_agents.format_agent_info("a9495d1")

        assert "a9495d1" in info
        assert "scout" in info.lower()
        assert "Capability gap analysis" in info
        assert "running" in info.lower()


class TestTelegramSubagentHandler:
    """Test Telegram /subagents command handler."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.effective_user.id = 123456
        update.effective_chat.id = -100123456
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context."""
        context = MagicMock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_subagents_list_command(self, mock_update, mock_context):
        """Handler should list subagents for session."""
        from tg_bot.handlers.subagents import subagents_command

        with patch('tg_bot.handlers.subagents.get_subagent_manager') as mock_manager:
            manager = MagicMock()
            manager.format_agent_list.return_value = "Agent list output"
            mock_manager.return_value = manager

            await subagents_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Agent list output" in call_args[0][0] or call_args[1].get('text') == "Agent list output"

    @pytest.mark.asyncio
    async def test_subagents_stop_command(self, mock_update, mock_context):
        """Handler should stop specified agent."""
        mock_context.args = ["stop", "a9495d1"]

        from tg_bot.handlers.subagents import subagents_command

        with patch('tg_bot.handlers.subagents.get_subagent_manager') as mock_manager:
            manager = MagicMock()
            manager.stop_agent.return_value = True
            mock_manager.return_value = manager

            await subagents_command(mock_update, mock_context)

        manager.stop_agent.assert_called_once_with("a9495d1")

    @pytest.mark.asyncio
    async def test_subagents_log_command(self, mock_update, mock_context):
        """Handler should show agent log."""
        mock_context.args = ["log", "a9495d1"]

        from tg_bot.handlers.subagents import subagents_command

        with patch('tg_bot.handlers.subagents.get_subagent_manager') as mock_manager:
            manager = MagicMock()
            manager.get_agent_log.return_value = "Agent log content"
            mock_manager.return_value = manager

            await subagents_command(mock_update, mock_context)

        manager.get_agent_log.assert_called_once_with("a9495d1")

    @pytest.mark.asyncio
    async def test_subagents_info_command(self, mock_update, mock_context):
        """Handler should show agent info."""
        mock_context.args = ["info", "a9495d1"]

        from tg_bot.handlers.subagents import subagents_command

        with patch('tg_bot.handlers.subagents.get_subagent_manager') as mock_manager:
            manager = MagicMock()
            manager.format_agent_info.return_value = "Agent info output"
            mock_manager.return_value = manager

            await subagents_command(mock_update, mock_context)

        manager.format_agent_info.assert_called_once_with("a9495d1")


class TestSubAgentSchema:
    """Test database schema for subagents table."""

    def test_schema_includes_subagents_table(self, temp_dir):
        """Schema should include subagents table."""
        from core.memory.database import DatabaseManager
        from core.memory.config import MemoryConfig

        config = MemoryConfig(memory_root=temp_dir)
        db = DatabaseManager(config)

        # Check if table exists
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='subagents'"
        )
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == "subagents"

    def test_schema_has_required_columns(self, temp_dir):
        """Schema should have all required columns."""
        from core.memory.database import DatabaseManager
        from core.memory.config import MemoryConfig

        config = MemoryConfig(memory_root=temp_dir)
        db = DatabaseManager(config)

        # Get table info
        cursor = db.execute("PRAGMA table_info(subagents)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {
            "id", "session_id", "subagent_type", "description", "prompt",
            "status", "started_at", "completed_at", "tokens_used",
            "output_file", "error", "metadata"
        }

        assert required_columns.issubset(columns)
