"""
Skill Executor - Runs skill scripts and captures output.

Executes Python scripts in isolated subprocesses with timeout support.
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


@dataclass
class SkillExecutionResult:
    """Result of a skill execution."""

    success: bool
    output: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: Optional[str] = None
    timed_out: bool = False
    execution_time: float = 0.0


class SkillExecutor:
    """
    Executes skill scripts in isolated subprocesses.

    Supports:
    - Synchronous and asynchronous execution
    - Timeout enforcement
    - Environment variable passing
    - Working directory isolation
    - Output capture (stdout/stderr)
    """

    def __init__(
        self,
        registry: SkillRegistry,
        timeout: int = 30,
        python_path: Optional[str] = None,
    ):
        """
        Initialize the skill executor.

        Args:
            registry: SkillRegistry instance for skill lookup.
            timeout: Default timeout in seconds for skill execution.
            python_path: Path to Python interpreter. Defaults to sys.executable.
        """
        self.registry = registry
        self.timeout = timeout
        self.python_path = python_path or sys.executable

    def execute(
        self,
        skill_name: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> SkillExecutionResult:
        """
        Execute a skill script synchronously.

        Args:
            skill_name: Name of the skill to execute.
            args: Arguments to pass to the script.
            env: Additional environment variables.
            timeout: Override default timeout.

        Returns:
            SkillExecutionResult with execution details.
        """
        skill = self.registry.get_skill(skill_name)

        if skill is None:
            # Try loading it
            skill = self.registry.load_skill(skill_name)

        if skill is None:
            return SkillExecutionResult(
                success=False,
                error=f"Skill '{skill_name}' not found",
                exit_code=-1,
            )

        skill_path: Path = skill["path"]
        script_path = skill_path / "script.py"

        if not script_path.exists():
            return SkillExecutionResult(
                success=False,
                error=f"Script not found: {script_path}",
                exit_code=-1,
            )

        # Build command
        cmd = [self.python_path, str(script_path)] + args

        # Build environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        # Execute with timeout
        effective_timeout = timeout if timeout is not None else self.timeout
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(skill_path),
                env=process_env,
            )

            execution_time = time.time() - start_time

            return SkillExecutionResult(
                success=result.returncode == 0,
                output=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time,
            )

        except subprocess.TimeoutExpired:
            return SkillExecutionResult(
                success=False,
                error=f"Timeout after {effective_timeout} seconds",
                timed_out=True,
                execution_time=effective_timeout,
            )

        except Exception as e:
            return SkillExecutionResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def execute_async(
        self,
        skill_name: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> SkillExecutionResult:
        """
        Execute a skill script asynchronously.

        Args:
            skill_name: Name of the skill to execute.
            args: Arguments to pass to the script.
            env: Additional environment variables.
            timeout: Override default timeout.

        Returns:
            SkillExecutionResult with execution details.
        """
        skill = self.registry.get_skill(skill_name)

        if skill is None:
            skill = self.registry.load_skill(skill_name)

        if skill is None:
            return SkillExecutionResult(
                success=False,
                error=f"Skill '{skill_name}' not found",
                exit_code=-1,
            )

        skill_path: Path = skill["path"]
        script_path = skill_path / "script.py"

        if not script_path.exists():
            return SkillExecutionResult(
                success=False,
                error=f"Script not found: {script_path}",
                exit_code=-1,
            )

        # Build environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        effective_timeout = timeout if timeout is not None else self.timeout
        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_exec(
                self.python_path,
                str(script_path),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(skill_path),
                env=process_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return SkillExecutionResult(
                    success=False,
                    error=f"Timeout after {effective_timeout} seconds",
                    timed_out=True,
                    execution_time=effective_timeout,
                )

            execution_time = time.time() - start_time

            return SkillExecutionResult(
                success=process.returncode == 0,
                output=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                execution_time=execution_time,
            )

        except Exception as e:
            return SkillExecutionResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )
