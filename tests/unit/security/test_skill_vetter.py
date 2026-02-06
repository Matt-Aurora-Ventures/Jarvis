"""
Tests for Skill Vetter - Security scanning for ClawdBot skills.

Tests cover:
- Secret detection (API keys, tokens, passwords)
- Dangerous code patterns (eval, exec, subprocess)
- Permission validation from skill manifests
- Report generation
"""

import pytest
import tempfile
from pathlib import Path
from typing import Optional

# Import will fail until we implement the module
from core.security.skill_vetter import (
    SkillVetter,
    VetResult,
    SecuritySeverity,
    SecurityFinding,
)


class TestSkillVetter:
    """Test suite for SkillVetter class."""

    @pytest.fixture
    def vetter(self) -> SkillVetter:
        """Create a SkillVetter instance."""
        return SkillVetter()

    @pytest.fixture
    def safe_skill(self, tmp_path: Path) -> Path:
        """Create a safe skill for testing."""
        skill_dir = tmp_path / "safe-skill"
        skill_dir.mkdir()

        # SKILL.md
        (skill_dir / "SKILL.md").write_text(
            "# Safe Skill\n\nA completely safe skill that does nothing harmful.\n"
        )

        # script.py - safe code
        (skill_dir / "script.py").write_text('''"""Safe skill script."""

def run(context: dict, **kwargs) -> str:
    """Run the skill safely."""
    name = kwargs.get("name", "World")
    return f"Hello, {name}!"
''')

        # config.json
        (skill_dir / "config.json").write_text('{"permissions": ["read"]}')

        return skill_dir

    @pytest.fixture
    def skill_with_secrets(self, tmp_path: Path) -> Path:
        """Create a skill containing hardcoded secrets."""
        skill_dir = tmp_path / "secret-skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("# Secret Skill\n\nContains secrets.\n")
        (skill_dir / "script.py").write_text('''"""Skill with hardcoded secrets."""

API_KEY = "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TELEGRAM_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"
PASSWORD = "my_secret_password_123"

def run(context: dict, **kwargs) -> str:
    return "done"
''')

        return skill_dir

    @pytest.fixture
    def skill_with_dangerous_calls(self, tmp_path: Path) -> Path:
        """Create a skill with dangerous function calls."""
        skill_dir = tmp_path / "dangerous-skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("# Dangerous Skill\n\nUses eval/exec.\n")
        (skill_dir / "script.py").write_text('''"""Skill with dangerous calls."""
import subprocess
import os

def run(context: dict, **kwargs) -> str:
    user_code = kwargs.get("code", "")
    # Dangerous: arbitrary code execution
    result = eval(user_code)
    exec("print('hello')")
    subprocess.run(["rm", "-rf", "/tmp/test"])
    os.system("echo hello")
    return str(result)
''')

        return skill_dir

    @pytest.fixture
    def skill_with_excessive_permissions(self, tmp_path: Path) -> Path:
        """Create a skill requesting too many permissions."""
        skill_dir = tmp_path / "perms-skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("# Permissions Skill\n\nNeeds lots of perms.\n")
        (skill_dir / "script.py").write_text('''"""Skill with permissions."""

def run(context: dict, **kwargs) -> str:
    return "done"
''')
        (skill_dir / "config.json").write_text('''{
    "permissions": [
        "filesystem:write",
        "network:all",
        "execute:shell",
        "admin:root"
    ]
}''')

        return skill_dir

    # --- Basic Vetting Tests ---

    def test_vet_safe_skill_passes(self, vetter: SkillVetter, safe_skill: Path):
        """A safe skill should pass vetting."""
        result = vetter.vet_skill(safe_skill)

        assert result.is_safe is True
        assert len(result.findings) == 0
        assert result.skill_path == safe_skill

    def test_vet_nonexistent_path_fails(self, vetter: SkillVetter, tmp_path: Path):
        """Vetting a non-existent path should fail."""
        result = vetter.vet_skill(tmp_path / "nonexistent")

        assert result.is_safe is False
        assert any("not found" in f.message.lower() for f in result.findings)

    def test_vet_returns_vet_result_type(self, vetter: SkillVetter, safe_skill: Path):
        """vet_skill should return a VetResult instance."""
        result = vetter.vet_skill(safe_skill)

        assert isinstance(result, VetResult)
        assert hasattr(result, "is_safe")
        assert hasattr(result, "findings")
        assert hasattr(result, "skill_path")

    # --- Secret Detection Tests ---

    def test_detects_api_keys(self, vetter: SkillVetter, skill_with_secrets: Path):
        """Should detect hardcoded API keys."""
        result = vetter.vet_skill(skill_with_secrets)

        assert result.is_safe is False
        assert any(f.category == "secrets" for f in result.findings)
        # Check for specific secret types
        messages = [f.message.lower() for f in result.findings]
        assert any("api" in m or "key" in m for m in messages)

    def test_detects_telegram_tokens(self, vetter: SkillVetter, skill_with_secrets: Path):
        """Should detect Telegram bot tokens."""
        result = vetter.vet_skill(skill_with_secrets)

        assert result.is_safe is False
        # Should find the telegram token pattern
        token_findings = [f for f in result.findings if "telegram" in f.message.lower()]
        assert len(token_findings) > 0

    def test_detects_aws_credentials(self, vetter: SkillVetter, skill_with_secrets: Path):
        """Should detect AWS access keys."""
        result = vetter.vet_skill(skill_with_secrets)

        aws_findings = [f for f in result.findings if "aws" in f.message.lower()]
        assert len(aws_findings) > 0

    def test_check_for_secrets_method(self, vetter: SkillVetter):
        """Test the check_for_secrets method directly."""
        code_with_secret = '''
API_KEY = "sk-ant-api03-xxxxxxxxxxxx"
'''
        findings = vetter.check_for_secrets(code_with_secret, "test.py")

        assert len(findings) > 0
        assert findings[0].category == "secrets"
        assert findings[0].severity in [SecuritySeverity.HIGH, SecuritySeverity.CRITICAL]

    def test_no_false_positives_on_safe_code(self, vetter: SkillVetter):
        """Should not flag safe code as containing secrets."""
        safe_code = '''
def get_api_key():
    """Load API key from environment."""
    import os
    return os.environ.get("API_KEY")
'''
        findings = vetter.check_for_secrets(safe_code, "test.py")

        # Should have no findings or only low-severity warnings
        critical_findings = [f for f in findings if f.severity == SecuritySeverity.CRITICAL]
        assert len(critical_findings) == 0

    # --- Dangerous Call Detection Tests ---

    def test_detects_eval(self, vetter: SkillVetter, skill_with_dangerous_calls: Path):
        """Should detect use of eval()."""
        result = vetter.vet_skill(skill_with_dangerous_calls)

        assert result.is_safe is False
        eval_findings = [f for f in result.findings if "eval" in f.message.lower()]
        assert len(eval_findings) > 0

    def test_detects_exec(self, vetter: SkillVetter, skill_with_dangerous_calls: Path):
        """Should detect use of exec()."""
        result = vetter.vet_skill(skill_with_dangerous_calls)

        exec_findings = [f for f in result.findings if "exec" in f.message.lower()]
        assert len(exec_findings) > 0

    def test_detects_subprocess(self, vetter: SkillVetter, skill_with_dangerous_calls: Path):
        """Should detect subprocess usage."""
        result = vetter.vet_skill(skill_with_dangerous_calls)

        subprocess_findings = [f for f in result.findings if "subprocess" in f.message.lower()]
        assert len(subprocess_findings) > 0

    def test_detects_os_system(self, vetter: SkillVetter, skill_with_dangerous_calls: Path):
        """Should detect os.system() usage."""
        result = vetter.vet_skill(skill_with_dangerous_calls)

        os_system_findings = [f for f in result.findings if "os.system" in f.message.lower()]
        assert len(os_system_findings) > 0

    def test_check_for_dangerous_calls_method(self, vetter: SkillVetter):
        """Test the check_for_dangerous_calls method directly."""
        dangerous_code = '''
import os
result = eval(user_input)
'''
        findings = vetter.check_for_dangerous_calls(dangerous_code, "test.py")

        assert len(findings) > 0
        assert any("eval" in f.message.lower() for f in findings)
        assert findings[0].category == "dangerous_code"

    def test_detects_pickle_load(self, vetter: SkillVetter):
        """Should detect pickle.load (deserialization vulnerability)."""
        code = '''
import pickle
with open("data.pkl", "rb") as f:
    data = pickle.load(f)
'''
        findings = vetter.check_for_dangerous_calls(code, "test.py")

        pickle_findings = [f for f in findings if "pickle" in f.message.lower()]
        assert len(pickle_findings) > 0

    # --- Permission Validation Tests ---

    def test_validates_safe_permissions(self, vetter: SkillVetter, safe_skill: Path):
        """Safe permissions should not raise flags."""
        result = vetter.vet_skill(safe_skill)

        perm_findings = [f for f in result.findings if f.category == "permissions"]
        assert len(perm_findings) == 0

    def test_flags_dangerous_permissions(
        self, vetter: SkillVetter, skill_with_excessive_permissions: Path
    ):
        """Dangerous permissions should be flagged."""
        result = vetter.vet_skill(skill_with_excessive_permissions)

        assert result.is_safe is False
        perm_findings = [f for f in result.findings if f.category == "permissions"]
        assert len(perm_findings) > 0

    def test_check_permissions_method(self, vetter: SkillVetter):
        """Test the check_permissions method directly."""
        manifest = {
            "permissions": ["execute:shell", "admin:root", "network:all"]
        }
        findings = vetter.check_permissions(manifest)

        assert len(findings) > 0
        assert all(f.category == "permissions" for f in findings)

    def test_missing_manifest_is_acceptable(self, vetter: SkillVetter, tmp_path: Path):
        """Skills without config.json should still be vettable."""
        skill_dir = tmp_path / "no-config-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# No Config\n\nNo config.json.\n")
        (skill_dir / "script.py").write_text('def run(context, **kwargs): return "ok"')

        result = vetter.vet_skill(skill_dir)

        # Should not crash, might have a warning but should still be safe if no other issues
        assert isinstance(result, VetResult)

    # --- Report Generation Tests ---

    def test_generate_report_returns_string(self, vetter: SkillVetter, safe_skill: Path):
        """generate_report should return a string."""
        report = vetter.generate_report(safe_skill)

        assert isinstance(report, str)
        assert len(report) > 0

    def test_report_includes_skill_path(self, vetter: SkillVetter, safe_skill: Path):
        """Report should include the skill path."""
        report = vetter.generate_report(safe_skill)

        assert str(safe_skill) in report or safe_skill.name in report

    def test_report_includes_findings(
        self, vetter: SkillVetter, skill_with_secrets: Path
    ):
        """Report should include all findings."""
        report = vetter.generate_report(skill_with_secrets)

        # Should mention secrets were found
        assert "secret" in report.lower() or "api" in report.lower()

    def test_report_shows_safe_status(self, vetter: SkillVetter, safe_skill: Path):
        """Report should indicate if skill is safe."""
        report = vetter.generate_report(safe_skill)

        assert "safe" in report.lower() or "passed" in report.lower()

    def test_report_json_format(self, vetter: SkillVetter, safe_skill: Path):
        """Report should be valid JSON when format specified."""
        import json

        report = vetter.generate_report(safe_skill, format="json")
        data = json.loads(report)

        assert "is_safe" in data
        assert "findings" in data
        assert "skill_path" in data


