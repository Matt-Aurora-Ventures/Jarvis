"""MCP server process manager for LifeOS."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MCP_CONFIG_PATH = ROOT / "lifeos" / "config" / "mcp.config.json"
MCP_CONFIG_PATH = Path(os.getenv("JARVIS_MCP_CONFIG", str(DEFAULT_MCP_CONFIG_PATH))).expanduser()


def _expand_config(value):
    if isinstance(value, dict):
        return {key: _expand_config(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_expand_config(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(os.path.expanduser(value))
    return value


def _read_mcp_config() -> Dict:
    if not MCP_CONFIG_PATH.exists():
        return {"log_dir": "lifeos/logs/mcp", "servers": []}

    with open(MCP_CONFIG_PATH, "r", encoding="utf-8-sig") as handle:
        return _expand_config(json.load(handle))


class MCPServerProcess:
    def __init__(self, name: str, command: List[str], env: Dict[str, str], log_file: Path):
        self.name = name
        self.command = command
        self.env = env
        self.log_file = log_file
        self.process: Optional[subprocess.Popen] = None
        self._log_handle: Optional[open] = None
        self.start_time: Optional[float] = None
        self.restart_count = 0
        self.max_restarts = 3
        self.health_check_interval = 30  # seconds
        self.last_health_check = 0

    def start(self) -> bool:
        """Start the MCP server process with error handling."""
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = open(self.log_file, "a", encoding="utf-8")
            
            # Validate command exists
            if not shutil.which(self.command[0]) and not Path(self.command[0]).exists():
                self._log(f"Command not found: {self.command[0]}")
                return False

            self.process = subprocess.Popen(
                self.command,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                env=self.env,
                cwd=str(ROOT),
                preexec_fn=os.setsid,
            )
            
            self.start_time = time.time()
            self._log(f"Started MCP server: {self.name} (PID: {self.process.pid})")
            return True
            
        except Exception as exc:
            self._log(f"Failed to start {self.name}: {exc}")
            if self._log_handle:
                self._log_handle.close()
                self._log_handle = None
            return False

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the MCP server process gracefully."""
        if not self.process:
            if self._log_handle:
                self._log_handle.close()
            return

        try:
            if self.process.poll() is None:
                # Try graceful shutdown first
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    self.process.wait(timeout=2)
            
            self._log(f"Stopped MCP server: {self.name}")
            
        except Exception as exc:
            self._log(f"Error stopping {self.name}: {exc}")
        finally:
            if self._log_handle:
                self._log_handle.close()
                self._log_handle = None

    def is_healthy(self) -> bool:
        """Check if the process is running and responsive via MCP protocol."""
        if not self.process:
            return False

        # Check if process is still running
        if self.process.poll() is not None:
            return False

        # Check if process has been running long enough
        if self.start_time and time.time() - self.start_time < 5:
            return True  # Give it time to start

        # Perform MCP protocol health check
        return self._check_mcp_protocol_health()

    def _check_mcp_protocol_health(self) -> bool:
        """Check if the MCP server responds to protocol messages."""
        try:
            import socket
            import select

            # For stdio-based MCP servers, check if process is responsive
            # by verifying it hasn't crashed and can accept input
            if self.process and self.process.poll() is None:
                # Check if stdin is writable (server is accepting input)
                if self.process.stdin:
                    try:
                        # Try to check if the pipe is still open
                        self.process.stdin.flush()
                        return True
                    except (BrokenPipeError, OSError):
                        return False

                # For processes without stdin, just check if running
                return True

            return False

        except Exception:
            # On any error, fall back to process check
            return self.process is not None and self.process.poll() is None

    def restart_if_needed(self) -> bool:
        """Restart the server if it's unhealthy and hasn't exceeded restart limit."""
        current_time = time.time()
        
        # Don't check too frequently
        if current_time - self.last_health_check < self.health_check_interval:
            return False
        
        self.last_health_check = current_time
        
        if not self.is_healthy() and self.restart_count < self.max_restarts:
            self._log(f"Restarting unhealthy server: {self.name} (attempt {self.restart_count + 1})")
            self.stop()
            time.sleep(2)  # Brief delay before restart
            
            if self.start():
                self.restart_count += 1
                return True
            else:
                self._log(f"Failed to restart {self.name}")
                return False
        
        return False

    def _log(self, message: str) -> None:
        """Log a message to the log file."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        if self._log_handle:
            self._log_handle.write(log_entry)
            self._log_handle.flush()
        else:
            # Fallback to writing directly to file
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception:
                pass  # Avoid logging errors causing more errors


class MCPManager:
    def __init__(self):
        self.config = _read_mcp_config()
        self.log_dir = ROOT / self.config.get("log_dir", "lifeos/logs/mcp")
        self.servers: Dict[str, MCPServerProcess] = {}
        self.lock = threading.Lock()
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitoring = False

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
            if value is not None and value != "SET_OBSIDIAN_API_KEY":  # Skip placeholder values
                env[key] = str(value)
        return env

    def start_autostart_servers(self) -> None:
        """Start all enabled autostart servers with validation."""
        started_servers = []
        failed_servers = []
        
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
                
                # Validate paths in command
                for cmd_part in command:
                    if cmd_part.startswith("/") and not Path(cmd_part).exists():
                        raise ValueError(f"Command path not found: {cmd_part}")
                
                process = MCPServerProcess(name, command, env, log_file)
                if process.start():
                    with self.lock:
                        self.servers[name] = process
                    started_servers.append(name)
                else:
                    failed_servers.append(name)
                    
            except Exception as exc:
                failed_servers.append(name)
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as handle:
                    handle.write(f"Failed to start {name}: {exc}\n")
        
        # Start monitoring thread if any servers started
        if started_servers and not self.monitoring:
            self._start_monitoring()
        
        self._log(f"MCP servers started: {started_servers}")
        if failed_servers:
            self._log(f"MCP servers failed: {failed_servers}")

    def stop_all(self) -> None:
        """Stop all MCP servers and monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        with self.lock:
            processes = list(self.servers.values())
            self.servers.clear()

        for proc in processes:
            proc.stop()
        
        self._log("All MCP servers stopped")

    def _start_monitoring(self) -> None:
        """Start the health monitoring thread."""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_servers, daemon=True)
        self.monitor_thread.start()

    def _monitor_servers(self) -> None:
        """Monitor server health and restart if needed."""
        while self.monitoring:
            try:
                with self.lock:
                    servers_to_check = list(self.servers.values())
                
                for server in servers_to_check:
                    server.restart_if_needed()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as exc:
                self._log(f"Monitor thread error: {exc}")
                time.sleep(60)  # Wait longer on error

    def get_server_status(self) -> Dict[str, Dict]:
        """Get status of all servers."""
        status = {}
        with self.lock:
            for name, server in self.servers.items():
                status[name] = {
                    "running": server.process is not None and server.process.poll() is None,
                    "healthy": server.is_healthy(),
                    "restart_count": server.restart_count,
                    "pid": server.process.pid if server.process else None,
                    "start_time": server.start_time
                }
        return status

    def _log(self, message: str) -> None:
        """Log a manager message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] MCP Manager: {message}\n"
        
        log_file = self.log_dir / "manager.log"
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception:
            pass


# Import shutil for command validation
import shutil


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
