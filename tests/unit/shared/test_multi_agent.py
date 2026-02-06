"""Tests for Multi-Agent Spawning System."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bots.shared.multi_agent import (
    AgentTask,
    MultiAgentDispatcher,
    TaskGroup,
    TaskStatus,
)


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create a temporary state directory."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    return str(tmp_path)


@pytest.fixture
def mock_coordinator():
    """Create a mock BotCoordinator."""
    coord = MagicMock()
    coord._role = MagicMock()
    coord._role.value = "matt"
    coord.delegate_task = MagicMock(return_value="task_abc123")
    return coord


@pytest.fixture
def dispatcher(mock_coordinator, temp_state_dir):
    """Create a MultiAgentDispatcher with temp directory."""
    return MultiAgentDispatcher(
        coordinator=mock_coordinator,
        bot_name="matt",
        state_dir=temp_state_dir,
    )


class TestAgentTask:
    """Tests for AgentTask dataclass."""

    def test_create_task(self):
        task = AgentTask(
            id="t1",
            target_bot="jarvis",
            description="Analyze trading",
        )
        assert task.id == "t1"
        assert task.target_bot == "jarvis"
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None

    def test_task_to_dict(self):
        task = AgentTask(
            id="t2",
            target_bot="friday",
            description="Draft tweet",
            context="marketing context",
        )
        d = task.to_dict()
        assert d["id"] == "t2"
        assert d["target_bot"] == "friday"
        assert d["status"] == "pending"
        assert d["context"] == "marketing context"

    def test_task_from_dict(self):
        data = {
            "id": "t3",
            "target_bot": "jarvis",
            "description": "Check servers",
            "context": "",
            "status": "completed",
            "result": "All good",
            "error": None,
            "created_at": "2026-02-02T00:00:00+00:00",
            "completed_at": "2026-02-02T00:01:00+00:00",
        }
        task = AgentTask.from_dict(data)
        assert task.id == "t3"
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "All good"


class TestClassifyRequest:
    """Tests for request classification."""

    def test_tech_only(self, dispatcher):
        agents = dispatcher.classify_request("Check the trading bot performance")
        assert "jarvis" in agents
        assert "friday" not in agents

    def test_marketing_only(self, dispatcher):
        agents = dispatcher.classify_request("Draft a tweet about the new feature")
        assert "friday" in agents
        assert "jarvis" not in agents

    def test_both_agents(self, dispatcher):
        agents = dispatcher.classify_request(
            "Analyze trading performance and draft a Twitter thread"
        )
        assert "jarvis" in agents
        assert "friday" in agents

    def test_no_agents(self, dispatcher):
        agents = dispatcher.classify_request("Hello, how are you?")
        assert len(agents) == 0

    def test_case_insensitive(self, dispatcher):
        agents = dispatcher.classify_request("DEPLOY the SERVER now")
        assert "jarvis" in agents


class TestDispatchParallel:
    """Tests for parallel task dispatching."""

    @pytest.mark.asyncio
    async def test_dispatch_writes_task_files(self, dispatcher, temp_state_dir):
        tasks = [
            AgentTask(id="t1", target_bot="jarvis", description="Check server"),
            AgentTask(id="t2", target_bot="friday", description="Draft post"),
        ]
        # Mock the polling so it completes immediately
        with patch.object(dispatcher, "_poll_task_completion") as mock_poll:
            mock_poll.return_value = None
            for t in tasks:
                t.status = TaskStatus.COMPLETED
                t.result = f"Done by {t.target_bot}"

            results = await dispatcher.dispatch_parallel(tasks, timeout=5)

        # Verify task files were written
        tasks_dir = Path(temp_state_dir) / "tasks"
        assert (tasks_dir / "t1.json").exists()
        assert (tasks_dir / "t2.json").exists()

    @pytest.mark.asyncio
    async def test_dispatch_timeout(self, dispatcher):
        tasks = [
            AgentTask(id="t1", target_bot="jarvis", description="Slow task"),
        ]
        # _poll_task_completion never completes the task
        with patch.object(dispatcher, "_poll_task_completion") as mock_poll:

            async def slow_poll(task, deadline):
                await asyncio.sleep(10)  # longer than timeout

            mock_poll.side_effect = slow_poll
            results = await dispatcher.dispatch_parallel(tasks, timeout=0.1)

        assert results[0].status == TaskStatus.TIMEOUT


class TestDispatchAndSynthesize:
    """Tests for the high-level dispatch_and_synthesize method."""

    @pytest.mark.asyncio
    async def test_no_agents_returns_none(self, dispatcher):
        result = await dispatcher.dispatch_and_synthesize("Hello there")
        assert result is None

    @pytest.mark.asyncio
    async def test_single_agent_returns_none(self, dispatcher):
        result = await dispatcher.dispatch_and_synthesize("Fix the bug in the code")
        assert result is None

    @pytest.mark.asyncio
    async def test_multi_agent_synthesizes(self, dispatcher):
        with patch.object(dispatcher, "dispatch_parallel") as mock_dispatch:
            t1 = AgentTask(
                id="t1", target_bot="jarvis", description="test",
                status=TaskStatus.COMPLETED, result="Trading is up 5%",
            )
            t2 = AgentTask(
                id="t2", target_bot="friday", description="test",
                status=TaskStatus.COMPLETED, result="Thread drafted with 5 tweets",
            )
            mock_dispatch.return_value = [t1, t2]

            result = await dispatcher.dispatch_and_synthesize(
                "Analyze trading performance and draft a Twitter thread"
            )

        assert result is not None
        assert "jarvis" in result.lower() or "trading" in result.lower()
        assert "friday" in result.lower() or "thread" in result.lower()


class TestSynthesizeResults:
    """Tests for result synthesis."""

    def test_all_completed(self, dispatcher):
        tasks = [
            AgentTask(
                id="t1", target_bot="jarvis", description="test",
                status=TaskStatus.COMPLETED, result="Server healthy",
            ),
            AgentTask(
                id="t2", target_bot="friday", description="test",
                status=TaskStatus.COMPLETED, result="Post drafted",
            ),
        ]
        result = dispatcher._synthesize_results("Check status and draft post", tasks)
        assert "jarvis" in result.lower()
        assert "friday" in result.lower()
        assert "server healthy" in result.lower()
        assert "post drafted" in result.lower()

    def test_partial_failure(self, dispatcher):
        tasks = [
            AgentTask(
                id="t1", target_bot="jarvis", description="test",
                status=TaskStatus.COMPLETED, result="All good",
            ),
            AgentTask(
                id="t2", target_bot="friday", description="test",
                status=TaskStatus.FAILED, error="API timeout",
            ),
        ]
        result = dispatcher._synthesize_results("Do things", tasks)
        assert "failed" in result.lower() or "error" in result.lower()

    def test_all_timeout(self, dispatcher):
        tasks = [
            AgentTask(
                id="t1", target_bot="jarvis", description="test",
                status=TaskStatus.TIMEOUT,
            ),
        ]
        result = dispatcher._synthesize_results("Do stuff", tasks)
        assert "timeout" in result.lower()


class TestTaskGroupPersistence:
    """Tests for saving task groups to disk."""

    def test_save_task_group(self, dispatcher, temp_state_dir):
        tasks = [
            AgentTask(id="t1", target_bot="jarvis", description="Test task"),
        ]
        group = TaskGroup(
            group_id="grp1",
            original_message="Test message",
            tasks=tasks,
        )
        dispatcher._save_task_group(group)

        groups_dir = Path(temp_state_dir) / "task_groups"
        saved = groups_dir / "grp1.json"
        assert saved.exists()

        data = json.loads(saved.read_text())
        assert data["group_id"] == "grp1"
        assert len(data["tasks"]) == 1
