"""
AI Runtime Layer for Jarvis

Optional, always-learning AI agents backed by local Ollama.
Fail-open design: if AI is unavailable, all applications continue normally.
"""

__version__ = "0.1.0"

# Export main classes for easy importing
from .supervisor.ai_supervisor import AISupervisor
from .config import AIRuntimeConfig

__all__ = ["AISupervisor", "AIRuntimeConfig"]
