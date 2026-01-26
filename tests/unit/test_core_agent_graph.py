"""
Comprehensive Unit Tests for core/agent_graph.py

Tests the GraphAgent class with its planning, execution, reflection, and
summarization nodes. Covers AgentState dataclass, JSON parsing utilities,
context building, model routing, error handling, and state rendering.

Uses extensive mocking to isolate the agent_graph module from external dependencies.
"""

import json
import pytest
from dataclasses import asdict
from unittest.mock import MagicMock, patch, PropertyMock

import sys
from pathlib import Path

# Ensure project root is in path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_router():
    """Mock ModelRouter that returns RouteDecision objects."""
    router = MagicMock()
    decision = MagicMock()
    decision.provider = "ollama"
    decision.model = "llama3"
    decision.max_output_tokens = 900
    router.route.return_value = decision
    return router


@pytest.fixture
def mock_executor():
    """Mock AutonomousAgent executor."""
    executor = MagicMock()
    executor.tools = {"web_search": MagicMock(), "browser": MagicMock(), "terminal": MagicMock()}
    executor._execute_step.return_value = {"status": "success", "result": "completed", "tool": "web_search"}
    return executor


@pytest.fixture
def mock_error_manager():
    """Mock error recovery manager."""
    manager = MagicMock()
    manager.handle_error.return_value = None
    return manager


@pytest.fixture
def mock_context_functions():
    """Mock context manager functions with real dataclass instances."""
    from core.context_manager import MasterContext, ActivityContext, ConversationContext

    master = MasterContext(
        user_name="TestUser",
        user_goals=["test goal"],
        current_projects=[],
        recent_topics=[],
        preferences={},
        learned_patterns=[],
        last_updated=0.0
    )

    activity = ActivityContext(
        current_app="",
        current_window="",
        recent_apps=[],
        activity_summary="",
        screen_content="",
        idle_time=0.0,
        focus_score=0.0,
        timestamp=0.0
    )

    conversation = ConversationContext(
        recent_messages=[],
        pending_tasks=[],
        mentioned_topics=[],
        action_history=[],
        session_start=0.0,
        conversation_summaries=[],
        key_facts=[],
        user_corrections=[]
    )

    return master, activity, conversation


@pytest.fixture
def graph_agent_with_mocks(mock_router, mock_executor, mock_error_manager, mock_context_functions):
    """Create a GraphAgent with all dependencies mocked."""
    master, activity, conversation = mock_context_functions

    with patch.multiple(
        'core.agent_graph',
        agent_router=MagicMock(),
        autonomous_agent=MagicMock(),
        error_recovery=MagicMock(),
        context_manager=MagicMock(),
        memory=MagicMock(),
        semantic_memory=MagicMock(),
        providers=MagicMock(),
        safety=MagicMock(),
    ) as mocks:
        # Configure mocks
        from core import agent_graph

        agent_graph.agent_router.ModelRouter.return_value = mock_router
        agent_graph.autonomous_agent.AutonomousAgent.return_value = mock_executor
        agent_graph.error_recovery.get_error_manager.return_value = mock_error_manager
        agent_graph.context_manager.load_master_context.return_value = master
        agent_graph.context_manager.load_activity_context.return_value = activity
        agent_graph.context_manager.load_conversation_context.return_value = conversation
        agent_graph.memory.fetch_recent_entries.return_value = []
        agent_graph.semantic_memory.search.return_value = []
        agent_graph.providers.provider_status.return_value = {"ollama_available": True}
        agent_graph.providers.ask_ollama_model.return_value = '{"steps": [{"description": "test", "tool": "web_search", "parameters": {}, "critical": false}]}'
        agent_graph.providers.generate_text.return_value = "Summary of results."

        agent = agent_graph.GraphAgent()
        agent._router = mock_router
        agent._executor = mock_executor
        agent._error_manager = mock_error_manager

        yield agent, mocks


# ==============================================================================
# Tests for AgentState Dataclass
# ==============================================================================


