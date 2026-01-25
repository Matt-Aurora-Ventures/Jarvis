"""
JARVIS Model Management System.

Provides multi-model support with:
- Model catalog with specs and pricing
- Provider abstraction (Anthropic, OpenAI, xAI)
- Per-session model selection
- Cost tracking integration

Usage:
    from core.models import get_model_manager, MODEL_CATALOG

    # Get manager singleton
    manager = get_model_manager()

    # Set session model
    manager.set_session_model("session-123", "claude-opus-4-5")

    # Generate with model
    response = await manager.generate(
        messages=[{"role": "user", "content": "Hello"}],
        session_id="session-123"
    )
"""

from .catalog import (
    MODEL_CATALOG,
    get_model_info,
    list_providers,
    list_models,
    format_models_list,
    format_model_info,
)

from .manager import (
    ModelManager,
    get_model_manager,
)

__all__ = [
    # Catalog
    "MODEL_CATALOG",
    "get_model_info",
    "list_providers",
    "list_models",
    "format_models_list",
    "format_model_info",
    # Manager
    "ModelManager",
    "get_model_manager",
]
