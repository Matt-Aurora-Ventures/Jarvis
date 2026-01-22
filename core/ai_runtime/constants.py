"""
AI Runtime Constants
"""

# Timeouts (milliseconds)
DEFAULT_AI_TIMEOUT_MS = 800
MAX_AI_TIMEOUT_MS = 5000
BUS_MESSAGE_TIMEOUT_MS = 5000

# Limits
MAX_MESSAGE_SIZE = 65536
MAX_MEMORY_ENTRIES_PER_NAMESPACE = 1000
MAX_INSIGHT_BUFFER_SIZE = 100

# Paths
DEFAULT_SOCKET_PATH = "/tmp/jarvis_ai_bus.sock"
DEFAULT_MEMORY_DB = "data/ai_memory.db"
DEFAULT_LOG_PATH = "logs/ai_runtime.log"

# Models
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"
FALLBACK_MODELS = ["qwen2.5-coder:3b", "llama3.2:3b"]

# Agent namespaces
NAMESPACE_TELEGRAM = "ai.telegram"
NAMESPACE_API = "ai.api"
NAMESPACE_WEB = "ai.web"
NAMESPACE_SUPERVISOR = "ai.supervisor"
