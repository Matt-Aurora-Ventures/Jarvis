"""
Unit tests for deploy/deployer.py - Deployer class

Tests:
- Deployer class instantiation
- deploy(bot_name) - deploy single bot
- deploy_all() - deploy all bots
- rollback(bot_name, version) - rollback to version
- get_deployed_version(bot_name) - get current version
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))


class TestDeployerInit:
    """Test Deployer class initialization"""

    def test_deployer_import(self):
        """Test that Deployer class can be imported"""
        from deploy.deployer import Deployer
        assert Deployer is not None

    def test_deployer_instantiation(self):
        """Test Deployer can be instantiated with VPS host"""
        from deploy.deployer import Deployer
        deployer = Deployer(vps_host="76.13.106.100")
        assert deployer.vps_host == "76.13.106.100"

    def test_deployer_default_user(self):
        """Test Deployer uses default user 'jarvis'"""
        from deploy.deployer import Deployer
        deployer = Deployer(vps_host="76.13.106.100")
        assert deployer.vps_user == "jarvis"

    def test_deployer_custom_user(self):
        """Test Deployer accepts custom user"""
        from deploy.deployer import Deployer
        deployer = Deployer(vps_host="76.13.106.100", vps_user="root")
        assert deployer.vps_user == "root"

    def test_deployer_default_remote_path(self):
        """Test Deployer uses default remote path"""
        from deploy.deployer import Deployer
        deployer = Deployer(vps_host="76.13.106.100")
        assert deployer.remote_path == "/home/jarvis/Jarvis"


class TestDeployerDeploy:
    """Test deploy(bot_name) method"""

    @pytest.fixture
    def mock_deployer(self):
        """Create deployer with mocked SSH/rsync"""
        from deploy.deployer import Deployer
        deployer = Deployer(vps_host="76.13.106.100")
        return deployer

    def test_deploy_single_bot_returns_result(self, mock_deployer):
        """Test deploy returns DeployResult object"""
        with patch.object(mock_deployer, '_run_ssh_command', return_value=(0, "ok")):
            with patch.object(mock_deployer, '_sync_files', return_value=True):
                with patch.object(mock_deployer, '_restart_service', return_value=True):
                    result = mock_deployer.deploy("clawdjarvis")
                    assert hasattr(result, 'success')
                    assert hasattr(result, 'bot_name')
                    assert result.bot_name == "clawdjarvis"

    def test_deploy_invalid_bot_raises_error(self, mock_deployer):
        """Test deploy raises error for unknown bot"""
        with pytest.raises(ValueError, match="Unknown bot"):
            mock_deployer.deploy("nonexistent_bot")

    def test_deploy_creates_backup(self, mock_deployer):
        """Test deploy creates backup before syncing"""
        with patch.object(mock_deployer, '_create_backup') as mock_backup:
            with patch.object(mock_deployer, '_sync_files', return_value=True):
                with patch.object(mock_deployer, '_restart_service', return_value=True):
                    mock_deployer.deploy("clawdjarvis")
                    mock_backup.assert_called_once()


class TestDeployerDeployAll:
    """Test deploy_all() method"""

    @pytest.fixture
    def mock_deployer(self):
        from deploy.deployer import Deployer
        return Deployer(vps_host="76.13.106.100")

    def test_deploy_all_returns_results_list(self, mock_deployer):
        """Test deploy_all returns list of results"""
        with patch.object(mock_deployer, 'deploy') as mock_deploy:
            mock_deploy.return_value = Mock(success=True)
            results = mock_deployer.deploy_all()
            assert isinstance(results, list)
            assert len(results) > 0

    def test_deploy_all_deploys_known_bots(self, mock_deployer):
        """Test deploy_all deploys all registered bots"""
        with patch.object(mock_deployer, 'deploy') as mock_deploy:
            mock_deploy.return_value = Mock(success=True)
            mock_deployer.deploy_all()
            # Should deploy at least supervisor, clawdjarvis, clawdfriday, clawdmatt
            assert mock_deploy.call_count >= 3


class TestDeployerRollback:
    """Test rollback(bot_name, version) method"""

    @pytest.fixture
    def mock_deployer(self):
        from deploy.deployer import Deployer
        return Deployer(vps_host="76.13.106.100")

    def test_rollback_restores_version(self, mock_deployer):
        """Test rollback restores specified version"""
        with patch.object(mock_deployer, '_get_backup_path', return_value="/backup/v1"):
            with patch.object(mock_deployer, '_restore_backup', return_value=True):
                with patch.object(mock_deployer, '_restart_service', return_value=True):
                    result = mock_deployer.rollback("clawdjarvis", "v1")
                    assert result.success is True

    def test_rollback_invalid_version_raises_error(self, mock_deployer):
        """Test rollback raises error for non-existent version"""
        with patch.object(mock_deployer, '_get_backup_path', return_value=None):
            with pytest.raises(ValueError, match="Version not found"):
                mock_deployer.rollback("clawdjarvis", "nonexistent")


class TestDeployerGetVersion:
    """Test get_deployed_version(bot_name) method"""

    @pytest.fixture
    def mock_deployer(self):
        from deploy.deployer import Deployer
        return Deployer(vps_host="76.13.106.100")

    def test_get_version_returns_string(self, mock_deployer):
        """Test get_deployed_version returns version string"""
        with patch.object(mock_deployer, '_run_ssh_command', return_value=(0, "v2026.02.02")):
            version = mock_deployer.get_deployed_version("clawdjarvis")
            assert isinstance(version, str)
            assert version.startswith("v")

    def test_get_version_reads_version_file(self, mock_deployer):
        """Test get_deployed_version reads from VERSION file"""
        with patch.object(mock_deployer, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "v2026.02.02")
            mock_deployer.get_deployed_version("clawdjarvis")
            # Should read VERSION file from remote
            call_args = mock_ssh.call_args[0][0]
            assert "VERSION" in call_args or "version" in call_args.lower()
