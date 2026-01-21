"""
Logging utilities for Jarvis.

Provides:
- StructuredLogger: Enhanced logger with context tracking
- JsonFormatter: JSON log formatter
- LogEntry, LogContext, BusinessEvent: Data models
- Log rotation and cleanup utilities
- Legacy support for existing code
"""

# Legacy imports (keep for backwards compatibility)
from core.logging.structured import StructuredFormatter, setup_structured_logging, get_logger
from core.logging.aggregation import LogAggregator

# New structured logging imports
from core.logging.log_models import LogEntry, LogContext, BusinessEvent, EventTypes
from core.logging.json_formatter import JsonFormatter, CompactJsonFormatter
from core.logging.structured_logger import (
    StructuredLogger,
    get_structured_logger,
    setup_structured_logger,
    get_log_filename,
    rotate_logs,
    rotate_and_cleanup_logs,
    get_rotating_file_handler,
    start_cleanup_scheduler,
    stop_cleanup_scheduler,
)
from core.logging.error_tracker import ErrorTracker, error_tracker

__all__ = [
    # Legacy
    "StructuredFormatter",
    "setup_structured_logging",
    "get_logger",
    "LogAggregator",
    # Data models
    "LogEntry",
    "LogContext",
    "BusinessEvent",
    "EventTypes",
    # Formatters
    "JsonFormatter",
    "CompactJsonFormatter",
    # Logger
    "StructuredLogger",
    "get_structured_logger",
    "setup_structured_logger",
    # Rotation
    "get_log_filename",
    "rotate_logs",
    "rotate_and_cleanup_logs",
    "get_rotating_file_handler",
    "start_cleanup_scheduler",
    "stop_cleanup_scheduler",
    # Error tracking
    "ErrorTracker",
    "error_tracker",
]
