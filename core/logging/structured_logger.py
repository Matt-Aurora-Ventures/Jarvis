"""
StructuredLogger - Enhanced logging with context tracking.

Provides:
- StructuredLogger class with persistent context
- Context propagation to child loggers
- Business event logging
- Log rotation utilities
- Setup helpers

Usage:
    from core.logging.structured_logger import get_structured_logger

    logger = get_structured_logger("jarvis.trading", service="trading_engine")
    logger.set_context("correlation_id", "trade-123")
    logger.log_event("TRADE_EXECUTED", symbol="SOL", amount=100)
"""

import asyncio
import gzip
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, List

from .json_formatter import JsonFormatter


# Logger registry for singleton pattern
_logger_registry: Dict[str, "StructuredLogger"] = {}


class StructuredLogger(logging.Logger):
    """
    Enhanced logger with structured context support.

    Extends Python's Logger with:
    - Persistent context (service, correlation_id, user_id, active_flags)
    - log_with_context() for adding per-call context
    - log_event() for business events
    - Child logger inheritance
    """

    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)
        self._context: Dict[str, Any] = {}

    @property
    def context(self) -> Dict[str, Any]:
        """Get the current context dictionary."""
        return self._context.copy()

    def set_context(self, key: str = None, value: Any = None, **kwargs) -> None:
        """
        Set context values.

        Can be called with:
            logger.set_context("service", "trading")
            logger.set_context(service="trading", user_id="123")
        """
        if key is not None and value is not None:
            self._context[key] = value
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context values."""
        self._context.clear()

    def _inject_context(self, record: logging.LogRecord) -> None:
        """Inject context into log record."""
        for key, value in self._context.items():
            if not hasattr(record, key):
                setattr(record, key, value)

    def makeRecord(
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: str,
        args,
        exc_info,
        func: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        sinfo: Optional[str] = None,
    ) -> logging.LogRecord:
        """Create a LogRecord with context injected."""
        record = super().makeRecord(
            name, level, fn, lno, msg, args, exc_info, func, extra, sinfo
        )
        self._inject_context(record)
        return record

    def log_with_context(
        self, level: int, message: str, exc_info=None, **kwargs
    ) -> None:
        """
        Log a message with additional context.

        Args:
            level: Logging level (e.g., logging.INFO)
            message: Log message
            exc_info: Exception info (optional)
            **kwargs: Additional context fields (symbol, amount, duration_ms, etc.)
        """
        # Merge kwargs with existing context for this log call
        extra_context = {**self._context}

        # Handle special fields
        context_data = {}
        special_fields = ["service", "correlation_id", "user_id", "active_flags", "duration_ms"]

        for key, value in kwargs.items():
            if key in special_fields:
                extra_context[key] = value
            else:
                context_data[key] = value

        if context_data:
            extra_context["context"] = context_data

        self.log(level, message, exc_info=exc_info, extra=extra_context)

    def log_event(self, event_name: str, level: int = logging.INFO, **data) -> None:
        """
        Log a business event.

        Args:
            event_name: Name of the event (e.g., "TRADE_EXECUTED")
            level: Logging level (default INFO)
            **data: Event data
        """
        message = f"[EVENT] {event_name}"
        extra_context = {**self._context, "event_name": event_name}

        # Separate special fields from context data
        context_data = {}
        special_fields = ["service", "correlation_id", "user_id", "active_flags", "duration_ms"]

        for key, value in data.items():
            if key in special_fields:
                extra_context[key] = value
            else:
                context_data[key] = value

        if context_data:
            extra_context["context"] = context_data

        self.log(level, message, extra=extra_context)

    def get_child(self, suffix: str) -> "StructuredLogger":
        """
        Get a child logger that inherits this logger's context.

        Args:
            suffix: Suffix to append to logger name (e.g., "executor")

        Returns:
            Child StructuredLogger with inherited context
        """
        child_name = f"{self.name}.{suffix}"
        child = get_structured_logger(child_name)
        # Copy parent's context to child
        child._context = self._context.copy()
        return child


def get_structured_logger(
    name: str,
    **initial_context
) -> StructuredLogger:
    """
    Get or create a StructuredLogger.

    Args:
        name: Logger name (e.g., "jarvis.trading")
        **initial_context: Initial context values (service, user_id, etc.)

    Returns:
        StructuredLogger instance (same instance for same name)
    """
    if name in _logger_registry:
        logger = _logger_registry[name]
        # Update context if new values provided
        if initial_context:
            logger.set_context(**initial_context)
        return logger

    # Create new structured logger
    # Register our custom logger class
    old_class = logging.getLoggerClass()
    logging.setLoggerClass(StructuredLogger)
    logger = logging.getLogger(name)
    logging.setLoggerClass(old_class)

    # Ensure it's a StructuredLogger
    if not isinstance(logger, StructuredLogger):
        # Wrap existing logger
        structured = StructuredLogger(name, logger.level)
        structured.handlers = logger.handlers
        structured.propagate = logger.propagate
        logger = structured

    # Set initial context
    if initial_context:
        logger.set_context(**initial_context)

    _logger_registry[name] = logger
    return logger


def setup_structured_logger(
    name: str,
    log_file: Optional[str] = None,
    console: bool = True,
    level: int = logging.INFO,
    service: Optional[str] = None,
) -> StructuredLogger:
    """
    Set up a structured logger with handlers.

    Args:
        name: Logger name
        log_file: Path to log file (optional)
        console: Whether to add console handler
        level: Logging level
        service: Default service name

    Returns:
        Configured StructuredLogger
    """
    logger = get_structured_logger(name)
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers = []

    formatter = JsonFormatter(service=service)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    if log_file:
        # Ensure directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    return logger


# Log rotation utilities

def get_log_filename(base_name: str, date: datetime) -> str:
    """
    Get log filename for a specific date.

    Args:
        base_name: Base name (e.g., "jarvis")
        date: Date for the log file

    Returns:
        Filename like "jarvis-2026-01-18.jsonl"
    """
    return f"{base_name}-{date.strftime('%Y-%m-%d')}.jsonl"


def rotate_logs(log_dir: Path, current_date: datetime) -> None:
    """
    Rotate log files (placeholder for daily rotation).

    Args:
        log_dir: Directory containing logs
        current_date: Current date for new log file
    """
    # This is handled by TimedRotatingFileHandler
    # This function is for manual rotation if needed
    pass


def rotate_and_cleanup_logs(
    log_dir: Path,
    archive_dir: Optional[Path] = None,
    keep_days: int = 7,
    delete_after_days: int = 30,
    base_name: str = "jarvis",
) -> None:
    """
    Rotate and clean up log files.

    - Keep logs < 7 days in log_dir
    - Archive logs 7-30 days old as gzipped in archive_dir
    - Delete logs > 30 days old

    Args:
        log_dir: Directory containing logs
        archive_dir: Directory for archives (default: log_dir/archive)
        keep_days: Days to keep logs before archiving
        delete_after_days: Days to keep archives before deletion
        base_name: Base name pattern for log files
    """
    # Ensure directories exist
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    if archive_dir is None:
        archive_dir = log_dir / "archive"
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    keep_threshold = now - timedelta(days=keep_days)
    delete_threshold = now - timedelta(days=delete_after_days)

    # Process log files
    for log_file in log_dir.glob(f"{base_name}-*.jsonl"):
        try:
            # Parse date from filename
            date_str = log_file.stem.split("-", 1)[1]  # e.g., "2026-01-18"
            file_date = datetime.strptime(date_str, "%Y-%m-%d")

            # Archive old logs
            if file_date < keep_threshold:
                archive_path = archive_dir / f"{log_file.name}.gz"
                with open(log_file, "rb") as f_in:
                    with gzip.open(archive_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                log_file.unlink()
        except (ValueError, IndexError):
            # Skip files that don't match expected pattern
            continue

    # Delete very old archives
    for archive_file in archive_dir.glob(f"{base_name}-*.jsonl.gz"):
        try:
            # Get file modification time
            mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
            if mtime < delete_threshold:
                archive_file.unlink()
        except (OSError, ValueError):
            continue


def get_rotating_file_handler(
    log_dir: Path,
    base_name: str = "jarvis",
    when: str = "midnight",
    backup_count: int = 7,
    service: Optional[str] = None,
) -> TimedRotatingFileHandler:
    """
    Get a timed rotating file handler.

    Args:
        log_dir: Directory for log files
        base_name: Base name for log files
        when: Rotation interval ("midnight", "H", "D", etc.)
        backup_count: Number of backup files to keep
        service: Service name for formatter

    Returns:
        Configured TimedRotatingFileHandler
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{base_name}.jsonl"

    handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when=when,
        backupCount=backup_count,
        encoding="utf-8",
    )

    handler.setFormatter(JsonFormatter(service=service))

    # Custom namer to use date suffix
    def namer(default_name: str) -> str:
        # Extract date from rotated filename
        base, ext = os.path.splitext(default_name)
        if ext.startswith("."):
            # TimedRotatingFileHandler adds date as extension
            return f"{base.rsplit('.', 1)[0]}-{ext[1:]}.jsonl"
        return default_name

    handler.namer = namer

    return handler


