"""
Autonomous Restart System for Jarvis.
Allows Jarvis to restart itself when needed for new integrations.
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, providers, evolution, guardian

ROOT = Path(__file__).resolve().parents[1]
RESTART_PATH = ROOT / "data" / "restarts"
RESTART_LOG_PATH = ROOT / "data" / "restart.log"
RESTART_FLAG_PATH = ROOT / "data" / ".restart_flag"
RESTART_STATE_PATH = ROOT / "data" / "restart_state.json"


class AutonomousRestart:
    """Manages autonomous restarts for Jarvis."""
    
    def __init__(self):
        self.restart_db = RESTART_PATH / "restarts.json"
        self._ensure_directories()
        self._load_restart_data()
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        RESTART_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_restart_data(self):
        """Load restart history and state."""
        if self.restart_db.exists():
            with open(self.restart_db, "r") as f:
                self.restart_data = json.load(f)
        else:
            self.restart_data = {
                "restart_history": [],
                "restart_triggers": [],
                "last_restart": None,
                "restart_count": 0,
                "auto_restart_enabled": True
            }
        
        # Load restart state if exists
        if RESTART_STATE_PATH.exists():
            with open(RESTART_STATE_PATH, "r") as f:
                self.restart_state = json.load(f)
        else:
            self.restart_state = {
                "pending_restart": False,
                "restart_reason": "",
                "restart_time": None,
                "preserve_state": {}
            }
    
    def _save_restart_data(self):
        """Save restart data."""
        with open(self.restart_db, "w") as f:
            json.dump(self.restart_data, f, indent=2)
        with open(RESTART_STATE_PATH, "w") as f:
            json.dump(self.restart_state, f, indent=2)
    
    def _log_restart(self, action: str, details: Dict[str, Any]):
        """Log restart activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        with open(RESTART_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def check_restart_needed(self, improvements: List[Dict[str, Any]]) -> bool:
        """Check if a restart is needed based on recent improvements."""
        if not self.restart_data["auto_restart_enabled"]:
            return False
        
        restart_triggers = [
            "core module modification",
            "provider system update",
            "autonomous controller change",
            "new dependency added",
            "system configuration change",
            "import system modification"
        ]
        
        for improvement in improvements:
            title = improvement.get("title", "").lower()
            files = improvement.get("files_to_modify", [])
            
            # Check if improvement affects core systems
            if any(trigger in title for trigger in restart_triggers):
                return True
            
            # Check if core files are modified
            core_files = [
                "core/__init__.py",
                "core/autonomous_controller.py",
                "core/providers.py",
                "core/evolution.py",
                "core/config.py"
            ]
            
            if any(file in core_files for file in files):
                return True
        
        return False
    
    def schedule_restart(self, reason: str, preserve_state: Optional[Dict[str, Any]] = None):
        """Schedule a restart with reason and state preservation."""
        self.restart_state["pending_restart"] = True
        self.restart_state["restart_reason"] = reason
        self.restart_state["restart_time"] = datetime.now().isoformat()
        self.restart_state["preserve_state"] = preserve_state or {}
        
        # Create restart flag file
        with open(RESTART_FLAG_PATH, "w") as f:
            f.write(f"Restart scheduled: {reason}\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
        
        self._save_restart_data()
        self._log_restart("restart_scheduled", {
            "reason": reason,
            "preserve_state_keys": list(preserve_state.keys()) if preserve_state else []
        })
    
    def execute_restart(self):
        """Execute the autonomous restart."""
        restart_info = {
            "timestamp": datetime.now().isoformat(),
            "reason": self.restart_state["restart_reason"],
            "pid": os.getpid(),
            "success": False
        }
        
        try:
            self._log_restart("restart_initiated", restart_info)
            
            # Save current state
            self._save_current_state()
            
            # Update restart history
            self.restart_data["restart_history"].append(restart_info)
            self.restart_data["last_restart"] = restart_info["timestamp"]
            self.restart_data["restart_count"] += 1
            self._save_restart_data()
            
            # Clean up restart flag
            if RESTART_FLAG_PATH.exists():
                RESTART_FLAG_PATH.unlink()
            
            # Restart Jarvis
            self._restart_jarvis()
            
        except Exception as e:
            restart_info["error"] = str(e)
            self._log_restart("restart_failed", restart_info)
            
            # Clean up on failure
            if RESTART_FLAG_PATH.exists():
                RESTART_FLAG_PATH.unlink()
            self.restart_state["pending_restart"] = False
            self._save_restart_data()
    
    def _save_current_state(self):
        """Save current state for restoration after restart."""
        current_state = {
            "timestamp": datetime.now().isoformat(),
            "cwd": os.getcwd(),
            "python_path": sys.path,
            "environment": dict(os.environ),
            "restart_reason": self.restart_state["restart_reason"],
            "preserve_state": self.restart_state["preserve_state"]
        }
        
        state_file = RESTART_PATH / f"state_{int(time.time())}.json"
        with open(state_file, "w") as f:
            json.dump(current_state, f, indent=2)
        
        self._log_restart("state_saved", {"state_file": str(state_file)})
    
    def _restart_jarvis(self):
        """Restart Jarvis process."""
        try:
            # Get current script path
            current_script = sys.argv[0] if sys.argv else "main.py"
            
            # Prepare restart command
            restart_cmd = [sys.executable, current_script]
            
            # Add any original arguments
            if len(sys.argv) > 1:
                restart_cmd.extend(sys.argv[1:])
            
            # Add restart flag
            restart_cmd.append("--autonomous-restart")
            restart_cmd.append(f"--restart-reason={self.restart_state['restart_reason']}")
            
            self._log_restart("executing_restart", {
                "command": restart_cmd,
                "current_pid": os.getpid()
            })
            
            # Start new process
            subprocess.Popen(restart_cmd, cwd=os.getcwd())
            
            # Give new process time to start
            time.sleep(2)
            
            # Exit current process
            os._exit(0)
            
        except Exception as e:
            self._log_restart("restart_execution_error", {"error": str(e)})
            raise
    
    def check_restart_flag(self) -> bool:
        """Check if Jarvis was restarted."""
        return RESTART_FLAG_PATH.exists()
    
    def restore_state(self) -> Dict[str, Any]:
        """Restore state after restart."""
        if not self.restart_state["pending_restart"]:
            return {}
        
        restored_state = {
            "restored_at": datetime.now().isoformat(),
            "restart_reason": self.restart_state["restart_reason"],
            "preserve_state": self.restart_state["preserve_state"]
        }
        
        # Clear restart state
        self.restart_state["pending_restart"] = False
        self.restart_state["restart_reason"] = ""
        self.restart_state["restart_time"] = None
        self._save_restart_data()
        
        self._log_restart("state_restored", restored_state)
        
        return restored_state
    
    def get_restart_status(self) -> Dict[str, Any]:
        """Get current restart status."""
        return {
            "auto_restart_enabled": self.restart_data["auto_restart_enabled"],
            "pending_restart": self.restart_state["pending_restart"],
            "restart_reason": self.restart_state["restart_reason"],
            "last_restart": self.restart_data["last_restart"],
            "restart_count": self.restart_data["restart_count"],
            "recent_history": self.restart_data["restart_history"][-5:]
        }
    
    def enable_auto_restart(self, enabled: bool = True):
        """Enable or disable auto restart."""
        self.restart_data["auto_restart_enabled"] = enabled
        self._save_restart_data()
        self._log_restart("auto_restart_toggled", {"enabled": enabled})
    
    def handle_improvement_integration(self, improvements: List[Dict[str, Any]]):
        """Handle restart logic after improvement integration."""
        if self.check_restart_needed(improvements):
            # Determine restart reason
            reasons = []
            for improvement in improvements:
                title = improvement.get("title", "")
                if "core" in title.lower():
                    reasons.append(f"Core modification: {title}")
                elif "provider" in title.lower():
                    reasons.append(f"Provider update: {title}")
                elif "autonomous" in title.lower():
                    reasons.append(f"Autonomous system change: {title}")
            
            reason = "; ".join(reasons) if reasons else "System integration required"
            
            # Schedule restart
            preserve_state = {
                "last_improvements": improvements,
                "restart_triggered_by": "improvement_integration"
            }
            
            self.schedule_restart(reason, preserve_state)
            
            return True
        
        return False


# Global autonomous restart instance
_restart_manager: Optional[AutonomousRestart] = None


def get_autonomous_restart() -> AutonomousRestart:
    """Get the global autonomous restart instance."""
    global _restart_manager
    if not _restart_manager:
        _restart_manager = AutonomousRestart()
    return _restart_manager


def check_for_restart_flag():
    """Check if Jarvis was restarted and handle restoration."""
    restart_manager = get_autonomous_restart()
    
    if restart_manager.check_restart_flag():
        restored_state = restart_manager.restore_state()
        return restored_state
    
    return None


def schedule_autonomous_restart(reason: str, preserve_state: Optional[Dict[str, Any]] = None):
    """Schedule an autonomous restart."""
    restart_manager = get_autonomous_restart()
    restart_manager.schedule_restart(reason, preserve_state)


def execute_autonomous_restart():
    """Execute the scheduled autonomous restart."""
    restart_manager = get_autonomous_restart()
    restart_manager.execute_restart()
