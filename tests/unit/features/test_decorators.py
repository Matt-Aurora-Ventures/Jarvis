"""
Unit tests for core/features/decorators.py - Feature flag decorators.

TDD: These tests define the expected behavior before implementation.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestFeatureFlagDecorator:
    """Test @feature_flag decorator."""

    def test_feature_flag_calls_function_when_enabled(self):
        """Function should be called when flag is enabled."""
        from core.features.decorators import feature_flag
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": True}}

        flags = FeatureFlags(storage=storage)

        @feature_flag("test_feature", flags=flags)
        def my_function():
            return "executed"

        result = my_function()
        assert result == "executed"

    def test_feature_flag_returns_none_when_disabled(self):
        """Function should return None when flag is disabled."""
        from core.features.decorators import feature_flag
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": False}}

        flags = FeatureFlags(storage=storage)

        @feature_flag("test_feature", flags=flags)
        def my_function():
            return "executed"

        result = my_function()
        assert result is None

    def test_feature_flag_respects_default_false(self):
        """Function should not execute when flag unknown and default=False."""
        from core.features.decorators import feature_flag
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {}

        flags = FeatureFlags(storage=storage)

        @feature_flag("unknown_feature", default=False, flags=flags)
        def my_function():
            return "executed"

        result = my_function()
        assert result is None

    def test_feature_flag_respects_default_true(self):
        """Function should execute when flag unknown and default=True."""
        from core.features.decorators import feature_flag
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {}

        flags = FeatureFlags(storage=storage)

        @feature_flag("unknown_feature", default=True, flags=flags)
        def my_function():
            return "executed"

        result = my_function()
        assert result == "executed"

    def test_feature_flag_preserves_function_signature(self):
        """Decorator should preserve function arguments."""
        from core.features.decorators import feature_flag
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": True}}

        flags = FeatureFlags(storage=storage)

        @feature_flag("test_feature", flags=flags)
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_feature_flag_custom_fallback(self):
        """Should return custom fallback value when disabled."""
        from core.features.decorators import feature_flag
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": False}}

        flags = FeatureFlags(storage=storage)

        @feature_flag("test_feature", fallback="default_value", flags=flags)
        def my_function():
            return "executed"

        result = my_function()
        assert result == "default_value"


class TestFeatureFlagUserDecorator:
    """Test @feature_flag_user decorator for user-based rollout."""

    def test_feature_flag_user_extracts_user_id(self):
        """Should extract user_id from function arguments."""
        from core.features.decorators import feature_flag_user
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": True, "percentage": 100}}

        flags = FeatureFlags(storage=storage)

        @feature_flag_user("test_feature", flags=flags)
        def process_user(user_id, data):
            return f"processed {user_id}"

        result = process_user("user123", {"some": "data"})
        assert result == "processed user123"

    def test_feature_flag_user_respects_percentage(self):
        """Should use percentage-based rollout with user_id."""
        from core.features.decorators import feature_flag_user
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": True, "percentage": 50}}

        flags = FeatureFlags(storage=storage)

        @feature_flag_user("test_feature", flags=flags)
        def process_user(user_id):
            return "processed"

        # Test multiple users - should get ~50% enabled
        enabled_count = 0
        total = 100

        for i in range(total):
            result = process_user(f"user_{i}")
            if result is not None:
                enabled_count += 1

        # Allow variance
        assert 30 <= enabled_count <= 70

    def test_feature_flag_user_consistent_for_same_user(self):
        """Same user should always get same result."""
        from core.features.decorators import feature_flag_user
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": True, "percentage": 50}}

        flags = FeatureFlags(storage=storage)

        @feature_flag_user("test_feature", flags=flags)
        def process_user(user_id):
            return "processed"

        # Call 10 times with same user
        results = [process_user("specific_user") for _ in range(10)]

        # All results should be the same
        assert len(set(results)) == 1

    def test_feature_flag_user_custom_user_id_param(self):
        """Should support custom user_id parameter name."""
        from core.features.decorators import feature_flag_user
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {"test_feature": {"enabled": True, "percentage": 100}}

        flags = FeatureFlags(storage=storage)

        @feature_flag_user("test_feature", user_id_param="account_id", flags=flags)
        def process_account(account_id, data):
            return f"processed {account_id}"

        result = process_account("acc_456", {"data": "value"})
        assert result == "processed acc_456"


class TestABTestDecorator:
    """Test @ab_test decorator for A/B testing."""

    def test_ab_test_assigns_variant(self):
        """Should assign user to a variant."""
        from core.features.decorators import ab_test
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "button_color_test": {"enabled": True, "percentage": 100}
        }

        flags = FeatureFlags(storage=storage)

        @ab_test("button_color_test", variants=["red", "blue", "green"], flags=flags)
        def render_button(user_id, variant=None):
            return f"button_{variant}"

        result = render_button("user123")
        assert result in ["button_red", "button_blue", "button_green"]

    def test_ab_test_consistent_assignment(self):
        """Same user should always get same variant."""
        from core.features.decorators import ab_test
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_experiment": {"enabled": True, "percentage": 100}
        }

        flags = FeatureFlags(storage=storage)

        @ab_test("test_experiment", variants=["control", "treatment"], flags=flags)
        def experiment_function(user_id, variant=None):
            return variant

        # Call multiple times with same user
        results = [experiment_function("user_abc") for _ in range(10)]

        # All should be the same
        assert len(set(results)) == 1

    def test_ab_test_distributes_variants(self):
        """Variants should be distributed across users."""
        from core.features.decorators import ab_test
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_experiment": {"enabled": True, "percentage": 100}
        }

        flags = FeatureFlags(storage=storage)

        @ab_test("test_experiment", variants=["A", "B"], flags=flags)
        def experiment(user_id, variant=None):
            return variant

        variant_counts = {"A": 0, "B": 0}
        total = 1000

        for i in range(total):
            result = experiment(f"user_{i}")
            variant_counts[result] += 1

        # Each variant should get roughly half
        ratio_a = variant_counts["A"] / total
        assert 0.40 <= ratio_a <= 0.60, f"Expected ~50% A but got {ratio_a*100:.1f}%"

    def test_ab_test_disabled_skips_function(self):
        """Should skip function when flag is disabled."""
        from core.features.decorators import ab_test
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_experiment": {"enabled": False}
        }

        flags = FeatureFlags(storage=storage)

        @ab_test("test_experiment", variants=["A", "B"], flags=flags)
        def experiment(user_id, variant=None):
            return variant

        result = experiment("user123")
        assert result is None

    def test_ab_test_fallback_variant(self):
        """Should support fallback variant when disabled."""
        from core.features.decorators import ab_test
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_experiment": {"enabled": False}
        }

        flags = FeatureFlags(storage=storage)

        @ab_test("test_experiment", variants=["A", "B"], fallback_variant="control", flags=flags)
        def experiment(user_id, variant=None):
            return variant

        result = experiment("user123")
        assert result == "control"


class TestDecoratorWithGlobalFlags:
    """Test decorators using global flags instance."""

    def test_feature_flag_uses_global_flags(self):
        """Should use global FeatureFlags when none provided."""
        from core.features.decorators import feature_flag
        from core.features import flags as flags_module

        # Mock the global flags
        with patch.object(flags_module, 'get_feature_flags') as mock_get:
            mock_flags = MagicMock()
            mock_flags.is_enabled.return_value = True
            mock_get.return_value = mock_flags

            @feature_flag("test_feature")
            def my_function():
                return "executed"

            result = my_function()
            assert result == "executed"
            mock_flags.is_enabled.assert_called_once_with("test_feature")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
