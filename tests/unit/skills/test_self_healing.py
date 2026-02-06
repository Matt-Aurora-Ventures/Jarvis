"""
Unit tests for the Self-Healing Skill Acquisition system.

Tests the ability to:
- Search for skills from registries (skills.sh, local)
- Auto-install pre-authorized skills
- Verify skill installation
- Update TOOLS.md after installation
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


class TestSkillRegistrySearch:
    """Tests for skill registry search functionality."""

    def test_search_skills_returns_matches(self, tmp_path):
        """search_skills should return matching skills from local registry."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        # Create a local skill
        skill_dir = tmp_path / "docker"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# Docker Skill
Manage Docker containers.
""")
        (skill_dir / "script.py").write_text("print('docker')")

        registry = SelfHealingSkillRegistry(skills_dir=tmp_path)
        results = registry.search_skills("docker")

        assert len(results) > 0
        assert any("docker" in r.get("name", "").lower() for r in results)

    def test_search_skills_returns_empty_for_no_match(self, tmp_path):
        """search_skills should return empty list when no matches found."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        registry = SelfHealingSkillRegistry(skills_dir=tmp_path)
        results = registry.search_skills("nonexistent_skill_xyz")

        assert results == []

    def test_search_skills_queries_remote_registry(self, tmp_path):
        """search_skills should query skills.sh when enabled."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        with patch("core.skills.self_healing.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "skills": [
                    {
                        "name": "linux-service-triage",
                        "description": "Systemd service management",
                        "verified": True,
                    }
                ]
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            registry = SelfHealingSkillRegistry(
                skills_dir=tmp_path, enable_remote_search=True
            )
            results = registry.search_skills("systemctl")

            assert len(results) > 0
            assert any("linux-service-triage" in r.get("name", "") for r in results)


class TestSkillInstallation:
    """Tests for skill installation functionality."""

    def test_install_skill_from_local(self, tmp_path):
        """install_skill should install from local source."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        # Create source skill
        source_dir = tmp_path / "sources" / "test-skill"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# Test Skill\nA test.")
        (source_dir / "script.py").write_text("print('test')")

        # Create target skills directory
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
        result = registry.install_skill("test-skill", source=source_dir)

        assert result.success is True
        assert (skills_dir / "test-skill" / "SKILL.md").exists()
        assert (skills_dir / "test-skill" / "script.py").exists()

    def test_install_skill_respects_pre_authorized_list(self, tmp_path):
        """install_skill should only auto-install pre-authorized skills."""
        from core.skills.self_healing import SelfHealingSkillRegistry, RiskLevel

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
        registry.pre_authorized_skills = ["docker", "pm2"]

        # Authorized skill
        assert registry.is_pre_authorized("docker") is True

        # Unauthorized skill
        assert registry.is_pre_authorized("dangerous-tool") is False

    def test_install_skill_logs_installation(self, tmp_path):
        """install_skill should log all installation attempts."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        log_path = tmp_path / "install.log"

        # Create source skill
        source_dir = tmp_path / "sources" / "logged-skill"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# Logged Skill\nA test.")
        (source_dir / "script.py").write_text("print('logged')")

        registry = SelfHealingSkillRegistry(
            skills_dir=skills_dir, install_log_path=log_path
        )
        registry.install_skill("logged-skill", source=source_dir)

        assert log_path.exists()
        log_content = log_path.read_text()
        assert "logged-skill" in log_content


class TestSkillVerification:
    """Tests for skill verification functionality."""

    def test_verify_skill_checks_script_exists(self, tmp_path):
        """verify_skill should check if script.py exists."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create incomplete skill (no script)
        skill_dir = skills_dir / "broken"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Broken\nNo script.")

        registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
        result = registry.verify_skill("broken")

        assert result is False

    def test_verify_skill_checks_syntax(self, tmp_path):
        """verify_skill should check Python syntax is valid."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create skill with bad syntax
        skill_dir = skills_dir / "bad-syntax"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Bad\nSyntax error.")
        (skill_dir / "script.py").write_text("def broken(:\n  pass")  # Invalid

        registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
        result = registry.verify_skill("bad-syntax")

        assert result is False

    def test_verify_skill_returns_true_for_valid(self, tmp_path):
        """verify_skill should return True for valid skill."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create valid skill
        skill_dir = skills_dir / "valid"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Valid\nWorks.")
        (skill_dir / "script.py").write_text("print('valid')")

        registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
        result = registry.verify_skill("valid")

        assert result is True


