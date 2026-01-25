"""
Comprehensive unit tests for core/config.py - Configuration Module.

Tests cover:
1. JSON Loading (_load_json) - File operations, error handling
2. Deep Merge (_deep_merge) - Nested dictionary merging
3. Config Loading (load_config) - Base + local config composition
4. Config Saving (save_local_config) - Persistence to file
5. Config Update (update_local_config) - Merge and persist updates
6. Path Resolution (resolve_path) - Relative/absolute path handling

Coverage target: 60%+ with 40-60 tests
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory structure."""
    config_dir = tmp_path / "lifeos" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def sample_base_config():
    """Sample base configuration for testing."""
    return {
        "version": "1.0",
        "trading": {
            "enabled": True,
            "max_positions": 10,
            "risk_per_trade": 0.02,
        },
        "memory": {
            "target_cap": 200,
            "min_cap": 50,
            "max_cap": 300,
        },
        "voice": {
            "enabled": True,
            "mode": "wake-word",
        },
    }


@pytest.fixture
def sample_local_config():
    """Sample local config overrides for testing."""
    return {
        "trading": {
            "max_positions": 50,  # Override
            "debug": True,  # New field
        },
        "custom_setting": "local_value",  # New top-level
    }


@pytest.fixture
def temp_base_config_file(temp_config_dir, sample_base_config):
    """Create a temporary base config file."""
    base_config = temp_config_dir / "lifeos.config.json"
    with open(base_config, 'w', encoding='utf-8') as f:
        json.dump(sample_base_config, f, indent=2)
    return base_config


@pytest.fixture
def temp_local_config_file(temp_config_dir, sample_local_config):
    """Create a temporary local config file."""
    local_config = temp_config_dir / "lifeos.config.local.json"
    with open(local_config, 'w', encoding='utf-8') as f:
        json.dump(sample_local_config, f, indent=2)
    return local_config


# =============================================================================
# TEST CLASS: _load_json Function
# =============================================================================


class TestLoadJson:
    """Tests for the _load_json function."""

    def test_load_json_valid_file(self, temp_config_dir):
        """Should load valid JSON from file."""
        from core.config import _load_json

        test_file = temp_config_dir / "test.json"
        test_data = {"key": "value", "number": 42}
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        result = _load_json(test_file)

        assert result == test_data

    def test_load_json_missing_file(self, temp_config_dir):
        """Should return empty dict for missing file."""
        from core.config import _load_json

        missing_file = temp_config_dir / "nonexistent.json"

        result = _load_json(missing_file)

        assert result == {}

    def test_load_json_invalid_json(self, temp_config_dir):
        """Should return empty dict for invalid JSON."""
        from core.config import _load_json

        invalid_file = temp_config_dir / "invalid.json"
        with open(invalid_file, 'w', encoding='utf-8') as f:
            f.write("not valid json {")

        result = _load_json(invalid_file)

        assert result == {}

    def test_load_json_empty_file(self, temp_config_dir):
        """Should return empty dict for empty file."""
        from core.config import _load_json

        empty_file = temp_config_dir / "empty.json"
        empty_file.touch()

        result = _load_json(empty_file)

        assert result == {}

    def test_load_json_non_dict_returns_empty(self, temp_config_dir):
        """Should return empty dict when JSON is not a dict."""
        from core.config import _load_json

        list_file = temp_config_dir / "list.json"
        with open(list_file, 'w', encoding='utf-8') as f:
            json.dump([1, 2, 3], f)

        result = _load_json(list_file)

        assert result == {}

    def test_load_json_string_returns_empty(self, temp_config_dir):
        """Should return empty dict when JSON is a string."""
        from core.config import _load_json

        string_file = temp_config_dir / "string.json"
        with open(string_file, 'w', encoding='utf-8') as f:
            json.dump("just a string", f)

        result = _load_json(string_file)

        assert result == {}

    def test_load_json_number_returns_empty(self, temp_config_dir):
        """Should return empty dict when JSON is a number."""
        from core.config import _load_json

        number_file = temp_config_dir / "number.json"
        with open(number_file, 'w', encoding='utf-8') as f:
            json.dump(42, f)

        result = _load_json(number_file)

        assert result == {}

    def test_load_json_null_returns_empty(self, temp_config_dir):
        """Should return empty dict when JSON is null."""
        from core.config import _load_json

        null_file = temp_config_dir / "null.json"
        with open(null_file, 'w', encoding='utf-8') as f:
            json.dump(None, f)

        result = _load_json(null_file)

        assert result == {}

    def test_load_json_nested_dict(self, temp_config_dir):
        """Should load deeply nested dictionaries."""
        from core.config import _load_json

        nested_file = temp_config_dir / "nested.json"
        nested_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        with open(nested_file, 'w', encoding='utf-8') as f:
            json.dump(nested_data, f)

        result = _load_json(nested_file)

        assert result == nested_data
        assert result["level1"]["level2"]["level3"]["value"] == "deep"

    def test_load_json_unicode_content(self, temp_config_dir):
        """Should handle unicode content correctly."""
        from core.config import _load_json

        unicode_file = temp_config_dir / "unicode.json"
        unicode_data = {"message": "Hello", "emoji": "Test", "chinese": "Test"}
        with open(unicode_file, 'w', encoding='utf-8') as f:
            json.dump(unicode_data, f, ensure_ascii=False)

        result = _load_json(unicode_file)

        assert result == unicode_data

    def test_load_json_large_file(self, temp_config_dir):
        """Should handle large JSON files."""
        from core.config import _load_json

        large_file = temp_config_dir / "large.json"
        large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}
        with open(large_file, 'w', encoding='utf-8') as f:
            json.dump(large_data, f)

        result = _load_json(large_file)

        assert len(result) == 1000
        assert result["key_500"] == "value_500"


