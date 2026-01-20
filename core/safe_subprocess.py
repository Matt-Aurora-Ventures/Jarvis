"""
Safe subprocess execution wrapper with aggressive timeout protection.
Prevents hanging commands from blocking LifeOS operations.
"""

import asyncio
import logging
import os
import signal
import subprocess
import threading
from typing import Any, Dict, Optional, Tuple, Union

from core.timeout_config import get_command_timeout, get_timeout
from core.command_validator import validate_before_run

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when a command times out."""
    pass


class CommandExecutionError(Exception):
    """Raised when a command fails to execute."""
    pass


def _kill_process_tree(pid: int):
    """Kill a process and all its children."""
    try:
        import psutil
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except Exception:  # noqa: BLE001 - intentional catch-all
                pass
        try:
            parent.kill()
        except Exception:  # noqa: BLE001 - intentional catch-all
            pass
    except ImportError:
        # Fallback without psutil
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:  # noqa: BLE001 - intentional catch-all
            pass


def run_command_safe(
    command: Union[str, list],
    timeout: Optional[int] = None,
    shell: bool = None,
    capture_output: bool = True,
    check: bool = False,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    skip_validation: bool = False,
) -> Dict[str, Any]:
    """Run a command with aggressive timeout protection.
    
    Args:
        command: Command to execute
        timeout: Timeout in seconds (auto-determined if None)
        shell: Run in shell
        capture_output: Capture stdout/stderr
        check: Raise error on non-zero exit
        cwd: Working directory
        env: Environment variables
        skip_validation: Skip command validation (use with caution)
        
    Returns:
        Dict with stdout, stderr, returncode, timed_out, killed
        
    Raises:
        TimeoutError: If command times out
        CommandExecutionError: If command fails and check=True
    """
    # Auto-determine shell mode if not specified
    if shell is None:
        shell = isinstance(command, str)
    
    # Validate command unless skipped
    if not skip_validation:
        cmd_str = command if isinstance(command, str) else " ".join(command)
        is_safe, error, warnings = validate_before_run(cmd_str)
        if not is_safe:
            logger.error(f"Blocked unsafe command: {error}")
            return {
                "stdout": "",
                "stderr": f"Command blocked by validator: {error}",
                "returncode": -1,
                "timed_out": False,
                "killed": False,
                "blocked": True,
                "command": cmd_str,
            }
        
        # Log warnings but allow execution
        for warning in warnings:
            logger.warning(f"Command warning: {warning}")
    
    # Auto-determine timeout if not specified
    if timeout is None:
        cmd_str = command if isinstance(command, str) else " ".join(command)
        timeout = get_command_timeout(cmd_str)
    
    # Log long-running command warnings
    if timeout > 30:
        cmd_str = command if isinstance(command, str) else " ".join(command)
        logger.warning(f"Command may take up to {timeout}s: {cmd_str[:100]}")
    
    result = {
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "timed_out": False,
        "killed": False,
        "blocked": False,
        "command": command,
        "timeout": timeout,
    }
    
    # Register with watchdog
    from core.command_watchdog import get_watchdog
    watchdog = get_watchdog()
    started_at = __import__('time').time()
    
    try:
        proc = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True,
            cwd=cwd,
            env=env,
        )
        
        # Register with watchdog for monitoring
        cmd_str = command if isinstance(command, str) else " ".join(command)
        watchdog.register(proc.pid, cmd_str, timeout, started_at)
        
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            result["stdout"] = stdout or ""
            result["stderr"] = stderr or ""
            result["returncode"] = proc.returncode
            
        except subprocess.TimeoutExpired:
            # Force kill the process tree
            cmd_str = command if isinstance(command, str) else " ".join(command)
            logger.error(f"Command timed out after {timeout}s: {cmd_str[:100]}")
            result["timed_out"] = True
            result["killed"] = True
            
            # Kill process tree
            _kill_process_tree(proc.pid)
            
            # Try to get partial output
            try:
                stdout, stderr = proc.communicate(timeout=1)
                result["stdout"] = stdout or ""
                result["stderr"] = stderr or ""
            except Exception:  # noqa: BLE001 - intentional catch-all
                pass
        
        finally:
            # Always unregister from watchdog
            watchdog.unregister(proc.pid)
            if result["timed_out"]:
                result["stderr"] += (
                    f"\n[TIMEOUT] Command exceeded {timeout}s limit and was killed"
                )
                if check:
                    raise TimeoutError(f"Command timed out after {timeout}s: {command}")
                
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        result["stderr"] = str(e)
        if check:
            raise CommandExecutionError(f"Failed to execute: {command}") from e
    
    return result


async def run_command_async(
    command: str,
    timeout: Optional[int] = None,
    shell: bool = True,
    capture_output: bool = True,
    check: bool = False,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run a command asynchronously with timeout protection.
    
    Args:
        command: Command to execute
        timeout: Timeout in seconds (auto-determined if None)
        shell: Run in shell
        capture_output: Capture stdout/stderr
        check: Raise error on non-zero exit
        cwd: Working directory
        env: Environment variables
        
    Returns:
        Dict with stdout, stderr, returncode, timed_out, killed
    """
    # Auto-determine timeout if not specified
    if timeout is None:
        timeout = get_command_timeout(command)
    
    result = {
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "timed_out": False,
        "killed": False,
        "command": command,
        "timeout": timeout,
    }
    
    try:
        if shell:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                cwd=cwd,
                env=env,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *command.split(),
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                cwd=cwd,
                env=env,
            )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            result["stdout"] = stdout.decode() if stdout else ""
            result["stderr"] = stderr.decode() if stderr else ""
            result["returncode"] = proc.returncode
            
        except asyncio.TimeoutError:
            logger.error(f"Async command timed out after {timeout}s: {command[:100]}")
            result["timed_out"] = True
            result["killed"] = True
            
            # Kill process
            try:
                proc.kill()
                await proc.wait()
            except Exception:  # noqa: BLE001 - intentional catch-all
                pass
            
            result["stderr"] = f"[TIMEOUT] Command exceeded {timeout}s limit and was killed"
            
            if check:
                raise TimeoutError(f"Command timed out after {timeout}s: {command}")
                
    except Exception as e:
        logger.error(f"Async command execution error: {e}")
        result["stderr"] = str(e)
        if check:
            raise CommandExecutionError(f"Failed to execute: {command}") from e
    
    return result


