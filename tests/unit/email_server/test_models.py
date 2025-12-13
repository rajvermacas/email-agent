"""
Unit tests for email models.
"""

import pytest

from info_agent.email_server.models import (
    Attachment,
    Email,
    EmailAddress,
    EmailCreateRequest,
    EmailListResponse,
    EmailStatus,
    WebhookConfig,
    WebhookEvent,
)


class TestEmailAddress:
    """Tests for EmailAddress model."""

    def test_simple_address(self) -> None:
        """Test creating address with just email."""
        addr = EmailAddress(address="test@example.com")
        assert addr.address == "test@example.com"
        assert addr.name is None
        assert str(addr) == "test@example.com"

    def test_address_with_name(self) -> None:
        """Test creating address with display name."""
        addr = EmailAddress(address="test@example.com", name="Test User")
        assert addr.address == "test@example.com"
        assert addr.name == "Test User"
        assert str(addr) == "Test User <test@example.com>"

    def test_from_string_simple(self) -> None:
        """Test parsing simple email string."""
        addr = EmailAddress.from_string("user@domain.com")
        assert addr.address == "user@domain.com"
        assert addr.name is None

    def test_from_string_with_name(self) -> None:
        """Test parsing email string with display name."""
        addr = EmailAddress.from_string("John Doe <john@example.com>")
        assert addr.address == "john@example.com"
        assert addr.name == "John Doe"

    def test_from_string_whitespace(self) -> None:
        """Test parsing handles whitespace."""
        addr = EmailAddress.from_string("  user@domain.com  ")
        assert addr.address == "user@domain.com"

    def test_from_string_name_with_spaces(self) -> None:
        """Test parsing name with spaces."""
        addr = EmailAddress.from_string("First Middle Last <user@domain.com>")
        assert addr.name == "First Middle Last"


class TestEmailStatus:
    """Tests for EmailStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Test all expected statuses exist."""
        assert EmailStatus.RECEIVED.value == "received"
        assert EmailStatus.SENT.value == "sent"
        assert EmailStatus.PENDING.value == "pending"
        assert EmailStatus.FAILED.value == "failed"
        assert EmailStatus.DELIVERED.value == "delivered"
        assert EmailStatus.READ.value == "read"


class TestAttachment:
    """Tests for Attachment model."""

    def test_basic_attachment(self) -> None:
        """Test creating basic attachment."""
        attach = Attachment(
            filename="test.txt",
            content="SGVsbG8gV29ybGQ=",  # Base64 for "Hello World"
        )
        assert attach.filename == "test.txt"
        assert attach.content_type == "application/octet-stream"
        assert attach.size == 0

    def test_attachment_with_type(self) -> None:
        """Test attachment with content type."""
        attach = Attachment(
            filename="image.png",
            content_type="image/png",
            content="base64data",
            size=1024,
        )
        assert attach.content_type == "image/png"
        assert attach.size == 1024


class TestEmail:
    """Tests for Email model."""

    def test_email_creation(self) -> None:
        """Test creating a basic email."""
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="recipient@example.com")],
            subject="Test Subject",
            body_text="Test body content",
        )

        assert email.from_address.address == "sender@example.com"
        assert len(email.to_addresses) == 1
        assert email.subject == "Test Subject"
        assert email.body_text == "Test body content"

    def test_email_has_id(self) -> None:
        """Test email has auto-generated ID."""
        email = Email(
            from_address=EmailAddress(address="test@example.com"),
        )
        assert email.id is not None
        assert len(email.id) > 0

    def test_email_has_message_id(self) -> None:
        """Test email generates message ID."""
        email = Email(
            from_address=EmailAddress(address="test@example.com"),
        )
        assert email.message_id is not None
        assert "@mock-email-server" in email.message_id

    def test_email_thread_id_from_reply(self) -> None:
        """Test thread ID extracted from in_reply_to."""
        original = Email(
            from_address=EmailAddress(address="sender@example.com"),
        )

        reply = Email(
            from_address=EmailAddress(address="recipient@example.com"),
            in_reply_to=original.message_id,
        )

        assert reply.thread_id == original.id

    def test_email_default_status(self) -> None:
        """Test email has default status."""
        email = Email(
            from_address=EmailAddress(address="test@example.com"),
        )
        assert email.status == EmailStatus.RECEIVED

    def test_email_mark_as_read(self) -> None:
        """Test marking email as read."""
        email = Email(
            from_address=EmailAddress(address="test@example.com"),
        )

        email.mark_as_read()

        assert email.status == EmailStatus.READ
        assert email.read_at is not None

    def test_email_mark_as_delivered(self) -> None:
        """Test marking email as delivered."""
        email = Email(
            from_address=EmailAddress(address="test@example.com"),
        )

        email.mark_as_delivered()

        assert email.status == EmailStatus.DELIVERED

    def test_email_mark_as_failed(self) -> None:
        """Test marking email as failed with reason."""
        email = Email(
            from_address=EmailAddress(address="test@example.com"),
        )

        email.mark_as_failed("Connection timeout")

        assert email.status == EmailStatus.FAILED
        assert email.metadata["failure_reason"] == "Connection timeout"

    def test_email_get_recipients(self) -> None:
        """Test getting all recipients."""
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="to@example.com")],
            cc_addresses=[EmailAddress(address="cc@example.com")],
            bcc_addresses=[EmailAddress(address="bcc@example.com")],
        )

        recipients = email.get_recipients()

        assert len(recipients) == 3

    def test_email_get_recipient_addresses(self) -> None:
        """Test getting recipient addresses as strings."""
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[
                EmailAddress(address="to1@example.com"),
                EmailAddress(address="to2@example.com"),
            ],
        )

        addresses = email.get_recipient_addresses()

        assert addresses == ["to1@example.com", "to2@example.com"]


