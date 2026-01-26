"""
Comprehensive unit tests for core/agent_router.py - Model Router System.

Tests for:
- RouteDecision dataclass
- ModelRouter initialization and configuration
- Routing logic based on role, prompt content, and context
- Forced route overrides
- Deep vs fast model selection
- Provider and token configuration

Target: 90%+ coverage of the 80-line module.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Any, Dict


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config_empty() -> Dict[str, Any]:
    """Empty configuration - all defaults."""
    return {}


@pytest.fixture
def mock_config_basic() -> Dict[str, Any]:
    """Basic router configuration."""
    return {
        "router": {
            "provider": "ollama",
            "fast_model": "llama3:8b",
            "deep_model": "llama3:70b",
            "fast_max_tokens": 256,
            "deep_max_tokens": 1024,
        }
    }


@pytest.fixture
def mock_config_auto_provider() -> Dict[str, Any]:
    """Configuration with auto provider."""
    return {
        "router": {
            "provider": "auto",
            "fast_model": "gpt-4o-mini",
            "deep_model": "gpt-4o",
            "fast_max_tokens": 500,
            "deep_max_tokens": 2000,
        }
    }


@pytest.fixture
def mock_config_ollama_fallback() -> Dict[str, Any]:
    """Configuration with ollama model fallback."""
    return {
        "providers": {
            "ollama": {
                "model": "mistral:7b"
            }
        }
    }


@pytest.fixture
def mock_config_no_models() -> Dict[str, Any]:
    """Configuration with no models specified."""
    return {
        "router": {
            "provider": "auto",
        }
    }


@pytest.fixture
def mock_config_partial_models() -> Dict[str, Any]:
    """Configuration with only fast model."""
    return {
        "router": {
            "provider": "openai",
            "fast_model": "gpt-4o-mini",
            # deep_model will fall back to fast_model
        }
    }


# =============================================================================
# RouteDecision Dataclass Tests
# =============================================================================


class TestRouteDecision:
    """Tests for RouteDecision dataclass."""

    def test_route_decision_creation_with_all_fields(self):
        """RouteDecision should be creatable with all fields."""
        from core.agent_router import RouteDecision

        decision = RouteDecision(
            mode="deep",
            provider="ollama",
            model="llama3:70b",
            max_output_tokens=1024,
            reason="role:coder",
        )

        assert decision.mode == "deep"
        assert decision.provider == "ollama"
        assert decision.model == "llama3:70b"
        assert decision.max_output_tokens == 1024
        assert decision.reason == "role:coder"

    def test_route_decision_with_none_model(self):
        """RouteDecision should accept None for model."""
        from core.agent_router import RouteDecision

        decision = RouteDecision(
            mode="fast",
            provider="auto",
            model=None,
            max_output_tokens=256,
            reason="lightweight",
        )

        assert decision.model is None
        assert decision.provider == "auto"

    def test_route_decision_fast_mode(self):
        """RouteDecision should handle fast mode."""
        from core.agent_router import RouteDecision

        decision = RouteDecision(
            mode="fast",
            provider="openai",
            model="gpt-4o-mini",
            max_output_tokens=500,
            reason="lightweight",
        )

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_decision_forced_reason(self):
        """RouteDecision should track forced route reason."""
        from core.agent_router import RouteDecision

        decision = RouteDecision(
            mode="deep",
            provider="anthropic",
            model="claude-3-opus",
            max_output_tokens=2000,
            reason="forced",
        )

        assert decision.reason == "forced"

    def test_route_decision_content_reason(self):
        """RouteDecision should track content-based reason."""
        from core.agent_router import RouteDecision

        decision = RouteDecision(
            mode="deep",
            provider="ollama",
            model="codellama",
            max_output_tokens=1024,
            reason="content",
        )

        assert decision.reason == "content"


# =============================================================================
# ModelRouter Initialization Tests
# =============================================================================


class TestModelRouterInit:
    """Tests for ModelRouter.__init__ configuration parsing."""

    def test_init_with_provided_config(self, mock_config_basic):
        """ModelRouter should use provided config."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)

        assert router._provider == "ollama"
        assert router._fast_model == "llama3:8b"
        assert router._deep_model == "llama3:70b"
        assert router._fast_tokens == 256
        assert router._deep_tokens == 1024

    def test_init_with_auto_provider(self, mock_config_auto_provider):
        """ModelRouter should handle auto provider."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_auto_provider)

        assert router._provider == "auto"
        assert router._fast_model == "gpt-4o-mini"
        assert router._deep_model == "gpt-4o"

    def test_init_falls_back_to_ollama_model(self, mock_config_ollama_fallback):
        """ModelRouter should fall back to ollama model when fast_model not set."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_ollama_fallback)

        assert router._fast_model == "mistral:7b"
        assert router._deep_model == "mistral:7b"

    def test_init_with_no_models(self, mock_config_no_models):
        """ModelRouter should handle missing model configs gracefully."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_no_models)

        assert router._fast_model == ""
        assert router._deep_model == ""

    def test_init_deep_model_falls_back_to_fast(self, mock_config_partial_models):
        """ModelRouter should use fast_model for deep_model if not specified."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_partial_models)

        assert router._fast_model == "gpt-4o-mini"
        assert router._deep_model == "gpt-4o-mini"

    def test_init_default_token_limits(self, mock_config_empty):
        """ModelRouter should use default token limits when not configured."""
        from core.agent_router import ModelRouter

        with patch("core.agent_router.config.load_config", return_value=mock_config_empty):
            router = ModelRouter()

        assert router._fast_tokens == 256
        assert router._deep_tokens == 900

    @patch("core.agent_router.config.load_config")
    def test_init_loads_config_when_none_provided(self, mock_load):
        """ModelRouter should call config.load_config when no config provided."""
        from core.agent_router import ModelRouter

        mock_load.return_value = {
            "router": {
                "provider": "openai",
                "fast_model": "test-fast",
                "deep_model": "test-deep",
            }
        }

        router = ModelRouter()

        mock_load.assert_called_once()
        assert router._fast_model == "test-fast"

    def test_init_provider_normalized_to_lowercase(self):
        """ModelRouter should normalize provider to lowercase."""
        from core.agent_router import ModelRouter

        cfg = {"router": {"provider": "OLLAMA"}}
        router = ModelRouter(cfg=cfg)

        assert router._provider == "ollama"

    def test_init_handles_non_string_provider(self):
        """ModelRouter should handle non-string provider values."""
        from core.agent_router import ModelRouter

        cfg = {"router": {"provider": 123}}
        router = ModelRouter(cfg=cfg)

        assert router._provider == "123"

    def test_init_strips_whitespace_from_models(self):
        """ModelRouter should strip whitespace from model names."""
        from core.agent_router import ModelRouter

        cfg = {
            "router": {
                "fast_model": "  llama3:8b  ",
                "deep_model": "  llama3:70b  ",
            }
        }
        router = ModelRouter(cfg=cfg)

        assert router._fast_model == "llama3:8b"
        assert router._deep_model == "llama3:70b"


