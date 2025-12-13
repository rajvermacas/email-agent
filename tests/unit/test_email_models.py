"""
Unit tests for email Pydantic models.

Tests all data models from src/info_agent/email/models.py:
- EmailAttachment: Attachment metadata model
- StoredEmail: Complete email data model
- CreateEmailRequest: Request model for creating emails
- EmailReplyRequest: Request model for replying to emails
- WebhookPayload: Webhook notification payload model

All tests use explicit test data with no fallback values.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from info_agent.email.models import (
    EmailAttachment,
    StoredEmail,
    CreateEmailRequest,
    EmailReplyRequest,
    WebhookPayload,
)


class TestEmailAttachment:
    """Tests for EmailAttachment model."""

    def test_valid_attachment(self):
        """Test creating a valid attachment."""
        attachment = EmailAttachment(
            filename="document.pdf",
            content_type="application/pdf",
            size=1024,
            content="YmFzZTY0IGVuY29kZWQgY29udGVudA==",
        )

        assert attachment.filename == "document.pdf"
        assert attachment.content_type == "application/pdf"
        assert attachment.size == 1024
        assert attachment.content == "YmFzZTY0IGVuY29kZWQgY29udGVudA=="

    def test_attachment_strips_whitespace_from_filename(self):
        """Test that filename whitespace is stripped."""
        attachment = EmailAttachment(
            filename="  document.pdf  ",
            content_type="application/pdf",
            size=1024,
            content="YmFzZTY0",
        )

        assert attachment.filename == "document.pdf"

    def test_attachment_strips_whitespace_from_content_type(self):
        """Test that content_type whitespace is stripped."""
        attachment = EmailAttachment(
            filename="document.pdf",
            content_type="  application/pdf  ",
            size=1024,
            content="YmFzZTY0",
        )

        assert attachment.content_type == "application/pdf"

    def test_attachment_empty_filename_fails(self):
        """Test that empty filename raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailAttachment(
                filename="",
                content_type="application/pdf",
                size=1024,
                content="YmFzZTY0",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("filename",) for error in errors)

    def test_attachment_whitespace_only_filename_fails(self):
        """Test that whitespace-only filename raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailAttachment(
                filename="   ",
                content_type="application/pdf",
                size=1024,
                content="YmFzZTY0",
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("filename",) and "empty or whitespace" in str(error["msg"])
            for error in errors
        )

    def test_attachment_empty_content_type_fails(self):
        """Test that empty content_type raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailAttachment(
                filename="document.pdf",
                content_type="",
                size=1024,
                content="YmFzZTY0",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("content_type",) for error in errors)

    def test_attachment_whitespace_only_content_type_fails(self):
        """Test that whitespace-only content_type raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailAttachment(
                filename="document.pdf",
                content_type="   ",
                size=1024,
                content="YmFzZTY0",
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("content_type",)
            and "empty or whitespace" in str(error["msg"])
            for error in errors
        )

    def test_attachment_negative_size_fails(self):
        """Test that negative size raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailAttachment(
                filename="document.pdf",
                content_type="application/pdf",
                size=-1,
                content="YmFzZTY0",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("size",) for error in errors)

    def test_attachment_zero_size_allowed(self):
        """Test that zero size is allowed for empty files."""
        attachment = EmailAttachment(
            filename="empty.txt",
            content_type="text/plain",
            size=0,
            content="e",  # Minimal base64 content
        )

        assert attachment.size == 0

    def test_attachment_empty_content_fails(self):
        """Test that empty content raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailAttachment(
                filename="document.pdf",
                content_type="application/pdf",
                size=1024,
                content="",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("content",) for error in errors)

    def test_attachment_large_file(self):
        """Test attachment with large size value."""
        large_content = "A" * 10000
        attachment = EmailAttachment(
            filename="large_file.bin",
            content_type="application/octet-stream",
            size=10485760,  # 10MB
            content=large_content,
        )

        assert attachment.size == 10485760
        assert len(attachment.content) == 10000


class TestStoredEmail:
    """Tests for StoredEmail model."""

    def test_valid_stored_email(self):
        """Test creating a valid stored email."""
        received_at = datetime.now(timezone.utc)
        email = StoredEmail(
            id="msg-abc123",
            inbox="user@example.com",
            thread_id="thread-xyz",
            from_address="sender@example.com",
            to_address="user@example.com",
            subject="Test Email",
            body_text="This is a test email.",
            attachments=[],
            received_at=received_at,
            read=False,
        )

        assert email.id == "msg-abc123"
        assert email.inbox == "user@example.com"
        assert email.thread_id == "thread-xyz"
        assert email.from_address == "sender@example.com"
        assert email.to_address == "user@example.com"
        assert email.subject == "Test Email"
        assert email.body_text == "This is a test email."
        assert email.attachments == []
        assert email.received_at == received_at
        assert email.read is False

    def test_stored_email_with_attachments(self):
        """Test stored email with attachments."""
        attachment = EmailAttachment(
            filename="doc.pdf",
            content_type="application/pdf",
            size=1024,
            content="YmFzZTY0",
        )
        email = StoredEmail(
            id="msg-abc123",
            inbox="user@example.com",
            thread_id=None,
            from_address="sender@example.com",
            to_address="user@example.com",
            subject="Email with Attachment",
            body_text="See attached.",
            attachments=[attachment],
            received_at=datetime.now(timezone.utc),
            read=False,
        )

        assert len(email.attachments) == 1
        assert email.attachments[0].filename == "doc.pdf"

    def test_stored_email_optional_thread_id(self):
        """Test that thread_id is optional."""
        email = StoredEmail(
            id="msg-abc123",
            inbox="user@example.com",
            thread_id=None,
            from_address="sender@example.com",
            to_address="user@example.com",
            subject="Test Email",
            body_text="This is a test email.",
            received_at=datetime.now(timezone.utc),
        )

        assert email.thread_id is None

    def test_stored_email_default_read_false(self):
        """Test that read defaults to False."""
        email = StoredEmail(
            id="msg-abc123",
            inbox="user@example.com",
            from_address="sender@example.com",
            to_address="user@example.com",
            subject="Test Email",
            body_text="This is a test email.",
            received_at=datetime.now(timezone.utc),
        )

        assert email.read is False

    def test_stored_email_strips_whitespace(self):
        """Test that string fields strip whitespace."""
        email = StoredEmail(
            id="  msg-abc123  ",
            inbox="  user@example.com  ",
            from_address="  sender@example.com  ",
            to_address="  recipient@example.com  ",
            subject="  Test Subject  ",
            body_text="  Test body  ",
            received_at=datetime.now(timezone.utc),
        )

        assert email.id == "msg-abc123"
        assert email.inbox == "user@example.com"
        assert email.from_address == "sender@example.com"
        assert email.to_address == "recipient@example.com"
        assert email.subject == "Test Subject"
        assert email.body_text == "Test body"

    def test_stored_email_empty_id_fails(self):
        """Test that empty id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="",
                inbox="user@example.com",
                from_address="sender@example.com",
                to_address="user@example.com",
                subject="Test",
                body_text="Test",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)

    def test_stored_email_whitespace_only_id_fails(self):
        """Test that whitespace-only id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="   ",
                inbox="user@example.com",
                from_address="sender@example.com",
                to_address="user@example.com",
                subject="Test",
                body_text="Test",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("id",) and "empty or whitespace" in str(error["msg"])
            for error in errors
        )

    def test_stored_email_invalid_inbox_email_fails(self):
        """Test that invalid inbox email raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="msg-123",
                inbox="invalid-email",
                from_address="sender@example.com",
                to_address="user@example.com",
                subject="Test",
                body_text="Test",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("inbox",) and "Invalid email address" in str(error["msg"])
            for error in errors
        )

    def test_stored_email_invalid_from_address_fails(self):
        """Test that invalid from_address raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="msg-123",
                inbox="user@example.com",
                from_address="invalid",
                to_address="user@example.com",
                subject="Test",
                body_text="Test",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("from_address",)
            and "Invalid email address" in str(error["msg"])
            for error in errors
        )

    def test_stored_email_invalid_to_address_fails(self):
        """Test that invalid to_address raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="msg-123",
                inbox="user@example.com",
                from_address="sender@example.com",
                to_address="user@",
                subject="Test",
                body_text="Test",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("to_address",)
            and "Invalid email address" in str(error["msg"])
            for error in errors
        )

    def test_stored_email_missing_domain_dot_fails(self):
        """Test that email without dot in domain fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="msg-123",
                inbox="user@localhost",
                from_address="sender@example.com",
                to_address="user@example.com",
                subject="Test",
                body_text="Test",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("inbox",) and "Invalid email domain" in str(error["msg"])
            for error in errors
        )

    def test_stored_email_empty_subject_fails(self):
        """Test that empty subject raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="msg-123",
                inbox="user@example.com",
                from_address="sender@example.com",
                to_address="user@example.com",
                subject="",
                body_text="Test",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("subject",) for error in errors)

    def test_stored_email_empty_body_text_fails(self):
        """Test that empty body_text raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="msg-123",
                inbox="user@example.com",
                from_address="sender@example.com",
                to_address="user@example.com",
                subject="Test",
                body_text="",
                received_at=datetime.now(timezone.utc),
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("body_text",) for error in errors)

    def test_stored_email_missing_received_at_fails(self):
        """Test that missing received_at raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoredEmail(
                id="msg-123",
                inbox="user@example.com",
                from_address="sender@example.com",
                to_address="user@example.com",
                subject="Test",
                body_text="Test",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("received_at",) for error in errors)


