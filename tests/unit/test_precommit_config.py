"""
Tests for pre-commit configuration files.
Validates that all required hooks and configurations are properly set up.
"""

import os
import yaml
import configparser
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestPreCommitConfig:
    """Test .pre-commit-config.yaml file."""

    @pytest.fixture
    def config_path(self):
        return PROJECT_ROOT / ".pre-commit-config.yaml"

    @pytest.fixture
    def config(self, config_path):
        assert config_path.exists(), f"Pre-commit config not found at {config_path}"
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def test_config_file_exists(self, config_path):
        """Pre-commit config file must exist."""
        assert config_path.exists(), "Missing .pre-commit-config.yaml"

    def test_has_repos_section(self, config):
        """Config must have repos section."""
        assert "repos" in config, "Config must have 'repos' section"
        assert isinstance(config["repos"], list), "repos must be a list"
        assert len(config["repos"]) > 0, "repos must not be empty"

    def test_has_black_hook(self, config):
        """Black formatter must be configured."""
        repos = config["repos"]
        black_found = any(
            "black" in repo.get("repo", "").lower()
            for repo in repos
        )
        assert black_found, "Black hook not found in config"

    def test_has_isort_hook(self, config):
        """isort import sorter must be configured."""
        repos = config["repos"]
        isort_found = any(
            "isort" in repo.get("repo", "").lower()
            for repo in repos
        )
        assert isort_found, "isort hook not found in config"

    def test_has_flake8_hook(self, config):
        """Flake8 linter must be configured."""
        repos = config["repos"]
        flake8_found = any(
            "flake8" in repo.get("repo", "").lower()
            for repo in repos
        )
        assert flake8_found, "flake8 hook not found in config"

    def test_has_mypy_hook(self, config):
        """mypy type checker must be configured."""
        repos = config["repos"]
        mypy_found = any(
            "mypy" in str(repo.get("repo", "")).lower() or
            any("mypy" in h.get("id", "") for h in repo.get("hooks", []))
            for repo in repos
        )
        assert mypy_found, "mypy hook not found in config"

    def test_has_yaml_checker(self, config):
        """YAML syntax checker must be configured."""
        repos = config["repos"]
        yaml_found = any(
            any("check-yaml" in h.get("id", "") for h in repo.get("hooks", []))
            for repo in repos
        )
        assert yaml_found, "check-yaml hook not found in config"

    def test_has_json_checker(self, config):
        """JSON syntax checker must be configured."""
        repos = config["repos"]
        json_found = any(
            any("check-json" in h.get("id", "") for h in repo.get("hooks", []))
            for repo in repos
        )
        assert json_found, "check-json hook not found in config"

    def test_has_trailing_whitespace(self, config):
        """Trailing whitespace fixer must be configured."""
        repos = config["repos"]
        found = any(
            any("trailing-whitespace" in h.get("id", "") for h in repo.get("hooks", []))
            for repo in repos
        )
        assert found, "trailing-whitespace hook not found in config"

    def test_has_end_of_file_fixer(self, config):
        """End of file fixer must be configured."""
        repos = config["repos"]
        found = any(
            any("end-of-file-fixer" in h.get("id", "") for h in repo.get("hooks", []))
            for repo in repos
        )
        assert found, "end-of-file-fixer hook not found in config"

    def test_has_no_commit_to_branch(self, config):
        """No commit to main branch protection must be configured."""
        repos = config["repos"]
        found = any(
            any("no-commit-to-branch" in h.get("id", "") for h in repo.get("hooks", []))
            for repo in repos
        )
        assert found, "no-commit-to-branch hook not found in config"

    def test_no_commit_protects_main(self, config):
        """No commit to branch must protect main branch."""
        repos = config["repos"]
        for repo in repos:
            for hook in repo.get("hooks", []):
                if hook.get("id") == "no-commit-to-branch":
                    args = hook.get("args", [])
                    # Check that main is protected
                    assert "--branch" in args or any("main" in str(a) for a in args), \
                        "no-commit-to-branch must protect main branch"
                    return
        pytest.fail("no-commit-to-branch hook not found")


