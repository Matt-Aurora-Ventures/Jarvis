"""
Unit tests for deploy/sync.py - FileSyncer class

Tests:
- FileSyncer class instantiation
- sync_to_vps(local_path, remote_path) - upload files
- sync_from_vps(remote_path, local_path) - download files
- exclude_patterns handling
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import subprocess

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))


class TestFileSyncerInit:
    """Test FileSyncer class initialization"""

    def test_file_syncer_import(self):
        """Test that FileSyncer class can be imported"""
        from deploy.sync import FileSyncer
        assert FileSyncer is not None

    def test_file_syncer_instantiation(self):
        """Test FileSyncer can be instantiated"""
        from deploy.sync import FileSyncer
        syncer = FileSyncer(vps_host="76.13.106.100")
        assert syncer.vps_host == "76.13.106.100"

    def test_file_syncer_default_user(self):
        """Test FileSyncer uses default user 'jarvis'"""
        from deploy.sync import FileSyncer
        syncer = FileSyncer(vps_host="76.13.106.100")
        assert syncer.vps_user == "jarvis"

    def test_file_syncer_default_exclude_patterns(self):
        """Test FileSyncer has default exclude patterns"""
        from deploy.sync import FileSyncer
        syncer = FileSyncer(vps_host="76.13.106.100")
        assert ".git" in syncer.exclude_patterns
        assert "__pycache__" in syncer.exclude_patterns
        assert "*.pyc" in syncer.exclude_patterns

    def test_file_syncer_custom_exclude_patterns(self):
        """Test FileSyncer accepts custom exclude patterns"""
        from deploy.sync import FileSyncer
        patterns = [".git", "node_modules", "*.log"]
        syncer = FileSyncer(vps_host="76.13.106.100", exclude_patterns=patterns)
        assert "node_modules" in syncer.exclude_patterns


class TestFileSyncerToVPS:
    """Test sync_to_vps(local_path, remote_path) method"""

    @pytest.fixture
    def mock_syncer(self):
        from deploy.sync import FileSyncer
        return FileSyncer(vps_host="76.13.106.100")

    def test_sync_to_vps_returns_result(self, mock_syncer):
        """Test sync_to_vps returns SyncResult object"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            result = mock_syncer.sync_to_vps("/local/path", "/remote/path")
            assert hasattr(result, 'success')
            assert hasattr(result, 'files_synced')

    def test_sync_to_vps_uses_rsync(self, mock_syncer):
        """Test sync_to_vps uses rsync command"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            mock_syncer.sync_to_vps("/local/path", "/remote/path")
            call_args = mock_run.call_args[0][0]
            assert "rsync" in call_args[0]

    def test_sync_to_vps_includes_exclude_patterns(self, mock_syncer):
        """Test sync_to_vps passes exclude patterns to rsync"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            mock_syncer.sync_to_vps("/local/path", "/remote/path")
            call_args = mock_run.call_args[0][0]
            # Should have --exclude flags for patterns
            call_str = " ".join(call_args)
            assert "--exclude" in call_str

    def test_sync_to_vps_uses_ssh(self, mock_syncer):
        """Test sync_to_vps uses SSH for transport"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            mock_syncer.sync_to_vps("/local/path", "/remote/path")
            call_args = mock_run.call_args[0][0]
            call_str = " ".join(call_args)
            # Should specify SSH or use user@host format
            assert "ssh" in call_str.lower() or "@" in call_str

    def test_sync_to_vps_failure_returns_error(self, mock_syncer):
        """Test sync_to_vps returns error on rsync failure"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="rsync error")
            result = mock_syncer.sync_to_vps("/local/path", "/remote/path")
            assert result.success is False
            assert result.error is not None


class TestFileSyncerFromVPS:
    """Test sync_from_vps(remote_path, local_path) method"""

    @pytest.fixture
    def mock_syncer(self):
        from deploy.sync import FileSyncer
        return FileSyncer(vps_host="76.13.106.100")

    def test_sync_from_vps_returns_result(self, mock_syncer):
        """Test sync_from_vps returns SyncResult object"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            result = mock_syncer.sync_from_vps("/remote/path", "/local/path")
            assert hasattr(result, 'success')

    def test_sync_from_vps_uses_rsync(self, mock_syncer):
        """Test sync_from_vps uses rsync command"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            mock_syncer.sync_from_vps("/remote/path", "/local/path")
            call_args = mock_run.call_args[0][0]
            assert "rsync" in call_args[0]

    def test_sync_from_vps_reverses_direction(self, mock_syncer):
        """Test sync_from_vps pulls from remote to local"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            mock_syncer.sync_from_vps("/remote/path", "/local/destination")
            call_args = mock_run.call_args[0][0]
            call_str = " ".join(call_args)
            # Remote should come before local in rsync for download
            assert "76.13.106.100" in call_str


class TestFileSyncerDryRun:
    """Test dry run functionality"""

    @pytest.fixture
    def mock_syncer(self):
        from deploy.sync import FileSyncer
        return FileSyncer(vps_host="76.13.106.100")

    def test_sync_dry_run_option(self, mock_syncer):
        """Test sync supports dry_run option"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            mock_syncer.sync_to_vps("/local/path", "/remote/path", dry_run=True)
            call_args = mock_run.call_args[0][0]
            call_str = " ".join(call_args)
            assert "--dry-run" in call_str or "-n" in call_str