# =============================================================================
# ModelRouter.route() - Forced Route Tests
# =============================================================================


class TestModelRouterForcedRoute:
    """Tests for forced route context overrides."""

    def test_route_forced_fast(self, mock_config_basic):
        """Forced route 'fast' should override all logic."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)

        # Even with a deep role, forced fast should win
        decision = router.route(
            role="coder",
            prompt="This is a complex coding task with traceback",
            context={"route": "fast"},
        )

        assert decision.mode == "fast"
        assert decision.reason == "forced"
        assert decision.model == "llama3:8b"
        assert decision.max_output_tokens == 256

    def test_route_forced_deep(self, mock_config_basic):
        """Forced route 'deep' should override all logic."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)

        # Even with a simple prompt, forced deep should win
        decision = router.route(
            role="user",
            prompt="Hi",
            context={"route": "deep"},
        )

        assert decision.mode == "deep"
        assert decision.reason == "forced"
        assert decision.model == "llama3:70b"
        assert decision.max_output_tokens == 1024

    def test_route_forced_case_insensitive(self, mock_config_basic):
        """Forced route should be case insensitive."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)

        decision_upper = router.route("user", "Hi", context={"route": "FAST"})
        decision_mixed = router.route("user", "Hi", context={"route": "Fast"})

        assert decision_upper.mode == "fast"
        assert decision_mixed.mode == "fast"

    def test_route_forced_invalid_value_ignored(self, mock_config_basic):
        """Invalid forced route values should be ignored."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)

        decision = router.route(
            role="coder",  # Deep role
            prompt="Code task",
            context={"route": "invalid"},
        )

        # Should use normal logic since "invalid" is not fast/deep
        assert decision.mode == "deep"
        assert decision.reason == "role:coder"


