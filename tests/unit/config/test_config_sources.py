"""
Unit tests for ConfigSource hierarchy.

Tests:
- ConfigSource abstract base class
- EnvSource - load from environment variables
- FileSource - load from JSON/YAML files
- ChainedSource - fallback chain of sources
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestConfigSourceAbstract:
    """Test ConfigSource abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """ConfigSource cannot be instantiated directly."""
        from core.config.sources import ConfigSource

        with pytest.raises(TypeError):
            ConfigSource()

    def test_subclass_must_implement_load(self):
        """Subclass must implement load() method."""
        from core.config.sources import ConfigSource

        class IncompleteSource(ConfigSource):
            pass

        with pytest.raises(TypeError):
            IncompleteSource()

    def test_subclass_with_load_can_be_instantiated(self):
        """Subclass implementing load() can be instantiated."""
        from core.config.sources import ConfigSource

        class CompleteSource(ConfigSource):
            def load(self):
                return {}

        source = CompleteSource()
        assert source is not None


class TestEnvSource:
    """Test EnvSource configuration source."""

    def setup_method(self):
        """Clean environment before each test."""
        # Remove test env vars
        for key in list(os.environ.keys()):
            if key.startswith("TEST_"):
                del os.environ[key]

    def test_load_env_vars_with_prefix(self):
        """EnvSource should load env vars with given prefix."""
        from core.config.sources import EnvSource

        os.environ["TEST_API_KEY"] = "secret_key"
        os.environ["TEST_DEBUG"] = "true"
        os.environ["OTHER_VAR"] = "ignored"

        source = EnvSource(prefix="TEST_")
        config = source.load()

        assert config["API_KEY"] == "secret_key"
        assert config["DEBUG"] == "true"
        assert "OTHER_VAR" not in config

    def test_load_env_vars_without_prefix(self):
        """EnvSource without prefix should load all env vars."""
        from core.config.sources import EnvSource

        os.environ["TEST_VAR1"] = "value1"
        os.environ["TEST_VAR2"] = "value2"

        source = EnvSource()
        config = source.load()

        assert "TEST_VAR1" in config
        assert "TEST_VAR2" in config

    def test_strip_prefix_option(self):
        """EnvSource strip_prefix should remove prefix from keys."""
        from core.config.sources import EnvSource

        os.environ["MYAPP_DATABASE_HOST"] = "localhost"
        os.environ["MYAPP_DATABASE_PORT"] = "5432"

        source = EnvSource(prefix="MYAPP_", strip_prefix=True)
        config = source.load()

        assert config["DATABASE_HOST"] == "localhost"
        assert config["DATABASE_PORT"] == "5432"

    def test_keep_prefix_option(self):
        """EnvSource with strip_prefix=False should keep prefix."""
        from core.config.sources import EnvSource

        os.environ["TEST_KEY"] = "value"

        source = EnvSource(prefix="TEST_", strip_prefix=False)
        config = source.load()

        assert config["TEST_KEY"] == "value"

    def test_type_conversion(self):
        """EnvSource should optionally convert types."""
        from core.config.sources import EnvSource

        os.environ["TEST_INT"] = "42"
        os.environ["TEST_FLOAT"] = "3.14"
        os.environ["TEST_BOOL"] = "true"
        os.environ["TEST_LIST"] = "a,b,c"

        source = EnvSource(prefix="TEST_", convert_types=True)
        config = source.load()

        assert config["INT"] == 42
        assert config["FLOAT"] == 3.14
        assert config["BOOL"] is True
        assert config["LIST"] == ["a", "b", "c"]

    def test_exclude_patterns(self):
        """EnvSource should exclude vars matching patterns."""
        from core.config.sources import EnvSource

        os.environ["TEST_PUBLIC"] = "visible"
        os.environ["TEST_SECRET_KEY"] = "hidden"
        os.environ["TEST_PASSWORD"] = "hidden"

        source = EnvSource(
            prefix="TEST_",
            exclude_patterns=["SECRET", "PASSWORD"]
        )
        config = source.load()

        assert config["PUBLIC"] == "visible"
        assert "SECRET_KEY" not in config
        assert "PASSWORD" not in config