class TestAgentState:
    """Test the AgentState dataclass."""

    def test_agent_state_initialization_minimal(self):
        """Test AgentState with minimal required fields."""
        from core.agent_graph import AgentState

        state = AgentState(goal="Test goal", context={"key": "value"})

        assert state.goal == "Test goal"
        assert state.context == {"key": "value"}
        assert state.plan == {}
        assert state.steps == []
        assert state.results == []
        assert state.reflections == []
        assert state.errors == []
        assert state.cycle == 0
        assert state.status == "initialized"
        assert state.summary == ""

    def test_agent_state_initialization_full(self):
        """Test AgentState with all fields specified."""
        from core.agent_graph import AgentState

        state = AgentState(
            goal="Complete task",
            context={"data": "test"},
            plan={"steps": []},
            steps=[{"step": 1}],
            results=[{"result": "ok"}],
            reflections=[{"reflection": "good"}],
            errors=["error1"],
            cycle=2,
            status="running",
            summary="Summary text"
        )

        assert state.goal == "Complete task"
        assert state.cycle == 2
        assert state.status == "running"
        assert len(state.steps) == 1
        assert len(state.results) == 1
        assert len(state.errors) == 1

    def test_agent_state_mutable_defaults(self):
        """Test that mutable default fields are properly isolated."""
        from core.agent_graph import AgentState

        state1 = AgentState(goal="goal1", context={})
        state2 = AgentState(goal="goal2", context={})

        state1.steps.append({"step": 1})
        state1.results.append({"result": 1})
        state1.errors.append("error")

        assert state2.steps == []
        assert state2.results == []
        assert state2.errors == []

    def test_agent_state_to_dict(self):
        """Test converting AgentState to dictionary."""
        from core.agent_graph import AgentState

        state = AgentState(goal="Test", context={"foo": "bar"})
        state_dict = asdict(state)

        assert isinstance(state_dict, dict)
        assert state_dict["goal"] == "Test"
        assert state_dict["context"] == {"foo": "bar"}
        assert state_dict["status"] == "initialized"


# ==============================================================================
# Tests for GraphAgent Initialization
# ==============================================================================


class TestGraphAgentInit:
    """Test GraphAgent initialization."""

    def test_graph_agent_initialization(self):
        """Test GraphAgent initializes with proper components."""
        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            from core.agent_graph import GraphAgent

            agent = GraphAgent()

            assert hasattr(agent, '_router')
            assert hasattr(agent, '_executor')
            assert hasattr(agent, '_error_manager')

    def test_graph_agent_router_is_model_router(self):
        """Test that router is a ModelRouter instance."""
        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            from core.agent_graph import GraphAgent
            from core import agent_graph

            mock_router = MagicMock()
            agent_graph.agent_router.ModelRouter.return_value = mock_router

            agent = GraphAgent()

            agent_graph.agent_router.ModelRouter.assert_called_once()


# ==============================================================================
# Tests for _build_context Method
# ==============================================================================


class TestBuildContext:
    """Test the _build_context method."""

    def test_build_context_with_no_extra(self, graph_agent_with_mocks):
        """Test context building without extra context."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        context = agent._build_context("test goal", None)

        assert "master" in context
        assert "activity" in context
        assert "conversation" in context
        assert "memory_recent" in context
        assert "memory_hits" in context
        assert "provider_status" in context
        assert "extra" not in context

    def test_build_context_with_extra(self, graph_agent_with_mocks):
        """Test context building with extra context."""
        agent, mocks = graph_agent_with_mocks

        extra = {"custom_key": "custom_value"}
        context = agent._build_context("test goal", extra)

        assert "extra" in context
        assert context["extra"] == extra

    def test_build_context_calls_context_functions(self, graph_agent_with_mocks):
        """Test that context functions are called."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        agent._build_context("test goal", None)

        agent_graph.context_manager.load_master_context.assert_called_once()
        agent_graph.context_manager.load_activity_context.assert_called_once()
        agent_graph.context_manager.load_conversation_context.assert_called_once()

    def test_build_context_fetches_memory(self, graph_agent_with_mocks):
        """Test that memory is fetched."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        agent._build_context("search query", None)

        agent_graph.memory.fetch_recent_entries.assert_called_once_with(limit=6)
        agent_graph.semantic_memory.search.assert_called_once_with("search query")


# ==============================================================================
# Tests for _call_model Method
# ==============================================================================


class TestCallModel:
    """Test the _call_model method."""

    def test_call_model_with_ollama_success(self, graph_agent_with_mocks):
        """Test successful model call with Ollama provider."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        agent_graph.providers.ask_ollama_model.return_value = "Response from Ollama"

        result = agent._call_model("planner", "Test prompt", max_output_tokens=500)

        assert result == "Response from Ollama"
        agent_graph.providers.ask_ollama_model.assert_called_once()

    def test_call_model_with_ollama_fallback_to_generate_text(self, graph_agent_with_mocks):
        """Test fallback to generate_text when Ollama fails."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        # Ollama raises exception
        agent_graph.providers.ask_ollama_model.side_effect = Exception("Ollama error")
        agent_graph.providers.generate_text.return_value = "Fallback response"

        result = agent._call_model("planner", "Test prompt", max_output_tokens=500)

        assert result == "Fallback response"
        agent._error_manager.handle_error.assert_called()

    def test_call_model_uses_min_tokens(self, graph_agent_with_mocks):
        """Test that min of requested and decision tokens is used."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        # Set decision max_output_tokens to 900
        agent._router.route.return_value.max_output_tokens = 900

        agent._call_model("planner", "Test", max_output_tokens=500)

        call_kwargs = agent_graph.providers.ask_ollama_model.call_args
        assert call_kwargs[1]["max_output_tokens"] == 500

    def test_call_model_non_ollama_provider(self, graph_agent_with_mocks):
        """Test model call with non-Ollama provider."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "OpenAI response"

        result = agent._call_model("planner", "Test prompt", max_output_tokens=500)

        assert result == "OpenAI response"

    def test_call_model_no_response_raises(self, graph_agent_with_mocks):
        """Test that no response raises RuntimeError."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = None

        with pytest.raises(RuntimeError, match="No model response"):
            agent._call_model("planner", "Test", max_output_tokens=500)


