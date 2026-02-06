"""Tests for package configuration files.

Verifies that setup.py, pyproject.toml, MANIFEST.in, and setup.cfg
are properly configured for the jarvis-core package.
"""

import ast
import configparser
import os
from pathlib import Path

import pytest

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TestSetupPy:
    """Tests for setup.py configuration."""

    @pytest.fixture
    def setup_py_path(self) -> Path:
        return PROJECT_ROOT / "setup.py"

    def test_setup_py_exists(self, setup_py_path: Path) -> None:
        """setup.py should exist at project root."""
        assert setup_py_path.exists(), f"setup.py not found at {setup_py_path}"

    def test_setup_py_is_valid_python(self, setup_py_path: Path) -> None:
        """setup.py should be valid Python syntax."""
        content = setup_py_path.read_text()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"setup.py has syntax error: {e}")

    def test_setup_py_has_name(self, setup_py_path: Path) -> None:
        """setup.py should define name='jarvis-core'."""
        content = setup_py_path.read_text()
        assert "name=" in content or 'name =' in content
        assert "jarvis-core" in content

    def test_setup_py_has_version(self, setup_py_path: Path) -> None:
        """setup.py should define version='2.0.0'."""
        content = setup_py_path.read_text()
        assert "version=" in content or 'version =' in content
        assert "2.0.0" in content

    def test_setup_py_has_find_packages(self, setup_py_path: Path) -> None:
        """setup.py should use find_packages()."""
        content = setup_py_path.read_text()
        assert "find_packages" in content

    def test_setup_py_has_install_requires(self, setup_py_path: Path) -> None:
        """setup.py should have install_requires from requirements.txt."""
        content = setup_py_path.read_text()
        assert "install_requires" in content

    def test_setup_py_has_entry_points(self, setup_py_path: Path) -> None:
        """setup.py should define CLI entry points."""
        content = setup_py_path.read_text()
        assert "entry_points" in content
        assert "console_scripts" in content


class TestPyprojectToml:
    """Tests for pyproject.toml configuration."""

    @pytest.fixture
    def pyproject_path(self) -> Path:
        return PROJECT_ROOT / "pyproject.toml"

    def test_pyproject_exists(self, pyproject_path: Path) -> None:
        """pyproject.toml should exist at project root."""
        assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    def test_pyproject_has_build_system(self, pyproject_path: Path) -> None:
        """pyproject.toml should have [build-system] section."""
        content = pyproject_path.read_text()
        assert "[build-system]" in content

    def test_pyproject_has_project_metadata(self, pyproject_path: Path) -> None:
        """pyproject.toml should have [project] section with name jarvis-core."""
        content = pyproject_path.read_text()
        assert "[project]" in content
        assert 'name = "jarvis-core"' in content

    def test_pyproject_has_version_2(self, pyproject_path: Path) -> None:
        """pyproject.toml should have version 2.0.0."""
        content = pyproject_path.read_text()
        assert 'version = "2.0.0"' in content

    def test_pyproject_has_pytest_config(self, pyproject_path: Path) -> None:
        """pyproject.toml should have [tool.pytest] or [tool.pytest.ini_options]."""
        content = pyproject_path.read_text()
        assert "[tool.pytest" in content

    def test_pyproject_has_black_config(self, pyproject_path: Path) -> None:
        """pyproject.toml should have [tool.black] section."""
        content = pyproject_path.read_text()
        assert "[tool.black]" in content

    def test_pyproject_has_isort_config(self, pyproject_path: Path) -> None:
        """pyproject.toml should have isort configuration."""
        content = pyproject_path.read_text()
        # Can be [tool.isort] or [tool.ruff.isort]
        assert "isort" in content.lower()

    def test_pyproject_has_mypy_config(self, pyproject_path: Path) -> None:
        """pyproject.toml should have [tool.mypy] section."""
        content = pyproject_path.read_text()
        assert "[tool.mypy]" in content


