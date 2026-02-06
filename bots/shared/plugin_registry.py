"""
MCP Plugin Registry for ClawdBots.

Lightweight plugin system that lets bots register and discover
capabilities (tools/skills) from each other.

Inspired by Model Context Protocol (MCP) patterns:
- Tools have names, descriptions, and parameter schemas
- Bots register tools they provide
- Other bots discover and invoke tools via the registry
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("CLAWDBOT_DATA_DIR", "/root/clawdbots/data"))
REGISTRY_FILE = DATA_DIR / "plugin_registry.json"


@dataclass
class ToolSpec:
    name: str
    description: str
    provider: str  # bot name
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_auth: bool = False
    min_auth_level: int = 10  # OBSERVER=10, OPERATOR=20, ADMIN=30, OWNER=40
    registered_at: str = ""

    def __post_init__(self):
        if not self.registered_at:
            self.registered_at = datetime.utcnow().isoformat()


class PluginRegistry:
    """Central registry for bot tools/capabilities."""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._handlers: Dict[str, Callable] = {}
        self._load()

    def register(self, tool: ToolSpec, handler: Optional[Callable] = None):
        """Register a tool in the registry."""
        self._tools[tool.name] = tool
        if handler:
            self._handlers[tool.name] = handler
        self._save()
        logger.info(f"Plugin registered: {tool.name} by {tool.provider}")

    def unregister(self, tool_name: str):
        """Remove a tool from the registry."""
        self._tools.pop(tool_name, None)
        self._handlers.pop(tool_name, None)
        self._save()

    def discover(self, provider: Optional[str] = None, query: Optional[str] = None) -> List[ToolSpec]:
        """Discover available tools, optionally filtered by provider or search query."""
        tools = list(self._tools.values())
        if provider:
            tools = [t for t in tools if t.provider == provider]
        if query:
            q = query.lower()
            tools = [t for t in tools if q in t.name.lower() or q in t.description.lower()]
        return tools

    async def invoke(self, tool_name: str, params: Dict[str, Any] = None) -> Any:
        """Invoke a registered tool by name."""
        handler = self._handlers.get(tool_name)
        if not handler:
            raise ValueError(f"No handler for tool: {tool_name}")
        return await handler(**(params or {}))

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """Get a specific tool spec."""
        return self._tools.get(name)

    def list_providers(self) -> List[str]:
        """List all registered providers (bots)."""
        return list(set(t.provider for t in self._tools.values()))

    def _load(self):
        if REGISTRY_FILE.exists():
            try:
                data = json.loads(REGISTRY_FILE.read_text())
                for item in data:
                    tool = ToolSpec(**item)
                    self._tools[tool.name] = tool
            except (json.JSONDecodeError, OSError, TypeError):
                pass

    def _save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = [asdict(t) for t in self._tools.values()]
        REGISTRY_FILE.write_text(json.dumps(data, indent=2))


def register_default_tools(registry: PluginRegistry):
    """Register the default ClawdBot tools."""
    defaults = [
        ToolSpec(
            name="morning_brief",
            description="Generate system health morning brief",
            provider="matt",
            parameters={"format": "text"},
        ),
        ToolSpec(
            name="handoff_task",
            description="Route a task to the appropriate specialist bot",
            provider="matt",
            parameters={"task": "string", "from_user": "string"},
        ),
        ToolSpec(
            name="analyze_sentiment",
            description="AI sentiment analysis for crypto tokens",
            provider="jarvis",
            parameters={"token_address": "string"},
            requires_auth=True,
            min_auth_level=20,
        ),
        ToolSpec(
            name="check_infrastructure",
            description="Check VPS health, services, disk, memory",
            provider="jarvis",
            parameters={},
        ),
        ToolSpec(
            name="draft_tweet",
            description="Draft a tweet or Twitter thread",
            provider="friday",
            parameters={"topic": "string", "tone": "string"},
        ),
        ToolSpec(
            name="content_review",
            description="Review content for brand alignment and PR compliance",
            provider="matt",
            parameters={"text": "string"},
        ),
        ToolSpec(
            name="spawn_parallel",
            description="Spawn parallel tasks across multiple bots",
            provider="matt",
            parameters={"instruction": "string"},
            requires_auth=True,
            min_auth_level=30,
        ),
        ToolSpec(
            name="kaizen_report",
            description="Generate weekly Kaizen self-improvement synthesis",
            provider="matt",
            parameters={"days": "int"},
        ),
        ToolSpec(
            name="memory_recall",
            description="Search SuperMemory for stored facts",
            provider="jarvis",
            parameters={"query": "string"},
        ),
        ToolSpec(
            name="log_analysis",
            description="Analyze bot logs for errors and anomalies",
            provider="jarvis",
            parameters={"hours": "int", "bot": "string"},
        ),
    ]
    for tool in defaults:
        registry.register(tool)
