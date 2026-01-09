"""
Tests for lifeos/pae (Provider-Action-Evaluator) system.

Tests cover:
- Provider base class
- Action base class
- Evaluator base class
- Registry functionality
- Pipeline execution
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.pae import (
    Provider,
    Action,
    Evaluator,
    PAERegistry,
    PAEPipeline,
    PipelineStep,
    PipelineResult,
    PAEError,
    ProviderError,
    ActionError,
    EvaluatorError,
)
from lifeos.pae.base import (
    ComponentStatus,
    ComponentHealth,
    EvaluationResult,
)


# =============================================================================
# Test Provider
# =============================================================================

class MockProvider(Provider):
    """Test provider that returns query data."""

    async def provide(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return {"received": query, "processed": True}


class FailingProvider(Provider):
    """Provider that always fails."""

    async def provide(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        raise ValueError("Provider failure")


class ValidatingProvider(Provider):
    """Provider with query validation."""

    async def validate_query(self, query: Dict[str, Any]) -> List[str]:
        errors = []
        if "required_field" not in query:
            errors.append("Missing required_field")
        return errors

    async def provide(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return query["required_field"]


class TestProvider:
    """Test Provider base class."""

    @pytest.mark.asyncio
    async def test_basic_provide(self):
        """Should provide data."""
        provider = MockProvider("test")
        result = await provider({"key": "value"})

        assert result["received"]["key"] == "value"
        assert result["processed"] is True

    @pytest.mark.asyncio
    async def test_provider_tracks_stats(self):
        """Should track usage statistics."""
        provider = MockProvider("test")

        await provider({"a": 1})
        await provider({"b": 2})

        stats = provider.stats
        assert stats["use_count"] == 2
        assert stats["error_count"] == 0

    @pytest.mark.asyncio
    async def test_provider_tracks_errors(self):
        """Should track errors."""
        provider = FailingProvider("test")

        with pytest.raises(ProviderError):
            await provider({})

        stats = provider.stats
        assert stats["error_count"] == 1

    @pytest.mark.asyncio
    async def test_provider_validates_query(self):
        """Should validate query before execution."""
        provider = ValidatingProvider("test")

        with pytest.raises(ProviderError) as exc_info:
            await provider({})

        assert "Missing required_field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_provider_passes_validation(self):
        """Should execute when validation passes."""
        provider = ValidatingProvider("test")
        result = await provider({"required_field": "value"})

        assert result == "value"

    @pytest.mark.asyncio
    async def test_provider_lifecycle(self):
        """Should handle lifecycle correctly."""
        provider = MockProvider("test")

        assert provider.status == ComponentStatus.UNINITIALIZED

        await provider.initialize()
        assert provider.status == ComponentStatus.READY

        await provider.shutdown()
        assert provider.status == ComponentStatus.DISABLED


# =============================================================================
# Test Action
# =============================================================================

class MockAction(Action):
    """Test action that records execution."""

    def __init__(self, name: str, dependencies=None):
        super().__init__(name, dependencies)
        self.executed_with = []

    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.executed_with.append(params)
        return {"success": True, "params": params}


class FailingAction(Action):
    """Action that always fails."""

    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise ValueError("Action failure")


class ReversibleAction(Action):
    """Action that can be rolled back."""

    def __init__(self, name: str, dependencies=None):
        super().__init__(name, dependencies)
        self.rollback_called = False

    @property
    def is_reversible(self) -> bool:
        return True

    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {"created": True}

    async def rollback(
        self,
        params: Dict[str, Any],
        result: Dict[str, Any],
    ) -> bool:
        self.rollback_called = True
        return True


class TestAction:
    """Test Action base class."""

    @pytest.mark.asyncio
    async def test_basic_execute(self):
        """Should execute action."""
        action = MockAction("test")
        result = await action({"key": "value"})

        assert result["success"] is True
        assert result["params"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_action_tracks_execution(self):
        """Should track what params were used."""
        action = MockAction("test")

        await action({"a": 1})
        await action({"b": 2})

        assert len(action.executed_with) == 2
        assert action.executed_with[0]["a"] == 1

    @pytest.mark.asyncio
    async def test_action_tracks_errors(self):
        """Should track errors."""
        action = FailingAction("test")

        with pytest.raises(ActionError):
            await action({})

        stats = action.stats
        assert stats["error_count"] == 1

    @pytest.mark.asyncio
    async def test_reversible_action(self):
        """Should support rollback."""
        action = ReversibleAction("test")

        assert action.is_reversible is True

        result = await action.execute({})
        success = await action.rollback({}, result)

        assert success is True
        assert action.rollback_called is True

    def test_default_not_reversible(self):
        """Actions should not be reversible by default."""
        action = MockAction("test")
        assert action.is_reversible is False


# =============================================================================
# Test Evaluator
# =============================================================================

class MockEvaluator(Evaluator):
    """Test evaluator that checks a threshold."""

    def __init__(self, name: str, threshold: float = 0.5, dependencies=None):
        super().__init__(name, dependencies)
        self.threshold = threshold

    async def evaluate(self, context: Dict[str, Any]) -> EvaluationResult:
        value = context.get("value", 0)
        decision = value > self.threshold

        return EvaluationResult(
            decision=decision,
            confidence=0.9,
            reasoning=f"Value {value} {'>' if decision else '<='} {self.threshold}",
        )


class FailingEvaluator(Evaluator):
    """Evaluator that always fails."""

    async def evaluate(self, context: Dict[str, Any]) -> EvaluationResult:
        raise ValueError("Evaluator failure")


class TestEvaluator:
    """Test Evaluator base class."""

    @pytest.mark.asyncio
    async def test_basic_evaluate(self):
        """Should evaluate and return result."""
        evaluator = MockEvaluator("test", threshold=0.5)

        result = await evaluator({"value": 0.8})

        assert result.decision is True
        assert result.confidence == 0.9
        assert "0.8" in result.reasoning

    @pytest.mark.asyncio
    async def test_evaluation_result_as_bool(self):
        """EvaluationResult should work in conditionals."""
        evaluator = MockEvaluator("test", threshold=0.5)

        high = await evaluator({"value": 0.8})
        low = await evaluator({"value": 0.2})

        assert high  # True
        assert not low  # False

    @pytest.mark.asyncio
    async def test_evaluator_tracks_errors(self):
        """Should track errors."""
        evaluator = FailingEvaluator("test")

        with pytest.raises(EvaluatorError):
            await evaluator({})

        stats = evaluator.stats
        assert stats["error_count"] == 1


# =============================================================================
# Test PAERegistry
# =============================================================================

class TestPAERegistry:
    """Test PAE Registry functionality."""

    def test_register_provider(self):
        """Should register provider."""
        registry = PAERegistry()
        provider = MockProvider("test")

        registry.register_provider("test", provider)

        assert registry.get_provider("test") is provider

    def test_register_action(self):
        """Should register action."""
        registry = PAERegistry()
        action = MockAction("test")

        registry.register_action("test", action)

        assert registry.get_action("test") is action

    def test_register_evaluator(self):
        """Should register evaluator."""
        registry = PAERegistry()
        evaluator = MockEvaluator("test")

        registry.register_evaluator("test", evaluator)

        assert registry.get_evaluator("test") is evaluator

    def test_list_components(self):
        """Should list all registered components."""
        registry = PAERegistry()
        registry.register_provider("provider1", MockProvider("p1"))
        registry.register_provider("provider2", MockProvider("p2"))
        registry.register_action("action1", MockAction("a1"))

        providers = registry.list_providers()
        actions = registry.list_actions()

        assert len(providers) == 2
        assert len(actions) == 1
        assert "provider1" in providers
        assert "action1" in actions

    def test_list_by_tag(self):
        """Should filter components by tag."""
        registry = PAERegistry()
        registry.register_provider(
            "weather",
            MockProvider("weather"),
            tags={"data", "external"}
        )
        registry.register_provider(
            "internal",
            MockProvider("internal"),
            tags={"data", "internal"}
        )

        external = registry.list_providers(tag="external")
        data = registry.list_providers(tag="data")

        assert len(external) == 1
        assert "weather" in external
        assert len(data) == 2

    def test_find_by_tag(self):
        """Should find all components with a tag."""
        registry = PAERegistry()
        registry.register_provider("p1", MockProvider("p1"), tags={"shared"})
        registry.register_action("a1", MockAction("a1"), tags={"shared"})

        result = registry.find_by_tag("shared")

        assert "p1" in result["providers"]
        assert "a1" in result["actions"]

    def test_disable_component(self):
        """Should disable component."""
        registry = PAERegistry()
        registry.register_provider("test", MockProvider("test"))

        registry.disable("test")

        assert registry.get_provider("test") is None

    def test_enable_component(self):
        """Should re-enable component."""
        registry = PAERegistry()
        registry.register_provider("test", MockProvider("test"))

        registry.disable("test")
        registry.enable("test")

        assert registry.get_provider("test") is not None

    def test_unregister_component(self):
        """Should unregister component."""
        registry = PAERegistry()
        registry.register_provider("test", MockProvider("test"))

        result = registry.unregister("test")

        assert result is True
        assert registry.get_provider("test") is None

    def test_get_component_any_type(self):
        """Should get component regardless of type."""
        registry = PAERegistry()
        registry.register_provider("prov", MockProvider("prov"))
        registry.register_action("act", MockAction("act"))

        assert registry.get_component("prov") is not None
        assert registry.get_component("act") is not None
        assert registry.get_component("missing") is None

    @pytest.mark.asyncio
    async def test_initialize_all(self):
        """Should initialize all components."""
        registry = PAERegistry()
        provider = MockProvider("test")
        registry.register_provider("test", provider)

        await registry.initialize()

        assert provider.status == ComponentStatus.READY

    @pytest.mark.asyncio
    async def test_shutdown_all(self):
        """Should shutdown all components."""
        registry = PAERegistry()
        provider = MockProvider("test")
        registry.register_provider("test", provider)

        await registry.initialize()
        await registry.shutdown()

        assert provider.status == ComponentStatus.DISABLED

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Should check health of all components."""
        registry = PAERegistry()
        registry.register_provider("test", MockProvider("test"))
        await registry.initialize()

        health = await registry.health_check()

        assert "test" in health
        assert health["test"].status == ComponentStatus.READY

    def test_get_stats(self):
        """Should return registry statistics."""
        registry = PAERegistry()
        registry.register_provider("p1", MockProvider("p1"))
        registry.register_action("a1", MockAction("a1"))

        stats = registry.get_stats()

        assert stats["providers"]["total"] == 1
        assert stats["actions"]["total"] == 1
        assert "p1" in stats["components"]

    def test_service_injection(self):
        """Should inject services into components."""
        services = {"db": "mock_db", "cache": "mock_cache"}
        registry = PAERegistry(services=services)

        @registry.provider("test")
        class TestProvider(Provider):
            async def provide(self, query, context=None):
                return self.get_dependency("db")

        provider = registry.get_provider("test")
        assert provider.has_dependency("db")
        assert provider.get_dependency("db") == "mock_db"