class TestManifestIn:
    """Tests for MANIFEST.in configuration."""

    @pytest.fixture
    def manifest_path(self) -> Path:
        return PROJECT_ROOT / "MANIFEST.in"

    def test_manifest_exists(self, manifest_path: Path) -> None:
        """MANIFEST.in should exist at project root."""
        assert manifest_path.exists(), f"MANIFEST.in not found at {manifest_path}"

    def test_manifest_includes_readme(self, manifest_path: Path) -> None:
        """MANIFEST.in should include README.md."""
        content = manifest_path.read_text()
        assert "README.md" in content

    def test_manifest_includes_requirements(self, manifest_path: Path) -> None:
        """MANIFEST.in should include requirements.txt."""
        content = manifest_path.read_text()
        assert "requirements.txt" in content

    def test_manifest_includes_core_py_files(self, manifest_path: Path) -> None:
        """MANIFEST.in should recursively include core/*.py files."""
        content = manifest_path.read_text()
        assert "recursive-include core" in content
        assert "*.py" in content

    def test_manifest_includes_bots_py_files(self, manifest_path: Path) -> None:
        """MANIFEST.in should recursively include bots/*.py files."""
        content = manifest_path.read_text()
        assert "recursive-include bots" in content


class TestSetupCfg:
    """Tests for setup.cfg configuration."""

    @pytest.fixture
    def setup_cfg_path(self) -> Path:
        return PROJECT_ROOT / "setup.cfg"

    def test_setup_cfg_exists(self, setup_cfg_path: Path) -> None:
        """setup.cfg should exist at project root."""
        assert setup_cfg_path.exists(), f"setup.cfg not found at {setup_cfg_path}"

    def test_setup_cfg_is_valid(self, setup_cfg_path: Path) -> None:
        """setup.cfg should be valid INI format."""
        config = configparser.ConfigParser()
        try:
            config.read(setup_cfg_path)
        except configparser.Error as e:
            pytest.fail(f"setup.cfg has invalid format: {e}")

    def test_setup_cfg_has_flake8(self, setup_cfg_path: Path) -> None:
        """setup.cfg should have [flake8] section."""
        config = configparser.ConfigParser()
        config.read(setup_cfg_path)
        assert "flake8" in config.sections(), "Missing [flake8] section"

    def test_setup_cfg_has_isort(self, setup_cfg_path: Path) -> None:
        """setup.cfg should have [isort] section."""
        config = configparser.ConfigParser()
        config.read(setup_cfg_path)
        assert "isort" in config.sections(), "Missing [isort] section"

    def test_setup_cfg_has_mypy(self, setup_cfg_path: Path) -> None:
        """setup.cfg should have [mypy] section."""
        config = configparser.ConfigParser()
        config.read(setup_cfg_path)
        assert "mypy" in config.sections(), "Missing [mypy] section"

    def test_flake8_max_line_length(self, setup_cfg_path: Path) -> None:
        """flake8 should have max-line-length setting."""
        config = configparser.ConfigParser()
        config.read(setup_cfg_path)
        assert config.has_option("flake8", "max-line-length")

    def test_isort_profile(self, setup_cfg_path: Path) -> None:
        """isort should have profile setting for black compatibility."""
        config = configparser.ConfigParser()
        config.read(setup_cfg_path)
        assert config.has_option("isort", "profile")


class TestPackageIntegration:
    """Integration tests for package configuration."""

    def test_requirements_txt_exists(self) -> None:
        """requirements.txt should exist for install_requires."""
        req_path = PROJECT_ROOT / "requirements.txt"
        assert req_path.exists(), f"requirements.txt not found at {req_path}"

    def test_core_package_exists(self) -> None:
        """core/ package should exist."""
        core_path = PROJECT_ROOT / "core"
        assert core_path.exists() and core_path.is_dir(), f"core/ not found at {core_path}"

    def test_bots_package_exists(self) -> None:
        """bots/ package should exist."""
        bots_path = PROJECT_ROOT / "bots"
        assert bots_path.exists() and bots_path.is_dir(), f"bots/ not found at {bots_path}"
