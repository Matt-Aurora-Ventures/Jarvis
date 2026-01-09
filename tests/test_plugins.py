"""
Tests for lifeos/plugins system.

Tests cover:
- Manifest validation
- Plugin lifecycle hooks
- Dependency resolution
- Plugin loading/unloading
- Plugin manager operations
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.plugins import (
    PluginManifest,
    PluginDependency,
    PluginPermission,
    PluginStatus,
    ManifestValidationError,
    Plugin,
    PluginContext,
    PluginError,
    PluginLoadError,
    PluginDependencyError,
    PluginLoader,
    PluginManager,
)


# =============================================================================
# Test Manifest
# =============================================================================

class TestPluginManifest:
    """Test PluginManifest class."""

    def test_create_minimal_manifest(self):
        """Should create manifest with minimal fields."""
        manifest = PluginManifest(
            name="test-plugin",
            version="1.0.0",
            entry_point="main.py",
        )
        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"
        assert manifest.status == PluginStatus.UNLOADED

    def test_validate_valid_manifest(self):
        """Valid manifest should have no errors."""
        manifest = PluginManifest(
            name="valid-plugin",
            version="1.0.0",
            entry_point="main.py",
        )
        errors = manifest.validate()
        assert errors == []

    def test_validate_missing_name(self):
        """Should fail if name is missing."""
        manifest = PluginManifest(
            name="",
            version="1.0.0",
            entry_point="main.py",
        )
        errors = manifest.validate()
        assert any("name" in e.lower() for e in errors)

    def test_validate_invalid_version(self):
        """Should fail for invalid version format."""
        manifest = PluginManifest(
            name="test",
            version="invalid",
            entry_point="main.py",
        )
        errors = manifest.validate()
        assert any("version" in e.lower() for e in errors)

    def test_validate_invalid_entry_point(self):
        """Should fail if entry point is not .py."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="main.js",
        )
        errors = manifest.validate()
        assert any("entry" in e.lower() for e in errors)

    def test_validate_invalid_permission(self):
        """Should fail for unknown permissions."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="main.py",
            permissions=["invalid_permission"],
        )
        errors = manifest.validate()
        assert any("permission" in e.lower() for e in errors)

    def test_from_dict(self):
        """Should create manifest from dictionary."""
        data = {
            "name": "from-dict",
            "version": "2.0.0",
            "entry_point": "plugin.py",
            "description": "Test plugin",
            "permissions": ["notifications"],
            "dependencies": [
                {"name": "other-plugin", "version": ">=1.0.0"},
                "simple-dep",
            ],
        }
        manifest = PluginManifest.from_dict(data)

        assert manifest.name == "from-dict"
        assert manifest.version == "2.0.0"
        assert len(manifest.dependencies) == 2
        assert manifest.dependencies[0].name == "other-plugin"
        assert manifest.dependencies[1].name == "simple-dep"

    def test_to_dict(self):
        """Should convert manifest to dictionary."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="main.py",
            description="Test",
        )
        data = manifest.to_dict()

        assert data["name"] == "test"
        assert data["version"] == "1.0.0"
        assert "entry_point" in data

    def test_has_permission(self):
        """Should check permissions correctly."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="main.py",
            permissions=["notifications", "market_read"],
        )

        assert manifest.has_permission("notifications")
        assert manifest.has_permission("market_read")
        assert not manifest.has_permission("llm_write")


# =============================================================================
# Test Plugin Base
# =============================================================================

class TestPluginBase:
    """Test Plugin base class."""

    def test_plugin_properties(self):
        """Should expose properties from manifest."""
        manifest = PluginManifest(
            name="test-plugin",
            version="1.0.0",
            entry_point="main.py",
        )
        context = PluginContext(
            plugin_name="test-plugin",
            permissions=["notifications"],
            config={"key": "value"},
            services={},
        )

        class TestPlugin(Plugin):
            pass

        plugin = TestPlugin(context, manifest)

        assert plugin.name == "test-plugin"
        assert plugin.version == "1.0.0"
        assert plugin.config["key"] == "value"
        assert not plugin.is_enabled

    def test_has_permission(self):
        """Should check context permissions."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="main.py",
        )
        context = PluginContext(
            plugin_name="test",
            permissions=["notifications"],
            config={},
            services={},
        )

        class TestPlugin(Plugin):
            pass

        plugin = TestPlugin(context, manifest)

        assert plugin.has_permission("notifications")
        assert not plugin.has_permission("llm_read")

    @pytest.mark.asyncio
    async def test_lifecycle_hooks_called(self):
        """Lifecycle hooks should be called."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="main.py",
        )
        context = PluginContext(
            plugin_name="test",
            permissions=[],
            config={},
            services={},
        )

        class TestPlugin(Plugin):
            def __init__(self, *args):
                super().__init__(*args)
                self.hooks_called = []

            async def on_load(self):
                self.hooks_called.append("load")

            async def on_enable(self):
                self.hooks_called.append("enable")

            async def on_disable(self):
                self.hooks_called.append("disable")

            async def on_unload(self):
                self.hooks_called.append("unload")

        plugin = TestPlugin(context, manifest)

        await plugin.on_load()
        assert "load" in plugin.hooks_called

        await plugin._do_enable()
        assert "enable" in plugin.hooks_called
        assert plugin.is_enabled

        await plugin._do_disable()
        assert "disable" in plugin.hooks_called
        assert not plugin.is_enabled

        await plugin.on_unload()
        assert "unload" in plugin.hooks_called

    @pytest.mark.asyncio
    async def test_task_management(self):
        """Tasks should be managed and cancelled."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="main.py",
        )
        context = PluginContext(
            plugin_name="test",
            permissions=[],
            config={},
            services={},
        )

        class TestPlugin(Plugin):
            pass

        plugin = TestPlugin(context, manifest)

        async def long_task():
            await asyncio.sleep(100)

        task = plugin.create_task(long_task())
        assert len(plugin._tasks) == 1

        await plugin.cancel_all_tasks()
        assert len(plugin._tasks) == 0
        assert task.cancelled()