# Cleanup scheduler

_cleanup_task: Optional[asyncio.Task] = None


async def start_cleanup_scheduler(
    log_dir: Path,
    archive_dir: Optional[Path] = None,
    interval_hours: int = 24,
    keep_days: int = 7,
    delete_after_days: int = 30,
) -> asyncio.Task:
    """
    Start a background task for log cleanup.

    Args:
        log_dir: Directory containing logs
        archive_dir: Directory for archives
        interval_hours: Hours between cleanup runs
        keep_days: Days to keep logs before archiving
        delete_after_days: Days to keep archives before deletion

    Returns:
        The cleanup task
    """
    async def cleanup_loop():
        while True:
            try:
                await asyncio.sleep(interval_hours * 3600)
                rotate_and_cleanup_logs(
                    log_dir=log_dir,
                    archive_dir=archive_dir,
                    keep_days=keep_days,
                    delete_after_days=delete_after_days,
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Log cleanup error: {e}")

    task = asyncio.create_task(cleanup_loop())
    global _cleanup_task
    _cleanup_task = task
    return task


async def stop_cleanup_scheduler(task: Optional[asyncio.Task] = None) -> None:
    """
    Stop the cleanup scheduler.

    Args:
        task: The task to stop (or uses global task)
    """
    global _cleanup_task
    task = task or _cleanup_task
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        _cleanup_task = None
