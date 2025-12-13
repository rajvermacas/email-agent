"""
Unit tests for SMTP email handler.

Tests the SMTP server components from src/info_agent/email/smtp.py:
- EmailHandler class for processing incoming emails
- Email parsing and extraction
- SMTP server startup
- Error handling
- Webhook integration

Uses mocked aiosmtpd and storage/webhook components.
"""

import pytest
import email
from datetime import datetime, timezone
from email.message import Message
from unittest.mock import AsyncMock, Mock, patch, call

from aiosmtpd.smtp import Envelope, Session

from info_agent.email.models import EmailAttachment, StoredEmail
from info_agent.email.smtp import EmailHandler, start_smtp_server
from info_agent.email.storage import EmailStorage
from info_agent.email.webhook import WebhookNotifier
from info_agent.utils.exceptions import EmailError


@pytest.fixture
def mock_storage():
    """Create mock EmailStorage instance."""
    storage = Mock(spec=EmailStorage)
    storage.save_email = AsyncMock()
    return storage


@pytest.fixture
def mock_webhook_notifier():
    """Create mock WebhookNotifier instance."""
    notifier = Mock(spec=WebhookNotifier)
    notifier.notify = AsyncMock()
    return notifier


@pytest.fixture
def simple_email_envelope():
    """Create a simple email envelope for testing."""
    msg = email.message.Message()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "Test Email"
    msg.set_payload("This is the email body.")

    envelope = Mock(spec=Envelope)
    envelope.mail_from = "sender@example.com"
    envelope.rcpt_tos = ["recipient@example.com"]
    envelope.content = msg.as_bytes()

    return envelope


@pytest.fixture
def multipart_email_envelope():
    """Create a multipart email envelope with attachments."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    import email.encoders

    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "Email with Attachment"
    msg["In-Reply-To"] = "original-msg-id"

    # Add text part
    text_part = MIMEText("Email body with attachment.", "plain")
    msg.attach(text_part)

    # Add attachment
    attachment = MIMEBase("application", "pdf")
    attachment.set_payload(b"PDF content here")
    email.encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", "attachment", filename="document.pdf")
    msg.attach(attachment)

    envelope = Mock(spec=Envelope)
    envelope.mail_from = "sender@example.com"
    envelope.rcpt_tos = ["recipient@example.com"]
    envelope.content = msg.as_bytes()

    return envelope


@pytest.fixture
def mock_session():
    """Create mock SMTP session."""
    session = Mock(spec=Session)
    session.peer = ("127.0.0.1", 12345)
    return session


class TestEmailHandlerInit:
    """Tests for EmailHandler initialization."""

    def test_init_with_storage_only(self, mock_storage):
        """Test initialization with storage but no webhook."""
        handler = EmailHandler(storage=mock_storage)

        assert handler.storage == mock_storage
        assert handler.webhook_notifier is None

    def test_init_with_storage_and_webhook(self, mock_storage, mock_webhook_notifier):
        """Test initialization with both storage and webhook."""
        handler = EmailHandler(
            storage=mock_storage,
            webhook_notifier=mock_webhook_notifier
        )

        assert handler.storage == mock_storage
        assert handler.webhook_notifier == mock_webhook_notifier

    def test_init_without_storage_fails(self):
        """Test that initialization without storage raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            EmailHandler(storage=None)

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Storage is required" in exc_info.value.message