class TestFlake8Config:
    """Test .flake8 configuration file."""

    @pytest.fixture
    def config_path(self):
        return PROJECT_ROOT / ".flake8"

    @pytest.fixture
    def config(self, config_path):
        assert config_path.exists(), f"Flake8 config not found at {config_path}"
        parser = configparser.ConfigParser()
        parser.read(config_path)
        return parser

    def test_config_file_exists(self, config_path):
        """Flake8 config file must exist."""
        assert config_path.exists(), "Missing .flake8"

    def test_has_flake8_section(self, config):
        """Config must have flake8 section."""
        assert "flake8" in config.sections(), "Config must have [flake8] section"

    def test_max_line_length(self, config):
        """Max line length must be 100."""
        max_length = config.get("flake8", "max-line-length", fallback=None)
        assert max_length is not None, "max-line-length must be set"
        assert int(max_length) == 100, "max-line-length must be 100"

    def test_excludes_pycache(self, config):
        """Must exclude __pycache__ directory."""
        exclude = config.get("flake8", "exclude", fallback="")
        assert "__pycache__" in exclude, "Must exclude __pycache__"

    def test_excludes_git(self, config):
        """Must exclude .git directory."""
        exclude = config.get("flake8", "exclude", fallback="")
        assert ".git" in exclude, "Must exclude .git"

    def test_excludes_venv(self, config):
        """Must exclude venv directory."""
        exclude = config.get("flake8", "exclude", fallback="")
        assert "venv" in exclude, "Must exclude venv"


class TestIsortConfig:
    """Test .isort.cfg configuration file."""

    @pytest.fixture
    def config_path(self):
        return PROJECT_ROOT / ".isort.cfg"

    @pytest.fixture
    def config(self, config_path):
        assert config_path.exists(), f"isort config not found at {config_path}"
        parser = configparser.ConfigParser()
        parser.read(config_path)
        return parser

    def test_config_file_exists(self, config_path):
        """isort config file must exist."""
        assert config_path.exists(), "Missing .isort.cfg"

    def test_has_settings_section(self, config):
        """Config must have settings section."""
        has_section = "settings" in config.sections() or "isort" in config.sections()
        assert has_section, "Config must have [settings] or [isort] section"

    def test_black_profile(self, config):
        """Profile must be black for compatibility."""
        section = "settings" if "settings" in config.sections() else "isort"
        profile = config.get(section, "profile", fallback=None)
        assert profile is not None, "profile must be set"
        assert profile == "black", "profile must be 'black'"

    def test_line_length(self, config):
        """Line length must be 100."""
        section = "settings" if "settings" in config.sections() else "isort"
        line_length = config.get(section, "line_length", fallback=None)
        assert line_length is not None, "line_length must be set"
        assert int(line_length) == 100, "line_length must be 100"

    def test_skip_gitignore(self, config):
        """skip_gitignore must be true."""
        section = "settings" if "settings" in config.sections() else "isort"
        skip = config.get(section, "skip_gitignore", fallback=None)
        assert skip is not None, "skip_gitignore must be set"
        assert skip.lower() in ("true", "1", "yes"), "skip_gitignore must be true"


class TestInstallHooksScript:
    """Test scripts/install-hooks.sh script."""

    @pytest.fixture
    def script_path(self):
        return PROJECT_ROOT / "scripts" / "install-hooks.sh"

    @pytest.fixture
    def script_content(self, script_path):
        assert script_path.exists(), f"Script not found at {script_path}"
        return script_path.read_text()

    def test_script_exists(self, script_path):
        """Install hooks script must exist."""
        assert script_path.exists(), "Missing scripts/install-hooks.sh"

    def test_has_shebang(self, script_content):
        """Script must have shebang."""
        assert script_content.startswith("#!/"), "Script must start with shebang"

    def test_installs_precommit(self, script_content):
        """Script must install pre-commit."""
        assert "pip install" in script_content and "pre-commit" in script_content, \
            "Script must install pre-commit"

    def test_runs_precommit_install(self, script_content):
        """Script must run pre-commit install."""
        assert "pre-commit install" in script_content, \
            "Script must run 'pre-commit install'"

    def test_runs_on_all_files(self, script_content):
        """Script must run pre-commit on all files."""
        assert "pre-commit run --all-files" in script_content, \
            "Script must run 'pre-commit run --all-files'"

    def test_is_executable(self, script_path):
        """Script should be executable (Unix) or at least exist."""
        # On Windows this test just verifies the file exists
        assert script_path.exists()
        # On Unix, check executable bit
        if os.name != 'nt':
            assert os.access(script_path, os.X_OK), "Script must be executable"
