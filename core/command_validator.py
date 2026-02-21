"""
Command validator to detect and prevent hanging command patterns.
Warns about or blocks commands that are likely to hang.
"""

import logging
import re
from typing import List, Optional, Tuple
import shlex

logger = logging.getLogger(__name__)

# Maximum acceptable command length (characters)
MAX_COMMAND_LENGTH = 500

# Maximum chain depth
MAX_CHAIN_DEPTH = 5

# Commands that often hang
HANGING_COMMAND_PATTERNS = [
    r"git\s+fetch.*origin.*&&.*git\s+log",  # Long git chains
    r"(&&.*){6,}",  # Too many chained commands
    r"while\s+true",  # Infinite loops
    r"tail\s+-f",  # Blocking tail
    r"watch\s+",  # Watch commands
    r"jupyter\s+(notebook|lab)",  # Jupyter blocking
    r"npm\s+start",  # Dev servers without background flag
    r"flask\s+run",  # Flask dev server
    r"python\s+-m\s+http\.server",  # Python HTTP server
    r"serve\s+",  # Various serve commands
]

# Commands that should be run in background
BACKGROUND_COMMAND_PATTERNS = [
    r".*server",
    r".*daemon",
    r"monitor.*",
    r".*watch",
]


class CommandValidator:
    """Validates commands before execution to prevent hangs."""
    
    def __init__(self):
        self.warnings_issued = []
    
    def validate_command(self, command: str) -> Tuple[bool, Optional[str], List[str]]:
        """Validate a command for hanging risks.
        
        Args:
            command: Command string to validate
            
        Returns:
            Tuple of (is_safe, error_message, warnings)
        """
        warnings = []
        
        # Check command length
        if len(command) > MAX_COMMAND_LENGTH:
            warnings.append(
                f"Command is very long ({len(command)} chars). "
                f"Consider breaking into smaller steps."
            )
        
        # Check chain depth
        chain_count = self._count_chains(command)
        if chain_count > MAX_CHAIN_DEPTH:
            return (
                False,
                f"Command has {chain_count} chained operations (max {MAX_CHAIN_DEPTH}). "
                f"This is likely to hang. Break into separate commands.",
                warnings
            )
        
        # Check for known hanging patterns
        for pattern in HANGING_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return (
                    False,
                    f"Command matches known hanging pattern: {pattern}. "
                    f"This command will likely block indefinitely.",
                    warnings
                )
        
        # Check if should be background
        should_background = False
        for pattern in BACKGROUND_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                should_background = True
                warnings.append(
                    f"Command appears to be a long-running process. "
                    f"Consider running in background with isBackground=true"
                )
                break
        
        # Check for missing timeouts on long operations
        if any(kw in command.lower() for kw in ['download', 'install', 'clone', 'pull']):
            warnings.append(
                "Command may take a long time. Ensure proper timeout is set."
            )
        
        return (True, None, warnings)

    def validate_argv(self, argv: List[str]) -> Tuple[bool, Optional[str], List[str]]:
        """Validate a tokenized command list with shell metachar blocking."""
        if not argv:
            return False, "Command argv is empty", []

        shell_meta = ["&&", "||", ";", "|", "`", "$(", ">", "<"]
        for token in argv:
            if any(meta in token for meta in shell_meta):
                return (
                    False,
                    f"Command token contains blocked shell metacharacters: {token}",
                    [],
                )

        command = " ".join(shlex.quote(part) for part in argv)
        return self.validate_command(command)
    
    def _count_chains(self, command: str) -> int:
        """Count the number of chained operations."""
        # Count &&, ||, |, and ;
        chain_indicators = ['&&', '||', '|', ';']
        total = 0
        for indicator in chain_indicators:
            total += command.count(indicator)
        return total
    
    def suggest_fixes(self, command: str) -> List[str]:
        """Suggest fixes for problematic commands.
        
        Args:
            command: Problematic command
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Long chains - suggest splitting
        chain_count = self._count_chains(command)
        if chain_count > MAX_CHAIN_DEPTH:
            suggestions.append(
                f"Split the {chain_count} chained commands into separate executions"
            )
            suggestions.append(
                "Example: Run each command individually with error handling between"
            )
        
        # Blocking commands - suggest background
        for pattern in BACKGROUND_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                suggestions.append(
                    "Run this command with isBackground=true to prevent blocking"
                )
                break
        
        # Long command - suggest refactoring
        if len(command) > MAX_COMMAND_LENGTH:
            suggestions.append(
                "Create a shell script for this complex operation instead of a one-liner"
            )
        
        return suggestions
    
    def auto_fix_command(self, command: str) -> Tuple[str, List[str]]:
        """Attempt to automatically fix command issues.
        
        Args:
            command: Command to fix
            
        Returns:
            Tuple of (fixed_command, changes_made)
        """
        fixed = command
        changes = []
        
        # Add timeouts to known slow commands
        if 'git clone' in command and 'timeout' not in command.lower():
            fixed = f"timeout 120 {fixed}"
            changes.append("Added 120s timeout to git clone")
        
        if 'npm install' in command and 'timeout' not in command.lower():
            fixed = f"timeout 180 {fixed}"
            changes.append("Added 180s timeout to npm install")
        
        # Remove infinite loops
        if 'while true' in command.lower():
            changes.append("WARNING: Cannot auto-fix infinite loop - command blocked")
            return command, changes
        
        return fixed, changes


# Global validator instance
_validator: Optional[CommandValidator] = None


def get_validator() -> CommandValidator:
    """Get the global command validator."""
    global _validator
    if _validator is None:
        _validator = CommandValidator()
    return _validator


def validate_before_run(command: str) -> Tuple[bool, Optional[str], List[str]]:
    """Convenience function to validate a command.
    
    Args:
        command: Command to validate
        
    Returns:
        Tuple of (is_safe, error_message, warnings)
    """
    validator = get_validator()
    is_safe, error, warnings = validator.validate_command(command)
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"Command warning: {warning}")
    
    # Log error
    if error:
        logger.error(f"Command blocked: {error}")
    
    return is_safe, error, warnings


def validate_argv_before_run(argv: List[str]) -> Tuple[bool, Optional[str], List[str]]:
    """Convenience function to validate tokenized commands."""
    validator = get_validator()
    is_safe, error, warnings = validator.validate_argv(argv)

    for warning in warnings:
        logger.warning(f"Command warning: {warning}")

    if error:
        logger.error(f"Command blocked: {error}")

    return is_safe, error, warnings