# =============================================================================
# ModelRouter.route() - Role-Based Routing Tests
# =============================================================================


class TestModelRouterRoleBasedRouting:
    """Tests for role-based routing decisions."""

    @pytest.fixture
    def router(self, mock_config_basic):
        """Create router with basic config."""
        from core.agent_router import ModelRouter
        return ModelRouter(cfg=mock_config_basic)

    def test_route_planner_role_uses_deep(self, router):
        """Planner role should route to deep."""
        decision = router.route("planner", "Simple question")

        assert decision.mode == "deep"
        assert decision.reason == "role:planner"

    def test_route_reflector_role_uses_deep(self, router):
        """Reflector role should route to deep."""
        decision = router.route("reflector", "Think about this")

        assert decision.mode == "deep"
        assert decision.reason == "role:reflector"

    def test_route_coder_role_uses_deep(self, router):
        """Coder role should route to deep."""
        decision = router.route("coder", "Write a function")

        assert decision.mode == "deep"
        assert decision.reason == "role:coder"

    def test_route_executor_role_uses_deep(self, router):
        """Executor role should route to deep."""
        decision = router.route("executor", "Execute this task")

        assert decision.mode == "deep"
        assert decision.reason == "role:executor"

    def test_route_role_case_insensitive(self, router):
        """Role matching should be case insensitive."""
        decision_upper = router.route("PLANNER", "Task")
        decision_mixed = router.route("Planner", "Task")
        decision_lower = router.route("planner", "Task")

        assert decision_upper.mode == "deep"
        assert decision_mixed.mode == "deep"
        assert decision_lower.mode == "deep"

    def test_route_unknown_role_uses_lightweight(self, router):
        """Unknown roles should use lightweight routing."""
        decision = router.route("assistant", "Short question")

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_empty_role_uses_lightweight(self, router):
        """Empty role should use lightweight routing."""
        decision = router.route("", "Short question")

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_none_role_uses_lightweight(self, router):
        """None role should use lightweight routing."""
        decision = router.route(None, "Short question")

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"


# =============================================================================
# ModelRouter.route() - Content-Based Routing Tests
# =============================================================================


