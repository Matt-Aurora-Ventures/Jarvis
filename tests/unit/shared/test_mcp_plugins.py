"""Tests for MCP Plugin System."""

import json
import sys
import types
import pytest
from pathlib import Path
from unittest.mock import patch


# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bots.shared.mcp_plugins import MCPPluginManager, PluginManifest


# ---------------------------------------------------------------------------
# PluginManifest tests
# ---------------------------------------------------------------------------

class TestPluginManifest:
    def test_from_dict_minimal(self):
        m = PluginManifest.from_dict({"name": "foo", "version": "1.0", "description": "bar"})
        assert m.name == "foo"
        assert m.version == "1.0"
        assert m.permissions == []
        assert m.enabled is True

    def test_from_dict_full(self):
        m = PluginManifest.from_dict({
            "name": "test",
            "version": "2.0",
            "description": "desc",
            "author": "me",
            "permissions": ["read_memory"],
            "entry_point": "main.py",
            "enabled": False,
        })
        assert m.author == "me"
        assert m.permissions == ["read_memory"]
        assert m.entry_point == "main.py"
        assert m.enabled is False

    def test_from_file(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({
            "name": "file_test", "version": "1.0", "description": "from file"
        }))
        m = PluginManifest.from_file(manifest_path)
        assert m.name == "file_test"

    def test_from_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PluginManifest.from_file(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# MCPPluginManager tests
# ---------------------------------------------------------------------------

def _make_plugin(plugin_dir: Path, name: str, perms=None, entry="plugin.py",
                 setup_code="", extra_funcs="", enabled=True):
    """Helper to create a plugin in a temp directory."""
    d = plugin_dir / name
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": "1.0",
        "description": f"Test plugin {name}",
        "permissions": perms or [],
        "entry_point": entry,
        "enabled": enabled,
    }
    (d / "manifest.json").write_text(json.dumps(manifest))
    code = f"""
def setup():
    pass

def teardown():
    pass

{extra_funcs}
"""
    if setup_code:
        code = setup_code
    (d / entry).write_text(code)
    return d


class TestMCPPluginManagerDiscover:
    def test_discover_empty(self, tmp_path):
        mgr = MCPPluginManager(plugin_dir=str(tmp_path / "plugins"))
        # dir doesn't exist yet
        result = mgr.discover_plugins()
        assert result == []

    def test_discover_finds_plugins(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "alpha")
        _make_plugin(pdir, "beta")
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        found = mgr.discover_plugins()
        names = {m.name for m in found}
        assert names == {"alpha", "beta"}

    def test_discover_skips_bad_manifest(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "good")
        bad = pdir / "bad"
        bad.mkdir()
        (bad / "manifest.json").write_text("NOT JSON")
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        found = mgr.discover_plugins()
        assert len(found) == 1
        assert found[0].name == "good"


class TestMCPPluginManagerLoad:
    def test_load_plugin(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "loader_test", extra_funcs='def greet(): return "hi"')
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        assert mgr.load_plugin("loader_test") is True
        assert "loader_test" in mgr.plugins

    def test_load_missing_plugin(self, tmp_path):
        mgr = MCPPluginManager(plugin_dir=str(tmp_path))
        assert mgr.load_plugin("nonexistent") is False

    def test_load_disabled_plugin(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "disabled_one", enabled=False)
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        assert mgr.load_plugin("disabled_one") is False

    def test_load_calls_setup(self, tmp_path):
        pdir = tmp_path / "plugins"
        code = """
_setup_called = False
def setup():
    global _setup_called
    _setup_called = True
def teardown():
    pass
"""
        _make_plugin(pdir, "setup_test", setup_code=code)
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        mgr.load_plugin("setup_test")
        assert mgr.plugins["setup_test"]._setup_called is True


class TestMCPPluginManagerUnload:
    def test_unload(self, tmp_path):
        pdir = tmp_path / "plugins"
        code = """
_torn = False
def setup(): pass
def teardown():
    global _torn
    _torn = True
"""
        _make_plugin(pdir, "ul_test", setup_code=code)
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        mgr.load_plugin("ul_test")
        assert mgr.unload_plugin("ul_test") is True
        assert "ul_test" not in mgr.plugins

    def test_unload_missing(self, tmp_path):
        mgr = MCPPluginManager(plugin_dir=str(tmp_path))
        assert mgr.unload_plugin("nope") is False


class TestMCPPluginManagerReload:
    def test_reload(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "rl", extra_funcs='def val(): return 1')
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        mgr.load_plugin("rl")
        assert mgr.execute_plugin("rl", "val") == 1
        # Update the code
        (pdir / "rl" / "plugin.py").write_text("""
def setup(): pass
def teardown(): pass
def val(): return 2
""")
        assert mgr.reload_plugin("rl") is True
        assert mgr.execute_plugin("rl", "val") == 2


class TestMCPPluginManagerPermissions:
    def test_allowed_permissions(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "safe", perms=["read_memory", "send_message"])
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        ok, msg = mgr.validate_permissions(mgr.manifests["safe"])
        assert ok is True

    def test_elevated_permissions_denied(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "danger", perms=["execute_shell"])
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        ok, msg = mgr.validate_permissions(mgr.manifests["danger"])
        assert ok is False
        assert "elevated" in msg.lower() or "execute_shell" in msg

    def test_unknown_permissions_denied(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "unknown", perms=["hack_nasa"])
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        ok, msg = mgr.validate_permissions(mgr.manifests["unknown"])
        assert ok is False


class TestMCPPluginManagerExecute:
    def test_execute_method(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "exec_test", extra_funcs='def add(a, b): return a + b')
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        mgr.load_plugin("exec_test")
        assert mgr.execute_plugin("exec_test", "add", a=2, b=3) == 5

    def test_execute_unloaded(self, tmp_path):
        mgr = MCPPluginManager(plugin_dir=str(tmp_path))
        with pytest.raises(KeyError):
            mgr.execute_plugin("nope", "foo")

    def test_execute_missing_method(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "no_method")
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        mgr.load_plugin("no_method")
        with pytest.raises(AttributeError):
            mgr.execute_plugin("no_method", "nonexistent_func")


class TestMCPPluginManagerList:
    def test_list_plugins(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "listed")
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        mgr.load_plugin("listed")
        result = mgr.list_plugins()
        assert len(result) == 1
        assert result[0]["name"] == "listed"
        assert result[0]["loaded"] is True


class TestMCPPluginManagerScaffold:
    def test_create_sample_plugin(self, tmp_path):
        pdir = tmp_path / "plugins"
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.create_sample_plugin("my_plugin", "A test plugin")
        assert (pdir / "my_plugin" / "manifest.json").exists()
        assert (pdir / "my_plugin" / "plugin.py").exists()
        manifest = json.loads((pdir / "my_plugin" / "manifest.json").read_text())
        assert manifest["name"] == "my_plugin"
        assert manifest["description"] == "A test plugin"


class TestMCPPluginManagerElevatedWithApproval:
    def test_load_elevated_blocked(self, tmp_path):
        pdir = tmp_path / "plugins"
        _make_plugin(pdir, "elev", perms=["execute_shell"])
        mgr = MCPPluginManager(plugin_dir=str(pdir))
        mgr.discover_plugins()
        assert mgr.load_plugin("elev") is False
