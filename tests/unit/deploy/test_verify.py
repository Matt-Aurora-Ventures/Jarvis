"""
Unit tests for deploy/verify.py - DeploymentVerifier class

Tests:
- DeploymentVerifier class instantiation
- verify_deployment(bot_name) -> bool
- check_process_running(bot_name)
- check_logs_healthy(bot_name)
- check_api_responding(bot_name)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))


class TestDeploymentVerifierInit:
    """Test DeploymentVerifier class initialization"""

    def test_verifier_import(self):
        """Test that DeploymentVerifier class can be imported"""
        from deploy.verify import DeploymentVerifier
        assert DeploymentVerifier is not None

    def test_verifier_instantiation(self):
        """Test DeploymentVerifier can be instantiated"""
        from deploy.verify import DeploymentVerifier
        verifier = DeploymentVerifier(vps_host="76.13.106.100")
        assert verifier.vps_host == "76.13.106.100"

    def test_verifier_default_user(self):
        """Test DeploymentVerifier uses default user 'jarvis'"""
        from deploy.verify import DeploymentVerifier
        verifier = DeploymentVerifier(vps_host="76.13.106.100")
        assert verifier.vps_user == "jarvis"


class TestVerifyDeployment:
    """Test verify_deployment(bot_name) method"""

    @pytest.fixture
    def mock_verifier(self):
        from deploy.verify import DeploymentVerifier
        return DeploymentVerifier(vps_host="76.13.106.100")

    def test_verify_deployment_returns_result(self, mock_verifier):
        """Test verify_deployment returns VerificationResult"""
        with patch.object(mock_verifier, 'check_process_running', return_value=True):
            with patch.object(mock_verifier, 'check_logs_healthy', return_value=True):
                with patch.object(mock_verifier, 'check_api_responding', return_value=True):
                    result = mock_verifier.verify_deployment("clawdjarvis")
                    assert hasattr(result, 'success')
                    assert hasattr(result, 'checks')

    def test_verify_deployment_all_pass_success(self, mock_verifier):
        """Test verify_deployment returns success when all checks pass"""
        with patch.object(mock_verifier, 'check_process_running', return_value=True):
            with patch.object(mock_verifier, 'check_logs_healthy', return_value=True):
                with patch.object(mock_verifier, 'check_api_responding', return_value=True):
                    result = mock_verifier.verify_deployment("clawdjarvis")
                    assert result.success is True

    def test_verify_deployment_any_fail_failure(self, mock_verifier):
        """Test verify_deployment returns failure when any check fails"""
        with patch.object(mock_verifier, 'check_process_running', return_value=False):
            with patch.object(mock_verifier, 'check_logs_healthy', return_value=True):
                with patch.object(mock_verifier, 'check_api_responding', return_value=True):
                    result = mock_verifier.verify_deployment("clawdjarvis")
                    assert result.success is False


class TestCheckProcessRunning:
    """Test check_process_running(bot_name) method"""

    @pytest.fixture
    def mock_verifier(self):
        from deploy.verify import DeploymentVerifier
        return DeploymentVerifier(vps_host="76.13.106.100")

    def test_check_process_running_returns_bool(self, mock_verifier):
        """Test check_process_running returns boolean"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "active")
            result = mock_verifier.check_process_running("clawdjarvis")
            assert isinstance(result, bool)

    def test_check_process_running_uses_systemctl(self, mock_verifier):
        """Test check_process_running uses systemctl status"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "active")
            mock_verifier.check_process_running("clawdjarvis")
            call_args = mock_ssh.call_args[0][0]
            assert "systemctl" in call_args

    def test_check_process_active_returns_true(self, mock_verifier):
        """Test check_process returns True when service is active"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "active\n")
            result = mock_verifier.check_process_running("clawdjarvis")
            assert result is True

    def test_check_process_inactive_returns_false(self, mock_verifier):
        """Test check_process returns False when service is inactive"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (3, "inactive\n")
            result = mock_verifier.check_process_running("clawdjarvis")
            assert result is False


class TestCheckLogsHealthy:
    """Test check_logs_healthy(bot_name) method"""

    @pytest.fixture
    def mock_verifier(self):
        from deploy.verify import DeploymentVerifier
        return DeploymentVerifier(vps_host="76.13.106.100")

    def test_check_logs_returns_bool(self, mock_verifier):
        """Test check_logs_healthy returns boolean"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "INFO: Bot started\nINFO: Running\n")
            result = mock_verifier.check_logs_healthy("clawdjarvis")
            assert isinstance(result, bool)

    def test_check_logs_uses_journalctl(self, mock_verifier):
        """Test check_logs_healthy uses journalctl"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "INFO: Running\n")
            mock_verifier.check_logs_healthy("clawdjarvis")
            call_args = mock_ssh.call_args[0][0]
            assert "journalctl" in call_args

    def test_check_logs_no_errors_returns_true(self, mock_verifier):
        """Test check_logs returns True when no errors in logs"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "INFO: Bot started\nINFO: Processing\n")
            result = mock_verifier.check_logs_healthy("clawdjarvis")
            assert result is True

    def test_check_logs_with_errors_returns_false(self, mock_verifier):
        """Test check_logs returns False when critical errors found"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, "ERROR: Connection failed\nCRITICAL: Bot crashed\n")
            result = mock_verifier.check_logs_healthy("clawdjarvis")
            assert result is False


class TestCheckAPIResponding:
    """Test check_api_responding(bot_name) method"""

    @pytest.fixture
    def mock_verifier(self):
        from deploy.verify import DeploymentVerifier
        return DeploymentVerifier(vps_host="76.13.106.100")

    def test_check_api_returns_bool(self, mock_verifier):
        """Test check_api_responding returns boolean"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, '{"status": "ok"}')
            result = mock_verifier.check_api_responding("clawdjarvis")
            assert isinstance(result, bool)

    def test_check_api_uses_curl(self, mock_verifier):
        """Test check_api_responding uses curl or health endpoint"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, '{"status": "ok"}')
            mock_verifier.check_api_responding("clawdjarvis")
            # Should check some form of health endpoint
            call_args = mock_ssh.call_args[0][0]
            assert "curl" in call_args or "health" in call_args.lower()

    def test_check_api_ok_returns_true(self, mock_verifier):
        """Test check_api returns True when API responds OK"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (0, '{"status": "ok"}')
            result = mock_verifier.check_api_responding("clawdjarvis")
            assert result is True

    def test_check_api_fail_returns_false(self, mock_verifier):
        """Test check_api returns False when API fails"""
        with patch.object(mock_verifier, '_run_ssh_command') as mock_ssh:
            mock_ssh.return_value = (7, "Connection refused")  # curl error code
            result = mock_verifier.check_api_responding("clawdjarvis")
            assert result is False

    def test_check_api_bot_without_api_returns_true(self, mock_verifier):
        """Test check_api returns True for bots without API endpoints"""
        # Some bots don't expose HTTP APIs - they should return True by default
        with patch.object(mock_verifier, '_get_bot_config') as mock_config:
            mock_config.return_value = {"has_api": False}
            result = mock_verifier.check_api_responding("telegram_bot")
            assert result is True
