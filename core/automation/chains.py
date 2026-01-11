"""
Action Chains - Multi-step sequential and parallel action execution.

Features:
- Sequential action chains
- Parallel action groups
- Conditional branching
- Error handling and rollback
- Progress tracking
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import uuid

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Status of a chain step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class ExecutionMode(Enum):
    """Execution mode for steps."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


@dataclass
class ChainStep:
    """
    A single step in an action chain.

    Attributes:
        name: Human-readable step name
        action: Async callable to execute
        params: Parameters to pass to action
        condition: Optional condition function (returns bool)
        on_error: Error handling strategy
        rollback: Optional rollback action
        timeout: Step timeout in seconds
        retries: Number of retry attempts
    """
    name: str
    action: Callable
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable[[], bool]] = None
    on_error: str = "fail"  # fail, skip, retry, continue
    rollback: Optional[Callable] = None
    timeout: float = 30.0
    retries: int = 0
    depends_on: List[str] = field(default_factory=list)

    # Runtime state
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0


@dataclass
class ChainResult:
    """Result of chain execution."""
    chain_id: str
    success: bool
    steps_completed: int
    steps_total: int
    results: Dict[str, Any]
    errors: List[Dict[str, str]]
    duration_ms: float
    rolled_back: bool = False


class ActionChain:
    """
    Multi-step action chain with error handling.

    Usage:
        chain = ActionChain("deploy-process")
        chain.add_step("build", build_action, params={"env": "prod"})
        chain.add_step("test", test_action, depends_on=["build"])
        chain.add_step("deploy", deploy_action, depends_on=["test"], rollback=rollback_deploy)

        result = await chain.execute()
    """

    def __init__(
        self,
        name: str,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        stop_on_error: bool = True,
        enable_rollback: bool = True,
    ):
        self.id = str(uuid.uuid4())[:12]
        self.name = name
        self.mode = mode
        self.stop_on_error = stop_on_error
        self.enable_rollback = enable_rollback

        self._steps: List[ChainStep] = []
        self._context: Dict[str, Any] = {}
        self._completed_steps: List[ChainStep] = []
        self._progress_callbacks: List[Callable] = []

    def add_step(
        self,
        name: str,
        action: Callable,
        params: Optional[Dict[str, Any]] = None,
        condition: Optional[Callable[[], bool]] = None,
        on_error: str = "fail",
        rollback: Optional[Callable] = None,
        timeout: float = 30.0,
        retries: int = 0,
        depends_on: Optional[List[str]] = None,
    ) -> "ActionChain":
        """Add a step to the chain."""
        step = ChainStep(
            name=name,
            action=action,
            params=params or {},
            condition=condition,
            on_error=on_error,
            rollback=rollback,
            timeout=timeout,
            retries=retries,
            depends_on=depends_on or [],
        )
        self._steps.append(step)
        return self

    def add_parallel_group(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        depends_on: Optional[List[str]] = None,
    ) -> "ActionChain":
        """Add a group of steps to execute in parallel."""
        for i, step_config in enumerate(steps):
            step_name = f"{name}_{i}" if "name" not in step_config else step_config["name"]
            self.add_step(
                name=step_name,
                action=step_config["action"],
                params=step_config.get("params", {}),
                depends_on=depends_on or [],
            )
        return self

    def on_progress(self, callback: Callable[[ChainStep, int, int], None]) -> None:
        """Register a progress callback."""
        self._progress_callbacks.append(callback)

    def set_context(self, key: str, value: Any) -> None:
        """Set a context value accessible by all steps."""
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value."""
        return self._context.get(key, default)

    async def execute(self) -> ChainResult:
        """Execute the action chain."""
        start_time = datetime.utcnow()
        errors = []
        results = {}

        logger.info(f"Starting chain '{self.name}' ({self.id}) with {len(self._steps)} steps")

        try:
            if self.mode == ExecutionMode.SEQUENTIAL:
                await self._execute_sequential(results, errors)
            else:
                await self._execute_parallel(results, errors)

        except Exception as e:
            logger.error(f"Chain execution failed: {e}")
            errors.append({"step": "chain", "error": str(e)})

            if self.enable_rollback:
                await self._rollback()

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        completed = len([s for s in self._steps if s.status == StepStatus.COMPLETED])
        success = completed == len(self._steps) and len(errors) == 0

        result = ChainResult(
            chain_id=self.id,
            success=success,
            steps_completed=completed,
            steps_total=len(self._steps),
            results=results,
            errors=errors,
            duration_ms=duration,
        )

        logger.info(f"Chain '{self.name}' completed: success={success}, "
                    f"steps={completed}/{len(self._steps)}, duration={duration:.1f}ms")

        return result

    async def _execute_sequential(
        self,
        results: Dict[str, Any],
        errors: List[Dict[str, str]],
    ) -> None:
        """Execute steps sequentially."""
        for i, step in enumerate(self._steps):
            # Check dependencies
            if not self._dependencies_met(step):
                step.status = StepStatus.SKIPPED
                continue

            # Check condition
            if step.condition and not step.condition():
                step.status = StepStatus.SKIPPED
                logger.info(f"Step '{step.name}' skipped (condition not met)")
                continue

            # Notify progress
            self._notify_progress(step, i + 1, len(self._steps))

            # Execute step
            success = await self._execute_step(step, results, errors)

            if not success and self.stop_on_error:
                break

    async def _execute_parallel(
        self,
        results: Dict[str, Any],
        errors: List[Dict[str, str]],
    ) -> None:
        """Execute steps in parallel (respecting dependencies)."""
        pending = list(self._steps)
        running = []

        while pending or running:
            # Start steps whose dependencies are met
            ready = [s for s in pending if self._dependencies_met(s)]

            for step in ready:
                pending.remove(step)

                if step.condition and not step.condition():
                    step.status = StepStatus.SKIPPED
                    continue

                task = asyncio.create_task(self._execute_step(step, results, errors))
                running.append((step, task))

            # Wait for at least one to complete
            if running:
                done_tasks = []
                for step, task in running:
                    if task.done():
                        done_tasks.append((step, task))

                if not done_tasks:
                    await asyncio.sleep(0.1)
                    continue

                for step, task in done_tasks:
                    running.remove((step, task))
                    try:
                        task.result()
                    except Exception as e:
                        errors.append({"step": step.name, "error": str(e)})
                        if self.stop_on_error:
                            # Cancel remaining tasks
                            for _, t in running:
                                t.cancel()
                            return

    async def _execute_step(
        self,
        step: ChainStep,
        results: Dict[str, Any],
        errors: List[Dict[str, str]],
    ) -> bool:
        """Execute a single step with retries and error handling."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()

        while step.retry_count <= step.retries:
            try:
                # Inject context into params
                params = {**step.params, "_context": self._context, "_results": results}

                # Execute with timeout
                if asyncio.iscoroutinefunction(step.action):
                    result = await asyncio.wait_for(
                        step.action(**params),
                        timeout=step.timeout,
                    )
                else:
                    result = step.action(**params)

                step.result = result
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.utcnow()
                results[step.name] = result
                self._completed_steps.append(step)

                logger.info(f"Step '{step.name}' completed successfully")
                return True

            except asyncio.TimeoutError:
                step.error = f"Timeout after {step.timeout}s"
                logger.warning(f"Step '{step.name}' timed out")

            except Exception as e:
                step.error = str(e)
                logger.error(f"Step '{step.name}' failed: {e}")

            step.retry_count += 1
            if step.retry_count <= step.retries:
                logger.info(f"Retrying step '{step.name}' ({step.retry_count}/{step.retries})")
                await asyncio.sleep(1)

        # All retries exhausted
        step.status = StepStatus.FAILED
        step.completed_at = datetime.utcnow()
        errors.append({"step": step.name, "error": step.error or "Unknown error"})

        if step.on_error == "skip":
            return True
        elif step.on_error == "continue":
            return True
        else:
            return False

    async def _rollback(self) -> None:
        """Rollback completed steps in reverse order."""
        logger.info(f"Rolling back chain '{self.name}'")

        for step in reversed(self._completed_steps):
            if step.rollback:
                try:
                    logger.info(f"Rolling back step '{step.name}'")
                    if asyncio.iscoroutinefunction(step.rollback):
                        await step.rollback(step.result)
                    else:
                        step.rollback(step.result)
                    step.status = StepStatus.ROLLED_BACK
                except Exception as e:
                    logger.error(f"Rollback failed for step '{step.name}': {e}")

    def _dependencies_met(self, step: ChainStep) -> bool:
        """Check if all dependencies for a step are met."""
        for dep_name in step.depends_on:
            dep_step = next((s for s in self._steps if s.name == dep_name), None)
            if dep_step is None or dep_step.status != StepStatus.COMPLETED:
                return False
        return True

    def _notify_progress(self, step: ChainStep, current: int, total: int) -> None:
        """Notify progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(step, current, total)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")


class ChainExecutor:
    """
    Executor for managing multiple action chains.

    Features:
    - Run multiple chains
    - Chain history
    - Pause/resume chains
    """

    def __init__(self):
        self._active_chains: Dict[str, ActionChain] = {}
        self._history: List[ChainResult] = []
        self._max_history = 100

    async def run(self, chain: ActionChain) -> ChainResult:
        """Run a chain and track its execution."""
        self._active_chains[chain.id] = chain

        try:
            result = await chain.execute()
            self._history.append(result)

            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            return result
        finally:
            del self._active_chains[chain.id]

    def get_active_chains(self) -> List[Dict[str, Any]]:
        """Get currently running chains."""
        return [
            {
                "id": chain.id,
                "name": chain.name,
                "steps": len(chain._steps),
                "completed": len([s for s in chain._steps if s.status == StepStatus.COMPLETED]),
            }
            for chain in self._active_chains.values()
        ]

    def get_history(self, limit: int = 20) -> List[ChainResult]:
        """Get chain execution history."""
        return self._history[-limit:]


# Singleton executor
_executor: Optional[ChainExecutor] = None


def get_chain_executor() -> ChainExecutor:
    """Get the global chain executor."""
    global _executor
    if _executor is None:
        _executor = ChainExecutor()
    return _executor
