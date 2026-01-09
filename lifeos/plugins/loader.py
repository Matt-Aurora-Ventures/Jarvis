"""
Plugin Loader

Handles plugin discovery, loading, and dependency resolution.
Supports hot-reload for development.

Features:
- Discovers plugins in configured directories
- Resolves dependencies using topological sort
- Validates manifests before loading
- Supports hot-reload via file watching
"""

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

from lifeos.plugins.manifest import (
    PluginManifest,
    PluginStatus,
    ManifestValidationError,
)
from lifeos.plugins.base import (
    Plugin,
    PluginContext,
    PluginError,
    PluginLoadError,
    PluginDependencyError,
)

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Loads and manages plugin instances.

    Handles:
    - Plugin discovery from directories
    - Manifest validation
    - Dependency resolution
    - Module loading and instantiation
    - Hot-reload support
    """

    def __init__(
        self,
        plugin_dirs: Optional[List[Path]] = None,
        services: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize plugin loader.

        Args:
            plugin_dirs: Directories to search for plugins
            services: Services to expose to plugins
        """
        self._plugin_dirs = plugin_dirs or []
        self._services = services or {}
        self._manifests: Dict[str, PluginManifest] = {}
        self._plugins: Dict[str, Plugin] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._modules: Dict[str, Any] = {}
        self._file_watchers: Dict[str, Any] = {}

    def add_plugin_dir(self, path: Path) -> None:
        """Add a directory to search for plugins."""
        if path not in self._plugin_dirs:
            self._plugin_dirs.append(path)

    def set_services(self, services: Dict[str, Any]) -> None:
        """Set services available to plugins."""
        self._services = services

    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> None:
        """Set configuration for a plugin."""
        self._configs[plugin_name] = config

    # =========================================================================
    # Discovery
    # =========================================================================

    def discover(self) -> List[PluginManifest]:
        """
        Discover all plugins in configured directories.

        Returns:
            List of discovered plugin manifests
        """
        discovered = []

        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                logger.warning(f"Plugin directory not found: {plugin_dir}")
                continue

            # Look for manifest.json in subdirectories
            for subdir in plugin_dir.iterdir():
                if not subdir.is_dir():
                    continue

                manifest_path = subdir / "manifest.json"
                if not manifest_path.exists():
                    continue

                try:
                    manifest = PluginManifest.from_file(manifest_path)
                    errors = manifest.validate()
                    if errors:
                        logger.warning(
                            f"Invalid manifest for {subdir.name}: {errors}"
                        )
                        manifest.status = PluginStatus.ERROR
                        manifest.error_message = "; ".join(errors)
                    discovered.append(manifest)
                except Exception as e:
                    logger.error(f"Failed to load manifest from {subdir}: {e}")

        return discovered

    # =========================================================================
    # Dependency Resolution
    # =========================================================================

    def resolve_dependencies(
        self,
        manifests: List[PluginManifest],
    ) -> List[PluginManifest]:
        """
        Resolve plugin dependencies and return load order.

        Uses topological sort to determine correct load order.

        Args:
            manifests: List of plugin manifests to resolve

        Returns:
            Manifests in correct load order

        Raises:
            PluginDependencyError: If circular dependency or missing dep
        """
        # Build dependency graph
        by_name = {m.name: m for m in manifests}
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}

        for manifest in manifests:
            if manifest.name not in graph:
                graph[manifest.name] = set()
                in_degree[manifest.name] = 0

            for dep in manifest.dependencies:
                if dep.name not in by_name and not dep.optional:
                    raise PluginDependencyError(
                        manifest.name,
                        f"Missing required dependency: {dep.name}"
                    )
                if dep.name in by_name:
                    # Ensure dependency node exists in graph
                    if dep.name not in graph:
                        graph[dep.name] = set()
                        in_degree[dep.name] = 0
                    graph[dep.name].add(manifest.name)
                    in_degree[manifest.name] = in_degree.get(manifest.name, 0) + 1

        # Topological sort (Kahn's algorithm)
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort by priority for deterministic order
            queue.sort(key=lambda n: by_name[n].priority)
            current = queue.pop(0)
            result.append(by_name[current])

            for dependent in graph.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(manifests):
            # Find cycles
            remaining = set(m.name for m in manifests) - set(m.name for m in result)
            raise PluginDependencyError(
                "system",
                f"Circular dependency detected involving: {remaining}"
            )

        return result

    # =========================================================================
    # Loading
    # =========================================================================

    async def load(self, manifest: PluginManifest) -> Plugin:
        """
        Load a single plugin.

        Args:
            manifest: Plugin manifest

        Returns:
            Loaded plugin instance

        Raises:
            PluginLoadError: If plugin fails to load
        """
        if manifest.name in self._plugins:
            return self._plugins[manifest.name]

        manifest.status = PluginStatus.LOADING
        logger.info(f"Loading plugin: {manifest.name} v{manifest.version}")

        try:
            # Validate manifest
            errors = manifest.validate()
            if errors:
                raise ManifestValidationError(errors)

            # Load the module
            plugin_class = self._load_module(manifest)

            # Create context
            config = self._configs.get(manifest.name, {})
            merged_config = {**manifest.default_config, **config}
            context = PluginContext(
                plugin_name=manifest.name,
                permissions=manifest.permissions,
                config=merged_config,
                services=self._services,
            )

            # Instantiate plugin
            plugin = plugin_class(context, manifest)

            # Call on_load
            await plugin.on_load()

            # Store references
            manifest.status = PluginStatus.LOADED
            from datetime import datetime, timezone
            manifest.loaded_at = datetime.now(timezone.utc)
            self._manifests[manifest.name] = manifest
            self._plugins[manifest.name] = plugin

            logger.info(f"Loaded plugin: {manifest.name}")
            return plugin

        except Exception as e:
            manifest.status = PluginStatus.ERROR
            manifest.error_message = str(e)
            logger.error(f"Failed to load plugin {manifest.name}: {e}")
            raise PluginLoadError(manifest.name, str(e))

    def _load_module(self, manifest: PluginManifest) -> Type[Plugin]:
        """
        Load plugin module and return plugin class.

        Args:
            manifest: Plugin manifest

        Returns:
            Plugin class

        Raises:
            PluginLoadError: If module cannot be loaded
        """
        if manifest.path is None:
            raise PluginLoadError(manifest.name, "Plugin path not set")

        entry_path = manifest.path / manifest.entry_point
        if not entry_path.exists():
            raise PluginLoadError(
                manifest.name,
                f"Entry point not found: {manifest.entry_point}"
            )

        # Create module name
        module_name = f"jarvis_plugins.{manifest.name.replace('-', '_')}"

        # Load module
        spec = importlib.util.spec_from_file_location(module_name, entry_path)
        if spec is None or spec.loader is None:
            raise PluginLoadError(manifest.name, "Failed to create module spec")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        self._modules[manifest.name] = module

        # Find plugin class
        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Plugin)
                and attr is not Plugin
            ):
                plugin_class = attr
                break

        if plugin_class is None:
            raise PluginLoadError(
                manifest.name,
                "No Plugin subclass found in entry point"
            )

        return plugin_class

    async def load_all(self) -> Dict[str, Plugin]:
        """
        Discover and load all plugins.

        Returns:
            Dictionary of loaded plugins by name
        """
        manifests = self.discover()
        ordered = self.resolve_dependencies(manifests)

        for manifest in ordered:
            try:
                await self.load(manifest)
            except PluginError as e:
                logger.error(f"Failed to load {manifest.name}: {e}")

        return self._plugins

    # =========================================================================
    # Unloading
    # =========================================================================

    async def unload(self, plugin_name: str) -> None:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of plugin to unload
        """
        if plugin_name not in self._plugins:
            return

        plugin = self._plugins[plugin_name]
        manifest = self._manifests[plugin_name]

        manifest.status = PluginStatus.UNLOADING
        logger.info(f"Unloading plugin: {plugin_name}")

        try:
            # Disable first if enabled
            if plugin.is_enabled:
                await plugin._do_disable()

            # Call on_unload
            await plugin.on_unload()

            # Clean up
            del self._plugins[plugin_name]
            del self._manifests[plugin_name]

            # Remove module from sys.modules
            module_name = f"jarvis_plugins.{plugin_name.replace('-', '_')}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            if plugin_name in self._modules:
                del self._modules[plugin_name]

            logger.info(f"Unloaded plugin: {plugin_name}")

        except Exception as e:
            manifest.status = PluginStatus.ERROR
            manifest.error_message = str(e)
            logger.error(f"Error unloading plugin {plugin_name}: {e}")

    async def unload_all(self) -> None:
        """Unload all plugins in reverse order."""
        # Unload in reverse dependency order
        plugin_names = list(self._plugins.keys())
        for name in reversed(plugin_names):
            await self.unload(name)

    # =========================================================================
    # Hot Reload
    # =========================================================================

    async def reload(self, plugin_name: str) -> Plugin:
        """
        Hot-reload a plugin.

        Preserves configuration but reloads code.

        Args:
            plugin_name: Name of plugin to reload

        Returns:
            Reloaded plugin instance
        """
        if plugin_name not in self._manifests:
            raise PluginLoadError(plugin_name, "Plugin not loaded")

        manifest = self._manifests[plugin_name]
        was_enabled = (
            plugin_name in self._plugins and self._plugins[plugin_name].is_enabled
        )

        # Unload
        await self.unload(plugin_name)

        # Re-read manifest
        if manifest.path:
            manifest = PluginManifest.from_file(manifest.path / "manifest.json")

        # Reload
        plugin = await self.load(manifest)

        # Re-enable if it was enabled
        if was_enabled:
            await plugin._do_enable()

        return plugin

    # =========================================================================
    # Accessors
    # =========================================================================

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a loaded plugin by name."""
        return self._plugins.get(name)

    def get_manifest(self, name: str) -> Optional[PluginManifest]:
        """Get a plugin manifest by name."""
        return self._manifests.get(name)

    def get_all_plugins(self) -> Dict[str, Plugin]:
        """Get all loaded plugins."""
        return dict(self._plugins)

    def get_all_manifests(self) -> Dict[str, PluginManifest]:
        """Get all manifests."""
        return dict(self._manifests)