# ==============================================================================
# Tests for _plan Method
# ==============================================================================


class TestPlanMethod:
    """Test the _plan method."""

    def test_plan_returns_parsed_steps(self, graph_agent_with_mocks):
        """Test that plan returns parsed JSON steps."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        plan_response = json.dumps({
            "steps": [
                {"description": "Step 1", "tool": "web_search", "parameters": {}, "critical": True, "expected_output": "results"}
            ]
        })
        agent_graph.providers.ask_ollama_model.return_value = plan_response

        state = AgentState(goal="Test goal", context={})
        result = agent._plan(state)

        assert "steps" in result
        assert len(result["steps"]) == 1

    def test_plan_with_invalid_json_returns_fallback(self, graph_agent_with_mocks):
        """Test that invalid JSON returns fallback plan."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent_graph.providers.ask_ollama_model.return_value = "Not valid JSON"

        state = AgentState(goal="Test goal", context={})
        result = agent._plan(state)

        # Should return fallback plan
        assert "steps" in result
        assert result["steps"][0]["tool"] == "web_search"

    def test_plan_with_exception_returns_fallback(self, graph_agent_with_mocks):
        """Test that exception during planning returns fallback."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent_graph.providers.ask_ollama_model.side_effect = Exception("Planning failed")
        agent_graph.providers.generate_text.return_value = None

        state = AgentState(goal="Test goal", context={})
        result = agent._plan(state)

        assert "steps" in result
        agent._error_manager.handle_error.assert_called()

    def test_plan_includes_available_tools(self, graph_agent_with_mocks):
        """Test that available tools are included in prompt."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        # Capture the prompt
        captured_prompt = None
        def capture_call(*args, **kwargs):
            nonlocal captured_prompt
            captured_prompt = args[0] if args else kwargs.get('prompt', '')
            return '{"steps": []}'

        agent_graph.providers.ask_ollama_model.side_effect = capture_call

        state = AgentState(goal="Test", context={})
        agent._plan(state)

        # Check that tools are mentioned
        assert "web_search" in captured_prompt or "browser" in captured_prompt


# ==============================================================================
# Tests for _execute_steps Method
# ==============================================================================


