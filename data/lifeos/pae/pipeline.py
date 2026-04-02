"""
PAE Pipeline

Allows chaining Provider, Action, and Evaluator components
into executable pipelines.

Features:
- Sequential and parallel step execution
- Conditional branching based on evaluator results
- Error handling and rollback
- Pipeline composition

Usage:
    pipeline = PAEPipeline("process_alert")
    pipeline.add_step(PipelineStep(provider="fetch_data"))
    pipeline.add_step(PipelineStep(evaluator="should_alert"))
    pipeline.add_step(PipelineStep(action="send_notification", condition="should_alert"))
    result = await pipeline.execute({"source": "sensor_1"})
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from lifeos.pae.base import (
    Provider,
    Action,
    Evaluator,
    EvaluationResult,
    PAEError,
    ProviderError,
    ActionError,
    EvaluatorError,
)

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Type of pipeline step."""
    PROVIDER = "provider"
    ACTION = "action"
    EVALUATOR = "evaluator"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class StepStatus(Enum):
    """Status of a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    """
    A single step in a pipeline.

    Each step can be:
    - A provider that fetches data
    - An action that performs an operation
    - An evaluator that makes a decision
    - A parallel group of steps
    - A conditional branch

    Attributes:
        provider: Name of provider to call
        action: Name of action to call
        evaluator: Name of evaluator to call
        parallel: List of steps to run in parallel
        condition: Evaluator result key that must be True
        input_mapping: Map context keys to component input
        output_key: Where to store the result
        on_error: What to do on error ("fail", "skip", "continue")
    """
    provider: Optional[str] = None
    action: Optional[str] = None
    evaluator: Optional[str] = None
    parallel: Optional[List["PipelineStep"]] = None
    condition: Optional[str] = None
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_key: Optional[str] = None
    on_error: str = "fail"
    name: Optional[str] = None

    def __post_init__(self):
        # Determine step type and name
        if self.provider:
            self._type = StepType.PROVIDER
            self.name = self.name or f"provider:{self.provider}"
        elif self.action:
            self._type = StepType.ACTION
            self.name = self.name or f"action:{self.action}"
        elif self.evaluator:
            self._type = StepType.EVALUATOR
            self.name = self.name or f"evaluator:{self.evaluator}"
        elif self.parallel:
            self._type = StepType.PARALLEL
            self.name = self.name or "parallel"
        else:
            raise ValueError("Step must have provider, action, evaluator, or parallel")

    @property
    def step_type(self) -> StepType:
        return self._type


@dataclass
class StepResult:
    """Result of executing a pipeline step."""
    step_name: str
    status: StepStatus
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineResult:
    """Result of executing a pipeline."""
    pipeline_name: str
    success: bool
    context: Dict[str, Any] = field(default_factory=dict)
    steps: List[StepResult] = field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0


class PAEPipeline:
    """
    Executable pipeline of PAE components.

    Chains providers, actions, and evaluators together
    with support for conditions, parallel execution, and error handling.

    Example:
        from lifeos.pae import PAEPipeline, PipelineStep

        pipeline = PAEPipeline("market_alert")

        # Fetch price data
        pipeline.add_step(PipelineStep(
            provider="price_provider",
            output_key="price_data"
        ))

        # Evaluate if price change is significant
        pipeline.add_step(PipelineStep(
            evaluator="price_change_evaluator",
            input_mapping={"data": "price_data"},
            output_key="should_alert"
        ))

        # Send alert if significant
        pipeline.add_step(PipelineStep(
            action="send_alert",
            condition="should_alert",
            input_mapping={"price": "price_data.price"}
        ))

        result = await pipeline.execute({"symbol": "SOL"})
    """

    def __init__(
        self,
        name: str,
        registry: Optional["PAERegistry"] = None,
    ):
        """
        Initialize pipeline.

        Args:
            name: Pipeline name
            registry: PAE registry to use (uses global if None)
        """
        self._name = name
        self._steps: List[PipelineStep] = []
        self._registry = registry

    @property
    def name(self) -> str:
        return self._name

    @property
    def steps(self) -> List[PipelineStep]:
        return list(self._steps)

    def add_step(self, step: PipelineStep) -> "PAEPipeline":
        """Add a step to the pipeline."""
        self._steps.append(step)
        return self

    def remove_step(self, index: int) -> "PAEPipeline":
        """Remove a step by index."""
        if 0 <= index < len(self._steps):
            del self._steps[index]
        return self

    def clear(self) -> "PAEPipeline":
        """Remove all steps."""
        self._steps.clear()
        return self

    async def execute(
        self,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Execute the pipeline.

        Args:
            initial_context: Initial context data

        Returns:
            Pipeline execution result
        """
        from lifeos.pae.registry import get_registry

        registry = self._registry or get_registry()
        context = dict(initial_context or {})
        step_results: List[StepResult] = []
        started_at = datetime.now(timezone.utc)

        logger.info(f"Executing pipeline: {self._name}")

        try:
            for step in self._steps:
                step_result = await self._execute_step(step, context, registry)
                step_results.append(step_result)

                if step_result.status == StepStatus.FAILED:
                    if step.on_error == "fail":
                        return PipelineResult(
                            pipeline_name=self._name,
                            success=False,
                            context=context,
                            steps=step_results,
                            error=step_result.error,
                            started_at=started_at,
                            completed_at=datetime.now(timezone.utc),
                        )
                    elif step.on_error == "skip":
                        continue

            return PipelineResult(
                pipeline_name=self._name,
                success=True,
                context=context,
                steps=step_results,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Pipeline {self._name} failed: {e}")
            return PipelineResult(
                pipeline_name=self._name,
                success=False,
                context=context,
                steps=step_results,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

    async def _execute_step(
        self,
        step: PipelineStep,
        context: Dict[str, Any],
        registry: "PAERegistry",
    ) -> StepResult:
        """Execute a single pipeline step."""
        started_at = datetime.now(timezone.utc)

        # Check condition
        if step.condition:
            condition_value = self._get_nested_value(context, step.condition)
            if not condition_value:
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )

        try:
            # Build input from mapping
            input_data = self._build_input(step.input_mapping, context)

            # Execute based on type
            if step.step_type == StepType.PROVIDER:
                result = await self._execute_provider(
                    step.provider, input_data, context, registry
                )
            elif step.step_type == StepType.ACTION:
                result = await self._execute_action(
                    step.action, input_data, context, registry
                )
            elif step.step_type == StepType.EVALUATOR:
                result = await self._execute_evaluator(
                    step.evaluator, input_data, context, registry
                )
            elif step.step_type == StepType.PARALLEL:
                result = await self._execute_parallel(
                    step.parallel, context, registry
                )
            else:
                raise ValueError(f"Unknown step type: {step.step_type}")

            # Store result
            if step.output_key:
                context[step.output_key] = result

            completed_at = datetime.now(timezone.utc)
            return StepResult(
                step_name=step.name,
                status=StepStatus.SUCCESS,
                result=result,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=(completed_at - started_at).total_seconds() * 1000,
            )

        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            logger.error(f"Step {step.name} failed: {e}")
            return StepResult(
                step_name=step.name,
                status=StepStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=(completed_at - started_at).total_seconds() * 1000,
            )

    async def _execute_provider(
        self,
        name: str,
        input_data: Dict[str, Any],
        context: Dict[str, Any],
        registry: "PAERegistry",
    ) -> Any:
        """Execute a provider step."""
        provider = registry.get_provider(name)
        if not provider:
            raise ProviderError(name, f"Provider not found: {name}")
        return await provider(input_data, context)

    async def _execute_action(
        self,
        name: str,
        input_data: Dict[str, Any],
        context: Dict[str, Any],
        registry: "PAERegistry",
    ) -> Dict[str, Any]:
        """Execute an action step."""
        action = registry.get_action(name)
        if not action:
            raise ActionError(name, f"Action not found: {name}")
        return await action(input_data, context)

    async def _execute_evaluator(
        self,
        name: str,
        input_data: Dict[str, Any],
        context: Dict[str, Any],
        registry: "PAERegistry",
    ) -> EvaluationResult:
        """Execute an evaluator step."""
        evaluator = registry.get_evaluator(name)
        if not evaluator:
            raise EvaluatorError(name, f"Evaluator not found: {name}")
        # Merge input with context for evaluator
        eval_context = {**context, **input_data}
        return await evaluator(eval_context)

    async def _execute_parallel(
        self,
        steps: List[PipelineStep],
        context: Dict[str, Any],
        registry: "PAERegistry",
    ) -> List[Any]:
        """Execute steps in parallel."""
        tasks = [
            self._execute_step(step, context, registry)
            for step in steps
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        output = []
        for step, result in zip(steps, results):
            if isinstance(result, Exception):
                if step.on_error == "fail":
                    raise result
                output.append(None)
            else:
                output.append(result.result)
                if step.output_key:
                    context[step.output_key] = result.result

        return output

    def _build_input(
        self,
        mapping: Dict[str, str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build input dict from mapping and context."""
        if not mapping:
            return dict(context)

        result = {}
        for target_key, source_path in mapping.items():
            value = self._get_nested_value(context, source_path)
            result[target_key] = value

        return result

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get a nested value using dot notation."""
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

            if current is None:
                return None

        return current

    def compose(self, other: "PAEPipeline") -> "PAEPipeline":
        """Compose this pipeline with another."""
        combined = PAEPipeline(
            f"{self._name}+{other._name}",
            registry=self._registry,
        )
        combined._steps = self._steps + other._steps
        return combined

    def __add__(self, other: "PAEPipeline") -> "PAEPipeline":
        """Allow pipeline + pipeline composition."""
        return self.compose(other)
