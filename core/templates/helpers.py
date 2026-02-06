"""
Template Helper Functions

This module provides built-in helper functions for template formatting:
- format_date: Format dates in various formats
- format_number: Format numbers with decimal precision and separators
- format_currency: Format monetary values with symbols
- truncate: Truncate text to a specified length
- uppercase, lowercase, capitalize: Case transformations
"""

from datetime import datetime, date, timezone
from typing import Any, Optional, Dict, Callable, Union
import re


class HelperError(Exception):
    """Raised when a helper function encounters an error."""
    pass


def format_date(
    value: Any,
    fmt: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    Format a date/datetime value.

    Args:
        value: A datetime, date, ISO string, Unix timestamp, or None
        fmt: strftime format string (default: "%Y-%m-%d %H:%M:%S")

    Returns:
        Formatted date string, empty string for None

    Raises:
        HelperError: If value cannot be parsed as a date
    """
    if value is None:
        return ""

    try:
        # Handle datetime objects
        if isinstance(value, datetime):
            return value.strftime(fmt)

        # Handle date objects
        if isinstance(value, date):
            return value.strftime(fmt)

        # Handle Unix timestamps (int or float)
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
            return dt.strftime(fmt)

        # Handle string values
        if isinstance(value, str):
            # Try ISO format first
            try:
                # Handle ISO format with or without timezone
                if "T" in value:
                    # Remove timezone info for simple parsing
                    clean_value = value.replace("Z", "+00:00")
                    if "+" in clean_value or clean_value.count("-") > 2:
                        # Has timezone
                        dt = datetime.fromisoformat(clean_value)
                    else:
                        dt = datetime.fromisoformat(value)
                else:
                    # Simple date format
                    dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.strftime(fmt)
            except ValueError:
                pass

            # Try common date formats
            for date_fmt in [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%Y/%m/%d",
                "%d-%m-%Y",
            ]:
                try:
                    dt = datetime.strptime(value, date_fmt)
                    return dt.strftime(fmt)
                except ValueError:
                    continue

            raise HelperError(f"Cannot parse date: {value}")

        raise HelperError(f"Unsupported date type: {type(value)}")

    except Exception as e:
        if isinstance(e, HelperError):
            raise
        raise HelperError(f"Error formatting date: {e}")


def format_number(
    value: Any,
    decimals: int = 2,
    thousands_separator: str = ","
) -> str:
    """
    Format a number with decimal precision and thousands separator.

    Args:
        value: A number (int, float, or string)
        decimals: Number of decimal places (default: 2)
        thousands_separator: Character for thousands (default: ",")

    Returns:
        Formatted number string

    Raises:
        HelperError: If value cannot be converted to a number
    """
    if value is None:
        return "0"

    try:
        # Convert to float
        if isinstance(value, str):
            # Remove existing separators for parsing
            clean = value.replace(",", "").replace(" ", "")
            num = float(clean)
        else:
            num = float(value)

        # Format with decimals
        if decimals == 0:
            formatted = str(int(round(num)))
        else:
            formatted = f"{num:.{decimals}f}"

        # Add thousands separator
        if thousands_separator and abs(num) >= 1000:
            parts = formatted.split(".")
            integer_part = parts[0]

            # Handle negative numbers
            negative = integer_part.startswith("-")
            if negative:
                integer_part = integer_part[1:]

            # Add separators
            result = ""
            for i, digit in enumerate(reversed(integer_part)):
                if i > 0 and i % 3 == 0:
                    result = thousands_separator + result
                result = digit + result

            if negative:
                result = "-" + result

            if len(parts) > 1:
                result = result + "." + parts[1]

            return result

        return formatted

    except (ValueError, TypeError) as e:
        raise HelperError(f"Cannot format number: {value} - {e}")


def format_currency(
    amount: Any,
    symbol: str = "$",
    decimals: int = 2
) -> str:
    """
    Format a monetary value with currency symbol.

    Args:
        amount: The monetary amount
        symbol: Currency symbol (default: "$")
        decimals: Number of decimal places (default: 2)

    Returns:
        Formatted currency string
    """
    if amount is None:
        return f"{symbol}0.00"

    try:
        num = float(amount)

        # Handle negative amounts
        if num < 0:
            formatted = format_number(abs(num), decimals=decimals)
            return f"-{symbol}{formatted}"
        else:
            formatted = format_number(num, decimals=decimals)
            return f"{symbol}{formatted}"

    except (ValueError, TypeError, HelperError):
        return f"{symbol}0.00"


def truncate(
    text: Any,
    length: int,
    suffix: str = "...",
    word_boundary: bool = False
) -> str:
    """
    Truncate text to a specified length.

    Args:
        text: The text to truncate
        length: Maximum length (excluding suffix)
        suffix: String to append when truncated (default: "...")
        word_boundary: If True, truncate at word boundary

    Returns:
        Truncated text
    """
    if text is None:
        return ""

    text = str(text)

    if len(text) <= length:
        return text

    if word_boundary:
        # Find last space before length
        truncated = text[:length]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated.rstrip() + suffix
    else:
        return text[:length] + suffix


def uppercase(text: Any) -> str:
    """
    Convert text to uppercase.

    Args:
        text: The text to convert

    Returns:
        Uppercase text
    """
    if text is None:
        return ""
    return str(text).upper()


def lowercase(text: Any) -> str:
    """
    Convert text to lowercase.

    Args:
        text: The text to convert

    Returns:
        Lowercase text
    """
    if text is None:
        return ""
    return str(text).lower()


def capitalize(text: Any) -> str:
    """
    Capitalize the first letter of text.

    Args:
        text: The text to capitalize

    Returns:
        Capitalized text
    """
    if text is None:
        return ""
    text = str(text)
    if not text:
        return ""
    return text[0].upper() + text[1:]


def get_builtin_helpers() -> Dict[str, Callable]:
    """
    Get a dictionary of all built-in helper functions.

    Returns:
        Dictionary mapping helper names to functions
    """
    return {
        "format_date": format_date,
        "format_number": format_number,
        "format_currency": format_currency,
        "truncate": truncate,
        "uppercase": uppercase,
        "lowercase": lowercase,
        "capitalize": capitalize,
    }
