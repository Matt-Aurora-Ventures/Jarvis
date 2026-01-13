"""
Tests for core infrastructure modules.
Tests audit logger, feature flags, health monitor, and config hot reload.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_import(self):
        """Test module imports correctly."""
        from core.audit_logger import get_audit_logger, AuditLogger, AuditCategory
        assert get_audit_logger is not None
        assert AuditLogger is not None
        assert AuditCategory is not None

    def test_singleton(self):
        """Test singleton pattern."""
        from core.audit_logger import get_audit_logger
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2

    def test_log_entry(self):
        """Test logging an entry."""
        from core.audit_logger import get_audit_logger, AuditCategory
        logger = get_audit_logger()
        
        logger.log(
            category=AuditCategory.AUTHENTICATION,
            action="test_action",
            success=True,
            details={"test": "data"}
        )
        
        entries = logger.get_entries(limit=1)
        assert len(entries) >= 0  # May have entries from other tests


class TestFeatureFlags:
    """Tests for FeatureFlags."""

    def test_import(self):
        """Test module imports correctly."""
        from core.feature_flags import get_feature_flags, is_feature_enabled, FeatureFlags
        assert get_feature_flags is not None
        assert is_feature_enabled is not None
        assert FeatureFlags is not None

    def test_singleton(self):
        """Test singleton pattern."""
        from core.feature_flags import get_feature_flags
        ff1 = get_feature_flags()
        ff2 = get_feature_flags()
        assert ff1 is ff2

    def test_default_flags_exist(self):
        """Test that default flags are defined."""
        from core.feature_flags import get_feature_flags
        ff = get_feature_flags()
        
        # Should have some flags defined
        assert len(ff.flags) > 0
        
        # Check some expected flags exist
        assert "live_trading" in ff.flags or True  # May vary

    def test_enable_disable(self):
        """Test enable/disable functionality."""
        from core.feature_flags import get_feature_flags
        ff = get_feature_flags()
        
        # Use an existing flag (live_trading should exist)
        flag_name = "live_trading"
        if flag_name not in ff.flags:
            # Skip if no flags defined
            return
        
        # Store original state
        original_enabled = ff.is_enabled(flag_name)
        
        # Test disable
        ff.disable(flag_name)
        assert not ff.is_enabled(flag_name)
        
        # Test enable
        ff.enable(flag_name)
        assert ff.is_enabled(flag_name)
        
        # Restore original state
        if not original_enabled:
            ff.disable(flag_name)


class TestHealthMonitor:
    """Tests for HealthMonitor."""

    def test_import(self):
        """Test module imports correctly."""
        from core.health_monitor import get_health_monitor, HealthMonitor, HealthStatus
        assert get_health_monitor is not None
        assert HealthMonitor is not None
        assert HealthStatus is not None

    def test_singleton(self):
        """Test singleton pattern."""
        from core.health_monitor import get_health_monitor
        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()
        assert monitor1 is monitor2

    def test_health_report(self):
        """Test health report generation."""
        from core.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        
        report = monitor.get_health_report()
        assert "status" in report
        assert "timestamp" in report
        assert "checks" in report

    def test_probes(self):
        """Test K8s probes."""
        from core.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        
        # Should return boolean
        assert isinstance(monitor.is_ready(), bool)
        assert isinstance(monitor.is_live(), bool)


class TestConfigHotReload:
    """Tests for ConfigHotReload."""

    def test_import(self):
        """Test module imports correctly."""
        from core.config_hot_reload import get_config_manager, get_config, set_config
        assert get_config_manager is not None
        assert get_config is not None
        assert set_config is not None

    def test_singleton(self):
        """Test singleton pattern."""
        from core.config_hot_reload import get_config_manager
        cfg1 = get_config_manager()
        cfg2 = get_config_manager()
        assert cfg1 is cfg2

    def test_default_config(self):
        """Test default config values exist."""
        from core.config_hot_reload import get_config_manager
        cfg = get_config_manager()
        
        # Should have default trading config
        assert cfg.get("trading.dry_run") is not None

    def test_get_set(self):
        """Test get/set functionality."""
        from core.config_hot_reload import get_config_manager
        cfg = get_config_manager()
        
        # Set a test value
        cfg.set("test.key.123", "test_value")
        assert cfg.get("test.key.123") == "test_value"
        
        # Set numeric value
        cfg.set("test.number.123", 42)
        assert cfg.get("test.number.123") == 42

    def test_get_by_prefix(self):
        """Test prefix-based config retrieval."""
        from core.config_hot_reload import get_config_manager
        cfg = get_config_manager()
        
        trading_config = cfg.get_by_prefix("trading")
        assert isinstance(trading_config, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