class TestExecuteSteps:
    """Test the _execute_steps method."""

    def test_execute_steps_success(self, graph_agent_with_mocks):
        """Test successful step execution."""
        agent, mocks = graph_agent_with_mocks
        from core.agent_graph import AgentState

        agent._executor._execute_step.return_value = {"status": "success", "result": "done", "tool": "web_search"}

        state = AgentState(goal="Test", context={})
        state.steps = [{"description": "Step 1", "tool": "web_search", "parameters": {}}]

        needs_replan = agent._execute_steps(state, max_step_retries=1)

        assert needs_replan is False
        assert len(state.results) == 1
        assert state.results[0]["status"] == "success"

    def test_execute_steps_tracks_results_in_context(self, graph_agent_with_mocks):
        """Test that results are tracked in context."""
        agent, mocks = graph_agent_with_mocks
        from core.agent_graph import AgentState

        agent._executor._execute_step.return_value = {"status": "success", "result": "data", "tool": "browser"}

        state = AgentState(goal="Test", context={})
        state.steps = [{"description": "Browse", "tool": "browser", "parameters": {}}]

        agent._execute_steps(state, max_step_retries=0)

        assert "tool_results" in state.context
        assert "last_result" in state.context

    def test_execute_steps_failure_triggers_reflection(self, graph_agent_with_mocks):
        """Test that step failure triggers reflection."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent._executor._execute_step.return_value = {"status": "failed", "error": "Something broke", "tool": "terminal"}
        agent_graph.providers.ask_ollama_model.return_value = json.dumps({"action": "abort", "reason": "unrecoverable"})

        state = AgentState(goal="Test", context={})
        state.steps = [{"description": "Run", "tool": "terminal", "parameters": {}, "critical": False}]

        agent._execute_steps(state, max_step_retries=1)

        assert len(state.reflections) > 0

    def test_execute_steps_retry_on_reflection_action(self, graph_agent_with_mocks):
        """Test retry when reflection suggests retry."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        # First call fails, second succeeds
        agent._executor._execute_step.side_effect = [
            {"status": "failed", "error": "transient", "tool": "web_search"},
            {"status": "success", "result": "done", "tool": "web_search"}
        ]
        agent_graph.providers.ask_ollama_model.return_value = json.dumps({"action": "retry", "reason": "transient error"})

        state = AgentState(goal="Test", context={})
        state.steps = [{"description": "Search", "tool": "web_search", "parameters": {}, "critical": False}]

        agent._execute_steps(state, max_step_retries=2)

        # Should have succeeded after retry
        assert any(r.get("status") == "success" for r in state.results)

    def test_execute_steps_replan_action(self, graph_agent_with_mocks):
        """Test replan when reflection suggests replan."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent._executor._execute_step.return_value = {"status": "failed", "error": "need different approach", "tool": "browser"}
        agent_graph.providers.ask_ollama_model.return_value = json.dumps({"action": "replan", "reason": "wrong approach"})

        state = AgentState(goal="Test", context={})
        state.steps = [{"description": "Browse", "tool": "browser", "parameters": {}, "critical": False}]

        needs_replan = agent._execute_steps(state, max_step_retries=1)

        assert needs_replan is True
        assert state.status == "replan"

    def test_execute_steps_update_step_action(self, graph_agent_with_mocks):
        """Test update_step when reflection provides updated step."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        call_count = [0]
        def execute_side_effect(step, context):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"status": "failed", "error": "wrong params", "tool": step.get("tool")}
            return {"status": "success", "result": "done", "tool": step.get("tool")}

        agent._executor._execute_step.side_effect = execute_side_effect
        updated_step = {"description": "Updated", "tool": "web_search", "parameters": {"query": "better"}}
        agent_graph.providers.ask_ollama_model.return_value = json.dumps({
            "action": "update_step",
            "reason": "params wrong",
            "updated_step": updated_step
        })

        state = AgentState(goal="Test", context={})
        state.steps = [{"description": "Original", "tool": "web_search", "parameters": {"query": "bad"}}]

        agent._execute_steps(state, max_step_retries=2)

        assert call_count[0] >= 2

    def test_execute_steps_critical_failure_stops(self, graph_agent_with_mocks):
        """Test that critical step failure stops execution."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent._executor._execute_step.return_value = {"status": "failed", "error": "critical error", "tool": "terminal"}
        agent_graph.providers.ask_ollama_model.return_value = json.dumps({"action": "abort", "reason": "fatal"})

        state = AgentState(goal="Test", context={})
        state.steps = [
            {"description": "Step 1", "tool": "terminal", "parameters": {}, "critical": True},
            {"description": "Step 2", "tool": "browser", "parameters": {}, "critical": False}
        ]

        needs_replan = agent._execute_steps(state, max_step_retries=0)

        # Should have stopped after first step
        assert needs_replan is False
        assert len(state.errors) > 0

    def test_execute_steps_exception_during_step(self, graph_agent_with_mocks):
        """Test handling of exception during step execution."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent._executor._execute_step.side_effect = Exception("Unexpected error")
        agent_graph.providers.ask_ollama_model.return_value = json.dumps({"action": "abort", "reason": "error"})

        state = AgentState(goal="Test", context={})
        state.steps = [{"description": "Failing", "tool": "web_search", "parameters": {}, "critical": False}]

        agent._execute_steps(state, max_step_retries=0)

        # Should have captured the error
        assert len(state.results) > 0
        assert state.results[0]["status"] == "failed"

    def test_execute_steps_healed_success_clears_error(self, graph_agent_with_mocks):
        """Test that healed_success clears last_error."""
        agent, mocks = graph_agent_with_mocks
        from core.agent_graph import AgentState

        # First call fails, second healed
        agent._executor._execute_step.side_effect = [
            {"status": "healed_success", "result": "recovered", "tool": "web_search"}
        ]

        state = AgentState(goal="Test", context={"last_error": "previous error"})
        state.steps = [{"description": "Heal", "tool": "web_search", "parameters": {}}]

        agent._execute_steps(state, max_step_retries=0)

        assert "last_error" not in state.context


# ==============================================================================
# Tests for _reflect Method
# ==============================================================================