class TestToolsUpdate:
    """Tests for TOOLS.md update functionality."""

    def test_update_tools_md_adds_skill_entry(self, tmp_path):
        """update_tools_md should add skill entry to TOOLS.md."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        tools_path = tmp_path / "TOOLS.md"
        tools_path.write_text("# Tools\n\nExisting tools.\n")

        registry = SelfHealingSkillRegistry(
            skills_dir=skills_dir, tools_md_path=tools_path
        )

        registry.update_tools_md(
            skill_name="new-skill",
            description="A newly installed skill",
            version="1.0.0",
        )

        content = tools_path.read_text()
        assert "new-skill" in content
        assert "newly installed skill" in content
        assert "Auto-Installed" in content


class TestSessionQuota:
    """Tests for session installation quota."""

    def test_respects_max_installs_per_session(self, tmp_path):
        """Should enforce max installs per session limit."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        registry = SelfHealingSkillRegistry(
            skills_dir=skills_dir, max_installs_per_session=2
        )

        # First install should succeed
        assert registry.can_auto_install() is True
        registry._increment_install_counter()

        # Second install should succeed
        assert registry.can_auto_install() is True
        registry._increment_install_counter()

        # Third install should be blocked
        assert registry.can_auto_install() is False


class TestRiskLevels:
    """Tests for skill risk level handling."""

    def test_risk_level_blocks_high_risk_auto_install(self, tmp_path):
        """Should block auto-install of HIGH risk skills."""
        from core.skills.self_healing import SelfHealingSkillRegistry, RiskLevel

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
        registry.max_auto_install_risk = RiskLevel.MEDIUM

        # LOW risk should be allowed
        assert registry.is_risk_acceptable(RiskLevel.LOW) is True

        # MEDIUM risk should be allowed
        assert registry.is_risk_acceptable(RiskLevel.MEDIUM) is True

        # HIGH risk should be blocked
        assert registry.is_risk_acceptable(RiskLevel.HIGH) is False

        # CRITICAL risk should be blocked
        assert registry.is_risk_acceptable(RiskLevel.CRITICAL) is False


class TestSelfHealingExecution:
    """Tests for the execute_with_healing wrapper."""

    @pytest.mark.asyncio
    async def test_execute_with_healing_retries_after_install(self, tmp_path):
        """execute_with_healing should retry task after installing skill."""
        from core.skills.self_healing import SelfHealingSkillRegistry
        from core.skills.self_healing import execute_with_healing, ToolNotFoundError

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create skill that will be "discovered" and installed
        source_skill = tmp_path / "sources" / "missing-tool"
        source_skill.mkdir(parents=True)
        (source_skill / "SKILL.md").write_text("# Missing Tool\nProvides the tool.")
        (source_skill / "script.py").write_text("print('tool found')")

        registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
        registry.pre_authorized_skills = ["missing-tool"]
        registry._skill_sources = {"missing-tool": source_skill}

        call_count = 0

        async def task_that_needs_tool():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ToolNotFoundError("missing-tool")
            return "success"

        result = await execute_with_healing(task_that_needs_tool, registry)

        assert result == "success"
        assert call_count == 2  # First attempt + retry


class TestEnvironmentVariable:
    """Tests for environment variable configuration."""

    def test_auto_install_disabled_by_env(self, tmp_path):
        """Auto-install should be disabled when env var is false."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        with patch.dict(os.environ, {"JARVIS_AUTO_SKILL_INSTALL": "false"}):
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()

            registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
            assert registry.auto_install_enabled is False

    def test_auto_install_enabled_by_env(self, tmp_path):
        """Auto-install should be enabled when env var is true."""
        from core.skills.self_healing import SelfHealingSkillRegistry

        with patch.dict(os.environ, {"JARVIS_AUTO_SKILL_INSTALL": "true"}):
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()

            registry = SelfHealingSkillRegistry(skills_dir=skills_dir)
            assert registry.auto_install_enabled is True
