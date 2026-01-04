"""
Centralized timeout configuration for LifeOS.
Prevents hanging operations by enforcing aggressive timeouts.
"""

from typing import Any, Dict

# Global timeout settings (in seconds)
TIMEOUTS = {
    # Terminal/subprocess operations
    "subprocess_default": 10,  # Very short default to prevent hangs
    "subprocess_quick": 5,     # For quick commands
    "subprocess_medium": 15,   # For medium tasks
    "subprocess_long": 30,     # Maximum for long tasks
    "subprocess_critical": 60, # Only for truly critical operations
    
    # Network operations
    "http_request": 10,
    "api_call": 15,
    "websocket": 20,
    
    # File operations
    "file_read": 5,
    "file_write": 10,
    
    # Trading operations
    "dex_api": 15,
    "swap_execution": 30,
    "position_check": 10,
    
    # AI/LLM operations
    "llm_quick": 20,
    "llm_standard": 60,
    "llm_long": 120,
    
    # Browser automation
    "browser_navigation": 15,
    "browser_scrape": 30,
}

# Command patterns that should NEVER take long (force short timeout)
QUICK_COMMAND_PATTERNS = [
    r"^git status",
    r"^git log",
    r"^ls\b",
    r"^pwd",
    r"^echo",
    r"^cat\b",
    r"check.*position",
]

# Command patterns that need longer timeouts
LONG_COMMAND_PATTERNS = [
    r"pip install",
    r"npm install",
    r"git clone",
    r"download",
    r"training",
]

def get_timeout(operation: str = "default", context: str = "subprocess") -> int:
    """Get timeout for an operation.
    
    Args:
        operation: Type of operation (default, quick, medium, long, critical)
        context: Context of operation (subprocess, http, file, etc.)
    
    Returns:
        Timeout in seconds
    """
    key = f"{context}_{operation}"
    return TIMEOUTS.get(key, TIMEOUTS.get("subprocess_default", 10))


def should_force_short_timeout(command: str) -> bool:
    """Check if a command should have a forced short timeout."""
    import re
    for pattern in QUICK_COMMAND_PATTERNS:
        if re.match(pattern, command.strip(), re.IGNORECASE):
            return True
    return False


def should_allow_long_timeout(command: str) -> bool:
    """Check if a command legitimately needs a long timeout."""
    import re
    for pattern in LONG_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def get_command_timeout(command: str) -> int:
    """Get appropriate timeout for a specific command.
    
    Args:
        command: The command to execute
        
    Returns:
        Timeout in seconds
    """
    # Force short timeout for quick commands
    if should_force_short_timeout(command):
        return TIMEOUTS["subprocess_quick"]
    
    # Allow longer timeout for legitimately long operations
    if should_allow_long_timeout(command):
        return TIMEOUTS["subprocess_long"]
    
    # Detect command chains (&&, ||, |, ;)
    chain_indicators = ["&&", "||", "|", ";"]
    chain_count = sum(command.count(indicator) for indicator in chain_indicators)
    
    # Long command chains are dangerous - use medium timeout at most
    if chain_count > 5:
        return TIMEOUTS["subprocess_medium"]
    elif chain_count > 2:
        return TIMEOUTS["subprocess_medium"]
    
    # Default to quick timeout
    return TIMEOUTS["subprocess_default"]


def get_adaptive_timeout(command: str, estimated_duration: int = None) -> int:
    """Get adaptive timeout based on command analysis and estimation.
    
    Args:
        command: The command to execute
        estimated_duration: Optional estimated duration in seconds
        
    Returns:
        Timeout in seconds with safety margin
    """
    if estimated_duration:
        # Add 50% safety margin to estimated duration
        return min(int(estimated_duration * 1.5), TIMEOUTS["subprocess_critical"])
    
    return get_command_timeout(command)
