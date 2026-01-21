"""Shared logging helpers for Jarvis components."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable

LOG_DIR = Path("logs")
DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def ensure_log_dir() -> Path:
    """Ensure the shared logs directory exists."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def has_rotating_handler(logger: logging.Logger, filename: str) -> bool:
    """Check if the logger already has a RotatingFileHandler for the given file."""
    return any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename).name == filename
        for handler in logger.handlers
    )


def add_rotating_handler(
    logger: logging.Logger,
    filename: str,
    level: int = logging.INFO,
    fmt: str = DEFAULT_FORMAT,
    max_bytes: int = 5_000_000,
    backup_count: int = 7,
) -> RotatingFileHandler:
    """Attach a rotating file handler to the logger."""
    log_dir = ensure_log_dir()
    handler = RotatingFileHandler(
        log_dir / filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    return handler


def configure_component_logger(
    namespace: str,
    prefix: str,
    level: int = logging.INFO,
    error_level: int = logging.ERROR,
) -> Iterable[RotatingFileHandler]:
    """
    Configure rotating logging for a component namespace.

    Args:
        namespace: Logger namespace (e.g., "tg_bot").
        prefix: File prefix (e.g., "telegram_bot").
        level: Level for general logs.
        error_level: Level threshold for error-only logs.
    """
    logger = logging.getLogger(namespace)
    logger.setLevel(min(level, error_level))

    handlers = []
    general_name = f"{prefix}.log"
    error_name = f"{prefix}_errors.log"

    if not has_rotating_handler(logger, general_name):
        handlers.append(add_rotating_handler(logger, general_name, level))

    if not has_rotating_handler(logger, error_name):
        handlers.append(add_rotating_handler(logger, error_name, error_level))

    return handlers


__all__ = [
    "configure_component_logger",
    "ensure_log_dir",
]