class TestCreateEmailRequest:
    """Tests for CreateEmailRequest model."""

    def test_valid_create_request(self):
        """Test creating a valid email request."""
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body_text="Test body content.",
            thread_id="thread-123",
            attachments=[],
        )

        assert request.from_address == "sender@example.com"
        assert request.to_address == "recipient@example.com"
        assert request.subject == "Test Subject"
        assert request.body_text == "Test body content."
        assert request.thread_id == "thread-123"
        assert request.attachments == []

    def test_create_request_minimal_fields(self):
        """Test request with only required fields."""
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body_text="Body",
        )

        assert request.from_address == "sender@example.com"
        assert request.to_address == "recipient@example.com"
        assert request.subject == "Test"
        assert request.body_text == "Body"
        assert request.thread_id is None
        assert request.attachments == []

    def test_create_request_with_attachments(self):
        """Test request with attachments."""
        attachment = EmailAttachment(
            filename="test.txt",
            content_type="text/plain",
            size=100,
            content="dGVzdA==",
        )
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body_text="Body",
            attachments=[attachment],
        )

        assert len(request.attachments) == 1
        assert request.attachments[0].filename == "test.txt"

    def test_create_request_strips_whitespace(self):
        """Test that string fields strip whitespace."""
        request = CreateEmailRequest(
            from_address="  sender@example.com  ",
            to_address="  recipient@example.com  ",
            subject="  Test Subject  ",
            body_text="  Test body  ",
        )

        assert request.from_address == "sender@example.com"
        assert request.to_address == "recipient@example.com"
        assert request.subject == "Test Subject"
        assert request.body_text == "Test body"

    def test_create_request_empty_from_address_fails(self):
        """Test that empty from_address raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CreateEmailRequest(
                from_address="",
                to_address="recipient@example.com",
                subject="Test",
                body_text="Body",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("from_address",) for error in errors)

    def test_create_request_invalid_from_address_fails(self):
        """Test that invalid from_address raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CreateEmailRequest(
                from_address="invalid-email",
                to_address="recipient@example.com",
                subject="Test",
                body_text="Body",
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("from_address",)
            and "Invalid email address" in str(error["msg"])
            for error in errors
        )

    def test_create_request_invalid_to_address_fails(self):
        """Test that invalid to_address raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CreateEmailRequest(
                from_address="sender@example.com",
                to_address="@example.com",
                subject="Test",
                body_text="Body",
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("to_address",)
            and "Invalid email address" in str(error["msg"])
            for error in errors
        )

    def test_create_request_empty_subject_fails(self):
        """Test that empty subject raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CreateEmailRequest(
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="",
                body_text="Body",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("subject",) for error in errors)

    def test_create_request_whitespace_only_body_text_fails(self):
        """Test that whitespace-only body_text raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CreateEmailRequest(
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body_text="   ",
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("body_text",)
            and "empty or whitespace" in str(error["msg"])
            for error in errors
        )


class TestEmailReplyRequest:
    """Tests for EmailReplyRequest model."""

    def test_valid_reply_request(self):
        """Test creating a valid reply request."""
        request = EmailReplyRequest(
            body_text="This is my reply.",
            attachments=[],
        )

        assert request.body_text == "This is my reply."
        assert request.attachments == []

    def test_reply_request_with_attachments(self):
        """Test reply request with attachments."""
        attachment = EmailAttachment(
            filename="reply.pdf",
            content_type="application/pdf",
            size=2048,
            content="cGRmIGNvbnRlbnQ=",
        )
        request = EmailReplyRequest(
            body_text="Please see attachment.",
            attachments=[attachment],
        )

        assert len(request.attachments) == 1
        assert request.attachments[0].filename == "reply.pdf"

    def test_reply_request_strips_whitespace(self):
        """Test that body_text strips whitespace."""
        request = EmailReplyRequest(
            body_text="  Reply content  ",
        )

        assert request.body_text == "Reply content"

    def test_reply_request_empty_body_text_fails(self):
        """Test that empty body_text raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailReplyRequest(body_text="")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("body_text",) for error in errors)

    def test_reply_request_whitespace_only_body_text_fails(self):
        """Test that whitespace-only body_text raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailReplyRequest(body_text="   ")

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("body_text",)
            and "empty or whitespace" in str(error["msg"])
            for error in errors
        )

    def test_reply_request_minimal(self):
        """Test minimal reply request."""
        request = EmailReplyRequest(body_text="OK")

        assert request.body_text == "OK"
        assert request.attachments == []


class TestWebhookPayload:
    """Tests for WebhookPayload model."""

    def test_valid_webhook_payload(self):
        """Test creating a valid webhook payload."""
        payload = WebhookPayload(
            event="email.received",
            message_id="msg-abc123",
            thread_id="thread-xyz",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Email",
            body="This is the body.",
            attachments=[],
            received_at="2025-12-13T10:30:00Z",
        )

        assert payload.event == "email.received"
        assert payload.message_id == "msg-abc123"
        assert payload.thread_id == "thread-xyz"
        assert payload.from_address == "sender@example.com"
        assert payload.to_address == "recipient@example.com"
        assert payload.subject == "Test Email"
        assert payload.body == "This is the body."
        assert payload.attachments == []
        assert payload.received_at == "2025-12-13T10:30:00Z"

    def test_webhook_payload_with_attachments(self):
        """Test webhook payload with attachments."""
        attachments = [
            {
                "filename": "doc.pdf",
                "content_type": "application/pdf",
                "size": 1024,
                "content": "YmFzZTY0",
            }
        ]
        payload = WebhookPayload(
            event="email.received",
            message_id="msg-abc123",
            thread_id=None,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body="Body",
            attachments=attachments,
            received_at="2025-12-13T10:30:00Z",
        )

        assert len(payload.attachments) == 1
        assert payload.attachments[0]["filename"] == "doc.pdf"

    def test_webhook_payload_optional_thread_id(self):
        """Test that thread_id is optional."""
        payload = WebhookPayload(
            event="email.received",
            message_id="msg-abc123",
            thread_id=None,
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body="Body",
            received_at="2025-12-13T10:30:00Z",
        )

        assert payload.thread_id is None

    def test_webhook_payload_strips_whitespace(self):
        """Test that string fields strip whitespace."""
        payload = WebhookPayload(
            event="  email.received  ",
            message_id="  msg-abc123  ",
            from_address="  sender@example.com  ",
            to_address="  recipient@example.com  ",
            subject="  Test  ",
            body="  Body  ",
            received_at="2025-12-13T10:30:00Z",  # received_at not validated for whitespace
        )

        assert payload.event == "email.received"
        assert payload.message_id == "msg-abc123"
        assert payload.from_address == "sender@example.com"
        assert payload.to_address == "recipient@example.com"
        assert payload.subject == "Test"
        assert payload.body == "Body"
        assert payload.received_at == "2025-12-13T10:30:00Z"

    def test_webhook_payload_empty_event_fails(self):
        """Test that empty event raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookPayload(
                event="",
                message_id="msg-abc123",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Body",
                received_at="2025-12-13T10:30:00Z",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("event",) for error in errors)

    def test_webhook_payload_empty_message_id_fails(self):
        """Test that empty message_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookPayload(
                event="email.received",
                message_id="",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Body",
                received_at="2025-12-13T10:30:00Z",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("message_id",) for error in errors)

    def test_webhook_payload_whitespace_only_subject_fails(self):
        """Test that whitespace-only subject raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookPayload(
                event="email.received",
                message_id="msg-abc123",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="   ",
                body="Body",
                received_at="2025-12-13T10:30:00Z",
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("subject",) and "empty or whitespace" in str(error["msg"])
            for error in errors
        )

    def test_webhook_payload_empty_body_fails(self):
        """Test that empty body raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookPayload(
                event="email.received",
                message_id="msg-abc123",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="",
                received_at="2025-12-13T10:30:00Z",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("body",) for error in errors)

    def test_webhook_payload_empty_received_at_fails(self):
        """Test that empty received_at raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookPayload(
                event="email.received",
                message_id="msg-abc123",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Body",
                received_at="",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("received_at",) for error in errors)
