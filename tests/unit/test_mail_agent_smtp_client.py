"""
Unit tests for SMTP client wrapper.

Tests the SMTPClient class with mocked aiosmtplib to avoid
actual SMTP connections during testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from info_agent.agents.mail.smtp_client import SMTPClient
from info_agent.utils.exceptions import EmailError


class TestSMTPClientInit:
    """Tests for SMTPClient initialization."""

    def test_init_success_with_defaults(self):
        """Test successful initialization with default timeout."""
        client = SMTPClient(host="smtp.example.com", port=25)

        assert client.host == "smtp.example.com"
        assert client.port == 25
        assert client.timeout == 30.0  # DEFAULT_TIMEOUT

    def test_init_success_with_custom_timeout(self):
        """Test successful initialization with custom timeout."""
        client = SMTPClient(host="smtp.example.com", port=587, timeout=60.0)

        assert client.host == "smtp.example.com"
        assert client.port == 587
        assert client.timeout == 60.0

    def test_init_missing_host(self):
        """Test initialization fails when host is missing."""
        with pytest.raises(EmailError) as exc_info:
            SMTPClient(host="", port=25)

        assert "SMTP host is required" in str(exc_info.value)
        assert exc_info.value.code == "EMAIL_ERROR"

    def test_init_none_host(self):
        """Test initialization fails when host is None."""
        with pytest.raises(EmailError) as exc_info:
            SMTPClient(host=None, port=25)  # type: ignore

        assert "SMTP host is required" in str(exc_info.value)

    def test_init_missing_port(self):
        """Test initialization fails when port is None."""
        with pytest.raises(EmailError) as exc_info:
            SMTPClient(host="smtp.example.com", port=None)  # type: ignore

        assert "SMTP port must be a positive integer" in str(exc_info.value)

    def test_init_invalid_port_zero(self):
        """Test initialization fails when port is zero."""
        with pytest.raises(EmailError) as exc_info:
            SMTPClient(host="smtp.example.com", port=0)

        assert "SMTP port must be a positive integer" in str(exc_info.value)

    def test_init_invalid_port_negative(self):
        """Test initialization fails when port is negative."""
        with pytest.raises(EmailError) as exc_info:
            SMTPClient(host="smtp.example.com", port=-25)

        assert "SMTP port must be a positive integer" in str(exc_info.value)

    def test_init_invalid_port_too_large(self):
        """Test initialization fails when port exceeds 65535."""
        with pytest.raises(EmailError) as exc_info:
            SMTPClient(host="smtp.example.com", port=70000)

        assert "SMTP port must be <= 65535" in str(exc_info.value)

    def test_init_port_boundary_valid(self):
        """Test initialization succeeds with port at upper boundary."""
        client = SMTPClient(host="smtp.example.com", port=65535)

        assert client.port == 65535


class TestSMTPClientSendEmail:
    """Tests for SMTPClient.send_email method."""

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Test successful email sending."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.return_value = None

            message_id = await client.send_email(
                to_address="recipient@example.com",
                subject="Test Subject",
                body_text="This is a test email body.",
            )

            assert message_id.startswith("<")
            assert message_id.endswith("@smtp.example.com>")
            assert "smtp.example.com" in message_id

            # Verify send was called
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args.kwargs["hostname"] == "smtp.example.com"
            assert call_args.kwargs["port"] == 25
            assert call_args.kwargs["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_send_email_with_custom_from(self):
        """Test email sending with custom from address."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.return_value = None

            message_id = await client.send_email(
                to_address="recipient@example.com",
                subject="Test",
                body_text="Body",
                from_address="custom@example.com",
            )

            assert message_id is not None

            # Check MIME message has correct from address
            call_args = mock_send.call_args
            msg = call_args.args[0]
            assert msg["From"] == "custom@example.com"
            assert msg["To"] == "recipient@example.com"

    @pytest.mark.asyncio
    async def test_send_email_with_default_from(self):
        """Test email sending uses default from address when not provided."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.return_value = None

            await client.send_email(
                to_address="recipient@example.com",
                subject="Test",
                body_text="Body",
            )

            call_args = mock_send.call_args
            msg = call_args.args[0]
            assert msg["From"] == "info-agent@localhost"

    @pytest.mark.asyncio
    async def test_send_email_with_thread_id(self):
        """Test email sending with thread ID for threading."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.return_value = None

            await client.send_email(
                to_address="recipient@example.com",
                subject="Re: Previous Email",
                body_text="Reply body",
                thread_id="<original-msg-id@example.com>",
            )

            call_args = mock_send.call_args
            msg = call_args.args[0]
            assert msg["In-Reply-To"] == "<original-msg-id@example.com>"
            assert msg["References"] == "<original-msg-id@example.com>"

    @pytest.mark.asyncio
    async def test_send_email_without_thread_id(self):
        """Test email sending without thread ID."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.return_value = None

            await client.send_email(
                to_address="recipient@example.com",
                subject="New Email",
                body_text="Body",
            )

            call_args = mock_send.call_args
            msg = call_args.args[0]
            assert "In-Reply-To" not in msg
            assert "References" not in msg

    @pytest.mark.asyncio
    async def test_send_email_missing_to_address(self):
        """Test email sending fails when to_address is missing."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with pytest.raises(EmailError) as exc_info:
            await client.send_email(
                to_address="",
                subject="Test",
                body_text="Body",
            )

        assert "Recipient address (to_address) is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_email_missing_subject(self):
        """Test email sending fails when subject is missing."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with pytest.raises(EmailError) as exc_info:
            await client.send_email(
                to_address="recipient@example.com",
                subject="",
                body_text="Body",
            )

        assert "Email subject is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_email_missing_body(self):
        """Test email sending fails when body is missing."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with pytest.raises(EmailError) as exc_info:
            await client.send_email(
                to_address="recipient@example.com",
                subject="Test",
                body_text="",
            )

        assert "Email body (body_text) is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_email_smtp_exception(self):
        """Test email sending handles SMTP exceptions."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            from aiosmtplib import SMTPException

            mock_send.side_effect = SMTPException("SMTP server error")

            with pytest.raises(EmailError) as exc_info:
                await client.send_email(
                    to_address="recipient@example.com",
                    subject="Test",
                    body_text="Body",
                )

            assert "SMTP error" in str(exc_info.value)
            assert exc_info.value.recipient == "recipient@example.com"

    @pytest.mark.asyncio
    async def test_send_email_network_error(self):
        """Test email sending handles network errors."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.side_effect = OSError("Connection refused")

            with pytest.raises(EmailError) as exc_info:
                await client.send_email(
                    to_address="recipient@example.com",
                    subject="Test",
                    body_text="Body",
                )

            assert "Network error" in str(exc_info.value)
            assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_email_unexpected_error(self):
        """Test email sending handles unexpected errors."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(EmailError) as exc_info:
                await client.send_email(
                    to_address="recipient@example.com",
                    subject="Test",
                    body_text="Body",
                )

            assert "Unexpected error while sending email" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_email_mime_creation_failure(self):
        """Test email sending handles MIME message creation failure."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch.object(client, "_create_mime_message") as mock_create:
            mock_create.side_effect = ValueError("Invalid email format")

            with pytest.raises(EmailError) as exc_info:
                await client.send_email(
                    to_address="recipient@example.com",
                    subject="Test",
                    body_text="Body",
                )

            assert "Failed to create email message" in str(exc_info.value)


