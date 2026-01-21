"""
Tests for API Log Management Endpoints

Tests:
- GET /api/logs/stats
- POST /api/logs/cleanup
- GET /api/logs/files
- GET /api/logs/config
- GET /api/logs/recent
"""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.logs import router


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_log_dir():
    """Create a temporary log directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Create test log files
        now = time.time()

        # Recent log (main api log file that endpoints look for)
        api_requests = log_dir / "api_requests.log"
        api_requests.write_text("2024-01-01 10:00:00 - INFO - Test log 1\n" * 10)

        # Another recent log for stats
        recent = log_dir / "api.log"
        recent.write_text("2024-01-01 10:00:00 - INFO - Test log 1\n" * 10)

        # Old log
        old = log_dir / "api.log.1"
        old.write_text("2024-01-01 09:00:00 - INFO - Old log\n" * 5)
        os.utime(old, (now - 10 * 86400, now - 10 * 86400))

        # Compressed log
        import gzip
        compressed = log_dir / "api.log.2.gz"
        with gzip.open(compressed, "wt") as f:
            f.write("2024-01-01 08:00:00 - INFO - Compressed log\n" * 3)
        os.utime(compressed, (now - 20 * 86400, now - 20 * 86400))

        yield log_dir


@pytest.fixture
def test_client(test_log_dir):
    """Create test client with logs router."""
    app = FastAPI()
    app.include_router(router)

    # Mock the log directory
    with patch("api.routes.logs.get_log_directory", return_value=test_log_dir):
        yield TestClient(app)


# =============================================================================
# Stats Endpoint Tests
# =============================================================================


def test_get_stats(test_client):
    """Test GET /api/logs/stats."""
    response = test_client.get("/api/logs/stats")

    assert response.status_code == 200
    data = response.json()

    assert "total_files" in data
    assert data["total_files"] >= 3  # We created 3 test files

    assert "total_size_mb" in data
    assert data["total_size_mb"] > 0

    assert "compressed_files" in data
    assert data["compressed_files"] >= 1

    assert "uncompressed_files" in data
    assert data["uncompressed_files"] >= 2


def test_get_stats_oldest_newest(test_client):
    """Test stats include oldest and newest log tracking."""
    response = test_client.get("/api/logs/stats")

    assert response.status_code == 200
    data = response.json()

    assert data["oldest_log"] is not None
    assert "file" in data["oldest_log"]
    assert "age_days" in data["oldest_log"]

    assert data["newest_log"] is not None
    assert "file" in data["newest_log"]


# =============================================================================
# Cleanup Endpoint Tests
# =============================================================================


def test_cleanup_dry_run(test_client, test_log_dir):
    """Test POST /api/logs/cleanup with dry_run."""
    response = test_client.post(
        "/api/logs/cleanup",
        json={
            "max_age_days": 15,
            "compress_age_days": 5,
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["dry_run"] is True
    assert data["scanned"] >= 3
    assert data["errors"] == 0

    # Files should still exist (dry run)
    assert (test_log_dir / "api.log.1").exists()
    assert (test_log_dir / "api.log.2.gz").exists()


def test_cleanup_compress_old_logs(test_client, test_log_dir):
    """Test cleanup compresses old logs."""
    response = test_client.post(
        "/api/logs/cleanup",
        json={
            "max_age_days": 30,
            "compress_age_days": 5,
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["dry_run"] is False
    assert data["compressed"] >= 1  # Should compress api.log.1 (10 days old)


def test_cleanup_delete_very_old_logs(test_client, test_log_dir):
    """Test cleanup deletes very old logs."""
    response = test_client.post(
        "/api/logs/cleanup",
        json={
            "max_age_days": 15,
            "compress_age_days": 5,
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["deleted"] >= 1  # Should delete compressed log (20 days old)
    assert not (test_log_dir / "api.log.2.gz").exists()


def test_cleanup_validation(test_client):
    """Test cleanup request validation."""
    # Invalid max_age_days (too low)
    response = test_client.post(
        "/api/logs/cleanup",
        json={
            "max_age_days": 0,
            "compress_age_days": 5,
        },
    )
    assert response.status_code == 422  # Validation error

    # Invalid max_age_days (too high)
    response = test_client.post(
        "/api/logs/cleanup",
        json={
            "max_age_days": 500,
            "compress_age_days": 5,
        },
    )
    assert response.status_code == 422


# =============================================================================
# List Files Endpoint Tests
# =============================================================================


def test_list_files(test_client):
    """Test GET /api/logs/files."""
    response = test_client.get("/api/logs/files")

    assert response.status_code == 200
    files = response.json()

    assert isinstance(files, list)
    assert len(files) >= 3

    # Check file structure
    file = files[0]
    assert "name" in file
    assert "size_bytes" in file
    assert "size_mb" in file
    assert "age_days" in file
    assert "compressed" in file
    assert "last_modified" in file


def test_list_files_limit(test_client):
    """Test files endpoint respects limit."""
    response = test_client.get("/api/logs/files?limit=2")

    assert response.status_code == 200
    files = response.json()

    assert len(files) <= 2


def test_list_files_compressed_only(test_client):
    """Test filtering compressed files."""
    response = test_client.get("/api/logs/files?compressed_only=true")

    assert response.status_code == 200
    files = response.json()

    # All returned files should be compressed
    for file in files:
        assert file["compressed"] is True
        assert file["name"].endswith(".gz")


def test_list_files_sorted_by_time(test_client):
    """Test files are sorted by modification time (newest first)."""
    response = test_client.get("/api/logs/files")

    assert response.status_code == 200
    files = response.json()

    # Should be sorted newest first
    if len(files) >= 2:
        first_time = files[0]["last_modified"]
        second_time = files[1]["last_modified"]
        assert first_time >= second_time


# =============================================================================
# Config Endpoint Tests
# =============================================================================


def test_get_config(test_client, test_log_dir):
    """Test GET /api/logs/config."""
    with patch.dict(
        os.environ,
        {
            "REQUEST_LOGGING_ENABLED": "true",
            "LOG_REQUEST_BODY": "true",
            "SLOW_REQUEST_THRESHOLD": "2.5",
        },
    ):
        response = test_client.get("/api/logs/config")

    assert response.status_code == 200
    config = response.json()

    assert "log_directory" in config
    assert "request_logging_enabled" in config
    assert config["request_logging_enabled"] == "true"

    assert "log_request_body" in config
    assert config["log_request_body"] == "true"

    assert "slow_request_threshold" in config
    assert config["slow_request_threshold"] == 2.5


# =============================================================================
# Recent Logs Endpoint Tests
# =============================================================================


def test_get_recent_logs(test_client):
    """Test GET /api/logs/recent."""
    response = test_client.get("/api/logs/recent")

    assert response.status_code == 200
    data = response.json()

    assert "total_lines" in data
    assert "returned_lines" in data
    assert "logs" in data

    assert isinstance(data["logs"], list)
    assert len(data["logs"]) <= 100  # Default limit


def test_get_recent_logs_custom_limit(test_client):
    """Test recent logs with custom limit."""
    response = test_client.get("/api/logs/recent?lines=5")

    assert response.status_code == 200
    data = response.json()

    assert data["returned_lines"] <= 5


def test_get_recent_logs_filter_by_level(test_client, test_log_dir):
    """Test filtering logs by level."""
    # Add logs with different levels
    log_file = test_log_dir / "api_requests.log"
    log_file.write_text(
        "2024-01-01 10:00:00 - INFO - Info message\n"
        "2024-01-01 10:00:01 - WARNING - Warning message\n"
        "2024-01-01 10:00:02 - ERROR - Error message\n"
        "2024-01-01 10:00:03 - INFO - Another info\n"
    )

    response = test_client.get("/api/logs/recent?level=ERROR")

    assert response.status_code == 200
    data = response.json()

    # Should only return ERROR logs
    assert data["returned_lines"] >= 1
    for log_line in data["logs"]:
        assert "ERROR" in log_line


def test_get_recent_logs_not_found(test_log_dir):
    """Test recent logs when file doesn't exist."""
    # Remove the api_requests.log file
    log_file = test_log_dir / "api_requests.log"
    if log_file.exists():
        log_file.unlink()

    app = FastAPI()
    app.include_router(router)

    with patch("api.routes.logs.get_log_directory", return_value=test_log_dir):
        client = TestClient(app)
        response = client.get("/api/logs/recent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# =============================================================================
# Error Handling Tests
# =============================================================================


def test_nonexistent_log_directory():
    """Test endpoints when log directory doesn't exist."""
    fake_dir = Path("/tmp/nonexistent_logs_12345")

    app = FastAPI()
    app.include_router(router)

    with patch("api.routes.logs.get_log_directory", return_value=fake_dir):
        client = TestClient(app)

        # Stats should return 404
        response = client.get("/api/logs/stats")
        assert response.status_code == 404

        # Cleanup should return 404
        response = client.post(
            "/api/logs/cleanup",
            json={"max_age_days": 30, "compress_age_days": 7},
        )
        assert response.status_code == 404

        # Files should return 404
        response = client.get("/api/logs/files")
        assert response.status_code == 404


# =============================================================================
# Integration Tests
# =============================================================================


def test_full_workflow(test_client, test_log_dir):
    """Test complete workflow: stats -> cleanup -> verify."""
    # 1. Get initial stats
    response = test_client.get("/api/logs/stats")
    assert response.status_code == 200
    initial_stats = response.json()
    initial_files = initial_stats["total_files"]

    # 2. List files
    response = test_client.get("/api/logs/files")
    assert response.status_code == 200
    files_before = response.json()

    # 3. Cleanup (dry run first)
    response = test_client.post(
        "/api/logs/cleanup",
        json={
            "max_age_days": 15,
            "compress_age_days": 5,
            "dry_run": True,
        },
    )
    assert response.status_code == 200

    # 4. Actual cleanup
    response = test_client.post(
        "/api/logs/cleanup",
        json={
            "max_age_days": 15,
            "compress_age_days": 5,
            "dry_run": False,
        },
    )
    assert response.status_code == 200
    cleanup_result = response.json()

    # 5. Get stats after cleanup
    response = test_client.get("/api/logs/stats")
    assert response.status_code == 200
    final_stats = response.json()

    # Should have fewer files after cleanup (if any were deleted)
    if cleanup_result["deleted"] > 0:
        assert final_stats["total_files"] < initial_files