class TestReflectMethod:
    """Test the _reflect method."""

    def test_reflect_returns_parsed_action(self, graph_agent_with_mocks):
        """Test that reflect returns parsed action."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        reflection_response = json.dumps({
            "action": "retry",
            "reason": "transient failure"
        })
        agent_graph.providers.ask_ollama_model.return_value = reflection_response

        state = AgentState(goal="Test", context={})
        step = {"description": "Failed step", "tool": "web_search"}
        result = {"status": "failed", "error": "timeout"}

        reflection = agent._reflect(step, result, state)

        assert reflection["action"] == "retry"
        assert reflection["reason"] == "transient failure"

    def test_reflect_stores_lesson_in_memory(self, graph_agent_with_mocks):
        """Test that lessons are stored in memory."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        reflection_response = json.dumps({
            "action": "abort",
            "reason": "unrecoverable",
            "lesson": "Always validate inputs first"
        })
        agent_graph.providers.ask_ollama_model.return_value = reflection_response

        state = AgentState(goal="Test", context={})
        step = {"description": "Failed step", "tool": "terminal"}
        result = {"status": "failed", "error": "bad input"}

        agent._reflect(step, result, state)

        agent_graph.memory.append_entry.assert_called_once()
        call_args = agent_graph.memory.append_entry.call_args
        assert "Always validate inputs first" in call_args[0][0]

    def test_reflect_with_invalid_json_returns_abort(self, graph_agent_with_mocks):
        """Test that invalid JSON returns abort action."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent_graph.providers.ask_ollama_model.return_value = "Not valid JSON"

        state = AgentState(goal="Test", context={})
        reflection = agent._reflect({}, {}, state)

        assert reflection["action"] == "abort"
        assert reflection["reason"] == "reflection_failed"

    def test_reflect_with_exception_returns_abort(self, graph_agent_with_mocks):
        """Test that exception during reflection returns abort."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent_graph.providers.ask_ollama_model.side_effect = Exception("Reflection error")
        agent_graph.providers.generate_text.return_value = None

        state = AgentState(goal="Test", context={})
        reflection = agent._reflect({}, {}, state)

        assert reflection["action"] == "abort"
        agent._error_manager.handle_error.assert_called()

    def test_reflect_empty_lesson_not_stored(self, graph_agent_with_mocks):
        """Test that empty lessons are not stored."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        reflection_response = json.dumps({
            "action": "retry",
            "reason": "try again",
            "lesson": ""
        })
        agent_graph.providers.ask_ollama_model.return_value = reflection_response

        state = AgentState(goal="Test", context={})
        agent._reflect({}, {}, state)

        agent_graph.memory.append_entry.assert_not_called()


# ==============================================================================
# Tests for _summarize Method
# ==============================================================================


class TestSummarizeMethod:
    """Test the _summarize method."""

    def test_summarize_returns_model_response(self, graph_agent_with_mocks):
        """Test that summarize returns model response."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "Execution completed successfully."

        state = AgentState(goal="Test goal", context={})
        state.results = [{"status": "success", "result": "data"}]

        summary = agent._summarize(state)

        assert summary == "Execution completed successfully."

    def test_summarize_with_exception_returns_unavailable(self, graph_agent_with_mocks):
        """Test that exception returns 'Summary unavailable.'"""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph
        from core.agent_graph import AgentState

        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.side_effect = Exception("Summary failed")

        state = AgentState(goal="Test", context={})
        summary = agent._summarize(state)

        assert summary == "Summary unavailable."
        agent._error_manager.handle_error.assert_called()


# ==============================================================================
# Tests for _summarize_result Static Method
# ==============================================================================


class TestSummarizeResult:
    """Test the _summarize_result static method."""

    def test_summarize_result_with_error(self):
        """Test summarize_result with error field."""
        from core.agent_graph import GraphAgent

        result = {"error": "Connection timeout", "result": "ignored"}
        summary = GraphAgent._summarize_result(result)

        assert summary == "Connection timeout"

    def test_summarize_result_with_result_string(self):
        """Test summarize_result with result field string."""
        from core.agent_graph import GraphAgent

        result = {"result": "Operation completed successfully"}
        summary = GraphAgent._summarize_result(result)

        assert summary == "Operation completed successfully"

    def test_summarize_result_with_result_dict(self):
        """Test summarize_result with result field as dict."""
        from core.agent_graph import GraphAgent

        result = {"result": {"data": "value", "count": 42}}
        summary = GraphAgent._summarize_result(result)

        assert "data" in summary
        assert "value" in summary

    def test_summarize_result_with_result_list(self):
        """Test summarize_result with result field as list."""
        from core.agent_graph import GraphAgent

        result = {"result": [1, 2, 3, 4, 5]}
        summary = GraphAgent._summarize_result(result)

        assert "[1, 2, 3, 4, 5]" in summary

    def test_summarize_result_truncates_long_output(self):
        """Test that long results are truncated to 200 chars."""
        from core.agent_graph import GraphAgent

        long_text = "x" * 500
        result = {"result": long_text}
        summary = GraphAgent._summarize_result(result)

        assert len(summary) <= 200

    def test_summarize_result_empty_falls_back_to_result_dict(self):
        """Test empty payload falls back to result dict."""
        from core.agent_graph import GraphAgent

        result = {"status": "unknown"}
        summary = GraphAgent._summarize_result(result)

        assert "status" in summary


# ==============================================================================
# Tests for JSON Parsing Methods
# ==============================================================================


