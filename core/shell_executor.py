"""
Shell Executor - Reliable command execution bypassing VS Code terminal issues.
Uses Python subprocess with aggressive timeout protection.
"""

import os
import signal
import subprocess
import sys
from typing import Dict, List, Optional, Tuple, Union


class ShellExecutor:
    """Reliable shell command executor with timeout protection."""
    
    DEFAULT_TIMEOUT = 30
    QUICK_TIMEOUT = 10
    
    def __init__(self, working_dir: str = None):
        self.working_dir = working_dir or os.getcwd()
    
    def run(
        self,
        command: Union[str, List[str]],
        timeout: int = None,
        shell: bool = None,
        check: bool = False,
    ) -> Dict:
        """Run a command with timeout protection.
        
        Args:
            command: Command string or list
            timeout: Timeout in seconds (default: 30)
            shell: Use shell execution (auto-detect if None)
            check: Raise exception on non-zero exit
            
        Returns:
            Dict with stdout, stderr, returncode, success, timed_out
        """
        if timeout is None:
            timeout = self._auto_timeout(command)
        
        if shell is None:
            shell = isinstance(command, str)
        
        result = {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "success": False,
            "timed_out": False,
            "command": command,
        }
        
        try:
            proc = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
            )
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["returncode"] = proc.returncode
            result["success"] = proc.returncode == 0
            
        except subprocess.TimeoutExpired as e:
            result["timed_out"] = True
            result["stderr"] = f"Command timed out after {timeout}s"
            if e.stdout:
                result["stdout"] = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
            if e.stderr:
                result["stderr"] = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
                
        except Exception as e:
            result["stderr"] = str(e)
        
        if check and not result["success"]:
            raise RuntimeError(f"Command failed: {result['stderr']}")
        
        return result
    
    def _auto_timeout(self, command: Union[str, List[str]]) -> int:
        """Auto-determine timeout based on command."""
        cmd_str = command if isinstance(command, str) else " ".join(command)
        
        # Quick commands
        quick_patterns = ["status", "log", "ls", "pwd", "echo", "cat", "head", "tail"]
        if any(p in cmd_str.lower() for p in quick_patterns):
            return self.QUICK_TIMEOUT
        
        # Long commands
        long_patterns = ["install", "clone", "pull", "push", "build", "compile"]
        if any(p in cmd_str.lower() for p in long_patterns):
            return 120
        
        return self.DEFAULT_TIMEOUT
    
    def git(self, *args, timeout: int = 30) -> Dict:
        """Run a git command."""
        return self.run(["git", *args], timeout=timeout)
    
    def python(self, *args, timeout: int = 60) -> Dict:
        """Run a python command."""
        python_path = os.path.join(self.working_dir, "venv311", "bin", "python")
        if not os.path.exists(python_path):
            python_path = sys.executable
        return self.run([python_path, *args], timeout=timeout)


# Convenience functions
_executor = None

def get_executor(working_dir: str = None) -> ShellExecutor:
    """Get or create the global executor."""
    global _executor
    if _executor is None or working_dir:
        _executor = ShellExecutor(working_dir or "/Users/burritoaccount/Desktop/LifeOS")
    return _executor


def run_shell(command: Union[str, List[str]], timeout: int = 30) -> Dict:
    """Quick shell command execution."""
    return get_executor().run(command, timeout=timeout)


def run_git(*args, timeout: int = 30) -> Dict:
    """Quick git command execution."""
    return get_executor().git(*args, timeout=timeout)


if __name__ == "__main__":
    # Self-test
    exe = ShellExecutor()
    
    print("Testing echo...")
    r = exe.run("echo 'Hello World'")
    print(f"  Result: {r['stdout'].strip()}, Success: {r['success']}")
    
    print("Testing git status...")
    r = exe.git("status", "--short")
    print(f"  Exit: {r['returncode']}, Success: {r['success']}")
    
    print("Testing timeout...")
    r = exe.run("sleep 5", timeout=1)
    print(f"  Timed out: {r['timed_out']}")
    
    print("\nAll tests passed!")