class TestEmailHandlerHandleData:
    """Tests for EmailHandler.handle_DATA method."""

    @pytest.mark.asyncio
    async def test_handle_data_simple_email(
        self, mock_storage, mock_session, simple_email_envelope
    ):
        """Test handling a simple email message."""
        handler = EmailHandler(storage=mock_storage)

        result = await handler.handle_DATA(None, mock_session, simple_email_envelope)

        assert result == "250 Message accepted for delivery"

        # Verify email was saved
        mock_storage.save_email.assert_called_once()
        saved_email = mock_storage.save_email.call_args[0][0]

        assert isinstance(saved_email, StoredEmail)
        assert saved_email.from_address == "sender@example.com"
        assert saved_email.to_address == "recipient@example.com"
        assert saved_email.inbox == "recipient@example.com"
        assert saved_email.subject == "Test Email"
        assert saved_email.body_text == "This is the email body."
        assert saved_email.read is False
        assert len(saved_email.attachments) == 0
        assert saved_email.id.startswith("msg-")

    @pytest.mark.asyncio
    async def test_handle_data_with_webhook(
        self, mock_storage, mock_webhook_notifier, mock_session, simple_email_envelope
    ):
        """Test handling email with webhook notification."""
        handler = EmailHandler(
            storage=mock_storage,
            webhook_notifier=mock_webhook_notifier
        )

        result = await handler.handle_DATA(None, mock_session, simple_email_envelope)

        assert result == "250 Message accepted for delivery"

        # Verify webhook was called
        mock_webhook_notifier.notify.assert_called_once()
        notified_email = mock_webhook_notifier.notify.call_args[0][0]
        assert isinstance(notified_email, StoredEmail)
        assert notified_email.from_address == "sender@example.com"

    @pytest.mark.asyncio
    async def test_handle_data_multipart_email(
        self, mock_storage, mock_session, multipart_email_envelope
    ):
        """Test handling multipart email with attachments."""
        handler = EmailHandler(storage=mock_storage)

        result = await handler.handle_DATA(None, mock_session, multipart_email_envelope)

        assert result == "250 Message accepted for delivery"

        # Verify email was saved with attachment
        saved_email = mock_storage.save_email.call_args[0][0]
        assert saved_email.subject == "Email with Attachment"
        assert saved_email.body_text == "Email body with attachment."
        assert saved_email.thread_id == "original-msg-id"
        assert len(saved_email.attachments) == 1
        assert saved_email.attachments[0].filename == "document.pdf"
        assert saved_email.attachments[0].content_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_handle_data_webhook_failure_does_not_fail_delivery(
        self, mock_storage, mock_webhook_notifier, mock_session, simple_email_envelope
    ):
        """Test that webhook failure doesn't prevent email storage."""
        handler = EmailHandler(
            storage=mock_storage,
            webhook_notifier=mock_webhook_notifier
        )

        # Make webhook fail
        mock_webhook_notifier.notify.side_effect = Exception("Webhook failed")

        result = await handler.handle_DATA(None, mock_session, simple_email_envelope)

        # Email should still be accepted
        assert result == "250 Message accepted for delivery"

        # Email should still be saved
        mock_storage.save_email.assert_called_once()

        # Webhook was attempted
        mock_webhook_notifier.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_data_storage_failure_returns_error(
        self, mock_storage, mock_session, simple_email_envelope
    ):
        """Test that storage failure returns SMTP error."""
        handler = EmailHandler(storage=mock_storage)

        # Make storage fail
        mock_storage.save_email.side_effect = Exception("Storage failed")

        result = await handler.handle_DATA(None, mock_session, simple_email_envelope)

        # Should return SMTP error
        assert result.startswith("554 Transaction failed")
        assert "Storage failed" in result


class TestEmailHandlerExtractEmail:
    """Tests for EmailHandler._extract_email method."""

    def test_extract_email_plain_address(self, mock_storage):
        """Test extracting plain email address."""
        handler = EmailHandler(storage=mock_storage)

        result = handler._extract_email("user@example.com")

        assert result == "user@example.com"

    def test_extract_email_with_name(self, mock_storage):
        """Test extracting email from 'Name <email>' format."""
        handler = EmailHandler(storage=mock_storage)

        result = handler._extract_email("John Doe <john@example.com>")

        assert result == "john@example.com"

    def test_extract_email_with_whitespace(self, mock_storage):
        """Test extracting email with whitespace."""
        handler = EmailHandler(storage=mock_storage)

        result = handler._extract_email("  user@example.com  ")

        assert result == "user@example.com"

    def test_extract_email_empty_fails(self, mock_storage):
        """Test that empty address raises EmailError."""
        handler = EmailHandler(storage=mock_storage)

        with pytest.raises(EmailError) as exc_info:
            handler._extract_email("")

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Email address is required" in exc_info.value.message

    def test_extract_email_invalid_format_fails(self, mock_storage):
        """Test that invalid email format raises EmailError."""
        handler = EmailHandler(storage=mock_storage)

        with pytest.raises(EmailError) as exc_info:
            handler._extract_email("invalid-email")

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Invalid email address format" in exc_info.value.message


