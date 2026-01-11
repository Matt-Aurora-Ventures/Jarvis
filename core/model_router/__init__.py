"""
Model Router - Intelligent AI model routing for JARVIS.

This module provides:
- ModelRouter: Automatic model selection based on task
- Provider management and fallback chains
- Cost optimization and rate limiting
"""

from .router import (
    ModelRouter,
    ModelProvider,
    RoutingPriority,
    ModelCapability,
    RoutingResult,
    get_model_router,
)

__all__ = [
    "ModelRouter",
    "ModelProvider",
    "RoutingPriority",
    "ModelCapability",
    "RoutingResult",
    "get_model_router",
]