class TestEmailCreateRequest:
    """Tests for EmailCreateRequest model."""

    def test_create_request(self) -> None:
        """Test creating email create request."""
        request = EmailCreateRequest(
            from_address="sender@example.com",
            to_addresses=["recipient@example.com"],
            subject="Test",
            body_text="Body",
        )

        assert request.from_address == "sender@example.com"
        assert request.to_addresses == ["recipient@example.com"]

    def test_to_email(self) -> None:
        """Test converting request to Email model."""
        request = EmailCreateRequest(
            from_address="sender@example.com",
            to_addresses=["recipient@example.com"],
            cc_addresses=["cc@example.com"],
            subject="Test Subject",
            body_text="Test body",
        )

        email = request.to_email()

        assert email.from_address.address == "sender@example.com"
        assert email.to_addresses[0].address == "recipient@example.com"
        assert email.cc_addresses[0].address == "cc@example.com"
        assert email.subject == "Test Subject"
        assert email.status == EmailStatus.PENDING
        assert email.mailbox == "sent"


class TestEmailListResponse:
    """Tests for EmailListResponse model."""

    def test_list_response(self) -> None:
        """Test email list response."""
        emails = [
            Email(from_address=EmailAddress(address="test@example.com"))
            for _ in range(5)
        ]

        response = EmailListResponse(
            emails=emails,
            total=25,
            page=1,
            page_size=5,
            has_more=True,
        )

        assert len(response.emails) == 5
        assert response.total == 25
        assert response.has_more is True


class TestWebhookConfig:
    """Tests for WebhookConfig model."""

    def test_webhook_config(self) -> None:
        """Test creating webhook config."""
        webhook = WebhookConfig(
            url="https://example.com/webhook",
            events=["email.received"],
        )

        assert webhook.url == "https://example.com/webhook"
        assert "email.received" in webhook.events
        assert webhook.active is True

    def test_webhook_has_id(self) -> None:
        """Test webhook has auto-generated ID."""
        webhook = WebhookConfig(url="https://example.com/webhook")
        assert webhook.id is not None
        assert len(webhook.id) > 0

    def test_webhook_with_secret(self) -> None:
        """Test webhook with secret."""
        webhook = WebhookConfig(
            url="https://example.com/webhook",
            secret="my-secret-key",
        )
        assert webhook.secret == "my-secret-key"


class TestWebhookEvent:
    """Tests for WebhookEvent model."""

    def test_webhook_event(self) -> None:
        """Test creating webhook event."""
        event = WebhookEvent(
            event_type="email.received",
            data={"email_id": "123"},
        )

        assert event.event_type == "email.received"
        assert event.data["email_id"] == "123"

    def test_event_has_id(self) -> None:
        """Test event has auto-generated ID."""
        event = WebhookEvent(event_type="email.received")
        assert event.id is not None

    def test_event_has_timestamp(self) -> None:
        """Test event has timestamp."""
        event = WebhookEvent(event_type="email.received")
        assert event.timestamp is not None
