"""
Response Building Module.

Provides consistent response formatting for Telegram and other platforms.

Modules:
- builder: Fluent text builder for message composition
- keyboard: Inline keyboard builder for Telegram
- templates: Pre-defined response templates
- formatter: Text formatting utilities
"""

from core.response.builder import ResponseBuilder
from core.response.keyboard import KeyboardBuilder
from core.response.templates import (
    error_response,
    success_response,
    loading_response,
    confirmation_response,
    info_response,
    warning_response,
    trade_success,
    trade_failed,
    portfolio_summary,
    position_summary,
    price_alert,
    position_alert,
    format_price,
    format_percentage,
    format_amount,
)
from core.response.formatter import (
    ResponseFormatter,
    Platform,
    format_list,
    format_table,
    format_code,
    truncate_safely,
    format_number,
    format_currency,
    escape_markdown,
    format_duration,
    format_timestamp,
)

__all__ = [
    # Builder
    "ResponseBuilder",

    # Keyboard
    "KeyboardBuilder",

    # Templates
    "error_response",
    "success_response",
    "loading_response",
    "confirmation_response",
    "info_response",
    "warning_response",
    "trade_success",
    "trade_failed",
    "portfolio_summary",
    "position_summary",
    "price_alert",
    "position_alert",
    "format_price",
    "format_percentage",
    "format_amount",

    # Formatter
    "ResponseFormatter",
    "Platform",
    "format_list",
    "format_table",
    "format_code",
    "truncate_safely",
    "format_number",
    "format_currency",
    "escape_markdown",
    "format_duration",
    "format_timestamp",
]