class TestParseJson:
    """Test the _parse_json method."""

    def test_parse_json_valid_json(self):
        """Test parsing valid JSON string."""
        from core.agent_graph import GraphAgent

        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            agent = GraphAgent()
            result = agent._parse_json('{"key": "value"}')

        assert result == {"key": "value"}

    def test_parse_json_with_markdown_wrapper(self):
        """Test parsing JSON wrapped in markdown."""
        from core.agent_graph import GraphAgent

        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            agent = GraphAgent()
            text = 'Here is the plan:\n```json\n{"steps": []}\n```\nEnd.'
            result = agent._parse_json(text)

        assert result == {"steps": []}

    def test_parse_json_with_text_before_json(self):
        """Test parsing with text before JSON object."""
        from core.agent_graph import GraphAgent

        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            agent = GraphAgent()
            text = 'Let me create a plan: {"action": "retry"}'
            result = agent._parse_json(text)

        assert result == {"action": "retry"}

    def test_parse_json_invalid_returns_none(self):
        """Test parsing invalid JSON returns None."""
        from core.agent_graph import GraphAgent

        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            agent = GraphAgent()
            result = agent._parse_json('Not JSON at all')

        assert result is None

    def test_parse_json_nested_objects(self):
        """Test parsing nested JSON objects."""
        from core.agent_graph import GraphAgent

        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            agent = GraphAgent()
            text = '{"outer": {"inner": {"deep": true}}}'
            result = agent._parse_json(text)

        assert result == {"outer": {"inner": {"deep": True}}}


class TestExtractJsonObject:
    """Test the _extract_json_object static method."""

    def test_extract_json_object_simple(self):
        """Test extracting simple JSON object."""
        from core.agent_graph import GraphAgent

        text = '{"key": "value"}'
        result = GraphAgent._extract_json_object(text)

        assert result == '{"key": "value"}'

    def test_extract_json_object_with_prefix(self):
        """Test extracting JSON with prefix text."""
        from core.agent_graph import GraphAgent

        text = 'Some text before {"data": 123} and after'
        result = GraphAgent._extract_json_object(text)

        assert result == '{"data": 123}'

    def test_extract_json_object_nested_braces(self):
        """Test extracting JSON with nested braces."""
        from core.agent_graph import GraphAgent

        text = '{"outer": {"inner": "value"}}'
        result = GraphAgent._extract_json_object(text)

        assert result == '{"outer": {"inner": "value"}}'

    def test_extract_json_object_empty_returns_none(self):
        """Test empty string returns None."""
        from core.agent_graph import GraphAgent

        result = GraphAgent._extract_json_object("")

        assert result is None

    def test_extract_json_object_no_braces_returns_none(self):
        """Test string without braces returns None."""
        from core.agent_graph import GraphAgent

        result = GraphAgent._extract_json_object("no json here")

        assert result is None

    def test_extract_json_object_unclosed_brace_returns_none(self):
        """Test unclosed brace returns None."""
        from core.agent_graph import GraphAgent

        result = GraphAgent._extract_json_object('{"key": "value"')

        assert result is None


# ==============================================================================
# Tests for _render_state Method
# ==============================================================================


class TestRenderState:
    """Test the _render_state method."""

    def test_render_state_without_results(self, graph_agent_with_mocks):
        """Test rendering state without results."""
        agent, mocks = graph_agent_with_mocks
        from core.agent_graph import AgentState

        state = AgentState(
            goal="Test goal",
            context={},
            plan={"steps": []},
            cycle=1,
            status="planned",
            errors=["error1"]
        )

        rendered = agent._render_state(state, include_results=False)

        assert rendered["goal"] == "Test goal"
        assert rendered["status"] == "planned"
        assert rendered["cycle"] == 1
        assert rendered["plan"] == {"steps": []}
        assert rendered["errors"] == ["error1"]
        assert "results" not in rendered
        assert "reflections" not in rendered
        assert "summary" not in rendered

    def test_render_state_with_results(self, graph_agent_with_mocks):
        """Test rendering state with results included."""
        agent, mocks = graph_agent_with_mocks
        from core.agent_graph import AgentState

        state = AgentState(
            goal="Test goal",
            context={},
            results=[{"status": "success"}],
            reflections=[{"action": "done"}],
            summary="Completed"
        )

        rendered = agent._render_state(state, include_results=True)

        assert "results" in rendered
        assert "reflections" in rendered
        assert "summary" in rendered
        assert rendered["results"] == [{"status": "success"}]
        assert rendered["summary"] == "Completed"


# ==============================================================================
# Tests for run Method
# ==============================================================================


