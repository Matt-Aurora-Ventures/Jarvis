"""Dexter tool registry and meta-router."""

from typing import Dict, Callable

class ToolRegistry:
    """Registry for Dexter tools."""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
    
    def register(self, name: str, tool: Callable):
        """Register a tool."""
        self.tools[name] = tool
    
    def get(self, name: str) -> Callable:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self):
        """List all available tools."""
        return list(self.tools.keys())

# Global registry
_registry = ToolRegistry()

def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry

__all__ = ["ToolRegistry", "get_tool_registry"]
