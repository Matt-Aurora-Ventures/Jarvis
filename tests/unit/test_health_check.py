"""
Unit tests for the health check system.

Tests cover:
- Bot process checking
- Bot API response checking
- Log error detection
- Memory usage monitoring
- API quota verification
- Comprehensive health checks
- JSON output format
- Exit code behavior
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_log_dir():
    """Create temporary log directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir()
        yield log_dir


@pytest.fixture
def sample_log_content():
    """Sample log file content with errors."""
    return """2026-02-01 10:00:00 - INFO - Bot starting
2026-02-01 10:00:01 - INFO - Connected to Telegram
2026-02-01 10:00:05 - ERROR - Failed to connect to API: timeout
2026-02-01 10:00:10 - WARNING - Retrying connection
2026-02-01 10:00:15 - ERROR - API rate limit exceeded
2026-02-01 10:00:20 - INFO - Recovery successful
"""


@pytest.fixture
def mock_process_info():
    """Mock process information."""
    return {
        "pid": 12345,
        "name": "python",
        "cmdline": ["python", "bots/supervisor.py"],
        "memory_percent": 2.5,
        "memory_info": MagicMock(rss=100 * 1024 * 1024),  # 100MB
        "cpu_percent": 5.0,
        "create_time": time.time() - 3600,  # 1 hour ago
    }


@pytest.fixture
def bot_names():
    """List of bot names to check."""
    return [
        "buy_bot",
        "sentiment_reporter",
        "twitter_poster",
        "telegram_bot",
        "autonomous_x",
        "treasury_bot",
    ]


# =============================================================================
# HEALTH CHECK MODULE TESTS
# =============================================================================

class TestHealthCheckImport:
    """Tests for module imports."""

    def test_import_health_check_module(self):
        """Test that health check module can be imported."""
        from scripts.health_check import HealthChecker
        assert HealthChecker is not None

    def test_import_health_check_functions(self):
        """Test that all required functions are exported."""
        from scripts.health_check import (
            check_bot_process,
            check_bot_response,
            check_log_errors,
            check_memory_usage,
            check_api_quotas,
            run_all_checks,
        )
        assert all([
            check_bot_process,
            check_bot_response,
            check_log_errors,
            check_memory_usage,
            check_api_quotas,
            run_all_checks,
        ])


# =============================================================================
# BOT PROCESS CHECKING TESTS
# =============================================================================

class TestCheckBotProcess:
    """Tests for check_bot_process function."""

    def test_process_running(self, mock_process_info):
        """Test detecting a running process."""
        from scripts.health_check import check_bot_process

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.info = mock_process_info
            mock_proc.is_running.return_value = True
            mock_psutil.process_iter.return_value = [mock_proc]

            result = check_bot_process("supervisor")

            assert result["status"] == "running"
            assert result["pid"] == 12345
            assert "uptime" in result

    def test_process_not_running(self):
        """Test detecting when process is not running."""
        from scripts.health_check import check_bot_process

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = []

            result = check_bot_process("nonexistent_bot")

            assert result["status"] == "not_running"
            assert result["pid"] is None

    def test_process_multiple_instances(self, mock_process_info):
        """Test detecting multiple instances of a process."""
        from scripts.health_check import check_bot_process

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_proc1 = MagicMock()
            mock_proc1.info = mock_process_info.copy()
            mock_proc1.info["pid"] = 12345
            mock_proc1.is_running.return_value = True

            mock_proc2 = MagicMock()
            mock_proc2.info = mock_process_info.copy()
            mock_proc2.info["pid"] = 12346
            mock_proc2.is_running.return_value = True

            mock_psutil.process_iter.return_value = [mock_proc1, mock_proc2]

            result = check_bot_process("supervisor")

            assert result["status"] == "running"
            assert result["instance_count"] == 2
            assert "warning" in result

    def test_process_check_returns_json_compatible(self, mock_process_info):
        """Test that result can be serialized to JSON."""
        from scripts.health_check import check_bot_process

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.info = mock_process_info
            mock_proc.is_running.return_value = True
            mock_psutil.process_iter.return_value = [mock_proc]

            result = check_bot_process("supervisor")

            # Should not raise
            json_str = json.dumps(result)
            assert isinstance(json_str, str)


# =============================================================================
# BOT RESPONSE CHECKING TESTS
# =============================================================================

