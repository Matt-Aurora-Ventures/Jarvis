"""
Command watchdog to prevent indefinite hangs.
Monitors active subprocess calls and force-kills them if they exceed timeout.
"""

import logging
import threading
import time
from typing import Dict, Optional
import psutil

logger = logging.getLogger(__name__)


class CommandWatchdog:
    """Monitors running commands and kills them if they hang."""
    
    def __init__(self, check_interval: int = 10):
        self.check_interval = check_interval
        self.active_commands: Dict[int, Dict] = {}
        self.lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def register(self, pid: int, command: str, timeout: int, started_at: float):
        """Register a command for monitoring."""
        with self.lock:
            self.active_commands[pid] = {
                "command": command,
                "timeout": timeout,
                "started_at": started_at,
                "killed": False,
            }
            logger.debug(f"Watchdog tracking PID {pid}: {command[:50]}")
    
    def unregister(self, pid: int):
        """Unregister a completed command."""
        with self.lock:
            if pid in self.active_commands:
                del self.active_commands[pid]
                logger.debug(f"Watchdog stopped tracking PID {pid}")
    
    def start(self):
        """Start the watchdog monitoring thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Command watchdog started")
    
    def stop(self):
        """Stop the watchdog."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Command watchdog stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_commands()
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
            
            time.sleep(self.check_interval)
    
    def _check_commands(self):
        """Check all active commands for timeouts."""
        now = time.time()
        
        with self.lock:
            to_kill = []
            
            for pid, info in list(self.active_commands.items()):
                age = now - info["started_at"]
                timeout = info["timeout"]
                
                # Add 10 second grace period beyond timeout
                if age > (timeout + 10) and not info["killed"]:
                    logger.warning(
                        f"Watchdog detected hung command (PID {pid}, age {int(age)}s, "
                        f"timeout {timeout}s): {info['command'][:80]}"
                    )
                    to_kill.append((pid, info["command"]))
                    info["killed"] = True
        
        # Kill processes outside the lock
        for pid, command in to_kill:
            self._force_kill(pid, command)
    
    def _force_kill(self, pid: int, command: str):
        """Force kill a process and its children."""
        try:
            proc = psutil.Process(pid)
            logger.error(f"Watchdog FORCE KILLING PID {pid}: {command[:80]}")
            
            # Kill children first
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Kill parent
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        except psutil.NoSuchProcess:
            logger.debug(f"PID {pid} already terminated")
        except Exception as e:
            logger.error(f"Failed to kill PID {pid}: {e}")


# Global watchdog instance
_watchdog: Optional[CommandWatchdog] = None


def get_watchdog() -> CommandWatchdog:
    """Get or create the global watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = CommandWatchdog()
        _watchdog.start()
    return _watchdog


def shutdown_watchdog():
    """Shutdown the global watchdog."""
    global _watchdog
    if _watchdog is not None:
        _watchdog.stop()
        _watchdog = None
