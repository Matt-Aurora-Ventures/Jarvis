"""
Emergency process kill utility for LifeOS.
Use when processes hang indefinitely despite timeout protections.
"""

import os
import signal
import subprocess
import psutil
from typing import List, Dict

MAX_SUBPROCESS_AGE = 300  # 5 minutes


def kill_hanging_processes(dry_run: bool = False) -> Dict[str, List[str]]:
    """Find and kill hanging Python subprocesses.
    
    Args:
        dry_run: If True, only report what would be killed
        
    Returns:
        Dictionary with 'found' and 'killed' process lists
    """
    current_pid = os.getpid()
    parent_proc = psutil.Process(current_pid)
    
    found = []
    killed = []
    
    # Find all children
    children = parent_proc.children(recursive=True)
    
    for child in children:
        try:
            # Get process info
            cmdline = " ".join(child.cmdline())
            age = child.create_time()
            current_time = psutil.time.time()
            age_seconds = current_time - age
            
            # Check if it's been running too long
            if age_seconds > MAX_SUBPROCESS_AGE:
                found.append(f"PID {child.pid}: {cmdline[:80]} (age: {int(age_seconds)}s)")
                
                if not dry_run:
                    try:
                        child.kill()
                        killed.append(f"Killed PID {child.pid}")
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.AccessDenied:
                        killed.append(f"Access denied to kill PID {child.pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return {
        "found": found,
        "killed": killed if not dry_run else [],
        "dry_run": dry_run,
    }


def force_kill_by_pattern(pattern: str, dry_run: bool = False) -> Dict[str, List[str]]:
    """Kill processes matching a command pattern.
    
    Args:
        pattern: String to match in command line
        dry_run: If True, only report what would be killed
        
    Returns:
        Dictionary with 'found' and 'killed' process lists
    """
    found = []
    killed = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            if pattern.lower() in cmdline.lower():
                found.append(f"PID {proc.pid}: {cmdline[:80]}")
                
                if not dry_run:
                    try:
                        proc.kill()
                        killed.append(f"Killed PID {proc.pid}")
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.AccessDenied:
                        killed.append(f"Access denied to kill PID {proc.pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            continue
    
    return {
        "found": found,
        "killed": killed if not dry_run else [],
        "dry_run": dry_run,
        "pattern": pattern,
    }


def emergency_reset() -> None:
    """Nuclear option: kill all child processes immediately."""
    current_pid = os.getpid()
    parent_proc = psutil.Process(current_pid)
    
    children = parent_proc.children(recursive=True)
    
    print(f"🚨 EMERGENCY RESET: Killing {len(children)} child processes")
    
    for child in children:
        try:
            print(f"  Killing PID {child.pid}: {' '.join(child.cmdline()[:3])}")
            child.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    print("✅ Emergency reset complete")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "emergency":
        emergency_reset()
    else:
        result = kill_hanging_processes(dry_run=True)
        print("Hanging processes found:")
        for proc in result["found"]:
            print(f"  - {proc}")
        
        if result["found"]:
            print("\nRun with 'emergency' argument to kill them")