class TestCheckBotResponse:
    """Tests for check_bot_response function."""

    @pytest.mark.asyncio
    async def test_health_endpoint_healthy(self):
        """Test checking a healthy bot endpoint."""
        from scripts.health_check import check_bot_response

        with patch('scripts.health_check.aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "healthy"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock()

            mock_session_instance = AsyncMock()
            mock_session_instance.get.return_value = mock_ctx
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock()

            mock_session.return_value = mock_session_instance

            result = await check_bot_response("health_endpoint", "http://localhost:8080/health")

            assert result["status"] == "healthy"
            assert result["response_time_ms"] is not None

    @pytest.mark.asyncio
    async def test_health_endpoint_unhealthy(self):
        """Test checking an unhealthy bot endpoint."""
        from scripts.health_check import check_bot_response

        with patch('scripts.health_check.aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 503
            mock_response.json = AsyncMock(return_value={"status": "error"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock()

            mock_session_instance = AsyncMock()
            mock_session_instance.get.return_value = mock_ctx
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock()

            mock_session.return_value = mock_session_instance

            result = await check_bot_response("health_endpoint", "http://localhost:8080/health")

            assert result["status"] == "unhealthy"
            assert result["http_status"] == 503

    @pytest.mark.asyncio
    async def test_health_endpoint_timeout(self):
        """Test handling endpoint timeout."""
        from scripts.health_check import check_bot_response

        with patch('scripts.health_check.aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.get.side_effect = asyncio.TimeoutError()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock()

            mock_session.return_value = mock_session_instance

            result = await check_bot_response("health_endpoint", "http://localhost:8080/health")

            assert result["status"] == "timeout"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_health_endpoint_connection_error(self):
        """Test handling connection errors."""
        from scripts.health_check import check_bot_response
        import aiohttp

        with patch('scripts.health_check.aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.get.side_effect = aiohttp.ClientError("Connection refused")
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock()

            mock_session.return_value = mock_session_instance

            result = await check_bot_response("health_endpoint", "http://localhost:8080/health")

            assert result["status"] == "error"
            assert "Connection refused" in result.get("error", "")


# =============================================================================
# LOG ERROR CHECKING TESTS
# =============================================================================

class TestCheckLogErrors:
    """Tests for check_log_errors function."""

    def test_find_recent_errors(self, temp_log_dir, sample_log_content):
        """Test finding errors in recent logs."""
        from scripts.health_check import check_log_errors

        # Write sample log
        log_file = temp_log_dir / "supervisor.log"
        log_file.write_text(sample_log_content)

        result = check_log_errors("supervisor", log_dir=str(temp_log_dir), minutes=60)

        assert result["error_count"] == 2
        assert "API rate limit" in str(result["recent_errors"])

    def test_no_errors_found(self, temp_log_dir):
        """Test when no errors are found."""
        from scripts.health_check import check_log_errors

        log_file = temp_log_dir / "supervisor.log"
        log_file.write_text("2026-02-01 10:00:00 - INFO - All good\n")

        result = check_log_errors("supervisor", log_dir=str(temp_log_dir), minutes=60)

        assert result["error_count"] == 0
        assert result["status"] == "healthy"

    def test_log_file_not_found(self, temp_log_dir):
        """Test handling missing log file."""
        from scripts.health_check import check_log_errors

        result = check_log_errors("nonexistent", log_dir=str(temp_log_dir), minutes=60)

        assert result["status"] == "unknown"
        assert "not found" in result.get("message", "").lower()

    def test_filter_by_time(self, temp_log_dir):
        """Test filtering errors by time window."""
        from scripts.health_check import check_log_errors

        # Create log with old and new errors
        old_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        new_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_content = f"""{old_time} - ERROR - Old error
{new_time} - ERROR - Recent error
"""
        log_file = temp_log_dir / "supervisor.log"
        log_file.write_text(log_content)

        result = check_log_errors("supervisor", log_dir=str(temp_log_dir), minutes=30)

        # Should only find the recent error
        assert result["error_count"] == 1
        assert "Recent error" in str(result["recent_errors"])

    def test_count_warnings_separately(self, temp_log_dir, sample_log_content):
        """Test counting warnings separately from errors."""
        from scripts.health_check import check_log_errors

        log_file = temp_log_dir / "supervisor.log"
        log_file.write_text(sample_log_content)

        result = check_log_errors("supervisor", log_dir=str(temp_log_dir), minutes=60)

        assert result["error_count"] == 2
        assert result["warning_count"] == 1


# =============================================================================
# MEMORY USAGE TESTS
# =============================================================================

class TestCheckMemoryUsage:
    """Tests for check_memory_usage function."""

    def test_memory_usage_normal(self, mock_process_info):
        """Test normal memory usage detection."""
        from scripts.health_check import check_memory_usage

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.info = mock_process_info
            mock_proc.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)
            mock_proc.memory_percent.return_value = 2.5
            mock_proc.is_running.return_value = True
            mock_psutil.process_iter.return_value = [mock_proc]

            result = check_memory_usage("supervisor")

            assert result["status"] == "healthy"
            assert result["memory_mb"] == 100
            assert result["memory_percent"] == 2.5

    def test_memory_usage_high(self, mock_process_info):
        """Test high memory usage warning."""
        from scripts.health_check import check_memory_usage

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.info = mock_process_info
            mock_proc.memory_info.return_value = MagicMock(rss=2000 * 1024 * 1024)  # 2GB
            mock_proc.memory_percent.return_value = 50.0
            mock_proc.is_running.return_value = True
            mock_psutil.process_iter.return_value = [mock_proc]

            result = check_memory_usage("supervisor", warn_threshold_mb=1000)

            assert result["status"] == "warning"
            assert result["memory_mb"] == 2000

    def test_memory_usage_critical(self, mock_process_info):
        """Test critical memory usage alert."""
        from scripts.health_check import check_memory_usage

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.info = mock_process_info
            mock_proc.memory_info.return_value = MagicMock(rss=4000 * 1024 * 1024)  # 4GB
            mock_proc.memory_percent.return_value = 80.0
            mock_proc.is_running.return_value = True
            mock_psutil.process_iter.return_value = [mock_proc]

            result = check_memory_usage("supervisor", critical_threshold_mb=3000)

            assert result["status"] == "critical"

    def test_memory_process_not_found(self):
        """Test memory check when process not found."""
        from scripts.health_check import check_memory_usage

        with patch('scripts.health_check.psutil') as mock_psutil:
            mock_psutil.process_iter.return_value = []

            result = check_memory_usage("nonexistent")

            assert result["status"] == "not_running"


# =============================================================================
# API QUOTA TESTS
# =============================================================================

class TestCheckApiQuotas:
    """Tests for check_api_quotas function."""

    @pytest.mark.asyncio
    async def test_telegram_api_quota(self):
        """Test Telegram API quota check."""
        from scripts.health_check import check_api_quotas

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            with patch('scripts.health_check.aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"ok": True})
                mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                mock_response.__aexit__ = AsyncMock()

                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
                mock_ctx.__aexit__ = AsyncMock()

                mock_session_instance = AsyncMock()
                mock_session_instance.get.return_value = mock_ctx
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock()

                mock_session.return_value = mock_session_instance

                result = await check_api_quotas()

                assert "telegram" in result
                assert result["telegram"]["status"] == "available"

    @pytest.mark.asyncio
    async def test_api_key_missing(self):
        """Test handling missing API keys."""
        from scripts.health_check import check_api_quotas

        with patch.dict(os.environ, {}, clear=True):
            result = await check_api_quotas()

            # Should report keys as not configured
            assert any(api["status"] == "not_configured" for api in result.values())

    @pytest.mark.asyncio
    async def test_api_rate_limited(self):
        """Test detecting rate limited APIs."""
        from scripts.health_check import check_api_quotas

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            with patch('scripts.health_check.aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 429
                mock_response.json = AsyncMock(return_value={"error": "rate limited"})
                mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                mock_response.__aexit__ = AsyncMock()

                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
                mock_ctx.__aexit__ = AsyncMock()

                mock_session_instance = AsyncMock()
                mock_session_instance.get.return_value = mock_ctx
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock()

                mock_session.return_value = mock_session_instance

                result = await check_api_quotas()

                assert result["telegram"]["status"] == "rate_limited"


# =============================================================================
# COMPREHENSIVE HEALTH CHECK TESTS
# =============================================================================

class TestRunAllChecks:
    """Tests for run_all_checks function."""

    @pytest.mark.asyncio
    async def test_run_all_checks_all_healthy(self, temp_log_dir):
        """Test running all checks when everything is healthy."""
        from scripts.health_check import run_all_checks

        with patch('scripts.health_check.check_bot_process') as mock_process:
            with patch('scripts.health_check.check_bot_response', new_callable=AsyncMock) as mock_response:
                with patch('scripts.health_check.check_log_errors') as mock_logs:
                    with patch('scripts.health_check.check_memory_usage') as mock_memory:
                        with patch('scripts.health_check.check_api_quotas', new_callable=AsyncMock) as mock_quotas:
                            mock_process.return_value = {"status": "running", "pid": 123}
                            mock_response.return_value = {"status": "healthy"}
                            mock_logs.return_value = {"status": "healthy", "error_count": 0}
                            mock_memory.return_value = {"status": "healthy", "memory_mb": 100}
                            mock_quotas.return_value = {"telegram": {"status": "available"}}

                            result = await run_all_checks(log_dir=str(temp_log_dir))

                            assert result["overall_status"] == "healthy"
                            assert "processes" in result
                            assert "api_quotas" in result

    @pytest.mark.asyncio
    async def test_run_all_checks_degraded(self, temp_log_dir):
        """Test running all checks when some issues exist."""
        from scripts.health_check import run_all_checks

        with patch('scripts.health_check.check_bot_process') as mock_process:
            with patch('scripts.health_check.check_bot_response', new_callable=AsyncMock) as mock_response:
                with patch('scripts.health_check.check_log_errors') as mock_logs:
                    with patch('scripts.health_check.check_memory_usage') as mock_memory:
                        with patch('scripts.health_check.check_api_quotas', new_callable=AsyncMock) as mock_quotas:
                            mock_process.return_value = {"status": "running", "pid": 123}
                            mock_response.return_value = {"status": "unhealthy"}
                            mock_logs.return_value = {"status": "warning", "error_count": 5}
                            mock_memory.return_value = {"status": "healthy", "memory_mb": 100}
                            mock_quotas.return_value = {"telegram": {"status": "available"}}

                            result = await run_all_checks(log_dir=str(temp_log_dir))

                            assert result["overall_status"] in ["degraded", "warning"]

    @pytest.mark.asyncio
    async def test_run_all_checks_critical(self, temp_log_dir):
        """Test running all checks with critical issues."""
        from scripts.health_check import run_all_checks

        with patch('scripts.health_check.check_bot_process') as mock_process:
            with patch('scripts.health_check.check_bot_response', new_callable=AsyncMock) as mock_response:
                with patch('scripts.health_check.check_log_errors') as mock_logs:
                    with patch('scripts.health_check.check_memory_usage') as mock_memory:
                        with patch('scripts.health_check.check_api_quotas', new_callable=AsyncMock) as mock_quotas:
                            mock_process.return_value = {"status": "not_running", "pid": None}
                            mock_response.return_value = {"status": "error"}
                            mock_logs.return_value = {"status": "critical", "error_count": 100}
                            mock_memory.return_value = {"status": "critical", "memory_mb": 5000}
                            mock_quotas.return_value = {"telegram": {"status": "rate_limited"}}

                            result = await run_all_checks(log_dir=str(temp_log_dir))

                            assert result["overall_status"] in ["critical", "unhealthy"]

    @pytest.mark.asyncio
    async def test_run_all_checks_json_output(self, temp_log_dir):
        """Test that run_all_checks returns JSON-serializable output."""
        from scripts.health_check import run_all_checks

        with patch('scripts.health_check.check_bot_process') as mock_process:
            with patch('scripts.health_check.check_bot_response', new_callable=AsyncMock) as mock_response:
                with patch('scripts.health_check.check_log_errors') as mock_logs:
                    with patch('scripts.health_check.check_memory_usage') as mock_memory:
                        with patch('scripts.health_check.check_api_quotas', new_callable=AsyncMock) as mock_quotas:
                            mock_process.return_value = {"status": "running", "pid": 123}
                            mock_response.return_value = {"status": "healthy"}
                            mock_logs.return_value = {"status": "healthy", "error_count": 0}
                            mock_memory.return_value = {"status": "healthy", "memory_mb": 100}
                            mock_quotas.return_value = {"telegram": {"status": "available"}}

                            result = await run_all_checks(log_dir=str(temp_log_dir))

                            # Should not raise
                            json_str = json.dumps(result, indent=2)
                            assert isinstance(json_str, str)

    @pytest.mark.asyncio
    async def test_run_all_checks_includes_timestamp(self, temp_log_dir):
        """Test that result includes timestamp."""
        from scripts.health_check import run_all_checks

        with patch('scripts.health_check.check_bot_process') as mock_process:
            with patch('scripts.health_check.check_bot_response', new_callable=AsyncMock) as mock_response:
                with patch('scripts.health_check.check_log_errors') as mock_logs:
                    with patch('scripts.health_check.check_memory_usage') as mock_memory:
                        with patch('scripts.health_check.check_api_quotas', new_callable=AsyncMock) as mock_quotas:
                            mock_process.return_value = {"status": "running", "pid": 123}
                            mock_response.return_value = {"status": "healthy"}
                            mock_logs.return_value = {"status": "healthy", "error_count": 0}
                            mock_memory.return_value = {"status": "healthy", "memory_mb": 100}
                            mock_quotas.return_value = {"telegram": {"status": "available"}}

                            result = await run_all_checks(log_dir=str(temp_log_dir))

                            assert "timestamp" in result
                            assert "duration_ms" in result


# =============================================================================
# EXIT CODE TESTS
# =============================================================================

class TestExitCodes:
    """Tests for exit code behavior."""

    def test_healthy_exit_code(self):
        """Test exit code 0 for healthy status."""
        from scripts.health_check import get_exit_code

        result = {"overall_status": "healthy"}
        assert get_exit_code(result) == 0

    def test_warning_exit_code(self):
        """Test exit code 1 for warning status."""
        from scripts.health_check import get_exit_code

        result = {"overall_status": "warning"}
        assert get_exit_code(result) == 1

    def test_degraded_exit_code(self):
        """Test exit code 1 for degraded status."""
        from scripts.health_check import get_exit_code

        result = {"overall_status": "degraded"}
        assert get_exit_code(result) == 1

    def test_critical_exit_code(self):
        """Test exit code 2 for critical status."""
        from scripts.health_check import get_exit_code

        result = {"overall_status": "critical"}
        assert get_exit_code(result) == 2

    def test_unhealthy_exit_code(self):
        """Test exit code 2 for unhealthy status."""
        from scripts.health_check import get_exit_code

        result = {"overall_status": "unhealthy"}
        assert get_exit_code(result) == 2


# =============================================================================
# VPS COMPATIBILITY TESTS
# =============================================================================

class TestVPSCompatibility:
    """Tests for VPS environment compatibility."""

    def test_detect_vps_environment(self):
        """Test detecting VPS environment."""
        from scripts.health_check import detect_environment

        with patch('scripts.health_check.Path.exists') as mock_exists:
            mock_exists.return_value = True

            env = detect_environment()

            assert env in ["vps", "local", "unknown"]

    def test_use_vps_paths(self):
        """Test using VPS-specific paths."""
        from scripts.health_check import get_default_paths

        with patch.dict(os.environ, {"VPS_MODE": "true"}):
            paths = get_default_paths()

            assert "/root/clawdbots" in paths.get("bot_dir", "") or paths.get("bot_dir", "") != ""

    def test_use_local_paths(self):
        """Test using local development paths."""
        from scripts.health_check import get_default_paths

        with patch.dict(os.environ, {"VPS_MODE": "false"}, clear=False):
            paths = get_default_paths()

            assert paths is not None


# =============================================================================
# HEALTH CHECKER CLASS TESTS
# =============================================================================

class TestHealthChecker:
    """Tests for the HealthChecker class."""

    def test_init_with_defaults(self):
        """Test HealthChecker initialization with defaults."""
        from scripts.health_check import HealthChecker

        checker = HealthChecker()

        assert checker is not None
        assert checker.bot_names is not None

    def test_init_with_custom_bots(self):
        """Test HealthChecker with custom bot list."""
        from scripts.health_check import HealthChecker

        checker = HealthChecker(bot_names=["buy_bot", "telegram_bot"])

        assert len(checker.bot_names) == 2

    @pytest.mark.asyncio
    async def test_run_checks(self, temp_log_dir):
        """Test running checks through the class."""
        from scripts.health_check import HealthChecker

        checker = HealthChecker(log_dir=str(temp_log_dir))

        with patch.object(checker, '_check_processes') as mock_proc:
            with patch.object(checker, '_check_endpoints', new_callable=AsyncMock) as mock_end:
                with patch.object(checker, '_check_logs') as mock_logs:
                    with patch.object(checker, '_check_memory') as mock_mem:
                        with patch.object(checker, '_check_apis', new_callable=AsyncMock) as mock_apis:
                            mock_proc.return_value = {}
                            mock_end.return_value = {}
                            mock_logs.return_value = {}
                            mock_mem.return_value = {}
                            mock_apis.return_value = {}

                            result = await checker.run()

                            assert result is not None
                            assert "overall_status" in result