class TestModelRouterContentBasedRouting:
    """Tests for content-based routing (keywords and length)."""

    @pytest.fixture
    def router(self, mock_config_basic):
        """Create router with basic config."""
        from core.agent_router import ModelRouter
        return ModelRouter(cfg=mock_config_basic)

    def test_route_long_prompt_uses_deep(self, router):
        """Prompts over 1200 chars should route to deep."""
        long_prompt = "x" * 1201

        decision = router.route("user", long_prompt)

        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_exactly_1200_chars_uses_fast(self, router):
        """Prompt exactly 1200 chars should use fast (not > 1200)."""
        prompt = "x" * 1200

        decision = router.route("user", prompt)

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_short_prompt_uses_fast(self, router):
        """Short prompts without keywords should use fast."""
        decision = router.route("user", "Hello, how are you?")

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    # Keyword tests - one for each keyword
    def test_route_keyword_traceback(self, router):
        """Traceback keyword should trigger deep routing."""
        decision = router.route("user", "I got a traceback in my code")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_stack_trace(self, router):
        """Stack trace keyword should trigger deep routing."""
        decision = router.route("user", "The stack trace shows an error")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_exception(self, router):
        """Exception keyword should trigger deep routing."""
        decision = router.route("user", "I'm getting an exception")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_error(self, router):
        """Error keyword should trigger deep routing."""
        decision = router.route("user", "There's an error message")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_bug(self, router):
        """Bug keyword should trigger deep routing."""
        decision = router.route("user", "I found a bug in the code")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_refactor(self, router):
        """Refactor keyword should trigger deep routing."""
        decision = router.route("user", "Please refactor this function")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_optimize(self, router):
        """Optimize keyword should trigger deep routing."""
        decision = router.route("user", "We need to optimize performance")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_unit_test(self, router):
        """Unit test keyword should trigger deep routing."""
        decision = router.route("user", "Write a unit test for this")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_pytest(self, router):
        """Pytest keyword should trigger deep routing."""
        decision = router.route("user", "How do I use pytest fixtures?")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_def(self, router):
        """'def ' keyword should trigger deep routing."""
        decision = router.route("user", "def calculate_total(items):")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_class(self, router):
        """'class ' keyword should trigger deep routing."""
        decision = router.route("user", "class MyClass:")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_import(self, router):
        """'import ' keyword should trigger deep routing."""
        decision = router.route("user", "import asyncio")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_sql(self, router):
        """SQL keyword should trigger deep routing."""
        decision = router.route("user", "Write an sql query for users")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_regex(self, router):
        """Regex keyword should trigger deep routing."""
        decision = router.route("user", "I need a regex pattern")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_http(self, router):
        """HTTP keyword should trigger deep routing."""
        decision = router.route("user", "Make an http request")
        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_keyword_case_insensitive(self, router):
        """Keywords should be case insensitive."""
        decision_lower = router.route("user", "traceback error")
        decision_upper = router.route("user", "TRACEBACK ERROR")
        decision_mixed = router.route("user", "TraceBack Error")

        assert decision_lower.mode == "deep"
        assert decision_upper.mode == "deep"
        assert decision_mixed.mode == "deep"

    def test_route_multiple_keywords(self, router):
        """Multiple keywords should still route to deep."""
        decision = router.route(
            "user",
            "The traceback shows an exception in the import statement"
        )

        assert decision.mode == "deep"
        assert decision.reason == "content"


# =============================================================================
# ModelRouter.route() - Context Handling Tests
# =============================================================================


class TestModelRouterContextHandling:
    """Tests for context parameter handling."""

    @pytest.fixture
    def router(self, mock_config_basic):
        """Create router with basic config."""
        from core.agent_router import ModelRouter
        return ModelRouter(cfg=mock_config_basic)

    def test_route_with_none_context(self, router):
        """None context should be handled gracefully."""
        decision = router.route("user", "Hello", context=None)

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_with_empty_context(self, router):
        """Empty context dict should be handled gracefully."""
        decision = router.route("user", "Hello", context={})

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_context_without_route_key(self, router):
        """Context without route key should be handled gracefully."""
        decision = router.route(
            "user",
            "Hello",
            context={"other_key": "value"},
        )

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_context_with_non_string_route(self, router):
        """Non-string route value should be handled."""
        decision = router.route(
            "user",
            "Hello",
            context={"route": 123},
        )

        # 123 lowercased is "123", not in {"fast", "deep"}
        assert decision.reason == "lightweight"


# =============================================================================
# ModelRouter.route() - Provider Selection Tests
# =============================================================================


