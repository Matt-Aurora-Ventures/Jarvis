"""Tests for feature flag management."""

import pytest
from core.feature_flags.flags import FeatureFlags, Flag


def test_flag_creation():
    """Test flag creation."""
    flag = Flag("test_feature", "Test description", enabled=True, rollout_percentage=50)
    
    assert flag.name == "test_feature"
    assert flag.description == "Test description"
    assert flag.enabled is True
    assert flag.rollout_percentage == 50


def test_flag_rollout_clamping():
    """Test rollout percentage clamping."""
    flag = Flag("test", "Desc", rollout_percentage=150)
    assert flag.rollout_percentage == 100
    
    flag = Flag("test", "Desc", rollout_percentage=-50)
    assert flag.rollout_percentage == 0


def test_feature_flags_register():
    """Test registering flags."""
    ff = FeatureFlags()
    flag = ff.register("new_feature", "New feature", enabled=True, rollout_percentage=75)
    
    assert "new_feature" in ff.flags
    assert flag.enabled is True
    assert flag.rollout_percentage == 75


def test_feature_flags_is_enabled_disabled():
    """Test disabled flag returns False."""
    ff = FeatureFlags()
    ff.register("disabled_feature", "Disabled", enabled=False)
    
    assert ff.is_enabled("disabled_feature") is False


def test_feature_flags_is_enabled_full_rollout():
    """Test flag with 100% rollout."""
    ff = FeatureFlags()
    ff.register("full_rollout", "Full", enabled=True, rollout_percentage=100)
    
    assert ff.is_enabled("full_rollout") is True
    assert ff.is_enabled("full_rollout", user_id="user1") is True
    assert ff.is_enabled("full_rollout", user_id="user2") is True


def test_feature_flags_percentage_rollout():
    """Test percentage-based rollout."""
    ff = FeatureFlags()
    ff.register("partial", "Partial", enabled=True, rollout_percentage=50)
    
    enabled_count = sum(1 for i in range(100) if ff.is_enabled("partial", f"user_{i}"))
    assert 20 < enabled_count < 80


def test_feature_flags_enable():
    """Test enabling flag."""
    ff = FeatureFlags()
    ff.register("feature", "Feature", enabled=False)
    
    assert ff.is_enabled("feature") is False
    
    ff.enable("feature", rollout_percentage=100)
    assert ff.is_enabled("feature") is True


def test_feature_flags_disable():
    """Test disabling flag."""
    ff = FeatureFlags()
    ff.register("feature", "Feature", enabled=True, rollout_percentage=100)
    
    assert ff.is_enabled("feature") is True
    
    ff.disable("feature")
    assert ff.is_enabled("feature") is False


def test_feature_flags_set_rollout():
    """Test setting rollout percentage."""
    ff = FeatureFlags()
    ff.register("feature", "Feature", enabled=True, rollout_percentage=10)
    
    ff.set_rollout("feature", 50)
    assert ff.flags["feature"].rollout_percentage == 50


def test_feature_flags_get_status():
    """Test getting flag status."""
    ff = FeatureFlags()
    ff.register("feature", "Test feature", enabled=True, rollout_percentage=75)
    
    status = ff.get_status("feature")
    assert status is not None
    assert status["name"] == "feature"
    assert status["enabled"] is True
    assert status["rollout_percentage"] == 75


def test_feature_flags_list_flags():
    """Test listing all flags."""
    ff = FeatureFlags()
    ff.register("feature1", "Feature 1", rollout_percentage=100)
    ff.register("feature2", "Feature 2", rollout_percentage=100)
    ff.register("feature3", "Feature 3", rollout_percentage=100)
    
    flags = ff.list_flags()
    assert len(flags) == 3
    assert "feature1" in flags
    assert "feature2" in flags
    assert "feature3" in flags


def test_feature_flags_unknown_flag():
    """Test querying unknown flag."""
    ff = FeatureFlags()
    
    assert ff.is_enabled("nonexistent") is False
    assert ff.get_status("nonexistent") is None


__all__ = []
