"""
Unit tests for the Skill Executor.

Tests the ability to execute skill scripts with arguments and capture output.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


class TestSkillExecutor:
    """Tests for SkillExecutor class."""

    def test_executor_initializes_with_registry(self, tmp_path):
        """Executor should initialize with a SkillRegistry."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        registry = SkillRegistry(skills_dir=tmp_path)
        executor = SkillExecutor(registry=registry)

        assert executor.registry is registry

    def test_execute_runs_script_and_captures_output(self, tmp_path):
        """execute should run skill script and capture stdout."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        # Create skill
        skill_dir = tmp_path / "echo"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Echo\nEchoes args.")
        (skill_dir / "script.py").write_text("""import sys
print(f"Echo: {' '.join(sys.argv[1:])}")
""")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()
        executor = SkillExecutor(registry=registry)

        result = executor.execute("echo", ["Hello", "World"])

        assert result.success is True
        assert "Echo: Hello World" in result.output
        assert result.exit_code == 0

    def test_execute_captures_stderr_on_error(self, tmp_path):
        """execute should capture stderr when script fails."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        # Create failing skill
        skill_dir = tmp_path / "fail"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Fail\nThis fails.")
        (skill_dir / "script.py").write_text("""import sys
print("Error occurred", file=sys.stderr)
sys.exit(1)
""")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()
        executor = SkillExecutor(registry=registry)

        result = executor.execute("fail", [])

        assert result.success is False
        assert "Error occurred" in result.stderr
        assert result.exit_code == 1

    def test_execute_returns_error_for_nonexistent_skill(self, tmp_path):
        """execute should return error for non-existent skill."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()
        executor = SkillExecutor(registry=registry)

        result = executor.execute("nonexistent", [])

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_execute_respects_timeout(self, tmp_path):
        """execute should timeout long-running scripts."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        # Create slow skill
        skill_dir = tmp_path / "slow"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Slow\nTakes forever.")
        (skill_dir / "script.py").write_text("""import time
time.sleep(10)
print("done")
""")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()
        executor = SkillExecutor(registry=registry, timeout=1)

        result = executor.execute("slow", [])

        assert result.success is False
        assert result.timed_out is True
        assert "timeout" in result.error.lower()

    def test_execute_passes_environment_variables(self, tmp_path):
        """execute should pass specified environment variables."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        # Create skill that reads env
        skill_dir = tmp_path / "env_test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Env Test\nReads env.")
        (skill_dir / "script.py").write_text("""import os
print(f"VALUE={os.environ.get('TEST_VAR', 'not set')}")
""")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()
        executor = SkillExecutor(registry=registry)

        result = executor.execute("env_test", [], env={"TEST_VAR": "hello"})

        assert result.success is True
        assert "VALUE=hello" in result.output

    def test_execute_isolates_working_directory(self, tmp_path):
        """execute should run script in skill directory."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        # Create skill that prints cwd
        skill_dir = tmp_path / "cwd_test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# CWD Test\nPrints cwd.")
        (skill_dir / "script.py").write_text("""import os
print(os.getcwd())
""")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()
        executor = SkillExecutor(registry=registry)

        result = executor.execute("cwd_test", [])

        assert result.success is True
        # Normalize paths for comparison
        assert str(skill_dir).replace("\\", "/").lower() in result.output.replace("\\", "/").lower()


class TestSkillExecutionResult:
    """Tests for SkillExecutionResult dataclass."""

    def test_result_attributes(self):
        """SkillExecutionResult should have all expected attributes."""
        from core.skills.executor import SkillExecutionResult

        result = SkillExecutionResult(
            success=True,
            output="test output",
            stderr="",
            exit_code=0,
            error=None,
            timed_out=False,
            execution_time=0.5,
        )

        assert result.success is True
        assert result.output == "test output"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.error is None
        assert result.timed_out is False
        assert result.execution_time == 0.5


class TestAsyncSkillExecutor:
    """Tests for async skill execution."""

    @pytest.mark.asyncio
    async def test_execute_async_runs_skill(self, tmp_path):
        """execute_async should run skill asynchronously."""
        from core.skills.executor import SkillExecutor
        from core.skills.registry import SkillRegistry

        # Create skill
        skill_dir = tmp_path / "async_test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Async Test\nAsync test.")
        (skill_dir / "script.py").write_text("print('async works')")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()
        executor = SkillExecutor(registry=registry)

        result = await executor.execute_async("async_test", [])

        assert result.success is True
        assert "async works" in result.output