class TestFileSource:
    """Test FileSource configuration source."""

    def test_load_json_file(self):
        """FileSource should load JSON config file."""
        from core.config.sources import FileSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"key": "value", "nested": {"inner": "data"}}, f)
            config_file = f.name

        try:
            source = FileSource(config_file)
            config = source.load()

            assert config["key"] == "value"
            assert config["nested.inner"] == "data"
        finally:
            os.unlink(config_file)

    def test_load_yaml_file(self):
        """FileSource should load YAML config file."""
        from core.config.sources import FileSource

        yaml_content = """
database:
  host: localhost
  port: 5432
debug: true
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            config_file = f.name

        try:
            source = FileSource(config_file)
            config = source.load()

            assert config["database.host"] == "localhost"
            assert config["database.port"] == 5432
            assert config["debug"] is True
        finally:
            os.unlink(config_file)

    def test_file_not_found_raises_error(self):
        """FileSource should raise error for missing file."""
        from core.config.sources import FileSource

        source = FileSource("/nonexistent/config.json")

        with pytest.raises(FileNotFoundError):
            source.load()

    def test_file_not_found_with_optional(self):
        """FileSource with optional=True should return empty dict."""
        from core.config.sources import FileSource

        source = FileSource("/nonexistent/config.json", optional=True)
        config = source.load()

        assert config == {}

    def test_invalid_json_raises_error(self):
        """FileSource should raise error for invalid JSON."""
        from core.config.sources import FileSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not valid json {{{")
            config_file = f.name

        try:
            source = FileSource(config_file)
            with pytest.raises(ValueError):
                source.load()
        finally:
            os.unlink(config_file)

    def test_flatten_nested_dict(self):
        """FileSource should flatten nested dicts to dot notation."""
        from core.config.sources import FileSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({
                "level1": {
                    "level2": {
                        "level3": "deep_value"
                    }
                }
            }, f)
            config_file = f.name

        try:
            source = FileSource(config_file)
            config = source.load()

            assert config["level1.level2.level3"] == "deep_value"
        finally:
            os.unlink(config_file)

    def test_env_var_expansion_in_file(self):
        """FileSource should expand ${VAR} patterns."""
        from core.config.sources import FileSource

        os.environ["FILE_TEST_VAR"] = "expanded_value"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"key": "${FILE_TEST_VAR}"}, f)
            config_file = f.name

        try:
            source = FileSource(config_file, expand_env=True)
            config = source.load()

            assert config["key"] == "expanded_value"
        finally:
            os.unlink(config_file)
            del os.environ["FILE_TEST_VAR"]


class TestChainedSource:
    """Test ChainedSource for fallback chains."""

    def test_load_from_single_source(self):
        """ChainedSource with one source should work."""
        from core.config.sources import ChainedSource, EnvSource

        os.environ["TEST_SINGLE"] = "value"

        try:
            chained = ChainedSource([EnvSource(prefix="TEST_")])
            config = chained.load()

            assert config["SINGLE"] == "value"
        finally:
            del os.environ["TEST_SINGLE"]

    def test_later_sources_override_earlier(self):
        """Later sources in chain should override earlier ones."""
        from core.config.sources import ChainedSource, FileSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f1:
            json.dump({"shared": "from_first", "first_only": "value1"}, f1)
            file1 = f1.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f2:
            json.dump({"shared": "from_second", "second_only": "value2"}, f2)
            file2 = f2.name

        try:
            source1 = FileSource(file1)
            source2 = FileSource(file2)

            chained = ChainedSource([source1, source2])
            config = chained.load()

            # Second source overrides shared key
            assert config["shared"] == "from_second"
            # Both unique keys present
            assert config["first_only"] == "value1"
            assert config["second_only"] == "value2"
        finally:
            os.unlink(file1)
            os.unlink(file2)

    def test_empty_chain_returns_empty_dict(self):
        """ChainedSource with no sources should return empty dict."""
        from core.config.sources import ChainedSource

        chained = ChainedSource([])
        config = chained.load()

        assert config == {}

    def test_add_source_dynamically(self):
        """ChainedSource should allow adding sources dynamically."""
        from core.config.sources import ChainedSource, EnvSource

        os.environ["TEST_DYNAMIC"] = "value"

        try:
            chained = ChainedSource([])
            chained.add_source(EnvSource(prefix="TEST_"))
            config = chained.load()

            assert config["DYNAMIC"] == "value"
        finally:
            del os.environ["TEST_DYNAMIC"]

    def test_source_priority_explicit(self):
        """ChainedSource should respect explicit priority."""
        from core.config.sources import ChainedSource, FileSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f1:
            json.dump({"key": "low_priority"}, f1)
            file1 = f1.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f2:
            json.dump({"key": "high_priority"}, f2)
            file2 = f2.name

        try:
            source_low = FileSource(file1)
            source_high = FileSource(file2)

            # Add with explicit priority (higher number = higher priority)
            chained = ChainedSource([])
            chained.add_source(source_low, priority=10)
            chained.add_source(source_high, priority=100)

            config = chained.load()

            assert config["key"] == "high_priority"
        finally:
            os.unlink(file1)
            os.unlink(file2)

    def test_failed_source_continues_chain(self):
        """ChainedSource should continue if optional source fails."""
        from core.config.sources import ChainedSource, FileSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"fallback": "value"}, f)
            fallback_file = f.name

        try:
            # First source doesn't exist (optional)
            missing_source = FileSource("/nonexistent.json", optional=True)
            fallback_source = FileSource(fallback_file)

            chained = ChainedSource([missing_source, fallback_source])
            config = chained.load()

            assert config["fallback"] == "value"
        finally:
            os.unlink(fallback_file)


class TestSourceRefresh:
    """Test source refresh/reload capabilities."""

    def test_env_source_reflects_changes(self):
        """EnvSource.load() should reflect env changes."""
        from core.config.sources import EnvSource

        os.environ["TEST_REFRESH"] = "initial"

        source = EnvSource(prefix="TEST_")

        config1 = source.load()
        assert config1["REFRESH"] == "initial"

        os.environ["TEST_REFRESH"] = "updated"

        config2 = source.load()
        assert config2["REFRESH"] == "updated"

        del os.environ["TEST_REFRESH"]

    def test_file_source_reflects_changes(self):
        """FileSource.load() should reflect file changes."""
        from core.config.sources import FileSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"key": "initial"}, f)
            config_file = f.name

        try:
            source = FileSource(config_file)

            config1 = source.load()
            assert config1["key"] == "initial"

            # Update file
            with open(config_file, "w") as f:
                json.dump({"key": "updated"}, f)

            config2 = source.load()
            assert config2["key"] == "updated"
        finally:
            os.unlink(config_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