class TestSMTPClientCreateMimeMessage:
    """Tests for SMTPClient._create_mime_message method."""

    def test_create_mime_message_basic(self):
        """Test MIME message creation with basic parameters."""
        client = SMTPClient(host="smtp.example.com", port=25)

        msg = client._create_mime_message(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body_text="Test body content",
            message_id="<msg-123@smtp.example.com>",
        )

        assert msg["From"] == "sender@example.com"
        assert msg["To"] == "recipient@example.com"
        assert msg["Subject"] == "Test Subject"
        assert msg["Message-ID"] == "<msg-123@smtp.example.com>"
        assert "Date" in msg

    def test_create_mime_message_with_threading(self):
        """Test MIME message creation with thread ID."""
        client = SMTPClient(host="smtp.example.com", port=25)

        thread_id = "<original-msg@example.com>"
        msg = client._create_mime_message(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Re: Test",
            body_text="Reply content",
            message_id="<reply-123@smtp.example.com>",
            thread_id=thread_id,
        )

        assert msg["In-Reply-To"] == thread_id
        assert msg["References"] == thread_id

    def test_create_mime_message_multipart(self):
        """Test MIME message is multipart."""
        client = SMTPClient(host="smtp.example.com", port=25)

        msg = client._create_mime_message(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body_text="Body",
            message_id="<msg-123@smtp.example.com>",
        )

        assert msg.is_multipart()
        assert len(msg.get_payload()) > 0

    def test_create_mime_message_body_encoding(self):
        """Test MIME message handles special characters in body."""
        client = SMTPClient(host="smtp.example.com", port=25)

        body_with_special = "Hello,\n\nThis contains special chars: é, ñ, 中文\n\nBest regards"

        msg = client._create_mime_message(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Special Characters",
            body_text=body_with_special,
            message_id="<msg-special@smtp.example.com>",
        )

        # Message should be created without errors
        assert msg is not None
        assert msg["Subject"] == "Special Characters"