class TestRunMethod:
    """Test the main run method."""

    def test_run_planning_only(self, graph_agent_with_mocks):
        """Test run with execute=False returns plan only."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_json = json.dumps({"steps": [{"description": "Step", "tool": "web_search", "parameters": {}}]})
        agent_graph.providers.ask_ollama_model.return_value = plan_json

        result = agent.run("Test goal", execute=False)

        assert result["status"] == "planned"
        assert "results" not in result

    def test_run_with_execution(self, graph_agent_with_mocks):
        """Test run with execution enabled."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_json = json.dumps({"steps": [{"description": "Step", "tool": "web_search", "parameters": {}, "critical": False}]})
        agent_graph.providers.ask_ollama_model.return_value = plan_json
        agent._executor._execute_step.return_value = {"status": "success", "result": "done", "tool": "web_search"}
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "Summary"

        result = agent.run("Test goal", execute=True, max_cycles=1)

        assert result["status"] == "completed"
        assert "results" in result
        assert "summary" in result

    def test_run_with_custom_context(self, graph_agent_with_mocks):
        """Test run with custom context."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_json = json.dumps({"steps": []})
        agent_graph.providers.ask_ollama_model.return_value = plan_json

        custom_context = {"custom": "data"}
        result = agent.run("Goal", context=custom_context, execute=False)

        assert result["status"] == "planned"

    def test_run_multiple_cycles_on_replan(self, graph_agent_with_mocks):
        """Test run with multiple cycles when replan is triggered."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        cycle_count = [0]

        def plan_side_effect(prompt, max_output_tokens):
            cycle_count[0] += 1
            if cycle_count[0] == 1:
                return json.dumps({"steps": [{"description": "Step", "tool": "web_search", "parameters": {}, "critical": False}]})
            return json.dumps({"steps": []})

        agent_graph.providers.ask_ollama_model.side_effect = plan_side_effect
        agent._executor._execute_step.return_value = {"status": "failed", "error": "need replan", "tool": "web_search"}

        # First call returns replan, subsequent don't
        agent._execute_steps = MagicMock(side_effect=[True, False])
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "Summary"

        result = agent.run("Goal", execute=True, max_cycles=2)

        # Should have cycled
        assert result["cycle"] >= 1

    def test_run_no_results_status(self, graph_agent_with_mocks):
        """Test run with no results sets no_results status."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        # Return plan with no steps
        plan_json = json.dumps({"steps": []})
        agent_graph.providers.ask_ollama_model.return_value = plan_json
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = ""

        # Mock _execute_steps to not add results (simulates no steps to execute)
        original_execute = agent._execute_steps
        def mock_execute(state, max_retries):
            # Don't add any results
            return False
        agent._execute_steps = mock_execute

        result = agent.run("Goal", execute=True, max_cycles=1)

        assert result["status"] == "no_results"

    def test_run_respects_max_cycles(self, graph_agent_with_mocks):
        """Test that run respects max_cycles limit."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_json = json.dumps({"steps": [{"description": "Step", "tool": "web_search", "parameters": {}, "critical": False}]})
        agent_graph.providers.ask_ollama_model.return_value = plan_json

        # Always trigger replan
        agent._execute_steps = MagicMock(return_value=True)
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "Summary"

        result = agent.run("Goal", execute=True, max_cycles=3)

        # Should have stopped at max_cycles
        assert result["cycle"] == 3