# =============================================================================
# TEST CLASS: _deep_merge Function
# =============================================================================


class TestDeepMerge:
    """Tests for the _deep_merge function."""

    def test_deep_merge_simple_override(self):
        """Should override simple values."""
        from core.config import _deep_merge

        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = _deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested_dicts(self):
        """Should merge nested dictionaries recursively."""
        from core.config import _deep_merge

        base = {
            "level1": {
                "x": 1,
                "y": 2,
            }
        }
        override = {
            "level1": {
                "y": 3,
                "z": 4,
            }
        }

        result = _deep_merge(base, override)

        assert result["level1"]["x"] == 1  # Preserved
        assert result["level1"]["y"] == 3  # Overridden
        assert result["level1"]["z"] == 4  # Added

    def test_deep_merge_deeply_nested(self):
        """Should merge deeply nested dictionaries."""
        from core.config import _deep_merge

        base = {
            "l1": {
                "l2": {
                    "l3": {
                        "a": 1,
                        "b": 2,
                    }
                }
            }
        }
        override = {
            "l1": {
                "l2": {
                    "l3": {
                        "b": 3,
                        "c": 4,
                    }
                }
            }
        }

        result = _deep_merge(base, override)

        assert result["l1"]["l2"]["l3"]["a"] == 1
        assert result["l1"]["l2"]["l3"]["b"] == 3
        assert result["l1"]["l2"]["l3"]["c"] == 4

    def test_deep_merge_preserves_base(self):
        """Should not modify original base dict."""
        from core.config import _deep_merge

        base = {"a": 1, "nested": {"x": 1}}
        override = {"a": 2, "nested": {"y": 2}}
        original_base = {"a": 1, "nested": {"x": 1}}

        _deep_merge(base, override)

        assert base == original_base

    def test_deep_merge_empty_base(self):
        """Should work with empty base."""
        from core.config import _deep_merge

        base = {}
        override = {"a": 1, "b": 2}

        result = _deep_merge(base, override)

        assert result == {"a": 1, "b": 2}

    def test_deep_merge_empty_override(self):
        """Should work with empty override."""
        from core.config import _deep_merge

        base = {"a": 1, "b": 2}
        override = {}

        result = _deep_merge(base, override)

        assert result == {"a": 1, "b": 2}

    def test_deep_merge_both_empty(self):
        """Should return empty dict when both are empty."""
        from core.config import _deep_merge

        result = _deep_merge({}, {})

        assert result == {}

    def test_deep_merge_override_with_non_dict(self):
        """Should replace dict with non-dict value."""
        from core.config import _deep_merge

        base = {"nested": {"x": 1, "y": 2}}
        override = {"nested": "replaced"}

        result = _deep_merge(base, override)

        assert result["nested"] == "replaced"

    def test_deep_merge_base_non_dict_with_dict(self):
        """Should replace non-dict with dict value."""
        from core.config import _deep_merge

        base = {"nested": "string_value"}
        override = {"nested": {"x": 1}}

        result = _deep_merge(base, override)

        assert result["nested"] == {"x": 1}

    def test_deep_merge_mixed_types(self):
        """Should handle mixed value types correctly."""
        from core.config import _deep_merge

        base = {
            "string": "hello",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"a": 1},
        }
        override = {
            "string": "world",
            "list": [4, 5],
            "nested": {"b": 2},
            "new": True,
        }

        result = _deep_merge(base, override)

        assert result["string"] == "world"
        assert result["number"] == 42
        assert result["list"] == [4, 5]  # Lists are replaced, not merged
        assert result["nested"] == {"a": 1, "b": 2}
        assert result["new"] is True

    def test_deep_merge_with_none_values(self):
        """Should handle None values correctly."""
        from core.config import _deep_merge

        base = {"a": 1, "b": None}
        override = {"a": None, "c": 3}

        result = _deep_merge(base, override)

        assert result["a"] is None
        assert result["b"] is None
        assert result["c"] == 3

    def test_deep_merge_multiple_nested_levels(self):
        """Should merge multiple separate nested structures."""
        from core.config import _deep_merge

        base = {
            "section1": {"a": 1},
            "section2": {"b": 2},
        }
        override = {
            "section1": {"c": 3},
            "section3": {"d": 4},
        }

        result = _deep_merge(base, override)

        assert result["section1"] == {"a": 1, "c": 3}
        assert result["section2"] == {"b": 2}
        assert result["section3"] == {"d": 4}


