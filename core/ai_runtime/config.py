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
    # Legacy/top-level knobs (used by supervisor + tests)
    interval_seconds: int = 60
    timeout_seconds: int = 12
    max_tokens: int = 512
    base_url: Optional[str] = None
    model: Optional[str] = None
    # Structured config (preferred by agent runtime)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    bus: BusConfig = field(default_factory=BusConfig)
    memory_db_path: str = DEFAULT_MEMORY_DB
    log_path: str = DEFAULT_LOG_PATH

    def __post_init__(self) -> None:
        if self.base_url:
            self.ollama.base_url = self.base_url
        else:
            self.base_url = self.ollama.base_url

        if self.model:
            self.ollama.model = self.model
        else:
            self.model = self.ollama.model

        if self.timeout_seconds:
            self.ollama.timeout_ms = int(self.timeout_seconds * 1000)
        else:
            self.timeout_seconds = max(1, int(self.ollama.timeout_ms / 1000))

    @classmethod
    def from_env(cls) -> "AIRuntimeConfig":
        """Load config from environment. Missing values use safe defaults."""
        return cls(
            enabled=os.getenv("AI_RUNTIME_ENABLED", "true").lower() == "true",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            timeout_seconds=int(int(os.getenv("AI_TIMEOUT_MS", str(DEFAULT_AI_TIMEOUT_MS))) / 1000),
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


def get_ai_runtime_config() -> AIRuntimeConfig:
    return AIRuntimeConfig.from_env()
