"""
LifeOS - Jarvis AI Assistant Framework

A comprehensive framework for building AI assistants with:
- Multi-provider LLM support
- Plugin architecture
- Memory sandboxing
- Event-driven communication
- Persona management
- Trading integrations

Usage:
    from lifeos import Jarvis

    jarvis = Jarvis()
    await jarvis.start()

    response = await jarvis.chat("Hello!")
    print(response)

    await jarvis.stop()
"""

from lifeos.jarvis import Jarvis
from lifeos.config import Config, get_config, set_config

__version__ = "4.0.0"

__all__ = [
    "Jarvis",
    "Config",
    "get_config",
    "set_config",
    "__version__",
]
