"""
Unit tests for the health check classes.

Tests cover:
- ProcessCheck - is process running
- MemoryCheck - memory usage
- ResponseCheck - can bot respond
- APICheck - API connectivity
- DiskCheck - disk space
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_process():
    """Mock psutil process."""
    proc = MagicMock()
    proc.info = {
        "pid": 12345,
        "name": "python",
        "cmdline": ["python", "bot.py"],
        "memory_info": MagicMock(rss=100 * 1024 * 1024),  # 100MB
        "memory_percent": 2.5,
        "cpu_percent": 5.0,
    }
    proc.is_running.return_value = True
    return proc


@pytest.fixture
def mock_disk_usage():
    """Mock disk usage."""
    return MagicMock(
        total=100 * 1024 * 1024 * 1024,  # 100GB
        used=50 * 1024 * 1024 * 1024,    # 50GB
        free=50 * 1024 * 1024 * 1024,    # 50GB
        percent=50.0,
    )


# =============================================================================
# PROCESS CHECK TESTS
# =============================================================================

class TestProcessCheckImport:
    """Tests for ProcessCheck import."""

    def test_import_process_check(self):
        """Test that ProcessCheck can be imported."""
        from core.health.checks import ProcessCheck
        assert ProcessCheck is not None


class TestProcessCheck:
    """Tests for ProcessCheck class."""

    def test_init(self):
        """Test ProcessCheck initialization."""
        from core.health.checks import ProcessCheck

        check = ProcessCheck("test_bot")
        assert check.bot_name == "test_bot"

    @pytest.mark.asyncio
    async def test_check_process_running(self, mock_process):
        """Test checking when process is running."""
        from core.health.checks import ProcessCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.process_iter.return_value = [mock_process]

            check = ProcessCheck("bot")
            result = await check.run()

            assert result["status"] == "healthy"
            assert result["running"] is True
            assert result["pid"] == 12345

    @pytest.mark.asyncio
    async def test_check_process_not_running(self):
        """Test checking when process is not running."""
        from core.health.checks import ProcessCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.process_iter.return_value = []

            check = ProcessCheck("bot")
            result = await check.run()

            assert result["status"] == "unhealthy"
            assert result["running"] is False
            assert result["pid"] is None

    @pytest.mark.asyncio
    async def test_check_process_psutil_not_available(self):
        """Test handling when psutil is not installed."""
        from core.health.checks import ProcessCheck

        with patch("core.health.checks.PSUTIL_AVAILABLE", False):
            check = ProcessCheck("bot")
            result = await check.run()

            assert result["status"] == "unknown"
            assert "psutil" in result["message"].lower()


# =============================================================================
# MEMORY CHECK TESTS
# =============================================================================

class TestMemoryCheckImport:
    """Tests for MemoryCheck import."""

    def test_import_memory_check(self):
        """Test that MemoryCheck can be imported."""
        from core.health.checks import MemoryCheck
        assert MemoryCheck is not None


class TestMemoryCheck:
    """Tests for MemoryCheck class."""

    def test_init(self):
        """Test MemoryCheck initialization."""
        from core.health.checks import MemoryCheck

        check = MemoryCheck(warn_threshold_mb=500, critical_threshold_mb=1000)
        assert check.warn_threshold_mb == 500
        assert check.critical_threshold_mb == 1000

    def test_init_defaults(self):
        """Test MemoryCheck default thresholds."""
        from core.health.checks import MemoryCheck

        check = MemoryCheck()
        assert check.warn_threshold_mb == 1000
        assert check.critical_threshold_mb == 3000

    @pytest.mark.asyncio
    async def test_check_memory_healthy(self):
        """Test checking memory when usage is healthy."""
        from core.health.checks import MemoryCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = MagicMock(
                total=16 * 1024 * 1024 * 1024,
                available=10 * 1024 * 1024 * 1024,
                percent=37.5,
            )

            check = MemoryCheck()
            result = await check.run()

            assert result["status"] == "healthy"
            assert result["percent"] == 37.5

    @pytest.mark.asyncio
    async def test_check_memory_warning(self):
        """Test checking memory when usage is in warning zone."""
        from core.health.checks import MemoryCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = MagicMock(
                total=16 * 1024 * 1024 * 1024,
                available=2 * 1024 * 1024 * 1024,
                percent=87.5,
            )

            check = MemoryCheck()
            result = await check.run()

            assert result["status"] in ("warning", "degraded")

    @pytest.mark.asyncio
    async def test_check_memory_critical(self):
        """Test checking memory when usage is critical."""
        from core.health.checks import MemoryCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = MagicMock(
                total=16 * 1024 * 1024 * 1024,
                available=500 * 1024 * 1024,  # 500MB free
                percent=96.9,
            )

            check = MemoryCheck()
            result = await check.run()

            assert result["status"] == "critical"


# =============================================================================
# RESPONSE CHECK TESTS
# =============================================================================

class TestResponseCheckImport:
    """Tests for ResponseCheck import."""

    def test_import_response_check(self):
        """Test that ResponseCheck can be imported."""
        from core.health.checks import ResponseCheck
        assert ResponseCheck is not None


class TestResponseCheck:
    """Tests for ResponseCheck class."""

    def test_init(self):
        """Test ResponseCheck initialization."""
        from core.health.checks import ResponseCheck

        check = ResponseCheck("http://localhost:8080/health", timeout=5)
        assert check.url == "http://localhost:8080/health"
        assert check.timeout == 5

    @pytest.mark.asyncio
    async def test_check_response_healthy(self):
        """Test checking response when endpoint is healthy."""
        from core.health.checks import ResponseCheck, AIOHTTP_AVAILABLE

        if not AIOHTTP_AVAILABLE:
            pytest.skip("aiohttp not available")

        with patch("core.health.checks.aiohttp") as mock_aiohttp:
            # Create proper async context managers
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})

            # Mock the async context manager for response
            async def response_cm():
                return mock_response

            mock_get_cm = MagicMock()
            mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get.return_value = mock_get_cm

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_aiohttp.ClientSession.return_value = mock_session_cm
            mock_aiohttp.ClientTimeout = MagicMock()

            check = ResponseCheck("http://localhost:8080/health")
            result = await check.run()

            assert result["status"] == "healthy"
            assert result["response_code"] == 200

    @pytest.mark.asyncio
    async def test_check_response_timeout(self):
        """Test checking response when endpoint times out."""
        from core.health.checks import ResponseCheck, AIOHTTP_AVAILABLE

        if not AIOHTTP_AVAILABLE:
            pytest.skip("aiohttp not available")

        with patch("core.health.checks.aiohttp") as mock_aiohttp:
            mock_session = MagicMock()
            mock_session.get.side_effect = asyncio.TimeoutError()

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_aiohttp.ClientSession.return_value = mock_session_cm
            mock_aiohttp.ClientTimeout = MagicMock()

            check = ResponseCheck("http://localhost:8080/health", timeout=1)
            result = await check.run()

            assert result["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_check_response_error(self):
        """Test checking response when endpoint returns error."""
        from core.health.checks import ResponseCheck, AIOHTTP_AVAILABLE

        if not AIOHTTP_AVAILABLE:
            pytest.skip("aiohttp not available")

        with patch("core.health.checks.aiohttp") as mock_aiohttp:
            mock_response = MagicMock()
            mock_response.status = 500

            mock_get_cm = MagicMock()
            mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get.return_value = mock_get_cm

            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)

            mock_aiohttp.ClientSession.return_value = mock_session_cm
            mock_aiohttp.ClientTimeout = MagicMock()

            check = ResponseCheck("http://localhost:8080/health")
            result = await check.run()

            assert result["status"] == "unhealthy"
            assert result["response_code"] == 500


# =============================================================================
# API CHECK TESTS
# =============================================================================

class TestAPICheckImport:
    """Tests for APICheck import."""

    def test_import_api_check(self):
        """Test that APICheck can be imported."""
        from core.health.checks import APICheck
        assert APICheck is not None


class TestAPICheck:
    """Tests for APICheck class."""

    def test_init(self):
        """Test APICheck initialization."""
        from core.health.checks import APICheck

        check = APICheck("telegram", "https://api.telegram.org/bot{token}/getMe")
        assert check.api_name == "telegram"
        assert check.url_template == "https://api.telegram.org/bot{token}/getMe"

    @pytest.mark.asyncio
    async def test_check_api_available(self):
        """Test checking API when it's available."""
        from core.health.checks import APICheck, AIOHTTP_AVAILABLE
        import os

        if not AIOHTTP_AVAILABLE:
            pytest.skip("aiohttp not available")

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            with patch("core.health.checks.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_get_cm = MagicMock()
                mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_get_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.get.return_value = mock_get_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm
                mock_aiohttp.ClientTimeout = MagicMock()

                check = APICheck("telegram", "https://api.telegram.org/bot{token}/getMe")
                result = await check.run()

                assert result["status"] == "available"

    @pytest.mark.asyncio
    async def test_check_api_rate_limited(self):
        """Test checking API when rate limited."""
        from core.health.checks import APICheck, AIOHTTP_AVAILABLE
        import os

        if not AIOHTTP_AVAILABLE:
            pytest.skip("aiohttp not available")

        with patch.dict(os.environ, {"API_KEY": "test_key"}):
            with patch("core.health.checks.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 429

                mock_get_cm = MagicMock()
                mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_get_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.get.return_value = mock_get_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm
                mock_aiohttp.ClientTimeout = MagicMock()

                check = APICheck("test_api", "https://api.example.com/health")
                result = await check.run()

                assert result["status"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_check_api_not_configured(self):
        """Test checking API when not configured."""
        from core.health.checks import APICheck
        import os

        with patch.dict(os.environ, {}, clear=True):
            check = APICheck(
                "telegram",
                "https://api.telegram.org/bot{token}/getMe",
                env_key="TELEGRAM_BOT_TOKEN"
            )
            result = await check.run()

            assert result["status"] == "not_configured"


# =============================================================================
# DISK CHECK TESTS
# =============================================================================

class TestDiskCheckImport:
    """Tests for DiskCheck import."""

    def test_import_disk_check(self):
        """Test that DiskCheck can be imported."""
        from core.health.checks import DiskCheck
        assert DiskCheck is not None


class TestDiskCheck:
    """Tests for DiskCheck class."""

    def test_init(self):
        """Test DiskCheck initialization."""
        from core.health.checks import DiskCheck

        check = DiskCheck(path="/", warn_threshold_percent=80, critical_threshold_percent=90)
        assert check.path == "/"
        assert check.warn_threshold_percent == 80
        assert check.critical_threshold_percent == 90

    def test_init_defaults(self):
        """Test DiskCheck default thresholds."""
        from core.health.checks import DiskCheck

        check = DiskCheck()
        assert check.path == "/"
        assert check.warn_threshold_percent == 80
        assert check.critical_threshold_percent == 90

    @pytest.mark.asyncio
    async def test_check_disk_healthy(self, mock_disk_usage):
        """Test checking disk when usage is healthy."""
        from core.health.checks import DiskCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.disk_usage.return_value = mock_disk_usage

            check = DiskCheck()
            result = await check.run()

            assert result["status"] == "healthy"
            assert result["percent"] == 50.0

    @pytest.mark.asyncio
    async def test_check_disk_warning(self):
        """Test checking disk when usage is in warning zone."""
        from core.health.checks import DiskCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.disk_usage.return_value = MagicMock(
                total=100 * 1024 * 1024 * 1024,
                used=85 * 1024 * 1024 * 1024,
                free=15 * 1024 * 1024 * 1024,
                percent=85.0,
            )

            check = DiskCheck()
            result = await check.run()

            assert result["status"] in ("warning", "degraded")

    @pytest.mark.asyncio
    async def test_check_disk_critical(self):
        """Test checking disk when usage is critical."""
        from core.health.checks import DiskCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            mock_psutil.disk_usage.return_value = MagicMock(
                total=100 * 1024 * 1024 * 1024,
                used=95 * 1024 * 1024 * 1024,
                free=5 * 1024 * 1024 * 1024,
                percent=95.0,
            )

            check = DiskCheck()
            result = await check.run()

            assert result["status"] == "critical"

    @pytest.mark.asyncio
    async def test_check_disk_min_free_bytes(self):
        """Test checking disk based on minimum free bytes."""
        from core.health.checks import DiskCheck

        with patch("core.health.checks.psutil") as mock_psutil:
            # 50GB total, 500MB free - should be critical based on free bytes
            mock_psutil.disk_usage.return_value = MagicMock(
                total=50 * 1024 * 1024 * 1024,
                used=49.5 * 1024 * 1024 * 1024,
                free=500 * 1024 * 1024,  # 500MB
                percent=99.0,
            )

            check = DiskCheck(min_free_gb=1.0)
            result = await check.run()

            assert result["status"] == "critical"
            assert result["free_gb"] < 1.0


# =============================================================================
# CHECK RESULT TESTS
# =============================================================================

class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_check_result_import(self):
        """Test that CheckResult can be imported."""
        from core.health.checks import CheckResult
        assert CheckResult is not None

    def test_check_result_creation(self):
        """Test creating a CheckResult."""
        from core.health.checks import CheckResult

        result = CheckResult(
            check_name="disk",
            status="healthy",
            message="Disk usage is normal",
            details={"percent": 50.0},
            latency_ms=5.5,
        )

        assert result.check_name == "disk"
        assert result.status == "healthy"
        assert result.details["percent"] == 50.0

    def test_check_result_to_dict(self):
        """Test converting CheckResult to dictionary."""
        from core.health.checks import CheckResult

        result = CheckResult(
            check_name="disk",
            status="healthy",
            message="OK",
            details={"percent": 50.0},
            latency_ms=5.5,
        )

        d = result.to_dict()

        assert d["check_name"] == "disk"
        assert d["status"] == "healthy"
        assert d["details"]["percent"] == 50.0