# =============================================================================
# TEST CLASS: load_config Function
# =============================================================================


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_config_returns_dict(self):
        """Should return a dictionary."""
        from core.config import load_config

        result = load_config()

        assert isinstance(result, dict)

    def test_load_config_with_base_only(self, tmp_path, sample_base_config):
        """Should load base config when no local exists."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        base_file = config_dir / "lifeos.config.json"
        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', config_dir / "nonexistent.json"):
                result = config.load_config()

        assert result == sample_base_config

    def test_load_config_merges_local(self, tmp_path, sample_base_config, sample_local_config):
        """Should merge local config over base."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)
        with open(local_file, 'w') as f:
            json.dump(sample_local_config, f)

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.load_config()

        # Should have base values
        assert result["version"] == "1.0"
        assert result["memory"]["target_cap"] == 200

        # Should have overridden values
        assert result["trading"]["max_positions"] == 50

        # Should have merged nested values
        assert result["trading"]["enabled"] is True  # From base
        assert result["trading"]["debug"] is True  # From local

        # Should have new top-level values
        assert result["custom_setting"] == "local_value"

    def test_load_config_handles_missing_both(self, tmp_path):
        """Should return empty dict when both configs missing."""
        from core import config

        missing_base = tmp_path / "nonexistent_base.json"
        missing_local = tmp_path / "nonexistent_local.json"

        with patch.object(config, 'BASE_CONFIG', missing_base):
            with patch.object(config, 'LOCAL_CONFIG', missing_local):
                result = config.load_config()

        assert result == {}

    def test_load_config_consistent_calls(self):
        """Should return equivalent config on multiple calls."""
        from core.config import load_config

        result1 = load_config()
        result2 = load_config()

        assert result1 == result2

    def test_load_config_handles_invalid_base(self, tmp_path, sample_local_config):
        """Should still load local when base is invalid."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            f.write("invalid json")
        with open(local_file, 'w') as f:
            json.dump(sample_local_config, f)

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.load_config()

        # Should use local as the result (merged with empty base)
        assert result == sample_local_config

    def test_load_config_handles_invalid_local(self, tmp_path, sample_base_config):
        """Should still load base when local is invalid."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)
        with open(local_file, 'w') as f:
            f.write("invalid json")

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.load_config()

        # Should use base as the result
        assert result == sample_base_config


# =============================================================================
# TEST CLASS: save_local_config Function
# =============================================================================