# =============================================================================
# Test Dependency Resolution
# =============================================================================

class TestDependencyResolution:
    """Test plugin dependency resolution."""

    def test_no_dependencies(self):
        """Should handle plugins with no dependencies."""
        loader = PluginLoader()
        manifests = [
            PluginManifest(name="a", version="1.0.0", entry_point="main.py"),
            PluginManifest(name="b", version="1.0.0", entry_point="main.py"),
        ]

        ordered = loader.resolve_dependencies(manifests)

        assert len(ordered) == 2
        # Should be in priority order
        names = [m.name for m in ordered]
        assert "a" in names
        assert "b" in names

    def test_simple_dependency(self):
        """Should load dependencies before dependents."""
        loader = PluginLoader()
        manifests = [
            PluginManifest(
                name="dependent",
                version="1.0.0",
                entry_point="main.py",
                dependencies=[PluginDependency(name="base")],
            ),
            PluginManifest(name="base", version="1.0.0", entry_point="main.py"),
        ]

        ordered = loader.resolve_dependencies(manifests)

        names = [m.name for m in ordered]
        assert names.index("base") < names.index("dependent")

    def test_missing_required_dependency(self):
        """Should raise error for missing required dependency."""
        loader = PluginLoader()
        manifests = [
            PluginManifest(
                name="plugin",
                version="1.0.0",
                entry_point="main.py",
                dependencies=[PluginDependency(name="missing")],
            ),
        ]

        with pytest.raises(PluginDependencyError):
            loader.resolve_dependencies(manifests)

    def test_optional_dependency_missing(self):
        """Should not fail for missing optional dependency."""
        loader = PluginLoader()
        manifests = [
            PluginManifest(
                name="plugin",
                version="1.0.0",
                entry_point="main.py",
                dependencies=[PluginDependency(name="missing", optional=True)],
            ),
        ]

        ordered = loader.resolve_dependencies(manifests)
        assert len(ordered) == 1

    def test_circular_dependency_detection(self):
        """Should detect circular dependencies."""
        loader = PluginLoader()
        manifests = [
            PluginManifest(
                name="a",
                version="1.0.0",
                entry_point="main.py",
                dependencies=[PluginDependency(name="b")],
            ),
            PluginManifest(
                name="b",
                version="1.0.0",
                entry_point="main.py",
                dependencies=[PluginDependency(name="a")],
            ),
        ]

        with pytest.raises(PluginDependencyError) as exc_info:
            loader.resolve_dependencies(manifests)

        assert "circular" in str(exc_info.value).lower()