class TestEmailHandlerDecodeHeader:
    """Tests for EmailHandler._decode_header method."""

    def test_decode_header_plain_text(self, mock_storage):
        """Test decoding plain text header."""
        handler = EmailHandler(storage=mock_storage)

        result = handler._decode_header("Plain Text Subject")

        assert result == "Plain Text Subject"

    def test_decode_header_encoded(self, mock_storage):
        """Test decoding encoded header."""
        handler = EmailHandler(storage=mock_storage)

        # Create encoded header
        encoded_subject = "=?utf-8?b?VGVzdCBTdWJqZWN0?="

        result = handler._decode_header(encoded_subject)

        assert result == "Test Subject"

    def test_decode_header_empty(self, mock_storage):
        """Test decoding empty header."""
        handler = EmailHandler(storage=mock_storage)

        result = handler._decode_header("")

        assert result == ""

    def test_decode_header_none(self, mock_storage):
        """Test decoding None header."""
        handler = EmailHandler(storage=mock_storage)

        result = handler._decode_header(None)

        assert result == ""


class TestEmailHandlerExtractBody:
    """Tests for EmailHandler._extract_body method."""

    def test_extract_body_plain_text(self, mock_storage):
        """Test extracting body from plain text message."""
        handler = EmailHandler(storage=mock_storage)

        msg = email.message.Message()
        msg.set_payload("This is the email body.")

        result = handler._extract_body(msg)

        assert result == "This is the email body."

    def test_extract_body_multipart(self, mock_storage):
        """Test extracting body from multipart message."""
        handler = EmailHandler(storage=mock_storage)

        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        text_part = MIMEText("This is the text body.", "plain")
        msg.attach(text_part)

        result = handler._extract_body(msg)

        assert result == "This is the text body."

    def test_extract_body_empty_message(self, mock_storage):
        """Test extracting body from empty message."""
        handler = EmailHandler(storage=mock_storage)

        msg = email.message.Message()

        result = handler._extract_body(msg)

        assert result == "(No body)"

    def test_extract_body_no_text_part(self, mock_storage):
        """Test extracting body when no text/plain part exists."""
        handler = EmailHandler(storage=mock_storage)

        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase

        msg = MIMEMultipart()
        attachment = MIMEBase("application", "pdf")
        msg.attach(attachment)

        result = handler._extract_body(msg)

        assert result == "(No body)"


class TestEmailHandlerExtractThreadId:
    """Tests for EmailHandler._extract_thread_id method."""

    def test_extract_thread_id_from_in_reply_to(self, mock_storage):
        """Test extracting thread ID from In-Reply-To header."""
        handler = EmailHandler(storage=mock_storage)

        msg = email.message.Message()
        msg["In-Reply-To"] = "original-message-id"

        result = handler._extract_thread_id(msg)

        assert result == "original-message-id"

    def test_extract_thread_id_from_references(self, mock_storage):
        """Test extracting thread ID from References header."""
        handler = EmailHandler(storage=mock_storage)

        msg = email.message.Message()
        msg["References"] = "msg1 msg2 msg3"

        result = handler._extract_thread_id(msg)

        assert result == "msg1"

    def test_extract_thread_id_prefers_in_reply_to(self, mock_storage):
        """Test that In-Reply-To is preferred over References."""
        handler = EmailHandler(storage=mock_storage)

        msg = email.message.Message()
        msg["In-Reply-To"] = "in-reply-to-id"
        msg["References"] = "ref1 ref2"

        result = handler._extract_thread_id(msg)

        assert result == "in-reply-to-id"

    def test_extract_thread_id_no_headers(self, mock_storage):
        """Test extracting thread ID when no headers present."""
        handler = EmailHandler(storage=mock_storage)

        msg = email.message.Message()

        result = handler._extract_thread_id(msg)

        assert result is None


class TestEmailHandlerExtractAttachments:
    """Tests for EmailHandler._extract_attachments method."""

    def test_extract_attachments_from_multipart(self, mock_storage):
        """Test extracting attachments from multipart message."""
        handler = EmailHandler(storage=mock_storage)

        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        import email.encoders

        msg = MIMEMultipart()

        # Add text part
        text_part = MIMEText("Body text", "plain")
        msg.attach(text_part)

        # Add attachment
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(b"PDF binary content")
        email.encoders.encode_base64(attachment)
        attachment.add_header("Content-Disposition", "attachment", filename="test.pdf")
        msg.attach(attachment)

        result = handler._extract_attachments(msg)

        assert len(result) == 1
        assert isinstance(result[0], EmailAttachment)
        assert result[0].filename == "test.pdf"
        assert result[0].content_type == "application/pdf"
        assert result[0].size == 18  # Length of b"PDF binary content"

    def test_extract_attachments_plain_message(self, mock_storage):
        """Test extracting attachments from plain text message."""
        handler = EmailHandler(storage=mock_storage)

        msg = email.message.Message()
        msg.set_payload("Plain text")

        result = handler._extract_attachments(msg)

        assert result == []

    def test_extract_attachments_no_filename(self, mock_storage):
        """Test that attachments without filename are skipped."""
        handler = EmailHandler(storage=mock_storage)

        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase

        msg = MIMEMultipart()

        # Add attachment without filename
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(b"Content")
        attachment.add_header("Content-Disposition", "attachment")
        msg.attach(attachment)

        result = handler._extract_attachments(msg)

        assert result == []

    def test_extract_attachments_multiple(self, mock_storage):
        """Test extracting multiple attachments."""
        handler = EmailHandler(storage=mock_storage)

        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        import email.encoders

        msg = MIMEMultipart()

        # Add first attachment
        att1 = MIMEBase("application", "pdf")
        att1.set_payload(b"PDF content")
        email.encoders.encode_base64(att1)
        att1.add_header("Content-Disposition", "attachment", filename="doc1.pdf")
        msg.attach(att1)

        # Add second attachment
        att2 = MIMEBase("image", "png")
        att2.set_payload(b"PNG content")
        email.encoders.encode_base64(att2)
        att2.add_header("Content-Disposition", "attachment", filename="image.png")
        msg.attach(att2)

        result = handler._extract_attachments(msg)

        assert len(result) == 2
        assert result[0].filename == "doc1.pdf"
        assert result[0].content_type == "application/pdf"
        assert result[1].filename == "image.png"
        assert result[1].content_type == "image/png"


class TestStartSmtpServer:
    """Tests for start_smtp_server function."""

    @pytest.mark.asyncio
    async def test_start_smtp_server_success(self, mock_storage):
        """Test successfully starting SMTP server."""
        mock_controller = Mock()
        mock_controller.start = Mock()

        with patch("info_agent.email.smtp.Controller", return_value=mock_controller):
            result = await start_smtp_server(
                host="localhost",
                port=1025,
                storage=mock_storage,
            )

        assert result == mock_controller
        mock_controller.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_smtp_server_with_webhook(
        self, mock_storage, mock_webhook_notifier
    ):
        """Test starting SMTP server with webhook notifier."""
        mock_controller = Mock()
        mock_controller.start = Mock()

        with patch("info_agent.email.smtp.Controller", return_value=mock_controller):
            result = await start_smtp_server(
                host="localhost",
                port=1025,
                storage=mock_storage,
                webhook_notifier=mock_webhook_notifier,
            )

        assert result == mock_controller
        mock_controller.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_smtp_server_empty_host_fails(self, mock_storage):
        """Test that empty host raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            await start_smtp_server(
                host="",
                port=1025,
                storage=mock_storage,
            )

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Host is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_start_smtp_server_invalid_port_fails(self, mock_storage):
        """Test that invalid port raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            await start_smtp_server(
                host="localhost",
                port=0,
                storage=mock_storage,
            )

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Valid port number is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_start_smtp_server_port_too_high_fails(self, mock_storage):
        """Test that port above 65535 raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            await start_smtp_server(
                host="localhost",
                port=70000,
                storage=mock_storage,
            )

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Valid port number is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_start_smtp_server_startup_failure(self, mock_storage):
        """Test handling of server startup failure."""
        with patch(
            "info_agent.email.smtp.Controller",
            side_effect=Exception("Failed to bind port")
        ):
            with pytest.raises(EmailError) as exc_info:
                await start_smtp_server(
                    host="localhost",
                    port=1025,
                    storage=mock_storage,
                )

            assert exc_info.value.code == "EMAIL_ERROR"
            assert "Failed to start SMTP server" in exc_info.value.message
