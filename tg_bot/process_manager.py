"""
Process Manager for Jarvis Telegram Bot.

Handles proper subprocess management to prevent zombie processes:
1. Tracks all spawned subprocesses
2. Reaps zombie children via signal handlers
3. Kills remaining children on shutdown
4. Prevents orphan accumulation

Root cause of zombies:
- subprocess.run() or asyncio.create_subprocess_exec() creates child processes
- If parent dies before calling wait(), children become zombies
- This module ensures proper cleanup via SIGCHLD handling and shutdown hooks

Usage:
    from tg_bot.process_manager import setup_process_manager, cleanup_processes
    
    # At startup
    setup_process_manager()
    
    # At shutdown
    await cleanup_processes()
"""

import asyncio
import atexit
import logging
import os
import signal
import sys
from typing import Set, Optional
from weakref import WeakSet

logger = logging.getLogger(__name__)

# Track active subprocess PIDs
_active_pids: Set[int] = set()
_active_processes: WeakSet = WeakSet()  # Track asyncio.subprocess.Process objects
_shutdown_in_progress = False


def _reap_zombies(signum=None, frame=None):
    """
    SIGCHLD handler - reap zombie children immediately.
    
    This is called when any child process terminates.
    We use os.waitpid with WNOHANG to reap without blocking.
    """
    if _shutdown_in_progress:
        return
        
    while True:
        try:
            # WNOHANG: don't block if no children are ready
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                # No more children to reap
                break
            
            # Remove from tracking
            _active_pids.discard(pid)
            
            exit_code = os.waitstatus_to_exitcode(status) if hasattr(os, 'waitstatus_to_exitcode') else status
            logger.debug(f"Reaped child process {pid}, exit code: {exit_code}")
            
        except ChildProcessError:
            # No child processes exist
            break
        except Exception as e:
            logger.debug(f"Error in reap_zombies: {e}")
            break


def track_subprocess(pid: int):
    """Track a subprocess PID for cleanup."""
    _active_pids.add(pid)
    logger.debug(f"Tracking subprocess PID {pid}")


def track_async_process(proc):
    """Track an asyncio.subprocess.Process for cleanup."""
    _active_processes.add(proc)
    if proc.pid:
        _active_pids.add(proc.pid)
    logger.debug(f"Tracking async process PID {proc.pid}")


def untrack_subprocess(pid: int):
    """Remove subprocess from tracking (after it completes)."""
    _active_pids.discard(pid)


def _kill_remaining_children():
    """Kill any remaining tracked child processes."""
    global _shutdown_in_progress
    _shutdown_in_progress = True
    
    if not _active_pids and not _active_processes:
        return
        
    logger.info(f"Cleaning up {len(_active_pids)} tracked processes...")
    
    # Kill async processes
    for proc in list(_active_processes):
        try:
            if proc.returncode is None:  # Still running
                logger.info(f"Killing async process {proc.pid}")
                proc.kill()
        except Exception as e:
            logger.debug(f"Error killing async process: {e}")
    
    # Kill by PID
    for pid in list(_active_pids):
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info(f"Sent SIGTERM to PID {pid}")
        except ProcessLookupError:
            # Already dead
            pass
        except Exception as e:
            logger.debug(f"Error killing PID {pid}: {e}")
    
    # Give them a moment to die gracefully
    import time
    time.sleep(0.5)
    
    # SIGKILL any remaining
    for pid in list(_active_pids):
        try:
            os.kill(pid, signal.SIGKILL)
            logger.info(f"Sent SIGKILL to PID {pid}")
        except ProcessLookupError:
            pass
        except Exception:
            pass
    
    # Final reap
    _reap_zombies()


async def cleanup_processes():
    """Async cleanup of processes at shutdown."""
    _kill_remaining_children()


def _cleanup_existing_zombies():
    """Clean up any existing zombie processes at startup."""
    try:
        import subprocess
        # Get our process ID
        our_pid = os.getpid()
        
        # Find zombie children of init (PPID=1) that are python processes
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,stat,comm", "--no-headers"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        zombies_killed = 0
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 4:
                pid, ppid, stat, comm = parts[0], parts[1], parts[2], parts[3]
                # Check for zombie state (Z)
                if 'Z' in stat and ppid == '1' and 'python' in comm:
                    # Can't actually kill zombies - they're already dead
                    # But we can log them for awareness
                    logger.info(f"Found zombie process: PID={pid} (will be reaped by init)")
                    zombies_killed += 1
        
        if zombies_killed > 0:
            logger.warning(f"Found {zombies_killed} zombie python processes - these are from previous bot instances")
            
    except Exception as e:
        logger.debug(f"Error checking for zombies: {e}")


def setup_process_manager():
    """
    Set up process management at bot startup.
    
    Must be called early in main() before any subprocesses are spawned.
    """
    logger.info("Setting up process manager for zombie prevention")
    
    # Install SIGCHLD handler to reap zombies immediately
    try:
        signal.signal(signal.SIGCHLD, _reap_zombies)
        logger.info("SIGCHLD handler installed - zombies will be reaped automatically")
    except Exception as e:
        logger.warning(f"Could not install SIGCHLD handler: {e}")
    
    # Register atexit handler for final cleanup
    atexit.register(_kill_remaining_children)
    
    # Clean up any existing zombies from previous runs
    _cleanup_existing_zombies()
    
    # Perform initial reap in case there are orphans
    _reap_zombies()
    
    logger.info("Process manager initialized")


def create_subprocess_with_tracking(*args, **kwargs):
    """
    Wrapper for asyncio.create_subprocess_exec that tracks the process.
    
    Use this instead of direct asyncio.create_subprocess_exec calls.
    """
    async def _create():
        proc = await asyncio.create_subprocess_exec(*args, **kwargs)
        track_async_process(proc)
        return proc
    return _create()


# Export for use in other modules
__all__ = [
    'setup_process_manager',
    'cleanup_processes', 
    'track_subprocess',
    'track_async_process',
    'untrack_subprocess',
    'create_subprocess_with_tracking',
]
