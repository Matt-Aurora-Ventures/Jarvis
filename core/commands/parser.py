"""
Command Parser - Message parsing and argument validation.

This module provides command parsing infrastructure:
- CommandParser for parsing messages
- ParsedCommand for parsed message representation
- Argument extraction with patterns
- Schema-based validation
"""

import logging
import re
import shlex
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """A single validation error."""
    field: str
    message: str
    value: Any = None


@dataclass
class ValidationResult:
    """Result of argument validation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    parsed_args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedCommand:
    """
    A parsed command message.

    Attributes:
        command: The command name (without prefix), or None if not a command
        args: List of parsed arguments
        raw_args: The raw argument string
        original_text: The original message text
    """
    command: Optional[str]
    args: List[str]
    raw_args: str
    original_text: str

    @property
    def is_command(self) -> bool:
        """Whether this is a valid command."""
        return self.command is not None

    @property
    def arg_count(self) -> int:
        """Number of arguments."""
        return len(self.args)

    def get_arg(self, index: int, default: Any = None) -> Any:
        """
        Get argument by index with optional default.

        Args:
            index: Argument index
            default: Default value if not found

        Returns:
            Argument value or default
        """
        if 0 <= index < len(self.args):
            return self.args[index]
        return default


@dataclass
class ParseAndValidateResult:
    """Result of combined parse and validate operation."""
    is_valid: bool
    command: Optional[str]
    parsed_args: Dict[str, Any]
    errors: List[ValidationError] = field(default_factory=list)


class CommandParser:
    """
    Parse command messages and validate arguments.

    Features:
    - Parse messages to extract command and arguments
    - Handle quoted arguments
    - Extract arguments with regex patterns
    - Validate arguments against schemas
    """

    def __init__(self, prefix: str = "/"):
        """
        Initialize the parser.

        Args:
            prefix: Command prefix (default "/")
        """
        self.prefix = prefix

    def parse(self, message: str) -> ParsedCommand:
        """
        Parse a message into command and arguments.

        Args:
            message: The message to parse

        Returns:
            ParsedCommand object
        """
        if not message or not message.strip():
            return ParsedCommand(
                command=None,
                args=[],
                raw_args="",
                original_text=message or ""
            )

        message = message.strip()

        # Check for prefix
        if not message.startswith(self.prefix):
            return ParsedCommand(
                command=None,
                args=[],
                raw_args="",
                original_text=message
            )

        # Remove prefix
        content = message[len(self.prefix):]
        if not content:
            return ParsedCommand(
                command=None,
                args=[],
                raw_args="",
                original_text=message
            )

        # Parse with shlex to handle quotes
        try:
            parts = shlex.split(content)
        except ValueError:
            # Fall back to simple split if quotes are unbalanced
            parts = content.split()

        if not parts:
            return ParsedCommand(
                command=None,
                args=[],
                raw_args="",
                original_text=message
            )

        # First part is the command
        command_part = parts[0]

        # Handle @botname suffix
        if "@" in command_part:
            command_part = command_part.split("@")[0]

        # Normalize command to lowercase
        command = command_part.lower()

        # Rest are arguments
        args = parts[1:] if len(parts) > 1 else []

        # Calculate raw_args
        raw_args = ""
        if args:
            # Find where args start in original content
            first_arg_pos = content.find(parts[1]) if len(parts) > 1 else len(content)
            raw_args = content[first_arg_pos:].strip() if first_arg_pos < len(content) else ""

        return ParsedCommand(
            command=command,
            args=args,
            raw_args=raw_args,
            original_text=message
        )

    def extract_args(
        self,
        message: str,
        pattern: str
    ) -> Dict[str, str]:
        """
        Extract arguments using a regex pattern.

        Args:
            message: The message to extract from
            pattern: Regex pattern with groups

        Returns:
            Dictionary of extracted arguments
        """
        # Remove prefix if present
        content = message
        if message.startswith(self.prefix):
            content = message[len(self.prefix):]
            # Remove command word
            parts = content.split(None, 1)
            content = parts[1] if len(parts) > 1 else ""

        match = re.match(pattern, content, re.IGNORECASE)
        if not match:
            return {}

        result = {}

        # Add numbered groups
        for i, group in enumerate(match.groups()):
            if group is not None:
                result[str(i)] = group

        # Add named groups (these will override numbered ones)
        result.update({k: v for k, v in match.groupdict().items() if v is not None})

        return result

    def validate_args(
        self,
        args: Dict[str, Any],
        schema: Dict[str, Dict[str, Any]]
    ) -> bool:
        """
        Validate arguments against a schema.

        Args:
            args: Dictionary of argument values
            schema: Validation schema

        Returns:
            True if valid, False otherwise
        """
        result = self.validate_args_detailed(args, schema)
        return result.is_valid

    def validate_args_detailed(
        self,
        args: Dict[str, Any],
        schema: Dict[str, Dict[str, Any]]
    ) -> ValidationResult:
        """
        Validate arguments against a schema with detailed errors.

        Args:
            args: Dictionary of argument values
            schema: Validation schema

        Returns:
            ValidationResult with errors
        """
        errors = []
        parsed_args = {}

        for field_name, field_schema in schema.items():
            value = args.get(field_name)
            required = field_schema.get("required", False)
            field_type = field_schema.get("type", "string")

            # Check required
            if value is None:
                if required:
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"Required field '{field_name}' is missing"
                    ))
                continue

            # Type validation and coercion
            try:
                if field_type == "number":
                    parsed_value = float(value)
                    # Check if it should be int
                    if parsed_value == int(parsed_value):
                        parsed_value = int(parsed_value)
                elif field_type == "string":
                    parsed_value = str(value)
                elif field_type == "boolean":
                    parsed_value = str(value).lower() in ("true", "1", "yes")
                else:
                    parsed_value = value
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    field=field_name,
                    message=f"Invalid type for '{field_name}': expected {field_type}",
                    value=value
                ))
                continue

            # Check choices
            choices = field_schema.get("choices")
            if choices and parsed_value not in choices:
                errors.append(ValidationError(
                    field=field_name,
                    message=f"Invalid value for '{field_name}': must be one of {choices}",
                    value=parsed_value
                ))
                continue

            # Check min/max for numbers
            if field_type == "number":
                min_val = field_schema.get("min")
                max_val = field_schema.get("max")

                if min_val is not None and parsed_value < min_val:
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"Value for '{field_name}' must be >= {min_val}",
                        value=parsed_value
                    ))
                    continue

                if max_val is not None and parsed_value > max_val:
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"Value for '{field_name}' must be <= {max_val}",
                        value=parsed_value
                    ))
                    continue

            # Check pattern for strings
            if field_type == "string":
                pattern = field_schema.get("pattern")
                if pattern and not re.match(pattern, str(parsed_value)):
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"Value for '{field_name}' does not match pattern",
                        value=parsed_value
                    ))
                    continue

            parsed_args[field_name] = parsed_value

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            parsed_args=parsed_args
        )

    def parse_and_validate(
        self,
        message: str,
        schema: Dict[str, Dict[str, Any]]
    ) -> ParseAndValidateResult:
        """
        Parse and validate a message in one step.

        Schema fields can have a 'position' key to map positional args.

        Args:
            message: The message to parse
            schema: Validation schema

        Returns:
            ParseAndValidateResult
        """
        parsed = self.parse(message)

        if not parsed.is_command:
            return ParseAndValidateResult(
                is_valid=False,
                command=None,
                parsed_args={},
                errors=[ValidationError(field="message", message="Not a valid command")]
            )

        # Build args dict from positional args
        args = {}
        for field_name, field_schema in schema.items():
            position = field_schema.get("position")
            if position is not None and position < len(parsed.args):
                args[field_name] = parsed.args[position]

        # Validate
        result = self.validate_args_detailed(args, schema)

        return ParseAndValidateResult(
            is_valid=result.is_valid,
            command=parsed.command,
            parsed_args=result.parsed_args,
            errors=result.errors
        )
