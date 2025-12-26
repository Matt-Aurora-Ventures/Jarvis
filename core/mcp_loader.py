"""MCP server process manager for LifeOS."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
MCP_CONFIG_PATH = ROOT / "lifeos" / "config" / "mcp.config.json"


def _read_mcp_config() -> Dict:
    if not MCP_CONFIG_PATH.exists():
        return {"log_dir": "lifeos/logs/mcp", "servers": []}

    with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


class MCPServerProcess:
    def __init__(self, name: str, command: List[str], env: Dict[str, str], log_file: Path):
        self.name = name
        self.command = command
        self.env = env
        self.log_file = log_file
        self.process: Optional[subprocess.Popen] = None
        self._log_handle: Optional[open] = None

    def start(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = open(self.log_file, "a", encoding="utf-8")

        self.process = subprocess.Popen(
            self.command,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            env=self.env,
            cwd=str(ROOT),
            preexec_fn=os.setsid,
        )

    def stop(self, timeout: float = 5.0) -> None:
        if not self.process:
            if self._log_handle:
                self._log_handle.close()
            return

        try:
            if self.process.poll() is None:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
        finally:
            if self._log_handle:
                self._log_handle.close()


class MCPManager:
    def __init__(self):
        self.config = _read_mcp_config()
        self.log_dir = ROOT / self.config.get("log_dir", "lifeos/logs/mcp")
        self.servers: Dict[str, MCPServerProcess] = {}
        self.lock = threading.Lock()

    def _build_command(self, server_cfg: Dict) -> List[str]:
        command = server_cfg.get("command")
        args = server_cfg.get("args", [])
        if not command:
            raise ValueError("Server command missing")

        cmd = [command]
        cmd.extend(args)
        return cmd

    def _build_env(self, server_cfg: Dict) -> Dict[str, str]:
        env = os.environ.copy()
        for key, value in server_cfg.get("env", {}).items():
            if value is not None:
                env[key] = str(value)
        return env

    def start_autostart_servers(self) -> None:
        for server in self.config.get("servers", []):
            if not server.get("enabled", True):
                continue
            if not server.get("autostart", True):
                continue

            name = server.get("name", "unknown")
            log_file = self.log_dir / f"{name}.log"

            try:
                command = self._build_command(server)
                env = self._build_env(server)
                process = MCPServerProcess(name, command, env, log_file)
                process.start()
                with self.lock:
                    self.servers[name] = process
            except Exception as exc:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as handle:
                    handle.write(f"Failed to start {name}: {exc}\n")

    def stop_all(self) -> None:
        with self.lock:
            processes = list(self.servers.values())
            self.servers.clear()

        for proc in processes:
            proc.stop()


_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    global _manager
    if _manager is None:
        _manager = MCPManager()
    return _manager


def start_mcp_servers() -> MCPManager:
    manager = get_mcp_manager()
    manager.start_autostart_servers()
    return manager


def stop_mcp_servers() -> None:
    global _manager
    if _manager is not None:
        _manager.stop_all()
        _manager = None