# ==============================================================================
# Additional Edge Case Tests
# ==============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_goal(self, graph_agent_with_mocks):
        """Test handling of empty goal."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_json = json.dumps({"steps": []})
        agent_graph.providers.ask_ollama_model.return_value = plan_json

        result = agent.run("", execute=False)

        assert result["goal"] == ""
        assert result["status"] == "planned"

    def test_unicode_in_goal(self, graph_agent_with_mocks):
        """Test handling of unicode in goal."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_json = json.dumps({"steps": []})
        agent_graph.providers.ask_ollama_model.return_value = plan_json

        unicode_goal = "Test with unicode: \u4e2d\u6587 \u0639\u0631\u0628\u064a"
        result = agent.run(unicode_goal, execute=False)

        assert result["goal"] == unicode_goal

    def test_very_long_goal(self, graph_agent_with_mocks):
        """Test handling of very long goal."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_json = json.dumps({"steps": []})
        agent_graph.providers.ask_ollama_model.return_value = plan_json

        long_goal = "Test " * 1000
        result = agent.run(long_goal, execute=False)

        assert result["goal"] == long_goal

    def test_context_with_special_characters(self, graph_agent_with_mocks):
        """Test context building with special characters."""
        agent, mocks = graph_agent_with_mocks

        special_context = {
            "quotes": 'He said "hello"',
            "newlines": "line1\nline2",
            "tabs": "col1\tcol2",
            "backslash": "path\\to\\file"
        }

        context = agent._build_context("goal", special_context)

        assert context["extra"] == special_context

    def test_json_with_arrays(self):
        """Test parsing JSON with arrays."""
        from core.agent_graph import GraphAgent

        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            agent = GraphAgent()
            text = '{"items": [1, 2, 3], "nested": [{"a": 1}, {"b": 2}]}'
            result = agent._parse_json(text)

        assert result == {"items": [1, 2, 3], "nested": [{"a": 1}, {"b": 2}]}

    def test_deeply_nested_json(self):
        """Test parsing deeply nested JSON."""
        from core.agent_graph import GraphAgent

        with patch.multiple(
            'core.agent_graph',
            agent_router=MagicMock(),
            autonomous_agent=MagicMock(),
            error_recovery=MagicMock(),
        ):
            agent = GraphAgent()
            deep = {"level1": {"level2": {"level3": {"level4": {"level5": "value"}}}}}
            text = json.dumps(deep)
            result = agent._parse_json(text)

        assert result == deep


# ==============================================================================
# Integration-style Tests (with mocks)
# ==============================================================================


class TestIntegrationScenarios:
    """Integration-style tests for complete workflows."""

    def test_full_planning_workflow(self, graph_agent_with_mocks):
        """Test complete planning workflow."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_response = json.dumps({
            "steps": [
                {"description": "Search for info", "tool": "web_search", "parameters": {"query": "test"}, "critical": True, "expected_output": "results"},
                {"description": "Analyze results", "tool": "browser", "parameters": {"url": "http://example.com"}, "critical": False, "expected_output": "analysis"}
            ]
        })
        agent_graph.providers.ask_ollama_model.return_value = plan_response

        result = agent.run("Find and analyze data", execute=False)

        assert result["status"] == "planned"
        assert len(result["plan"]["steps"]) == 2
        assert result["plan"]["steps"][0]["tool"] == "web_search"

    def test_full_execution_workflow(self, graph_agent_with_mocks):
        """Test complete execution workflow with success."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_response = json.dumps({
            "steps": [
                {"description": "Do task", "tool": "web_search", "parameters": {}, "critical": False, "expected_output": "done"}
            ]
        })
        agent_graph.providers.ask_ollama_model.return_value = plan_response
        agent._executor._execute_step.return_value = {"status": "success", "result": "Task completed", "tool": "web_search"}
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "All tasks completed successfully."

        result = agent.run("Complete the task", execute=True)

        assert result["status"] == "completed"
        assert len(result["results"]) == 1
        assert result["summary"] == "All tasks completed successfully."

    def test_workflow_with_failure_and_recovery(self, graph_agent_with_mocks):
        """Test workflow with failure, reflection, and recovery."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_response = json.dumps({
            "steps": [
                {"description": "Try task", "tool": "terminal", "parameters": {}, "critical": False}
            ]
        })

        # First planning call returns plan, second returns reflection
        call_count = [0]
        def ollama_side_effect(prompt, model=None, max_output_tokens=None):
            call_count[0] += 1
            if "Planner" in prompt:
                return plan_response
            elif "Reflector" in prompt:
                return json.dumps({"action": "retry", "reason": "transient"})
            else:
                return json.dumps({"action": "abort"})

        agent_graph.providers.ask_ollama_model.side_effect = ollama_side_effect

        # First execution fails, second succeeds
        exec_count = [0]
        def exec_side_effect(step, context):
            exec_count[0] += 1
            if exec_count[0] == 1:
                return {"status": "failed", "error": "temp failure", "tool": "terminal"}
            return {"status": "success", "result": "recovered", "tool": "terminal"}

        agent._executor._execute_step.side_effect = exec_side_effect
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "Recovered and completed."

        result = agent.run("Complete task", execute=True, max_step_retries=2)

        assert result["status"] == "completed"


# ==============================================================================
# Tests for State Transitions
# ==============================================================================


class TestStateTransitions:
    """Test state transitions during execution."""

    def test_state_transitions_during_run(self, graph_agent_with_mocks):
        """Track state transitions through run method."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_response = json.dumps({"steps": [{"description": "Step", "tool": "web_search", "parameters": {}}]})
        agent_graph.providers.ask_ollama_model.return_value = plan_response
        agent._executor._execute_step.return_value = {"status": "success", "result": "done", "tool": "web_search"}
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "Done"

        # States: initialized -> planning -> executing -> completed
        result = agent.run("Goal", execute=True)

        assert result["status"] == "completed"

    def test_cycle_increments(self, graph_agent_with_mocks):
        """Test that cycle counter increments correctly."""
        agent, mocks = graph_agent_with_mocks
        from core import agent_graph

        plan_response = json.dumps({"steps": [{"description": "Step", "tool": "web_search", "parameters": {}, "critical": False}]})
        agent_graph.providers.ask_ollama_model.return_value = plan_response

        # Force replan on first cycle
        agent._execute_steps = MagicMock(side_effect=[True, False])
        agent._router.route.return_value.provider = "openai"
        agent_graph.providers.generate_text.return_value = "Summary"

        result = agent.run("Goal", execute=True, max_cycles=3)

        assert result["cycle"] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
