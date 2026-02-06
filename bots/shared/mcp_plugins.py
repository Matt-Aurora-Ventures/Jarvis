"""
MCP Plugin System for ClawdBots.

Enables hot-loadable plugins that extend bot capabilities.
Plugins are Python modules with a manifest.json describing capabilities.

Plugin directory: /root/clawdbots/plugins/
Each plugin: /root/clawdbots/plugins/{name}/
  - manifest.json (name, version, description, permissions, entry_point)
  - plugin.py (main module with setup() and teardown())
"""

import json
import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str = ""
    permissions: List[str] = field(default_factory=list)
    entry_point: str = "plugin.py"
    enabled: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "PluginManifest":
        return cls(
            name=d["name"],
            version=d["version"],
            description=d["description"],
            author=d.get("author", ""),
            permissions=d.get("permissions") or [],
            entry_point=d.get("entry_point", "plugin.py"),
            enabled=d.get("enabled", True),
        )

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


class MCPPluginManager:
    """Manages discovery, loading, and execution of MCP plugins."""

    ALLOWED_PERMISSIONS = {
        "read_memory", "write_memory",
        "send_message", "query_graph",
        "read_state", "write_state",
        "execute_skill",
    }
    ELEVATED_PERMISSIONS = {"execute_shell", "manage_plugins", "access_keys"}

    def __init__(self, plugin_dir: str = "/root/clawdbots/plugins", allowed_bots: Optional[List[str]] = None):
        self.plugin_dir = Path(plugin_dir)
        self.plugins: Dict[str, Any] = {}  # name -> loaded module
        self.manifests: Dict[str, PluginManifest] = {}  # name -> manifest
        self.allowed_bots = allowed_bots

    def discover_plugins(self) -> List[PluginManifest]:
        """Scan plugin directory for available plugins."""
        if not self.plugin_dir.exists():
            logger.debug("Plugin directory does not exist: %s", self.plugin_dir)
            return []

        discovered: List[PluginManifest] = []
        for child in self.plugin_dir.iterdir():
            if not child.is_dir():
                continue
            manifest_path = child / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = PluginManifest.from_file(manifest_path)
                self.manifests[manifest.name] = manifest
                discovered.append(manifest)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("Skipping plugin %s: %s", child.name, exc)
        return discovered

    def load_plugin(self, name: str) -> bool:
        """Load a plugin by name. Validates permissions first."""
        manifest = self.manifests.get(name)
        if manifest is None:
            logger.warning("Plugin not discovered: %s", name)
            return False

        if not manifest.enabled:
            logger.info("Plugin %s is disabled", name)
            return False

        ok, msg = self.validate_permissions(manifest)
        if not ok:
            logger.warning("Plugin %s failed permission check: %s", name, msg)
            return False

        # Security: validate entry_point is a simple filename (no path traversal)
        if ".." in manifest.entry_point or "/" in manifest.entry_point or "\\" in manifest.entry_point:
            logger.error("Rejected plugin %s: entry_point contains path traversal: %s", name, manifest.entry_point)
            return False
        plugin_path = (self.plugin_dir / name / manifest.entry_point).resolve()
        if not str(plugin_path).startswith(str(self.plugin_dir.resolve())):
            logger.error("Rejected plugin %s: resolved path escapes plugin dir: %s", name, plugin_path)
            return False
        if not plugin_path.exists():
            logger.error("Entry point not found: %s", plugin_path)
            return False

        try:
            module_name = f"_mcp_plugin_{name}"
            spec = importlib.util.spec_from_file_location(module_name, str(plugin_path))
            if spec is None or spec.loader is None:
                logger.error("Cannot create spec for %s", plugin_path)
                return False
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if hasattr(module, "setup"):
                module.setup()

            self.plugins[name] = module
            logger.info("Loaded plugin: %s v%s", name, manifest.version)
            return True
        except Exception as exc:
            logger.error("Failed to load plugin %s: %s", name, exc)
            return False

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin, calling teardown if available."""
        module = self.plugins.get(name)
        if module is None:
            return False

        try:
            if hasattr(module, "teardown"):
                module.teardown()
        except Exception as exc:
            logger.warning("Error in teardown for %s: %s", name, exc)

        del self.plugins[name]
        module_name = f"_mcp_plugin_{name}"
        sys.modules.pop(module_name, None)
        logger.info("Unloaded plugin: %s", name)
        return True

    def reload_plugin(self, name: str) -> bool:
        """Hot-reload a plugin by unloading then loading."""
        if name in self.plugins:
            self.unload_plugin(name)
        # Re-read manifest in case it changed
        manifest_path = self.plugin_dir / name / "manifest.json"
        if manifest_path.exists():
            try:
                self.manifests[name] = PluginManifest.from_file(manifest_path)
            except Exception:
                pass
        return self.load_plugin(name)

    def validate_permissions(self, manifest: PluginManifest) -> Tuple[bool, str]:
        """Check if plugin permissions are safe."""
        all_known = self.ALLOWED_PERMISSIONS | self.ELEVATED_PERMISSIONS
        for perm in manifest.permissions:
            if perm in self.ELEVATED_PERMISSIONS:
                return False, f"Elevated permission requires owner approval: {perm}"
            if perm not in all_known:
                return False, f"Unknown permission: {perm}"
        return True, "OK"

    def execute_plugin(self, name: str, method: str, **kwargs) -> Any:
        """Execute a method on a loaded plugin."""
        module = self.plugins.get(name)
        if module is None:
            raise KeyError(f"Plugin not loaded: {name}")
        func = getattr(module, method)  # raises AttributeError if missing
        return func(**kwargs)

    def list_plugins(self) -> List[dict]:
        """List all discovered plugins with status."""
        result = []
        for name, manifest in self.manifests.items():
            result.append({
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "author": manifest.author,
                "permissions": manifest.permissions,
                "enabled": manifest.enabled,
                "loaded": name in self.plugins,
            })
        return result

    def create_sample_plugin(self, name: str, description: str) -> None:
        """Generate a new plugin scaffold."""
        plugin_dir = self.plugin_dir / name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "name": name,
            "version": "1.0.0",
            "description": description,
            "author": "",
            "permissions": [],
            "entry_point": "plugin.py",
            "enabled": True,
        }
        (plugin_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        plugin_code = '''"""Plugin: {name}

{description}
"""


def setup():
    """Called when the plugin is loaded."""
    pass


def teardown():
    """Called when the plugin is unloaded."""
    pass


def greet(who: str = "world") -> str:
    """Example method."""
    return f"Hello, {{who}}!"
'''.format(name=name, description=description)

        (plugin_dir / "plugin.py").write_text(plugin_code, encoding="utf-8")
        logger.info("Created sample plugin: %s at %s", name, plugin_dir)