class TestSMTPClientTestConnection:
    """Tests for SMTPClient.test_connection method."""

    @pytest.mark.asyncio
    async def test_connection_success(self):
        """Test successful connection test."""
        client = SMTPClient(host="smtp.example.com", port=25)

        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.noop = AsyncMock(return_value=(250, "OK"))

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.return_value = mock_smtp

            result = await client.test_connection()

            assert result is True
            mock_smtp.noop.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_smtp_exception(self):
        """Test connection test handles SMTP exceptions."""
        client = SMTPClient(host="smtp.example.com", port=25)

        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.SMTP") as mock_smtp_class:
            from aiosmtplib import SMTPException

            mock_smtp_class.side_effect = SMTPException("SMTP error")

            with pytest.raises(EmailError) as exc_info:
                await client.test_connection()

            assert "SMTP connection test failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_network_error(self):
        """Test connection test handles network errors."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.side_effect = OSError("Network unreachable")

            with pytest.raises(EmailError) as exc_info:
                await client.test_connection()

            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_unexpected_error(self):
        """Test connection test handles unexpected errors."""
        client = SMTPClient(host="smtp.example.com", port=25)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.side_effect = RuntimeError("Unexpected")

            with pytest.raises(EmailError) as exc_info:
                await client.test_connection()

            assert "Unexpected connection error" in str(exc_info.value)


class TestSMTPClientIntegration:
    """Integration-style tests for common usage scenarios."""

    @pytest.mark.asyncio
    async def test_typical_email_workflow(self):
        """Test typical workflow of creating client and sending email."""
        client = SMTPClient(host="smtp.example.com", port=587, timeout=45.0)

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.return_value = None

            # Send first email
            msg_id_1 = await client.send_email(
                to_address="user1@example.com",
                subject="First Email",
                body_text="Hello, this is the first email.",
                from_address="sender@example.com",
            )

            assert msg_id_1 is not None

            # Send reply email with threading
            msg_id_2 = await client.send_email(
                to_address="user1@example.com",
                subject="Re: First Email",
                body_text="This is a follow-up.",
                from_address="sender@example.com",
                thread_id=msg_id_1,
            )

            assert msg_id_2 is not None
            assert msg_id_1 != msg_id_2

            # Verify both calls were made
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_email_sending(self):
        """Test sending multiple emails in sequence."""
        client = SMTPClient(host="smtp.example.com", port=25)

        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
        message_ids = []

        with patch("info_agent.agents.mail.smtp_client.aiosmtplib.send") as mock_send:
            mock_send.return_value = None

            for recipient in recipients:
                msg_id = await client.send_email(
                    to_address=recipient,
                    subject="Batch Email",
                    body_text=f"Hello {recipient}",
                )
                message_ids.append(msg_id)

            # All message IDs should be unique
            assert len(message_ids) == 3
            assert len(set(message_ids)) == 3

            # Send should be called for each recipient
            assert mock_send.call_count == 3
