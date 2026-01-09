"""
Provider-Action-Evaluator (PAE) Registry

A unified registry system for managing:
- Providers: Data sources and information providers
- Actions: Executable capabilities and commands
- Evaluators: Decision-making components

Usage:
    from lifeos.pae import PAERegistry, Provider, Action, Evaluator

    registry = PAERegistry()

    @registry.provider("weather")
    class WeatherProvider(Provider):
        async def provide(self, query):
            return {"temp": 72}

    @registry.action("send_notification")
    class NotifyAction(Action):
        async def execute(self, params):
            await notify(params["message"])

    @registry.evaluator("should_alert")
    class AlertEvaluator(Evaluator):
        async def evaluate(self, context):
            return context["severity"] > 5
"""

from lifeos.pae.base import (
    Provider,
    Action,
    Evaluator,
    PAEComponent,
    PAEError,
    ProviderError,
    ActionError,
    EvaluatorError,
)
from lifeos.pae.registry import PAERegistry
from lifeos.pae.pipeline import PAEPipeline, PipelineStep, PipelineResult

__all__ = [
    # Base classes
    "Provider",
    "Action",
    "Evaluator",
    "PAEComponent",
    # Errors
    "PAEError",
    "ProviderError",
    "ActionError",
    "EvaluatorError",
    # Registry
    "PAERegistry",
    # Pipeline
    "PAEPipeline",
    "PipelineStep",
    "PipelineResult",
]