class TestVetResult:
    """Tests for VetResult dataclass."""

    def test_vet_result_is_safe_when_no_critical_findings(self):
        """VetResult.is_safe should be True when no critical/high findings."""
        result = VetResult(
            skill_path=Path("/tmp/test"),
            findings=[
                SecurityFinding(
                    category="info",
                    severity=SecuritySeverity.LOW,
                    message="Just a note",
                    file="test.py",
                    line=1,
                )
            ],
        )

        assert result.is_safe is True

    def test_vet_result_unsafe_with_high_severity(self):
        """VetResult.is_safe should be False with high severity findings."""
        result = VetResult(
            skill_path=Path("/tmp/test"),
            findings=[
                SecurityFinding(
                    category="secrets",
                    severity=SecuritySeverity.HIGH,
                    message="Found API key",
                    file="test.py",
                    line=5,
                )
            ],
        )

        assert result.is_safe is False


class TestSecurityFinding:
    """Tests for SecurityFinding dataclass."""

    def test_security_finding_has_required_fields(self):
        """SecurityFinding should have all required fields."""
        finding = SecurityFinding(
            category="secrets",
            severity=SecuritySeverity.HIGH,
            message="Found hardcoded API key",
            file="script.py",
            line=10,
        )

        assert finding.category == "secrets"
        assert finding.severity == SecuritySeverity.HIGH
        assert finding.message == "Found hardcoded API key"
        assert finding.file == "script.py"
        assert finding.line == 10


class TestSecuritySeverity:
    """Tests for SecuritySeverity enum."""

    def test_severity_levels_exist(self):
        """All expected severity levels should exist."""
        assert hasattr(SecuritySeverity, "LOW")
        assert hasattr(SecuritySeverity, "MEDIUM")
        assert hasattr(SecuritySeverity, "HIGH")
        assert hasattr(SecuritySeverity, "CRITICAL")

    def test_severity_ordering(self):
        """Severity levels should be orderable."""
        assert SecuritySeverity.LOW.value < SecuritySeverity.MEDIUM.value
        assert SecuritySeverity.MEDIUM.value < SecuritySeverity.HIGH.value
        assert SecuritySeverity.HIGH.value < SecuritySeverity.CRITICAL.value
