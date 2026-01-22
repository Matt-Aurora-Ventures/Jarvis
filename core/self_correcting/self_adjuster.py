"""
Self-Adjustment Engine

Monitors component performance and automatically adjusts parameters.
Features:
- Performance metric tracking
- Automatic parameter tuning
- A/B testing for parameter changes
- Rollback on degradation
- Learning from adjustments

Components can register tunable parameters and the engine will optimize them.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics


logger = logging.getLogger("jarvis.self_adjuster")


class MetricType(Enum):
    """Types of metrics to track."""
    SUCCESS_RATE = "success_rate"  # 0.0-1.0
    LATENCY = "latency"  # milliseconds
    ERROR_RATE = "error_rate"  # 0.0-1.0
    THROUGHPUT = "throughput"  # items/second
    COST = "cost"  # dollars
    USER_SATISFACTION = "user_satisfaction"  # 0.0-1.0


@dataclass
class Metric:
    """A performance metric value."""
    type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Parameter:
    """A tunable parameter."""
    name: str
    current_value: Any
    min_value: Any
    max_value: Any
    step: Any  # How much to change by
    affects_metrics: List[MetricType]  # Which metrics this impacts
    last_adjusted: datetime = field(default_factory=datetime.now)
    adjustment_count: int = 0


@dataclass
class ParameterTest:
    """A/B test for a parameter change."""
    parameter_name: str
    old_value: Any
    new_value: Any
    start_time: datetime
    end_time: Optional[datetime] = None
    old_metrics: Dict[MetricType, List[float]] = field(default_factory=dict)
    new_metrics: Dict[MetricType, List[float]] = field(default_factory=dict)
    winner: Optional[str] = None  # "old" or "new"
    confidence: float = 0.0


class SelfAdjuster:
    """
    Automatically tunes component parameters based on performance.

    Components register their tunable parameters and metrics,
    then the adjuster experiments with different values to find optimal settings.
    """

    def __init__(
        self,
        adjustment_interval_seconds: int = 3600,  # 1 hour
        test_duration_seconds: int = 1800,  # 30 min per A/B test
        min_samples_for_decision: int = 100
    ):
        self.adjustment_interval = adjustment_interval_seconds
        self.test_duration = test_duration_seconds
        self.min_samples = min_samples_for_decision

        self.components: Dict[str, Dict[str, Parameter]] = {}  # component -> params
        self.metrics: Dict[str, Dict[MetricType, List[Metric]]] = {}  # component -> metrics
        self.active_tests: Dict[str, ParameterTest] = {}  # component -> test
        self.completed_tests: List[ParameterTest] = []

        self._running = False
        self._task = None

        logger.info("SelfAdjuster initialized")

    def register_component(
        self,
        component: str,
        parameters: Dict[str, Parameter]
    ):
        """Register a component's tunable parameters."""
        self.components[component] = parameters
        self.metrics[component] = {metric_type: [] for metric_type in MetricType}

        logger.info(
            f"[{component}] Registered {len(parameters)} tunable parameters"
        )

    def record_metric(
        self,
        component: str,
        metric_type: MetricType,
        value: float
    ):
        """Record a performance metric."""
        if component not in self.metrics:
            logger.warning(f"Component {component} not registered")
            return

        metric = Metric(type=metric_type, value=value)
        self.metrics[component][metric_type].append(metric)

        # Keep only recent metrics (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self.metrics[component][metric_type] = [
            m for m in self.metrics[component][metric_type]
            if m.timestamp > cutoff
        ]

        # If in A/B test, also record for test
        if component in self.active_tests:
            test = self.active_tests[component]
            param = self.components[component][test.parameter_name]

            if param.current_value == test.new_value:
                # Recording for new value
                if metric_type not in test.new_metrics:
                    test.new_metrics[metric_type] = []
                test.new_metrics[metric_type].append(value)
            else:
                # Recording for old value
                if metric_type not in test.old_metrics:
                    test.old_metrics[metric_type] = []
                test.old_metrics[metric_type].append(value)

    def get_current_performance(
        self,
        component: str,
        metric_type: MetricType,
        window_minutes: int = 60
    ) -> Optional[float]:
        """Get average performance for a metric over recent window."""
        if component not in self.metrics:
            return None

        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent_metrics = [
            m.value for m in self.metrics[component][metric_type]
            if m.timestamp > cutoff
        ]

        if not recent_metrics:
            return None

        return statistics.mean(recent_metrics)

    async def start(self):
        """Start the self-adjustment engine."""
        self._running = True
        self._task = asyncio.create_task(self._adjustment_loop())
        logger.info("SelfAdjuster started")

    async def stop(self):
        """Stop the engine."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _adjustment_loop(self):
        """Main loop - periodically adjusts parameters."""
        while self._running:
            try:
                await asyncio.sleep(self.adjustment_interval)

                # Check active tests
                await self._check_active_tests()

                # Start new tests if no active tests
                for component in self.components.keys():
                    if component not in self.active_tests:
                        await self._start_parameter_test(component)

            except Exception as e:
                logger.error(f"Error in adjustment loop: {e}")

    async def _check_active_tests(self):
        """Check if any active A/B tests are ready to conclude."""
        to_conclude = []

        for component, test in self.active_tests.items():
            # Check if test has run long enough
            duration = (datetime.now() - test.start_time).total_seconds()
            if duration < self.test_duration:
                continue

            # Check if we have enough samples
            total_samples = sum(
                len(values) for values in test.new_metrics.values()
            )
            if total_samples < self.min_samples:
                logger.info(
                    f"[{component}] Test for {test.parameter_name} needs more samples"
                )
                continue

            to_conclude.append(component)

        # Conclude tests
        for component in to_conclude:
            await self._conclude_test(component)

    async def _conclude_test(self, component: str):
        """Conclude an A/B test and make decision."""
        test = self.active_tests[component]
        param = self.components[component][test.parameter_name]

        logger.info(
            f"[{component}] Concluding test for {test.parameter_name}: "
            f"{test.old_value} vs {test.new_value}"
        )

        # Compare metrics
        old_score = 0.0
        new_score = 0.0

        for metric_type in param.affects_metrics:
            if metric_type not in test.old_metrics or metric_type not in test.new_metrics:
                continue

            old_avg = statistics.mean(test.old_metrics[metric_type])
            new_avg = statistics.mean(test.new_metrics[metric_type])

            # Higher is better for success_rate, throughput, satisfaction
            # Lower is better for latency, error_rate, cost
            if metric_type in [
                MetricType.SUCCESS_RATE,
                MetricType.THROUGHPUT,
                MetricType.USER_SATISFACTION
            ]:
                if new_avg > old_avg:
                    new_score += 1
                else:
                    old_score += 1
            else:
                if new_avg < old_avg:
                    new_score += 1
                else:
                    old_score += 1

        # Decide winner
        if new_score > old_score:
            test.winner = "new"
            test.confidence = new_score / (new_score + old_score)
            # Keep new value
            logger.info(
                f"[{component}] New value {test.new_value} won "
                f"(confidence: {test.confidence:.2f})"
            )
        else:
            test.winner = "old"
            test.confidence = old_score / (new_score + old_score)
            # Rollback to old value
            param.current_value = test.old_value
            logger.info(
                f"[{component}] Old value {test.old_value} won "
                f"(confidence: {test.confidence:.2f}) - rolling back"
            )

        test.end_time = datetime.now()
        self.completed_tests.append(test)
        del self.active_tests[component]

        # Store learning in shared memory
        from .shared_memory import get_shared_memory, LearningType
        memory = get_shared_memory()

        memory.add_learning(
            component=component,
            learning_type=LearningType.OPTIMIZATION,
            content=f"Parameter {test.parameter_name}: {test.winner} value "
                   f"({test.new_value if test.winner == 'new' else test.old_value}) performed better",
            context={
                "parameter": test.parameter_name,
                "old_value": test.old_value,
                "new_value": test.new_value,
                "winner": test.winner,
                "confidence": test.confidence
            },
            confidence=test.confidence
        )

    async def _start_parameter_test(self, component: str):
        """Start A/B test for a parameter."""
        if not self.components[component]:
            return

        # Choose a parameter to test
        # Prefer parameters that haven't been adjusted recently
        candidates = [
            (name, param) for name, param in self.components[component].items()
            if (datetime.now() - param.last_adjusted).total_seconds() > 3600
        ]

        if not candidates:
            logger.debug(f"[{component}] No parameters ready for adjustment")
            return

        # Pick least recently adjusted
        param_name, param = min(candidates, key=lambda x: x[1].last_adjusted)

        # Calculate new value
        if isinstance(param.current_value, (int, float)):
            # Numeric parameter - try increasing/decreasing
            # Use recent performance to decide direction
            current_perf = self.get_current_performance(
                component,
                param.affects_metrics[0] if param.affects_metrics else MetricType.SUCCESS_RATE
            )

            if current_perf is None or current_perf < 0.7:
                # Performance not great, try increasing (assuming higher is better)
                new_value = min(
                    param.current_value + param.step,
                    param.max_value
                )
            else:
                # Try decreasing
                new_value = max(
                    param.current_value - param.step,
                    param.min_value
                )

            if new_value == param.current_value:
                # Already at limit
                return

        else:
            # Non-numeric parameter (e.g., boolean, string)
            # For now, just toggle or pick next in sequence
            if isinstance(param.current_value, bool):
                new_value = not param.current_value
            else:
                # Skip non-boolean non-numeric for now
                return

        # Start test
        test = ParameterTest(
            parameter_name=param_name,
            old_value=param.current_value,
            new_value=new_value,
            start_time=datetime.now()
        )

        self.active_tests[component] = test
        param.current_value = new_value
        param.last_adjusted = datetime.now()
        param.adjustment_count += 1

        logger.info(
            f"[{component}] Starting A/B test: {param_name} = "
            f"{test.old_value} vs {test.new_value}"
        )

    def get_component_stats(self, component: str) -> Dict[str, Any]:
        """Get statistics for a component."""
        if component not in self.components:
            return {}

        recent_metrics = {}
        for metric_type in MetricType:
            avg = self.get_current_performance(component, metric_type, window_minutes=60)
            if avg is not None:
                recent_metrics[metric_type.value] = avg

        return {
            "parameters": {
                name: {
                    "current_value": param.current_value,
                    "adjustment_count": param.adjustment_count,
                    "last_adjusted": param.last_adjusted.isoformat()
                }
                for name, param in self.components[component].items()
            },
            "recent_metrics": recent_metrics,
            "active_test": self.active_tests.get(component) is not None
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global statistics."""
        return {
            "total_components": len(self.components),
            "active_tests": len(self.active_tests),
            "completed_tests": len(self.completed_tests),
            "successful_optimizations": len([
                t for t in self.completed_tests if t.winner == "new"
            ])
        }


# Global self-adjuster instance
_self_adjuster: Optional[SelfAdjuster] = None


def get_self_adjuster() -> SelfAdjuster:
    """Get the global self-adjuster instance."""
    global _self_adjuster
    if _self_adjuster is None:
        _self_adjuster = SelfAdjuster()
    return _self_adjuster
