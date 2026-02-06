"""Hello World Plugin - MCP Plugin System Demo.

A minimal plugin showing setup/teardown lifecycle and a greet method.
"""

_initialized = False


def setup():
    """Called when the plugin is loaded."""
    global _initialized
    _initialized = True


def teardown():
    """Called when the plugin is unloaded."""
    global _initialized
    _initialized = False


def greet(who: str = "world") -> str:
    """Return a greeting string."""
    return f"Hello, {who}! (initialized={_initialized})"