# =============================================================================
# Test PAEPipeline
# =============================================================================

class TestPAEPipeline:
    """Test PAE Pipeline execution."""

    @pytest.fixture
    def registry(self):
        """Create a registry with test components."""
        reg = PAERegistry()

        # Data provider
        class DataProvider(Provider):
            async def provide(self, query, context=None):
                return {"value": query.get("value", 10)}

        # Threshold evaluator
        class ThresholdEvaluator(Evaluator):
            async def evaluate(self, context):
                value = context.get("data", {}).get("value", 0)
                return EvaluationResult(
                    decision=value > 5,
                    confidence=1.0,
                    reasoning=f"Value is {'above' if value > 5 else 'below'} threshold"
                )

        # Notification action
        class NotifyAction(Action):
            def __init__(self, name, deps=None):
                super().__init__(name, deps)
                self.notifications = []

            async def execute(self, params, context=None):
                self.notifications.append(params)
                return {"notified": True}

        reg.register_provider("data", DataProvider("data"))
        reg.register_evaluator("threshold", ThresholdEvaluator("threshold"))
        reg.register_action("notify", NotifyAction("notify"))

        return reg

    @pytest.mark.asyncio
    async def test_simple_pipeline(self, registry):
        """Should execute a simple pipeline."""
        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(
            provider="data",
            output_key="data",
        ))

        result = await pipeline.execute({"value": 42})

        assert result.success is True
        assert result.context["data"]["value"] == 42

    @pytest.mark.asyncio
    async def test_pipeline_with_evaluator(self, registry):
        """Should execute evaluator in pipeline."""
        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(
            provider="data",
            output_key="data",
        ))
        pipeline.add_step(PipelineStep(
            evaluator="threshold",
            output_key="should_notify",
        ))

        result = await pipeline.execute({"value": 10})

        assert result.success is True
        assert result.context["should_notify"].decision is True

    @pytest.mark.asyncio
    async def test_pipeline_conditional_action(self, registry):
        """Should skip action when condition is false."""
        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(
            provider="data",
            output_key="data",
        ))
        pipeline.add_step(PipelineStep(
            evaluator="threshold",
            output_key="should_notify",
        ))
        pipeline.add_step(PipelineStep(
            action="notify",
            condition="should_notify",
        ))

        # Value below threshold
        result = await pipeline.execute({"value": 3})

        assert result.success is True
        # Find the notify step result
        notify_step = next(
            (s for s in result.steps if "notify" in s.step_name),
            None
        )
        assert notify_step.status.value == "skipped"

    @pytest.mark.asyncio
    async def test_pipeline_executes_conditional_action(self, registry):
        """Should execute action when condition is true."""
        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(
            provider="data",
            output_key="data",
        ))
        pipeline.add_step(PipelineStep(
            evaluator="threshold",
            output_key="should_notify",
        ))
        pipeline.add_step(PipelineStep(
            action="notify",
            condition="should_notify",
            output_key="notify_result",
        ))

        # Value above threshold
        result = await pipeline.execute({"value": 10})

        assert result.success is True
        assert result.context.get("notify_result", {}).get("notified") is True

    @pytest.mark.asyncio
    async def test_pipeline_failure(self, registry):
        """Should handle step failure."""
        # Register failing provider
        class FailProvider(Provider):
            async def provide(self, query, context=None):
                raise ValueError("Failed!")

        registry.register_provider("fail", FailProvider("fail"))

        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(provider="fail"))

        result = await pipeline.execute({})

        assert result.success is False
        assert "Failed!" in result.error

    @pytest.mark.asyncio
    async def test_pipeline_continue_on_error(self, registry):
        """Should continue when on_error is 'continue'."""
        class FailProvider(Provider):
            async def provide(self, query, context=None):
                raise ValueError("Failed!")

        registry.register_provider("fail", FailProvider("fail"))

        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(
            provider="fail",
            on_error="continue",
        ))
        pipeline.add_step(PipelineStep(
            provider="data",
            output_key="data",
        ))

        result = await pipeline.execute({"value": 5})

        assert result.success is True
        assert result.context.get("data") is not None

    @pytest.mark.asyncio
    async def test_pipeline_input_mapping(self, registry):
        """Should map inputs correctly."""
        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(
            provider="data",
            input_mapping={"value": "input_value"},
            output_key="result",
        ))

        result = await pipeline.execute({"input_value": 99})

        assert result.context["result"]["value"] == 99

    def test_pipeline_composition(self, registry):
        """Should compose pipelines."""
        pipeline1 = PAEPipeline("first", registry)
        pipeline1.add_step(PipelineStep(provider="data", output_key="d1"))

        pipeline2 = PAEPipeline("second", registry)
        pipeline2.add_step(PipelineStep(evaluator="threshold", output_key="e1"))

        combined = pipeline1 + pipeline2

        assert len(combined.steps) == 2
        assert combined.name == "first+second"

    def test_pipeline_duration(self, registry):
        """Pipeline result should track duration."""
        pipeline = PAEPipeline("test", registry)
        pipeline.add_step(PipelineStep(provider="data"))

        # Execute synchronously for simplicity
        result = asyncio.get_event_loop().run_until_complete(
            pipeline.execute({})
        )

        assert result.duration_ms >= 0
        assert result.started_at is not None
        assert result.completed_at is not None


# =============================================================================
# Test Error Classes
# =============================================================================

class TestErrors:
    """Test PAE error classes."""

    def test_pae_error_format(self):
        """Should format error message."""
        err = PAEError("component", "Something failed")

        assert "[component]" in str(err)
        assert "Something failed" in str(err)

    def test_pae_error_with_original(self):
        """Should store original error."""
        original = ValueError("original")
        err = PAEError("component", "wrapped", original_error=original)

        assert err.original_error is original

    def test_provider_error(self):
        """ProviderError should be PAEError."""
        err = ProviderError("prov", "failed")

        assert isinstance(err, PAEError)
        assert "[prov]" in str(err)

    def test_action_error(self):
        """ActionError should be PAEError."""
        err = ActionError("act", "failed")

        assert isinstance(err, PAEError)

    def test_evaluator_error(self):
        """EvaluatorError should be PAEError."""
        err = EvaluatorError("eval", "failed")

        assert isinstance(err, PAEError)
