"""
Tests for System Diagnostics Module.

Tests cover:
- Observation dataclass
- Process listing
- Port scanning
- System profile observations
- Full diagnostics run
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import diagnostics
from core.diagnostics import Observation


# =============================================================================
# Test Observation Dataclass
# =============================================================================

class TestObservation:
    """Test Observation dataclass."""

    def test_create_observation(self):
        """Should create observation with all fields."""
        obs = Observation(
            title="Test Issue",
            detail="Something happened",
            why_it_matters="Important reason",
            confidence="high",
            next_step="Do something",
        )

        assert obs.title == "Test Issue"
        assert obs.detail == "Something happened"
        assert obs.why_it_matters == "Important reason"
        assert obs.confidence == "high"
        assert obs.next_step == "Do something"

    def test_observation_equality(self):
        """Observations with same fields should be equal."""
        obs1 = Observation("A", "B", "C", "D", "E")
        obs2 = Observation("A", "B", "C", "D", "E")
        assert obs1 == obs2

    def test_observation_different(self):
        """Observations with different fields should not be equal."""
        obs1 = Observation("A", "B", "C", "D", "E")
        obs2 = Observation("X", "B", "C", "D", "E")
        assert obs1 != obs2


# =============================================================================
# Test Top Processes
# =============================================================================

class TestTopProcesses:
    """Test _top_processes function."""

    def test_returns_list(self):
        """Should return a list."""
        result = diagnostics._top_processes()
        assert isinstance(result, list)

    def test_respects_limit(self):
        """Should respect limit parameter."""
        result = diagnostics._top_processes(limit=3)
        assert len(result) <= 3

    def test_handles_psutil_import_error(self):
        """Should handle missing psutil gracefully."""
        with patch.dict("sys.modules", {"psutil": None}):
            # Force reload to trigger import error path
            result = diagnostics._top_processes()
            assert isinstance(result, list)

    def test_process_dict_structure(self):
        """Process dicts should have expected keys."""
        result = diagnostics._top_processes(limit=1)
        if result:
            proc = result[0]
            assert "pid" in proc
            assert "name" in proc
            assert "cpu" in proc
            assert "mem_mb" in proc

    def test_sorted_by_memory(self):
        """Should be sorted by memory descending."""
        result = diagnostics._top_processes(limit=10)
        if len(result) >= 2:
            for i in range(len(result) - 1):
                assert float(result[i]["mem_mb"]) >= float(result[i + 1]["mem_mb"])


# =============================================================================
# Test Listening Ports
# =============================================================================

class TestListeningPorts:
    """Test _listening_ports function."""

    def test_returns_list(self):
        """Should return a list."""
        result = diagnostics._listening_ports()
        assert isinstance(result, list)

    def test_handles_command_failure(self):
        """Should handle command failure gracefully."""
        with patch("subprocess.run", side_effect=Exception("Command failed")):
            result = diagnostics._listening_ports()
            assert result == []

    def test_handles_empty_output(self):
        """Should handle empty lsof output."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = diagnostics._listening_ports()
            assert result == []

    def test_parses_lsof_output(self):
        """Should parse lsof output correctly."""
        mock_result = MagicMock()
        mock_result.stdout = """COMMAND  PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
python  1234 user   3u  IPv4  12345      0t0  TCP *:8080 (LISTEN)
node    5678 user   4u  IPv4  67890      0t0  TCP *:3000 (LISTEN)
"""
        with patch("subprocess.run", return_value=mock_result):
            result = diagnostics._listening_ports()
            assert len(result) == 2
            assert result[0]["name"] == "python"
            assert result[0]["pid"] == "1234"
            assert result[1]["name"] == "node"

    def test_max_10_ports(self):
        """Should return max 10 ports."""
        # Create output with 15 ports
        lines = ["COMMAND  PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME"]
        for i in range(15):
            lines.append(f"proc{i}  {i} user   3u  IPv4  12345      0t0  TCP *:{8000+i} (LISTEN)")
        mock_result = MagicMock()
        mock_result.stdout = "\n".join(lines)
        with patch("subprocess.run", return_value=mock_result):
            result = diagnostics._listening_ports()
            assert len(result) <= 10