class TestModelRouterProviderSelection:
    """Tests for provider selection in route decisions."""

    def test_route_uses_configured_provider(self, mock_config_basic):
        """Route should use the configured provider."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)
        decision = router.route("user", "Hello")

        assert decision.provider == "ollama"

    def test_route_provider_auto_when_no_model(self, mock_config_no_models):
        """Provider should be 'auto' when no model is configured."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_no_models)
        decision = router.route("user", "Hello")

        assert decision.provider == "auto"
        assert decision.model is None

    def test_route_provider_auto_with_model(self, mock_config_auto_provider):
        """Auto provider should be used when configured with models."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_auto_provider)
        decision = router.route("user", "Hello")

        assert decision.provider == "auto"
        assert decision.model == "gpt-4o-mini"


# =============================================================================
# ModelRouter.route() - Token Limits Tests
# =============================================================================


class TestModelRouterTokenLimits:
    """Tests for max_output_tokens in route decisions."""

    def test_route_fast_uses_fast_tokens(self, mock_config_basic):
        """Fast route should use fast_max_tokens."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)
        decision = router.route("user", "Hello")

        assert decision.mode == "fast"
        assert decision.max_output_tokens == 256

    def test_route_deep_uses_deep_tokens(self, mock_config_basic):
        """Deep route should use deep_max_tokens."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)
        decision = router.route("coder", "Write code")

        assert decision.mode == "deep"
        assert decision.max_output_tokens == 1024

    def test_route_custom_token_limits(self):
        """Custom token limits should be respected."""
        from core.agent_router import ModelRouter

        cfg = {
            "router": {
                "fast_max_tokens": 100,
                "deep_max_tokens": 5000,
            }
        }
        router = ModelRouter(cfg=cfg)

        fast_decision = router.route("user", "Hi")
        deep_decision = router.route("coder", "Code")

        assert fast_decision.max_output_tokens == 100
        assert deep_decision.max_output_tokens == 5000


# =============================================================================
# ModelRouter.route() - Model Selection Tests
# =============================================================================


class TestModelRouterModelSelection:
    """Tests for model selection in route decisions."""

    def test_route_fast_uses_fast_model(self, mock_config_basic):
        """Fast route should use fast_model."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)
        decision = router.route("user", "Hello")

        assert decision.mode == "fast"
        assert decision.model == "llama3:8b"

    def test_route_deep_uses_deep_model(self, mock_config_basic):
        """Deep route should use deep_model."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_basic)
        decision = router.route("coder", "Write code")

        assert decision.mode == "deep"
        assert decision.model == "llama3:70b"

    def test_route_model_none_when_empty(self, mock_config_no_models):
        """Model should be None when not configured."""
        from core.agent_router import ModelRouter

        router = ModelRouter(cfg=mock_config_no_models)
        decision = router.route("user", "Hello")

        assert decision.model is None


# =============================================================================
# Code Keywords Constant Tests
# =============================================================================


class TestCodeKeywords:
    """Tests for _CODE_KEYWORDS constant."""

    def test_code_keywords_is_tuple(self):
        """_CODE_KEYWORDS should be a tuple for immutability."""
        from core.agent_router import _CODE_KEYWORDS

        assert isinstance(_CODE_KEYWORDS, tuple)

    def test_code_keywords_contains_expected_keywords(self):
        """_CODE_KEYWORDS should contain all expected keywords."""
        from core.agent_router import _CODE_KEYWORDS

        expected = {
            "traceback",
            "stack trace",
            "exception",
            "error",
            "bug",
            "refactor",
            "optimize",
            "unit test",
            "pytest",
            "def ",
            "class ",
            "import ",
            "sql",
            "regex",
            "http",
        }

        for keyword in expected:
            assert keyword in _CODE_KEYWORDS, f"Missing keyword: {keyword}"

    def test_code_keywords_all_lowercase(self):
        """_CODE_KEYWORDS should all be lowercase."""
        from core.agent_router import _CODE_KEYWORDS

        for keyword in _CODE_KEYWORDS:
            assert keyword == keyword.lower(), f"Keyword not lowercase: {keyword}"


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestModelRouterEdgeCases:
    """Tests for edge cases and unusual inputs."""

    @pytest.fixture
    def router(self, mock_config_basic):
        """Create router with basic config."""
        from core.agent_router import ModelRouter
        return ModelRouter(cfg=mock_config_basic)

    def test_route_empty_prompt(self, router):
        """Empty prompt should route to fast."""
        decision = router.route("user", "")

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_whitespace_prompt(self, router):
        """Whitespace-only prompt should route to fast."""
        decision = router.route("user", "   \n\t  ")

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_unicode_prompt(self, router):
        """Unicode prompt should be handled."""
        decision = router.route("user", "Hello world!")

        assert decision.mode == "fast"
        assert decision.reason == "lightweight"

    def test_route_long_unicode_prompt(self, router):
        """Long unicode prompt should trigger deep."""
        long_unicode = "test " * 300  # Over 1200 chars

        decision = router.route("user", long_unicode)

        assert decision.mode == "deep"
        assert decision.reason == "content"

    def test_route_role_priority_over_short_content(self, router):
        """Role should take priority over short content."""
        decision = router.route("planner", "Hi")

        assert decision.mode == "deep"
        assert decision.reason == "role:planner"

    def test_route_forced_priority_over_role(self, router):
        """Forced route should take priority over role."""
        decision = router.route("planner", "Hi", context={"route": "fast"})

        assert decision.mode == "fast"
        assert decision.reason == "forced"

    def test_route_forced_priority_over_content(self, router):
        """Forced route should take priority over content keywords."""
        decision = router.route(
            "user",
            "traceback exception error bug",
            context={"route": "fast"},
        )

        assert decision.mode == "fast"
        assert decision.reason == "forced"


class TestModelRouterIntegration:
    """Integration tests for complete routing scenarios."""

    def test_full_deep_routing_scenario(self):
        """Test complete deep routing with all config options."""
        from core.agent_router import ModelRouter

        cfg = {
            "router": {
                "provider": "anthropic",
                "fast_model": "claude-haiku",
                "deep_model": "claude-opus",
                "fast_max_tokens": 512,
                "deep_max_tokens": 4096,
            }
        }
        router = ModelRouter(cfg=cfg)

        decision = router.route(
            role="coder",
            prompt="Please write a comprehensive test suite with pytest",
        )

        assert decision.mode == "deep"
        assert decision.provider == "anthropic"
        assert decision.model == "claude-opus"
        assert decision.max_output_tokens == 4096
        # Could be either role:coder or content (pytest keyword)
        assert decision.reason in ("role:coder", "content")

    def test_full_fast_routing_scenario(self):
        """Test complete fast routing with simple input."""
        from core.agent_router import ModelRouter

        cfg = {
            "router": {
                "provider": "openai",
                "fast_model": "gpt-4o-mini",
                "deep_model": "gpt-4o",
                "fast_max_tokens": 256,
                "deep_max_tokens": 2048,
            }
        }
        router = ModelRouter(cfg=cfg)

        decision = router.route(
            role="assistant",
            prompt="What's the weather like?",
        )

        assert decision.mode == "fast"
        assert decision.provider == "openai"
        assert decision.model == "gpt-4o-mini"
        assert decision.max_output_tokens == 256
        assert decision.reason == "lightweight"

    def test_routing_respects_priority_order(self):
        """Test that routing follows: forced > role > content > lightweight."""
        from core.agent_router import ModelRouter

        cfg = {"router": {"fast_model": "fast", "deep_model": "deep"}}
        router = ModelRouter(cfg=cfg)

        # 1. Forced takes priority over everything
        d1 = router.route("coder", "traceback error", {"route": "fast"})
        assert d1.reason == "forced"

        # 2. Role takes priority over content (when not forced)
        d2 = router.route("planner", "simple short question")
        assert d2.reason == "role:planner"

        # 3. Content keywords trigger deep
        d3 = router.route("user", "fix this error please")
        assert d3.reason == "content"

        # 4. Length triggers deep
        d4 = router.route("user", "x" * 1201)
        assert d4.reason == "content"

        # 5. Otherwise lightweight
        d5 = router.route("user", "hello")
        assert d5.reason == "lightweight"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
