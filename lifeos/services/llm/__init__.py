"""
LLM Service Adapters

Provides adapters for various LLM providers:
- Groq (fast, free tier)
- Ollama (local, free)
- OpenAI (premium, reliable)

Usage:
    from lifeos.services.llm import GroqLLMAdapter

    groq = GroqLLMAdapter(api_key="...")
    response = await groq.generate("Hello!")
"""

from lifeos.services.llm.groq_adapter import GroqLLMAdapter
from lifeos.services.llm.ollama_adapter import OllamaLLMAdapter
from lifeos.services.llm.openai_adapter import OpenAILLMAdapter

__all__ = [
    "GroqLLMAdapter",
    "OllamaLLMAdapter",
    "OpenAILLMAdapter",
]
