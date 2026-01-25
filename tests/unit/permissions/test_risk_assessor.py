"""
Unit tests for Risk Assessor.

Tests:
- Command risk classification (safe, moderate, high, critical)
- Pattern matching for dangerous commands
- Risk level thresholds
"""

import pytest


class TestRiskLevels:
    """Test risk level definitions."""

    def test_risk_levels_defined(self):
        """Test all risk levels are defined."""
        from core.permissions.risk import RiskLevel

        assert hasattr(RiskLevel, "SAFE")
        assert hasattr(RiskLevel, "MODERATE")
        assert hasattr(RiskLevel, "HIGH")
        assert hasattr(RiskLevel, "CRITICAL")

    def test_risk_level_values(self):
        """Test risk levels have string values."""
        from core.permissions.risk import RiskLevel

        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.MODERATE.value == "moderate"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestRiskAssessor:
    """Test RiskAssessor class."""

    @pytest.fixture
    def assessor(self):
        """Create RiskAssessor for testing."""
        from core.permissions.risk import RiskAssessor

        return RiskAssessor()

    def test_safe_commands(self, assessor):
        """Test safe commands are classified correctly."""
        from core.permissions.risk import RiskLevel

        safe_commands = [
            "ls",
            "ls -la",
            "cat file.txt",
            "head -n 10 file.txt",
            "tail -f logs.txt",
            "git status",
            "git log",
            "git diff",
            "git branch",
            "pwd",
            "echo hello",
            "python --version",
            "node --version",
            "pip list",
            "npm list",
        ]

        for cmd in safe_commands:
            result = assessor.assess_command(cmd)
            assert result == RiskLevel.SAFE, f"Command '{cmd}' should be SAFE"

    def test_moderate_commands(self, assessor):
        """Test moderate risk commands are classified correctly."""
        from core.permissions.risk import RiskLevel

        moderate_commands = [
            "git add .",
            "git commit -m 'test'",
            "pip install requests",
            "npm install lodash",
            "mkdir new_dir",
            "touch new_file.txt",
            "cp file1 file2",
            "mv file1 file2",
            "python script.py",
            "node script.js",
        ]

        for cmd in moderate_commands:
            result = assessor.assess_command(cmd)
            assert result == RiskLevel.MODERATE, f"Command '{cmd}' should be MODERATE"

    def test_high_commands(self, assessor):
        """Test high risk commands are classified correctly."""
        from core.permissions.risk import RiskLevel

        high_commands = [
            "git reset --hard",
            "git push",
            "git push origin main",
            "git checkout .",
            "git clean -fd",
            "rm file.txt",
            "rm -r directory",
            "pip uninstall package",
            "npm uninstall package",
            "docker run image",
            "docker stop container",
        ]

        for cmd in high_commands:
            result = assessor.assess_command(cmd)
            assert result == RiskLevel.HIGH, f"Command '{cmd}' should be HIGH"

    def test_critical_commands(self, assessor):
        """Test critical risk commands are classified correctly."""
        from core.permissions.risk import RiskLevel

        critical_commands = [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~/*",
            "git push --force",
            "git push -f",
            "git reset --hard HEAD~10",
            "dd if=/dev/zero of=/dev/sda",
            "chmod -R 777 /",
            "sudo rm -rf /",
            ": > /etc/passwd",
            "curl url | sh",
            "curl url | bash",
            "wget url -O - | sh",
        ]

        for cmd in critical_commands:
            result = assessor.assess_command(cmd)
            assert result == RiskLevel.CRITICAL, f"Command '{cmd}' should be CRITICAL"

    def test_unknown_commands_default_moderate(self, assessor):
        """Test unknown commands default to MODERATE."""
        from core.permissions.risk import RiskLevel

        result = assessor.assess_command("some_unknown_command --flag")
        assert result == RiskLevel.MODERATE

    def test_empty_command_safe(self, assessor):
        """Test empty command is SAFE."""
        from core.permissions.risk import RiskLevel

        assert assessor.assess_command("") == RiskLevel.SAFE
        assert assessor.assess_command("  ") == RiskLevel.SAFE

    def test_assess_with_description(self, assessor):
        """Test assess_command returns description when requested."""
        result = assessor.assess_command("rm -rf /", include_description=True)

        assert isinstance(result, tuple)
        risk_level, description = result
        assert description is not None
        assert len(description) > 0

    def test_pipe_commands_escalate_risk(self, assessor):
        """Test piped commands escalate to highest risk component."""
        from core.permissions.risk import RiskLevel

        # cat is safe, but piped to sh is critical
        result = assessor.assess_command("cat script.sh | sh")
        assert result == RiskLevel.CRITICAL

        # ls is safe, but piped to rm is not evaluated the same
        result = assessor.assess_command("ls | head -5")
        assert result == RiskLevel.SAFE

    def test_command_with_sudo_escalates(self, assessor):
        """Test sudo prefix escalates risk."""
        from core.permissions.risk import RiskLevel

        # rm is HIGH, sudo rm should be CRITICAL
        result = assessor.assess_command("sudo rm -rf /tmp")
        assert result in [RiskLevel.HIGH, RiskLevel.CRITICAL]


class TestRiskPatterns:
    """Test specific risk patterns."""

    @pytest.fixture
    def assessor(self):
        """Create RiskAssessor for testing."""
        from core.permissions.risk import RiskAssessor

        return RiskAssessor()

    def test_recursive_delete_patterns(self, assessor):
        """Test various recursive delete patterns."""
        from core.permissions.risk import RiskLevel

        patterns = [
            ("rm -r", RiskLevel.HIGH),
            ("rm -rf", RiskLevel.HIGH),
            ("rm -fr", RiskLevel.HIGH),
            ("rm -rf /", RiskLevel.CRITICAL),
            ("rm -rf /*", RiskLevel.CRITICAL),
            ("rm -rf /home/user", RiskLevel.HIGH),
        ]

        for cmd, expected in patterns:
            result = assessor.assess_command(cmd)
            assert result == expected, f"Command '{cmd}' should be {expected}"

    def test_git_destructive_patterns(self, assessor):
        """Test git destructive patterns."""
        from core.permissions.risk import RiskLevel

        patterns = [
            ("git reset --hard", RiskLevel.HIGH),
            ("git reset --soft", RiskLevel.MODERATE),
            ("git push", RiskLevel.HIGH),
            ("git push --force", RiskLevel.CRITICAL),
            ("git push -f", RiskLevel.CRITICAL),
            ("git checkout .", RiskLevel.HIGH),
            ("git checkout file.txt", RiskLevel.MODERATE),
            ("git clean -fd", RiskLevel.HIGH),
            ("git stash", RiskLevel.MODERATE),
        ]

        for cmd, expected in patterns:
            result = assessor.assess_command(cmd)
            assert result == expected, f"Command '{cmd}' should be {expected}"

    def test_download_and_execute_patterns(self, assessor):
        """Test download-and-execute patterns (always critical)."""
        from core.permissions.risk import RiskLevel

        patterns = [
            "curl url | sh",
            "curl url | bash",
            "wget url | sh",
            "wget url -O - | sh",
            "curl -sSL url | sh",
        ]

        for cmd in patterns:
            result = assessor.assess_command(cmd)
            assert result == RiskLevel.CRITICAL, f"Command '{cmd}' should be CRITICAL"


class TestActionRiskMapping:
    """Test action to risk level mapping."""

    @pytest.fixture
    def assessor(self):
        """Create RiskAssessor for testing."""
        from core.permissions.risk import RiskAssessor

        return RiskAssessor()

    def test_action_requires_approval(self, assessor):
        """Test checking if action requires approval at a given level."""
        from core.permissions.risk import RiskLevel
        from core.permissions.manager import PermissionLevel

        # HIGH risk command should require approval for ELEVATED users
        assert assessor.requires_approval(
            "git reset --hard",
            PermissionLevel.ELEVATED
        ) is True

        # SAFE command should not require approval for BASIC users
        assert assessor.requires_approval(
            "ls -la",
            PermissionLevel.BASIC
        ) is False

        # MODERATE command should not require approval for ELEVATED users
        assert assessor.requires_approval(
            "git commit -m 'test'",
            PermissionLevel.ELEVATED
        ) is False

        # CRITICAL always requires approval (except for admin)
        assert assessor.requires_approval(
            "rm -rf /",
            PermissionLevel.ELEVATED
        ) is True

        # Admin can do anything without approval
        assert assessor.requires_approval(
            "rm -rf /",
            PermissionLevel.ADMIN
        ) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