class TestSaveLocalConfig:
    """Tests for the save_local_config function."""

    def test_save_local_config_creates_file(self, tmp_path):
        """Should create local config file."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        local_file = config_dir / "lifeos.config.local.json"
        test_data = {"key": "value"}

        with patch.object(config, 'LOCAL_CONFIG', local_file):
            config.save_local_config(test_data)

        assert local_file.exists()
        with open(local_file) as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_save_local_config_creates_parent_dirs(self, tmp_path):
        """Should create parent directories if they don't exist."""
        from core import config

        nested_dir = tmp_path / "deep" / "nested" / "config"
        local_file = nested_dir / "lifeos.config.local.json"
        test_data = {"nested": True}

        with patch.object(config, 'LOCAL_CONFIG', local_file):
            config.save_local_config(test_data)

        assert local_file.exists()
        assert nested_dir.exists()

    def test_save_local_config_overwrites_existing(self, tmp_path):
        """Should overwrite existing local config."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        local_file = config_dir / "lifeos.config.local.json"

        # Create initial file
        with open(local_file, 'w') as f:
            json.dump({"old": "data"}, f)

        new_data = {"new": "data"}
        with patch.object(config, 'LOCAL_CONFIG', local_file):
            config.save_local_config(new_data)

        with open(local_file) as f:
            saved_data = json.load(f)
        assert saved_data == new_data
        assert "old" not in saved_data

    def test_save_local_config_pretty_prints(self, tmp_path):
        """Should save with indentation (pretty print)."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        local_file = config_dir / "lifeos.config.local.json"
        test_data = {"key": "value", "nested": {"a": 1}}

        with patch.object(config, 'LOCAL_CONFIG', local_file):
            config.save_local_config(test_data)

        with open(local_file) as f:
            content = f.read()

        # Should be indented (multi-line)
        assert "\n" in content
        assert "  " in content  # Indentation

    def test_save_local_config_sorts_keys(self, tmp_path):
        """Should sort keys in output."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        local_file = config_dir / "lifeos.config.local.json"
        test_data = {"zebra": 1, "alpha": 2, "middle": 3}

        with patch.object(config, 'LOCAL_CONFIG', local_file):
            config.save_local_config(test_data)

        with open(local_file) as f:
            content = f.read()

        # Keys should appear in sorted order
        alpha_pos = content.index("alpha")
        middle_pos = content.index("middle")
        zebra_pos = content.index("zebra")
        assert alpha_pos < middle_pos < zebra_pos

    def test_save_local_config_empty_dict(self, tmp_path):
        """Should save empty dict correctly."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        local_file = config_dir / "lifeos.config.local.json"

        with patch.object(config, 'LOCAL_CONFIG', local_file):
            config.save_local_config({})

        with open(local_file) as f:
            saved_data = json.load(f)
        assert saved_data == {}

    def test_save_local_config_complex_nested(self, tmp_path):
        """Should save complex nested structures."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        local_file = config_dir / "lifeos.config.local.json"
        complex_data = {
            "trading": {
                "strategies": {
                    "sma": {"fast": 5, "slow": 20},
                    "rsi": {"period": 14, "thresholds": [30, 70]},
                },
                "enabled": True,
            },
            "providers": ["groq", "openai", "ollama"],
        }

        with patch.object(config, 'LOCAL_CONFIG', local_file):
            config.save_local_config(complex_data)

        with open(local_file) as f:
            saved_data = json.load(f)
        assert saved_data == complex_data


# =============================================================================
# TEST CLASS: update_local_config Function
# =============================================================================


class TestUpdateLocalConfig:
    """Tests for the update_local_config function."""

    def test_update_local_config_adds_new_keys(self, tmp_path, sample_base_config):
        """Should add new keys to local config."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)
        # No local file initially

        updates = {"new_setting": "new_value"}

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.update_local_config(updates)

        # Should return merged config
        assert result["new_setting"] == "new_value"
        assert result["version"] == "1.0"  # From base

        # Should have saved to local file
        with open(local_file) as f:
            saved_local = json.load(f)
        assert saved_local == updates

    def test_update_local_config_merges_with_existing(self, tmp_path, sample_base_config):
        """Should merge updates with existing local config."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)

        existing_local = {"existing": "value", "trading": {"debug": True}}
        with open(local_file, 'w') as f:
            json.dump(existing_local, f)

        updates = {"new": "update", "trading": {"new_option": True}}

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.update_local_config(updates)

        # Should have merged all three: base, existing local, updates
        assert result["existing"] == "value"
        assert result["new"] == "update"
        assert result["trading"]["debug"] is True
        assert result["trading"]["new_option"] is True
        assert result["trading"]["enabled"] is True  # From base

    def test_update_local_config_overrides_values(self, tmp_path, sample_base_config):
        """Should override existing values."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)

        existing_local = {"value": "old"}
        with open(local_file, 'w') as f:
            json.dump(existing_local, f)

        updates = {"value": "new"}

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.update_local_config(updates)

        assert result["value"] == "new"

    def test_update_local_config_returns_full_merged(self, tmp_path, sample_base_config):
        """Should return the full merged config (base + local + updates)."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)

        updates = {"trading": {"max_positions": 100}}

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.update_local_config(updates)

        # Should have base values
        assert result["version"] == "1.0"
        assert result["memory"]["target_cap"] == 200

        # Should have updated values
        assert result["trading"]["max_positions"] == 100

        # Should have preserved other base trading values
        assert result["trading"]["risk_per_trade"] == 0.02

    def test_update_local_config_empty_updates(self, tmp_path, sample_base_config):
        """Should handle empty updates gracefully."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump(sample_base_config, f)

        existing_local = {"existing": "value"}
        with open(local_file, 'w') as f:
            json.dump(existing_local, f)

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.update_local_config({})

        # Should preserve existing local and merge with base
        assert result["existing"] == "value"
        assert result["version"] == "1.0"

    def test_update_local_config_deep_nested_update(self, tmp_path, sample_base_config):
        """Should handle deeply nested updates."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        base_with_deep = {
            "deep": {
                "level1": {
                    "level2": {
                        "value": "original"
                    }
                }
            }
        }
        with open(base_file, 'w') as f:
            json.dump(base_with_deep, f)

        updates = {
            "deep": {
                "level1": {
                    "level2": {
                        "value": "updated",
                        "new": "added"
                    }
                }
            }
        }

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                result = config.update_local_config(updates)

        assert result["deep"]["level1"]["level2"]["value"] == "updated"
        assert result["deep"]["level1"]["level2"]["new"] == "added"


# =============================================================================
# TEST CLASS: resolve_path Function
# =============================================================================


class TestResolvePath:
    """Tests for the resolve_path function."""

    def test_resolve_path_absolute_unchanged(self, tmp_path):
        """Should return absolute path unchanged."""
        from core.config import resolve_path

        if os.name == 'nt':  # Windows
            abs_path = "C:\\Users\\test\\config.json"
        else:
            abs_path = "/home/user/config.json"

        result = resolve_path(abs_path)

        assert result == Path(abs_path)

    def test_resolve_path_relative_resolved(self):
        """Should resolve relative path against ROOT."""
        from core import config

        relative_path = "lifeos/config/test.json"

        result = config.resolve_path(relative_path)

        # Should be resolved against ROOT
        expected = (config.ROOT / relative_path).resolve()
        assert result == expected

    def test_resolve_path_returns_path_object(self):
        """Should return a Path object."""
        from core.config import resolve_path

        result = resolve_path("some/path")

        assert isinstance(result, Path)

    def test_resolve_path_simple_filename(self):
        """Should resolve simple filename against ROOT."""
        from core import config

        result = config.resolve_path("config.json")

        expected = (config.ROOT / "config.json").resolve()
        assert result == expected

    def test_resolve_path_with_dots(self):
        """Should handle paths with dots (parent directory references)."""
        from core import config

        result = config.resolve_path("../sibling/file.json")

        # Should resolve properly
        assert result.is_absolute()

    def test_resolve_path_nested_relative(self):
        """Should handle deeply nested relative paths."""
        from core import config

        result = config.resolve_path("a/b/c/d/file.json")

        expected = (config.ROOT / "a/b/c/d/file.json").resolve()
        assert result == expected

    def test_resolve_path_preserves_resolution(self):
        """Should return resolved (normalized) path."""
        from core import config

        result = config.resolve_path("./config.json")

        # Resolved path shouldn't have ./
        assert "./" not in str(result)

    def test_resolve_path_with_trailing_slash(self):
        """Should handle paths with trailing slash."""
        from core.config import resolve_path

        result = resolve_path("some/directory/")

        assert isinstance(result, Path)


# =============================================================================
# TEST CLASS: Module Constants
# =============================================================================


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_root_is_path(self):
        """ROOT should be a Path object."""
        from core.config import ROOT

        assert isinstance(ROOT, Path)

    def test_root_is_absolute(self):
        """ROOT should be an absolute path."""
        from core.config import ROOT

        assert ROOT.is_absolute()

    def test_config_dir_is_path(self):
        """CONFIG_DIR should be a Path object."""
        from core.config import CONFIG_DIR

        assert isinstance(CONFIG_DIR, Path)

    def test_config_dir_under_root(self):
        """CONFIG_DIR should be under ROOT."""
        from core.config import ROOT, CONFIG_DIR

        # CONFIG_DIR should contain ROOT in its path
        assert str(ROOT) in str(CONFIG_DIR)

    def test_base_config_is_path(self):
        """BASE_CONFIG should be a Path object."""
        from core.config import BASE_CONFIG

        assert isinstance(BASE_CONFIG, Path)

    def test_base_config_has_json_extension(self):
        """BASE_CONFIG should have .json extension."""
        from core.config import BASE_CONFIG

        assert BASE_CONFIG.suffix == ".json"

    def test_local_config_is_path(self):
        """LOCAL_CONFIG should be a Path object."""
        from core.config import LOCAL_CONFIG

        assert isinstance(LOCAL_CONFIG, Path)

    def test_local_config_has_json_extension(self):
        """LOCAL_CONFIG should have .json extension."""
        from core.config import LOCAL_CONFIG

        assert LOCAL_CONFIG.suffix == ".json"

    def test_local_config_has_local_in_name(self):
        """LOCAL_CONFIG should have 'local' in filename."""
        from core.config import LOCAL_CONFIG

        assert "local" in LOCAL_CONFIG.name.lower()


# =============================================================================
# TEST CLASS: Integration Tests
# =============================================================================


class TestConfigIntegration:
    """Integration tests for the config module."""

    def test_full_config_lifecycle(self, tmp_path):
        """Test complete config lifecycle: load, update, save, reload."""
        from core import config

        # Setup
        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        initial_base = {
            "app": "jarvis",
            "version": "1.0",
            "settings": {
                "debug": False,
                "timeout": 30,
            }
        }
        with open(base_file, 'w') as f:
            json.dump(initial_base, f)

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                # Initial load
                cfg1 = config.load_config()
                assert cfg1["settings"]["debug"] is False

                # Update with new values
                cfg2 = config.update_local_config({
                    "settings": {"debug": True, "new_option": "value"}
                })
                assert cfg2["settings"]["debug"] is True
                assert cfg2["settings"]["new_option"] == "value"
                assert cfg2["settings"]["timeout"] == 30  # Preserved

                # Reload should have same result
                cfg3 = config.load_config()
                assert cfg3["settings"]["debug"] is True
                assert cfg3["settings"]["new_option"] == "value"

    def test_config_preserves_base_on_local_update(self, tmp_path):
        """Updating local should not affect base config file."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        initial_base = {"original": "base_value"}
        with open(base_file, 'w') as f:
            json.dump(initial_base, f)

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                config.update_local_config({"new": "local_value"})

        # Base file should be unchanged
        with open(base_file) as f:
            base_after = json.load(f)
        assert base_after == initial_base

    def test_multiple_sequential_updates(self, tmp_path):
        """Should handle multiple sequential updates correctly."""
        from core import config

        config_dir = tmp_path / "lifeos" / "config"
        config_dir.mkdir(parents=True)
        base_file = config_dir / "lifeos.config.json"
        local_file = config_dir / "lifeos.config.local.json"

        with open(base_file, 'w') as f:
            json.dump({"base": True}, f)

        with patch.object(config, 'BASE_CONFIG', base_file):
            with patch.object(config, 'LOCAL_CONFIG', local_file):
                # First update
                config.update_local_config({"update1": "value1"})

                # Second update
                config.update_local_config({"update2": "value2"})

                # Third update
                config.update_local_config({"update3": "value3"})

                # Load and verify all updates present
                final = config.load_config()

        assert final["base"] is True
        assert final["update1"] == "value1"
        assert final["update2"] == "value2"
        assert final["update3"] == "value3"


# =============================================================================
# RUN CONFIGURATION
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
