"""
Personality Validator.

Provides validation functions for Personality objects, checking
file existence and format compliance.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from core.personality.model import Personality

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for validation errors."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """
    Represents a validation error or warning.

    Attributes:
        field: Name of the field with the error
        message: Human-readable error message
        severity: Error severity level
    """
    field: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.field}: {self.message}"


def validate_personality(
    personality: Personality,
    base_path: Optional[str] = None
) -> List[ValidationError]:
    """
    Validate a Personality object.

    Checks:
    - Required fields are present
    - File paths point to existing files
    - SOUL/IDENTITY files have proper format (markdown with headers)

    Args:
        personality: Personality object to validate
        base_path: Base path for resolving relative file paths

    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors: List[ValidationError] = []

    # Use personality's base path if not provided
    effective_base_path = base_path or personality._base_path

    # Validate file paths
    errors.extend(_validate_file_path(
        personality.soul_path,
        "soul_path",
        effective_base_path,
        validate_format=True,
        file_type="soul"
    ))

    errors.extend(_validate_file_path(
        personality.identity_path,
        "identity_path",
        effective_base_path,
        validate_format=True,
        file_type="identity"
    ))

    errors.extend(_validate_file_path(
        personality.bootstrap_path,
        "bootstrap_path",
        effective_base_path,
        validate_format=False  # Bootstrap doesn't need special format
    ))

    return errors


def _validate_file_path(
    file_path: Optional[str],
    field_name: str,
    base_path: Optional[str],
    validate_format: bool = False,
    file_type: Optional[str] = None
) -> List[ValidationError]:
    """
    Validate a single file path.

    Args:
        file_path: Path to validate
        field_name: Name of the field for error messages
        base_path: Base path for resolving relative paths
        validate_format: Whether to validate file format
        file_type: Type of file ('soul' or 'identity') for format validation

    Returns:
        List of ValidationError objects
    """
    errors: List[ValidationError] = []

    if not file_path:
        # Path not set is OK - optional
        return errors

    # Resolve path
    path = Path(file_path)
    if not path.is_absolute() and base_path:
        path = Path(base_path) / file_path

    # Check existence
    if not path.exists():
        errors.append(ValidationError(
            field=field_name,
            message=f"File not found: {path}",
            severity=ErrorSeverity.ERROR
        ))
        return errors  # Can't validate format if file doesn't exist

    # Validate format if requested
    if validate_format:
        format_errors = _validate_markdown_format(
            path,
            field_name,
            file_type
        )
        errors.extend(format_errors)

    return errors


def _validate_markdown_format(
    path: Path,
    field_name: str,
    file_type: Optional[str] = None
) -> List[ValidationError]:
    """
    Validate markdown file format.

    Checks:
    - File is not empty
    - File has at least one markdown heading

    Args:
        path: Path to markdown file
        field_name: Field name for error messages
        file_type: Type of file for specific checks

    Returns:
        List of ValidationError objects
    """
    errors: List[ValidationError] = []

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(ValidationError(
            field=field_name,
            message=f"Error reading file: {e}",
            severity=ErrorSeverity.ERROR
        ))
        return errors

    # Check for empty file
    if not content.strip():
        errors.append(ValidationError(
            field=field_name,
            message=f"File is empty: {path}",
            severity=ErrorSeverity.ERROR
        ))
        return errors

    # Check for markdown heading
    lines = content.split("\n")
    has_heading = any(
        line.strip().startswith("#")
        for line in lines
    )

    if not has_heading:
        errors.append(ValidationError(
            field=field_name,
            message=f"File lacks markdown heading (# Title): {path}",
            severity=ErrorSeverity.WARNING
        ))

    return errors
