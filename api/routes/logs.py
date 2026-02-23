"""
API Logging Management Endpoints

Provides endpoints to:
- View log statistics
- Trigger log rotation
- Cleanup old logs
- Download log files

Usage:
    GET  /api/logs/stats        - Get log statistics
    POST /api/logs/cleanup      - Trigger log cleanup
    POST /api/logs/rotate       - Force log rotation
    GET  /api/logs/files        - List log files
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from api.log_rotation import cleanup_old_logs, get_log_stats

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _parse_float_env(name: str, default: float) -> float:
    """Parse a float environment variable, returning default on invalid value."""
    try:
        return float(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


# =============================================================================
# Request/Response Models
# =============================================================================


class LogStatsResponse(BaseModel):
    """Log statistics response."""
    total_files: int
    total_size_mb: float
    compressed_files: int
    compressed_size_mb: float
    uncompressed_files: int
    uncompressed_size_mb: float
    oldest_log: Optional[dict] = None
    newest_log: Optional[dict] = None


class LogCleanupRequest(BaseModel):
    """Log cleanup request."""
    max_age_days: int = Field(30, ge=1, le=365, description="Delete logs older than this")
    compress_age_days: int = Field(7, ge=1, le=365, description="Compress logs older than this")
    dry_run: bool = Field(False, description="Preview changes without applying")


class LogCleanupResponse(BaseModel):
    """Log cleanup response."""
    scanned: int
    compressed: int
    deleted: int
    total_size_freed_mb: float
    errors: int
    dry_run: bool


class LogFileInfo(BaseModel):
    """Information about a log file."""
    name: str
    size_bytes: int
    size_mb: float
    age_days: float
    compressed: bool
    last_modified: str


# =============================================================================
# Helper Functions
# =============================================================================


def get_log_directory() -> Path:
    """Get the log directory path."""
    log_dir = os.getenv("API_LOG_DIR", "/var/log/jarvis")
    return Path(log_dir)


def verify_log_directory():
    """Verify log directory exists."""
    log_dir = get_log_directory()
    if not log_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log directory not found: {log_dir}"
        )
    return log_dir


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/stats", response_model=LogStatsResponse)
async def get_stats(
    log_dir: Path = Depends(verify_log_directory),
):
    """
    Get log file statistics.

    Returns information about all log files including:
    - Total number and size of files
    - Compressed vs uncompressed files
    - Oldest and newest log files
    """
    stats = get_log_stats(str(log_dir), pattern="*.log*")

    if "error" in stats:
        raise HTTPException(status_code=500, detail=stats["error"])

    return LogStatsResponse(**stats)


@router.post("/cleanup", response_model=LogCleanupResponse)
async def cleanup_logs(
    request: LogCleanupRequest,
    log_dir: Path = Depends(verify_log_directory),
):
    """
    Cleanup old log files.

    - Compresses logs older than `compress_age_days`
    - Deletes logs older than `max_age_days`
    - Use `dry_run=true` to preview changes

    **Note:** This operation cannot be undone (unless dry_run=true).
    """
    stats = cleanup_old_logs(
        log_dir=str(log_dir),
        max_age_days=request.max_age_days,
        compress_age_days=request.compress_age_days,
        pattern="*.log*",
        dry_run=request.dry_run,
    )

    if "error" in stats:
        raise HTTPException(status_code=500, detail=stats["error"])

    return LogCleanupResponse(
        scanned=stats["scanned"],
        compressed=stats["compressed"],
        deleted=stats["deleted"],
        total_size_freed_mb=stats["total_size_freed"] / 1024 / 1024,
        errors=stats["errors"],
        dry_run=request.dry_run,
    )


@router.get("/files", response_model=list[LogFileInfo])
async def list_log_files(
    limit: int = Query(50, ge=1, le=500, description="Max files to return"),
    compressed_only: bool = Query(False, description="Only show compressed files"),
    log_dir: Path = Depends(verify_log_directory),
):
    """
    List log files in the log directory.

    Returns a list of log files sorted by modification time (newest first).
    """
    import time

    pattern = "*.log.gz" if compressed_only else "*.log*"
    files = []

    for log_file in log_dir.glob(pattern):
        if not log_file.is_file():
            continue

        stat = log_file.stat()
        age_seconds = time.time() - stat.st_mtime

        files.append(
            LogFileInfo(
                name=log_file.name,
                size_bytes=stat.st_size,
                size_mb=round(stat.st_size / 1024 / 1024, 2),
                age_days=round(age_seconds / 86400, 2),
                compressed=log_file.suffix == ".gz",
                last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            )
        )

    # Sort by modification time (newest first)
    files.sort(key=lambda f: f.last_modified, reverse=True)

    return files[:limit]


@router.get("/config")
async def get_log_config():
    """
    Get current logging configuration.

    Returns the environment variables that control logging behavior.
    """
    return {
        "log_directory": str(get_log_directory()),
        "request_logging_enabled": os.getenv("REQUEST_LOGGING_ENABLED", "true"),
        "log_request_body": os.getenv("LOG_REQUEST_BODY", "false"),
        "log_response_body": os.getenv("LOG_RESPONSE_BODY", "false"),
        "slow_request_threshold": _parse_float_env("SLOW_REQUEST_THRESHOLD", 1.0),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


@router.get("/recent")
async def get_recent_logs(
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to return"),
    level: Optional[str] = Query(None, description="Filter by log level (INFO, WARNING, ERROR)"),
    log_dir: Path = Depends(verify_log_directory),
):
    """
    Get recent log entries.

    Returns the last N lines from the current log file.
    Optionally filter by log level.
    """
    log_file = log_dir / "api_requests.log"

    if not log_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Current log file not found"
        )

    try:
        # Read last N lines
        with open(log_file, "r") as f:
            all_lines = f.readlines()

        # Get last N lines
        recent_lines = all_lines[-lines:]

        # Filter by level if specified
        if level:
            level_upper = level.upper()
            recent_lines = [
                line for line in recent_lines
                if level_upper in line
            ]

        return {
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines),
            "logs": recent_lines,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading log file: {str(e)}"
        )