# =============================================================================
# Test Posture Observations
# =============================================================================

class TestPostureObservations:
    """Test _posture_observations function."""

    def test_low_disk_observation(self):
        """Should detect low disk space."""
        mock_profile = MagicMock()
        mock_profile.disk_free_gb = 5.0
        mock_profile.ram_free_gb = 8.0
        mock_profile.cpu_load = 1.0

        observations = diagnostics._posture_observations(mock_profile)
        titles = [obs.title for obs in observations]
        assert "Low disk free space" in titles

    def test_low_ram_observation(self):
        """Should detect low RAM."""
        mock_profile = MagicMock()
        mock_profile.disk_free_gb = 50.0
        mock_profile.ram_free_gb = 1.0
        mock_profile.cpu_load = 1.0

        observations = diagnostics._posture_observations(mock_profile)
        titles = [obs.title for obs in observations]
        assert "Low available memory" in titles

    def test_high_cpu_observation(self):
        """Should detect high CPU load."""
        mock_profile = MagicMock()
        mock_profile.disk_free_gb = 50.0
        mock_profile.ram_free_gb = 8.0
        mock_profile.cpu_load = 10.0

        observations = diagnostics._posture_observations(mock_profile)
        titles = [obs.title for obs in observations]
        assert "High CPU load" in titles

    def test_no_observations_when_healthy(self):
        """Should return empty list when system is healthy."""
        mock_profile = MagicMock()
        mock_profile.disk_free_gb = 100.0
        mock_profile.ram_free_gb = 16.0
        mock_profile.cpu_load = 0.5

        observations = diagnostics._posture_observations(mock_profile)
        assert len(observations) == 0

    def test_multiple_observations(self):
        """Should return multiple observations when multiple issues."""
        mock_profile = MagicMock()
        mock_profile.disk_free_gb = 5.0
        mock_profile.ram_free_gb = 1.0
        mock_profile.cpu_load = 10.0

        observations = diagnostics._posture_observations(mock_profile)
        assert len(observations) == 3

    def test_handles_none_values(self):
        """Should handle None values in profile."""
        mock_profile = MagicMock()
        mock_profile.disk_free_gb = None
        mock_profile.ram_free_gb = None
        mock_profile.cpu_load = None

        observations = diagnostics._posture_observations(mock_profile)
        assert isinstance(observations, list)


# =============================================================================
# Test Run Diagnostics
# =============================================================================

class TestRunDiagnostics:
    """Test run_diagnostics function."""

    def test_returns_dict(self):
        """Should return dictionary."""
        result = diagnostics.run_diagnostics()
        assert isinstance(result, dict)

    def test_dict_has_expected_keys(self):
        """Should have expected keys."""
        result = diagnostics.run_diagnostics()
        assert "profile" in result
        assert "processes" in result
        assert "ports" in result
        assert "observations" in result

    def test_respects_limit(self):
        """Should pass limit to _top_processes."""
        with patch.object(diagnostics, "_top_processes", return_value=[]) as mock:
            diagnostics.run_diagnostics(limit=3)
            mock.assert_called_once_with(limit=3)

    def test_observations_based_on_profile(self):
        """Observations should be based on profile."""
        mock_profile = MagicMock()
        mock_profile.disk_free_gb = 5.0
        mock_profile.ram_free_gb = 8.0
        mock_profile.cpu_load = 1.0

        with patch("core.system_profiler.read_profile", return_value=mock_profile):
            with patch.object(diagnostics, "_top_processes", return_value=[]):
                with patch.object(diagnostics, "_listening_ports", return_value=[]):
                    result = diagnostics.run_diagnostics()
                    assert result["profile"] == mock_profile
                    assert len(result["observations"]) == 1  # Low disk
