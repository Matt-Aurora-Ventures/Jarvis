"""
AI Runtime Configuration

All AI operations are OPTIONAL. If any config is missing or Ollama is unavailable,
the system continues without AI features.
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from .constants import (
    DEFAULT_AI_TIMEOUT_MS,
    DEFAULT_SOCKET_PATH,
    DEFAULT_MEMORY_DB,
    DEFAULT_LOG_PATH,
    DEFAULT_OLLAMA_MODEL,
    MAX_MESSAGE_SIZE,
    MAX_MEMORY_ENTRIES_PER_NAMESPACE,
)


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = DEFAULT_OLLAMA_MODEL
    timeout_ms: int = DEFAULT_AI_TIMEOUT_MS
    max_retries: int = 1


@dataclass
class AgentConfig:
    name: str
    namespace: str
    capabilities: dict = field(default_factory=dict)
    memory_limit_mb: int = 100


@dataclass
class BusConfig:
    socket_path: str = DEFAULT_SOCKET_PATH
    hmac_key: Optional[str] = None  # Loaded from env
    max_message_size: int = MAX_MESSAGE_SIZE
    rate_limit_per_second: int = 100


@dataclass
class AIRuntimeConfig:
    enabled: bool = True
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    bus: BusConfig = field(default_factory=BusConfig)
    memory_db_path: str = DEFAULT_MEMORY_DB
    log_path: str = DEFAULT_LOG_PATH

    @classmethod
    def from_env(cls) -> "AIRuntimeConfig":
        """Load config from environment. Missing values use safe defaults."""
        return cls(
            enabled=os.getenv("AI_RUNTIME_ENABLED", "true").lower() == "true",
            ollama=OllamaConfig(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
                timeout_ms=int(os.getenv("AI_TIMEOUT_MS", str(DEFAULT_AI_TIMEOUT_MS))),
            ),
            bus=BusConfig(
                socket_path=os.getenv("AI_BUS_SOCKET", DEFAULT_SOCKET_PATH),
                hmac_key=os.getenv("AI_BUS_HMAC_KEY"),
            ),
            memory_db_path=os.getenv("AI_MEMORY_DB", DEFAULT_MEMORY_DB),
            log_path=os.getenv("AI_LOG_PATH", DEFAULT_LOG_PATH),
        )