# =============================================================================
# Test Plugin Manager
# =============================================================================

class TestPluginManager:
    """Test PluginManager class."""

    def test_create_manager(self):
        """Should create plugin manager."""
        manager = PluginManager()
        assert not manager._started

    def test_add_plugin_dir(self):
        """Should add plugin directory."""
        manager = PluginManager()
        test_path = Path("/test/plugins")
        manager.add_plugin_dir(test_path)

        assert test_path in manager._loader._plugin_dirs

    def test_configure_plugin(self):
        """Should store plugin configuration."""
        manager = PluginManager()
        manager.configure_plugin("test", {"key": "value"})

        assert "test" in manager._loader._configs
        assert manager._loader._configs["test"]["key"] == "value"

    def test_list_plugins_empty(self):
        """Should return empty list when no plugins."""
        manager = PluginManager()
        plugins = manager.list_plugins()
        assert plugins == []

    def test_is_loaded_false(self):
        """Should return False for non-existent plugin."""
        manager = PluginManager()
        assert not manager.is_loaded("nonexistent")

    def test_is_enabled_false(self):
        """Should return False for non-existent plugin."""
        manager = PluginManager()
        assert not manager.is_enabled("nonexistent")


# =============================================================================
# Test Plugin Loading with Temp Directory
# =============================================================================

class TestPluginLoading:
    """Test plugin loading from files."""

    @pytest.fixture
    def temp_plugin_dir(self):
        """Create a temporary plugin directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test-plugin"
            plugin_dir.mkdir()

            # Create manifest
            manifest = {
                "name": "test-plugin",
                "version": "1.0.0",
                "entry_point": "main.py",
                "description": "Test plugin",
            }
            with open(plugin_dir / "manifest.json", "w") as f:
                json.dump(manifest, f)

            # Create main.py
            main_py = '''
from lifeos.plugins import Plugin

class TestPlugin(Plugin):
    async def on_load(self):
        self.loaded = True

    async def on_enable(self):
        self.enabled = True
'''
            with open(plugin_dir / "main.py", "w") as f:
                f.write(main_py)

            yield Path(tmpdir)

    def test_discover_plugins(self, temp_plugin_dir):
        """Should discover plugins in directory."""
        loader = PluginLoader(plugin_dirs=[temp_plugin_dir])
        manifests = loader.discover()

        assert len(manifests) == 1
        assert manifests[0].name == "test-plugin"

    @pytest.mark.asyncio
    async def test_load_plugin(self, temp_plugin_dir):
        """Should load a plugin."""
        loader = PluginLoader(plugin_dirs=[temp_plugin_dir])
        manifests = loader.discover()

        plugin = await loader.load(manifests[0])

        assert plugin is not None
        assert plugin.name == "test-plugin"
        assert hasattr(plugin, "loaded")
        assert plugin.loaded is True

    @pytest.mark.asyncio
    async def test_unload_plugin(self, temp_plugin_dir):
        """Should unload a plugin."""
        loader = PluginLoader(plugin_dirs=[temp_plugin_dir])
        manifests = loader.discover()

        await loader.load(manifests[0])
        assert loader.get_plugin("test-plugin") is not None

        await loader.unload("test-plugin")
        assert loader.get_plugin("test-plugin") is None