def run_with_live_output(
    command: str,
    timeout: Optional[int] = None,
    callback = None,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """Run command with live output streaming.
    
    Args:
        command: Command to execute
        timeout: Timeout in seconds
        callback: Optional callback(line: str) for each output line
        cwd: Working directory
        
    Returns:
        Dict with stdout, stderr, returncode, timed_out
    """
    if timeout is None:
        timeout = get_command_timeout(command)
    
    result = {
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "timed_out": False,
    }
    
    start_time = time.time()
    
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        
        stdout_lines = []
        
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                result["timed_out"] = True
                _kill_process_tree(proc.pid)
                result["stderr"] = f"[TIMEOUT] Killed after {timeout}s"
                break
            
            line = proc.stdout.readline()
            if not line:
                break
                
            stdout_lines.append(line)
            if callback:
                callback(line.rstrip())
        
        proc.wait(timeout=1)
        result["stdout"] = "".join(stdout_lines)
        result["returncode"] = proc.returncode
        
    except Exception as e:
        logger.error(f"Live output command error: {e}")
        result["stderr"] = str(e)
    
    return result


import time


def split_long_command_chain(command: str, max_chain_length: int = 3) -> list:
    """Split a long command chain into smaller chunks.
    
    Args:
        command: Command string with &&, ||, |, or ; chains
        max_chain_length: Maximum commands per chunk
        
    Returns:
        List of command chunks
    """
    # Simple splitting by && (most common)
    if "&&" in command:
        parts = command.split("&&")
        chunks = []
        current_chunk = []
        
        for part in parts:
            current_chunk.append(part.strip())
            if len(current_chunk) >= max_chain_length:
                chunks.append(" && ".join(current_chunk))
                current_chunk = []
        
        if current_chunk:
            chunks.append(" && ".join(current_chunk))
        
        return chunks
    
    return [command]
