"""
Email Client Integration

Provides a unified interface for email operations across providers:
- Gmail (OAuth2)
- IMAP/SMTP (generic)
- Microsoft 365 (future)

Features:
- Fetch unread emails
- Send emails (text and HTML)
- Search emails
- Mark as read/unread
- Folder management
"""

import email
import imaplib
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents an email message."""
    id: str
    subject: str
    sender: str
    sender_name: str
    recipients: List[str]
    date: datetime
    body_text: str
    body_html: Optional[str] = None
    is_read: bool = False
    folder: str = "INBOX"
    headers: Dict[str, str] = field(default_factory=dict)
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def snippet(self) -> str:
        """Get first 100 chars of body."""
        text = self.body_text or ""
        return text[:100].strip() + "..." if len(text) > 100 else text.strip()


@dataclass
class EmailConfig:
    """Email client configuration."""
    # IMAP settings
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_ssl: bool = True

    # SMTP settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_tls: bool = True

    # Authentication
    email: str = ""
    password: str = ""  # App password for Gmail

    # Provider hint
    provider: str = "gmail"  # gmail, outlook, imap


class EmailClient:
    """
    Unified email client supporting IMAP/SMTP.

    For Gmail: Use App Passwords (Settings > Security > App passwords)
    """

    def __init__(self, config: EmailConfig):
        self._config = config
        self._imap: Optional[imaplib.IMAP4_SSL] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to IMAP server."""
        try:
            if self._config.imap_ssl:
                context = ssl.create_default_context()
                self._imap = imaplib.IMAP4_SSL(
                    self._config.imap_host,
                    self._config.imap_port,
                    ssl_context=context
                )
            else:
                self._imap = imaplib.IMAP4(
                    self._config.imap_host,
                    self._config.imap_port
                )

            self._imap.login(self._config.email, self._config.password)
            self._connected = True
            logger.info(f"Connected to {self._config.imap_host}")
            return True

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP login failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from IMAP server."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None
        self._connected = False

    def list_folders(self) -> List[str]:
        """List all email folders."""
        if not self._ensure_connected():
            return []

        try:
            status, folders = self._imap.list()
            if status != "OK":
                return []

            result = []
            for folder in folders:
                if isinstance(folder, bytes):
                    # Parse folder name from response
                    parts = folder.decode().split(' "/" ')
                    if len(parts) > 1:
                        result.append(parts[1].strip('"'))
            return result
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
            return []

    def fetch_unread(
        self,
        folder: str = "INBOX",
        limit: int = 10,
    ) -> List[EmailMessage]:
        """Fetch unread emails from a folder."""
        return self.search(folder=folder, criteria="UNSEEN", limit=limit)

    def search(
        self,
        folder: str = "INBOX",
        criteria: str = "ALL",
        limit: int = 50,
    ) -> List[EmailMessage]:
        """
        Search emails in a folder.

        Criteria examples:
        - "ALL" - all messages
        - "UNSEEN" - unread messages
        - "FROM someone@example.com"
        - "SUBJECT hello"
        - "SINCE 01-Jan-2024"
        """
        if not self._ensure_connected():
            return []

        try:
            self._imap.select(folder)
            status, data = self._imap.search(None, criteria)

            if status != "OK":
                return []

            message_ids = data[0].split()
            # Get most recent messages first
            message_ids = message_ids[-limit:] if limit else message_ids
            message_ids.reverse()

            messages = []
            for msg_id in message_ids:
                msg = self._fetch_message(msg_id, folder)
                if msg:
                    messages.append(msg)

            return messages

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _fetch_message(
        self,
        msg_id: bytes,
        folder: str,
    ) -> Optional[EmailMessage]:
        """Fetch a single message by ID."""
        try:
            status, data = self._imap.fetch(msg_id, "(RFC822 FLAGS)")
            if status != "OK":
                return None

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Extract flags
            flags_data = data[0][0].decode() if data[0][0] else ""
            is_read = "\\Seen" in flags_data

            # Parse headers
            subject = self._decode_header(msg["Subject"] or "")
            sender_raw = msg["From"] or ""
            sender_name, sender_email = parseaddr(sender_raw)
            date_str = msg["Date"] or ""

            # Parse date
            try:
                date = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.now()

            # Get recipients
            to_raw = msg["To"] or ""
            recipients = [addr.strip() for addr in to_raw.split(",")]

            # Extract body
            body_text = ""
            body_html = None

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text = payload.decode("utf-8", errors="replace")
                    elif content_type == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_html = payload.decode("utf-8", errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body_text = payload.decode("utf-8", errors="replace")

            return EmailMessage(
                id=msg_id.decode(),
                subject=subject,
                sender=sender_email,
                sender_name=sender_name or sender_email,
                recipients=recipients,
                date=date,
                body_text=body_text,
                body_html=body_html,
                is_read=is_read,
                folder=folder,
            )

        except Exception as e:
            logger.error(f"Failed to fetch message: {e}")
            return None

    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ""
        try:
            decoded = email.header.decode_header(header)
            parts = []
            for content, encoding in decoded:
                if isinstance(content, bytes):
                    parts.append(content.decode(encoding or "utf-8", errors="replace"))
                else:
                    parts.append(content)
            return "".join(parts)
        except Exception:
            return header

    def mark_as_read(self, msg_id: str, folder: str = "INBOX") -> bool:
        """Mark a message as read."""
        if not self._ensure_connected():
            return False

        try:
            self._imap.select(folder)
            self._imap.store(msg_id.encode(), "+FLAGS", "\\Seen")
            return True
        except Exception as e:
            logger.error(f"Failed to mark as read: {e}")
            return False

    def mark_as_unread(self, msg_id: str, folder: str = "INBOX") -> bool:
        """Mark a message as unread."""
        if not self._ensure_connected():
            return False

        try:
            self._imap.select(folder)
            self._imap.store(msg_id.encode(), "-FLAGS", "\\Seen")
            return True
        except Exception as e:
            logger.error(f"Failed to mark as unread: {e}")
            return False

    def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SMTP.

        Args:
            to: List of recipient addresses
            subject: Email subject
            body: Plain text body
            html: Optional HTML body
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            reply_to: Optional reply-to address

        Returns:
            True if sent successfully
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._config.email
            msg["To"] = ", ".join(to)

            if cc:
                msg["Cc"] = ", ".join(cc)
            if reply_to:
                msg["Reply-To"] = reply_to

            # Add text part
            msg.attach(MIMEText(body, "plain"))

            # Add HTML part if provided
            if html:
                msg.attach(MIMEText(html, "html"))

            # Build recipient list
            all_recipients = list(to)
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            # Connect and send
            if self._config.smtp_tls:
                with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                    server.starttls()
                    server.login(self._config.email, self._config.password)
                    server.sendmail(self._config.email, all_recipients, msg.as_string())
            else:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self._config.smtp_host,
                    self._config.smtp_port,
                    context=context
                ) as server:
                    server.login(self._config.email, self._config.password)
                    server.sendmail(self._config.email, all_recipients, msg.as_string())

            logger.info(f"Email sent to {', '.join(to)}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _ensure_connected(self) -> bool:
        """Ensure IMAP connection is active."""
        if not self._connected or not self._imap:
            return self.connect()

        try:
            self._imap.noop()
            return True
        except Exception:
            return self.connect()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# Factory functions for common providers

def create_gmail_client(
    email: str,
    app_password: str,
) -> EmailClient:
    """
    Create a Gmail client.

    Requires an App Password (not regular password).
    Set up at: https://myaccount.google.com/apppasswords
    """
    config = EmailConfig(
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_tls=True,
        email=email,
        password=app_password,
        provider="gmail",
    )
    return EmailClient(config)


def create_outlook_client(
    email: str,
    password: str,
) -> EmailClient:
    """Create an Outlook/Hotmail client."""
    config = EmailConfig(
        imap_host="outlook.office365.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.office365.com",
        smtp_port=587,
        smtp_tls=True,
        email=email,
        password=password,
        provider="outlook",
    )
    return EmailClient(config)


def create_imap_client(
    email: str,
    password: str,
    imap_host: str,
    smtp_host: str,
    imap_port: int = 993,
    smtp_port: int = 587,
) -> EmailClient:
    """Create a generic IMAP client."""
    config = EmailConfig(
        imap_host=imap_host,
        imap_port=imap_port,
        imap_ssl=True,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_tls=True,
        email=email,
        password=password,
        provider="imap",
    )
    return EmailClient(config)
