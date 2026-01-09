"""
Tests for Email Client Integration.

Tests verify:
- Email configuration
- Gmail client factory
- Message parsing
- IMAP operations (mocked)
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.integrations.email_client import (
    EmailMessage,
    EmailConfig,
    EmailClient,
    create_gmail_client,
    create_outlook_client,
    create_imap_client,
)


# =============================================================================
# Test EmailMessage Dataclass
# =============================================================================

class TestEmailMessage:
    """Test EmailMessage dataclass."""

    def test_create_message(self):
        """Should create email message with required fields."""
        msg = EmailMessage(
            id="123",
            subject="Test Subject",
            sender="sender@example.com",
            sender_name="Sender Name",
            recipients=["recipient@example.com"],
            date=datetime.now(),
            body_text="Hello, World!",
        )
        assert msg.id == "123"
        assert msg.subject == "Test Subject"
        assert msg.sender == "sender@example.com"

    def test_snippet_short_body(self):
        """Snippet should return full body if short."""
        msg = EmailMessage(
            id="1",
            subject="Test",
            sender="a@b.com",
            sender_name="A",
            recipients=["c@d.com"],
            date=datetime.now(),
            body_text="Short body",
        )
        assert msg.snippet == "Short body"

    def test_snippet_long_body(self):
        """Snippet should truncate long body."""
        long_text = "A" * 200
        msg = EmailMessage(
            id="1",
            subject="Test",
            sender="a@b.com",
            sender_name="A",
            recipients=["c@d.com"],
            date=datetime.now(),
            body_text=long_text,
        )
        assert len(msg.snippet) == 103  # 100 chars + "..."
        assert msg.snippet.endswith("...")

    def test_default_values(self):
        """Should have sensible defaults."""
        msg = EmailMessage(
            id="1",
            subject="Test",
            sender="a@b.com",
            sender_name="A",
            recipients=["c@d.com"],
            date=datetime.now(),
            body_text="Body",
        )
        assert msg.is_read is False
        assert msg.folder == "INBOX"
        assert msg.body_html is None
        assert msg.headers == {}
        assert msg.attachments == []


# =============================================================================
# Test EmailConfig
# =============================================================================

class TestEmailConfig:
    """Test EmailConfig dataclass."""

    def test_gmail_defaults(self):
        """Default config should be for Gmail."""
        config = EmailConfig()
        assert config.imap_host == "imap.gmail.com"
        assert config.smtp_host == "smtp.gmail.com"
        assert config.imap_port == 993
        assert config.smtp_port == 587
        assert config.imap_ssl is True
        assert config.smtp_tls is True

    def test_custom_config(self):
        """Should accept custom configuration."""
        config = EmailConfig(
            imap_host="imap.custom.com",
            smtp_host="smtp.custom.com",
            imap_port=143,
            email="test@custom.com",
            password="secret",
        )
        assert config.imap_host == "imap.custom.com"
        assert config.email == "test@custom.com"


# =============================================================================
# Test EmailClient Factory Functions
# =============================================================================

class TestEmailClientFactories:
    """Test client factory functions."""

    def test_create_gmail_client(self):
        """Gmail factory should create correct config."""
        client = create_gmail_client(
            email="user@gmail.com",
            app_password="app_password_here",
        )
        assert client._config.imap_host == "imap.gmail.com"
        assert client._config.smtp_host == "smtp.gmail.com"
        assert client._config.email == "user@gmail.com"
        assert client._config.provider == "gmail"

    def test_create_outlook_client(self):
        """Outlook factory should create correct config."""
        client = create_outlook_client(
            email="user@outlook.com",
            password="password_here",
        )
        assert client._config.imap_host == "outlook.office365.com"
        assert client._config.smtp_host == "smtp.office365.com"
        assert client._config.provider == "outlook"

    def test_create_imap_client(self):
        """Generic IMAP factory should accept custom hosts."""
        client = create_imap_client(
            email="user@example.com",
            password="password",
            imap_host="imap.example.com",
            smtp_host="smtp.example.com",
        )
        assert client._config.imap_host == "imap.example.com"
        assert client._config.smtp_host == "smtp.example.com"
        assert client._config.provider == "imap"


# =============================================================================
# Test EmailClient Operations (Mocked)
# =============================================================================

class TestEmailClientOperations:
    """Test EmailClient with mocked IMAP."""

    @pytest.fixture
    def mock_imap(self):
        """Create mock IMAP connection."""
        mock = MagicMock()
        mock.login.return_value = ("OK", [])
        mock.logout.return_value = ("OK", [])
        mock.noop.return_value = ("OK", [])
        mock.list.return_value = ("OK", [b'() "/" "INBOX"', b'() "/" "Sent"'])
        mock.select.return_value = ("OK", [b"10"])
        mock.search.return_value = ("OK", [b"1 2 3"])
        return mock

    def test_connect_success(self, mock_imap):
        """Should connect successfully."""
        with patch("core.integrations.email_client.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = create_gmail_client("test@gmail.com", "password")
            result = client.connect()
            assert result is True
            assert client._connected is True

    def test_connect_auth_failure(self, mock_imap):
        """Should handle authentication failure."""
        mock_imap.login.side_effect = Exception("Authentication failed")
        with patch("core.integrations.email_client.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = create_gmail_client("test@gmail.com", "wrong_password")
            result = client.connect()
            assert result is False
            assert client._connected is False

    def test_disconnect(self, mock_imap):
        """Should disconnect cleanly."""
        with patch("core.integrations.email_client.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = create_gmail_client("test@gmail.com", "password")
            client.connect()
            client.disconnect()
            assert client._connected is False
            mock_imap.logout.assert_called_once()

    def test_list_folders(self, mock_imap):
        """Should list folders."""
        with patch("core.integrations.email_client.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = create_gmail_client("test@gmail.com", "password")
            client.connect()
            folders = client.list_folders()
            assert "INBOX" in folders
            assert "Sent" in folders

    def test_context_manager(self, mock_imap):
        """Should work as context manager."""
        with patch("core.integrations.email_client.imaplib.IMAP4_SSL", return_value=mock_imap):
            with create_gmail_client("test@gmail.com", "password") as client:
                assert client._connected is True
            assert client._connected is False


# =============================================================================
# Test SMTP Send (Mocked)
# =============================================================================

class TestEmailSend:
    """Test email sending with mocked SMTP."""

    @pytest.fixture
    def mock_smtp(self):
        """Create mock SMTP connection."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_send_email_success(self, mock_smtp):
        """Should send email successfully."""
        with patch("core.integrations.email_client.smtplib.SMTP", return_value=mock_smtp):
            client = create_gmail_client("sender@gmail.com", "password")
            result = client.send_email(
                to=["recipient@example.com"],
                subject="Test Subject",
                body="Test body",
            )
            assert result is True
            mock_smtp.sendmail.assert_called_once()

    def test_send_email_with_html(self, mock_smtp):
        """Should send email with HTML body."""
        with patch("core.integrations.email_client.smtplib.SMTP", return_value=mock_smtp):
            client = create_gmail_client("sender@gmail.com", "password")
            result = client.send_email(
                to=["recipient@example.com"],
                subject="Test Subject",
                body="Plain text",
                html="<h1>HTML body</h1>",
            )
            assert result is True

    def test_send_email_with_cc_bcc(self, mock_smtp):
        """Should send email with CC and BCC."""
        with patch("core.integrations.email_client.smtplib.SMTP", return_value=mock_smtp):
            client = create_gmail_client("sender@gmail.com", "password")
            result = client.send_email(
                to=["recipient@example.com"],
                subject="Test",
                body="Body",
                cc=["cc@example.com"],
                bcc=["bcc@example.com"],
            )
            assert result is True
            # Verify all recipients are included
            call_args = mock_smtp.sendmail.call_args
            recipients = call_args[0][1]
            assert "recipient@example.com" in recipients
            assert "cc@example.com" in recipients
            assert "bcc@example.com" in recipients

    def test_send_email_auth_failure(self, mock_smtp):
        """Should handle SMTP auth failure."""
        import smtplib
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, "Auth failed")
        with patch("core.integrations.email_client.smtplib.SMTP", return_value=mock_smtp):
            client = create_gmail_client("sender@gmail.com", "wrong_password")
            result = client.send_email(
                to=["recipient@example.com"],
                subject="Test",
                body="Body",
            )
            assert result is False


# =============================================================================
# Test Header Decoding
# =============================================================================

class TestHeaderDecoding:
    """Test email header decoding."""

    def test_decode_simple_header(self):
        """Should decode simple ASCII header."""
        client = EmailClient(EmailConfig())
        result = client._decode_header("Simple Subject")
        assert result == "Simple Subject"

    def test_decode_none_header(self):
        """Should handle None header."""
        client = EmailClient(EmailConfig())
        result = client._decode_header(None)
        assert result == ""

    def test_decode_empty_header(self):
        """Should handle empty header."""
        client = EmailClient(EmailConfig())
        result = client._decode_header("")
        assert result == ""
