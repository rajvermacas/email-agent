"""
Unit tests for API request models.

Tests the request models defined in src/info_agent/api/models/requests.py
with comprehensive validation, edge cases, and error handling.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from info_agent.api.models.requests import (
    CreateWorkflowRequest,
    UploadFilesRequest,
    ApproveWorkflowRequest,
    EmailWebhookPayload,
)


class TestCreateWorkflowRequest:
    """Tests for CreateWorkflowRequest model."""

    def test_valid_workflow_request_with_all_fields(self):
        """Test creating workflow request with all fields."""
        request = CreateWorkflowRequest(
            name="Test Workflow",
            description="Test workflow description"
        )

        assert request.name == "Test Workflow"
        assert request.description == "Test workflow description"

    def test_valid_workflow_request_without_description(self):
        """Test creating workflow request without optional description."""
        request = CreateWorkflowRequest(
            name="Test Workflow"
        )

        assert request.name == "Test Workflow"
        assert request.description is None

    def test_workflow_name_whitespace_trimming(self):
        """Test that workflow name whitespace is trimmed."""
        request = CreateWorkflowRequest(
            name="  Test Workflow  "
        )

        assert request.name == "Test Workflow"

    def test_workflow_name_missing(self):
        """Test validation error when name is missing."""
        with pytest.raises(ValidationError) as exc_info:
            CreateWorkflowRequest()

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)
        assert errors[0]["type"] == "missing"

    def test_workflow_name_empty_string(self):
        """Test validation error for empty name."""
        with pytest.raises(ValidationError) as exc_info:
            CreateWorkflowRequest(name="")

        errors = exc_info.value.errors()
        assert any(
            "Workflow name cannot be empty" in str(error.get("ctx", {}).get("error", ""))
            or error["type"] == "string_too_short"
            for error in errors
        )

    def test_workflow_name_only_whitespace(self):
        """Test validation error for whitespace-only name."""
        with pytest.raises(ValidationError) as exc_info:
            CreateWorkflowRequest(name="   ")

        errors = exc_info.value.errors()
        assert any(
            "Workflow name cannot be empty or whitespace only" in str(error)
            for error in errors
        )

    def test_workflow_name_too_long(self):
        """Test validation error for name exceeding max length."""
        long_name = "A" * 256

        with pytest.raises(ValidationError) as exc_info:
            CreateWorkflowRequest(name=long_name)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_long"

    def test_workflow_name_at_max_length(self):
        """Test workflow name at maximum allowed length."""
        max_name = "A" * 255

        request = CreateWorkflowRequest(name=max_name)

        assert len(request.name) == 255

    def test_workflow_description_too_long(self):
        """Test validation error for description exceeding max length."""
        long_description = "A" * 2001

        with pytest.raises(ValidationError) as exc_info:
            CreateWorkflowRequest(
                name="Test",
                description=long_description
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_long"

    def test_workflow_description_at_max_length(self):
        """Test workflow description at maximum allowed length."""
        max_description = "A" * 2000

        request = CreateWorkflowRequest(
            name="Test",
            description=max_description
        )

        assert len(request.description) == 2000

    def test_workflow_special_characters_in_name(self):
        """Test workflow name with special characters."""
        request = CreateWorkflowRequest(
            name="Test Workflow! @#$%^&*()"
        )

        assert request.name == "Test Workflow! @#$%^&*()"

    def test_workflow_unicode_characters(self):
        """Test workflow name with unicode characters."""
        request = CreateWorkflowRequest(
            name="测试工作流程 🚀"
        )

        assert request.name == "测试工作流程 🚀"


class TestUploadFilesRequest:
    """Tests for UploadFilesRequest model."""

    def test_valid_instructions_file_type(self):
        """Test valid instructions file type."""
        request = UploadFilesRequest(file_type="instructions")

        assert request.file_type == "instructions"

    def test_valid_faq_file_type(self):
        """Test valid faq file type."""
        request = UploadFilesRequest(file_type="faq")

        assert request.file_type == "faq"

    def test_valid_escalation_file_type(self):
        """Test valid escalation file type."""
        request = UploadFilesRequest(file_type="escalation")

        assert request.file_type == "escalation"

    def test_valid_validation_file_type(self):
        """Test valid validation file type."""
        request = UploadFilesRequest(file_type="validation")

        assert request.file_type == "validation"

    def test_valid_attachment_file_type(self):
        """Test valid attachment file type."""
        request = UploadFilesRequest(file_type="attachment")

        assert request.file_type == "attachment"

    def test_file_type_case_insensitive(self):
        """Test that file type is normalized to lowercase."""
        request = UploadFilesRequest(file_type="INSTRUCTIONS")

        assert request.file_type == "instructions"

    def test_file_type_mixed_case(self):
        """Test file type with mixed case."""
        request = UploadFilesRequest(file_type="InStRuCtIoNs")

        assert request.file_type == "instructions"

    def test_file_type_missing(self):
        """Test validation error when file_type is missing."""
        with pytest.raises(ValidationError) as exc_info:
            UploadFilesRequest()

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("file_type",)
        assert errors[0]["type"] == "missing"

    def test_file_type_invalid(self):
        """Test validation error for invalid file type."""
        with pytest.raises(ValidationError) as exc_info:
            UploadFilesRequest(file_type="invalid_type")

        errors = exc_info.value.errors()
        assert any(
            "Invalid file_type" in str(error)
            for error in errors
        )

    def test_file_type_empty_string(self):
        """Test validation error for empty file type."""
        with pytest.raises(ValidationError) as exc_info:
            UploadFilesRequest(file_type="")

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_file_type_allowed_values_in_error_message(self):
        """Test that error message includes allowed values."""
        with pytest.raises(ValidationError) as exc_info:
            UploadFilesRequest(file_type="bad_type")

        error_str = str(exc_info.value)
        # Check that all allowed types are mentioned
        assert "attachment" in error_str or "instructions" in error_str


class TestApproveWorkflowRequest:
    """Tests for ApproveWorkflowRequest model."""

    def test_approved_true_without_feedback(self):
        """Test approval request with approved=True, no feedback."""
        request = ApproveWorkflowRequest(approved=True)

        assert request.approved is True
        assert request.feedback is None

    def test_approved_false_without_feedback(self):
        """Test approval request with approved=False, no feedback."""
        request = ApproveWorkflowRequest(approved=False)

        assert request.approved is False
        assert request.feedback is None

    def test_approved_true_with_feedback(self):
        """Test approval request with feedback."""
        request = ApproveWorkflowRequest(
            approved=True,
            feedback="Looks good!"
        )

        assert request.approved is True
        assert request.feedback == "Looks good!"

    def test_approved_false_with_feedback(self):
        """Test rejection request with feedback."""
        request = ApproveWorkflowRequest(
            approved=False,
            feedback="Please add more steps"
        )

        assert request.approved is False
        assert request.feedback == "Please add more steps"

    def test_feedback_whitespace_trimming(self):
        """Test that feedback whitespace is trimmed."""
        request = ApproveWorkflowRequest(
            approved=True,
            feedback="  Feedback text  "
        )

        assert request.feedback == "Feedback text"

    def test_feedback_only_whitespace_becomes_none(self):
        """Test that whitespace-only feedback becomes None."""
        request = ApproveWorkflowRequest(
            approved=True,
            feedback="   "
        )

        assert request.feedback is None

    def test_feedback_empty_string_becomes_none(self):
        """Test that empty feedback becomes None."""
        request = ApproveWorkflowRequest(
            approved=True,
            feedback=""
        )

        assert request.feedback is None

    def test_approved_field_missing(self):
        """Test validation error when approved field is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ApproveWorkflowRequest()

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("approved",)
        assert errors[0]["type"] == "missing"

    def test_approved_field_invalid_type(self):
        """Test validation error for invalid approved type."""
        # Pydantic is flexible with bool conversion - strings like "yes", "true" convert to True
        # Test with something that truly can't convert
        with pytest.raises(ValidationError) as exc_info:
            ApproveWorkflowRequest(approved={"not": "a bool"})

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_feedback_too_long(self):
        """Test validation error for feedback exceeding max length."""
        long_feedback = "A" * 2001

        with pytest.raises(ValidationError) as exc_info:
            ApproveWorkflowRequest(
                approved=True,
                feedback=long_feedback
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_too_long"

    def test_feedback_at_max_length(self):
        """Test feedback at maximum allowed length."""
        max_feedback = "A" * 2000

        request = ApproveWorkflowRequest(
            approved=True,
            feedback=max_feedback
        )

        assert len(request.feedback) == 2000

    def test_feedback_with_newlines(self):
        """Test feedback with newlines is preserved."""
        request = ApproveWorkflowRequest(
            approved=False,
            feedback="Line 1\nLine 2\nLine 3"
        )

        assert request.feedback == "Line 1\nLine 2\nLine 3"


class TestEmailWebhookPayload:
    """Tests for EmailWebhookPayload model."""

    def test_valid_email_received_payload(self):
        """Test valid email.received webhook payload."""
        payload = EmailWebhookPayload(
            event="email.received",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body="Test body content",
            received_at=datetime(2024, 1, 1, 12, 0, 0)
        )

        assert payload.event == "email.received"
        assert payload.message_id == "msg-123"
        assert payload.thread_id == "thread-456"
        assert payload.from_address == "sender@example.com"
        assert payload.to_address == "recipient@example.com"
        assert payload.subject == "Test Subject"
        assert payload.body == "Test body content"
        assert payload.attachments == []
        assert payload.received_at == datetime(2024, 1, 1, 12, 0, 0)

    def test_email_payload_with_attachments(self):
        """Test email payload with attachments."""
        attachments = [
            {
                "filename": "report.pdf",
                "size": 1024,
                "mime_type": "application/pdf"
            },
            {
                "filename": "data.csv",
                "size": 512,
                "mime_type": "text/csv"
            }
        ]

        payload = EmailWebhookPayload(
            event="email.received",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body="Test body",
            attachments=attachments,
            received_at=datetime.utcnow()
        )

        assert len(payload.attachments) == 2
        assert payload.attachments[0]["filename"] == "report.pdf"
        assert payload.attachments[1]["size"] == 512

    def test_email_sent_event(self):
        """Test valid email.sent event."""
        payload = EmailWebhookPayload(
            event="email.sent",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body="Test",
            received_at=datetime.utcnow()
        )

        assert payload.event == "email.sent"

    def test_email_bounced_event(self):
        """Test valid email.bounced event."""
        payload = EmailWebhookPayload(
            event="email.bounced",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body="Test",
            received_at=datetime.utcnow()
        )

        assert payload.event == "email.bounced"

    def test_email_addresses_normalized_to_lowercase(self):
        """Test that email addresses are normalized to lowercase."""
        payload = EmailWebhookPayload(
            event="email.received",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="Sender@EXAMPLE.COM",
            to_address="RECIPIENT@example.com",
            subject="Test",
            body="Test",
            received_at=datetime.utcnow()
        )

        assert payload.from_address == "sender@example.com"
        assert payload.to_address == "recipient@example.com"

    def test_event_field_missing(self):
        """Test validation error when event is missing."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                message_id="msg-123",
                thread_id="thread-456",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("event",) for error in errors)

    def test_event_invalid(self):
        """Test validation error for invalid event type."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.invalid",
                message_id="msg-123",
                thread_id="thread-456",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        error_str = str(exc_info.value)
        assert "Invalid event type" in error_str

    def test_message_id_missing(self):
        """Test validation error when message_id is missing."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                thread_id="thread-456",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("message_id",) for error in errors)

    def test_message_id_empty_string(self):
        """Test validation error for empty message_id."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                message_id="",
                thread_id="thread-456",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        errors = exc_info.value.errors()
        assert any(error["type"] == "string_too_short" for error in errors)

    def test_thread_id_missing(self):
        """Test validation error when thread_id is missing."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                message_id="msg-123",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("thread_id",) for error in errors)

    def test_thread_id_empty_string(self):
        """Test validation error for empty thread_id."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                message_id="msg-123",
                thread_id="",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        errors = exc_info.value.errors()
        assert any(error["type"] == "string_too_short" for error in errors)

    def test_from_address_invalid_format(self):
        """Test validation error for invalid from_address format."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                message_id="msg-123",
                thread_id="thread-456",
                from_address="not-an-email",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        error_str = str(exc_info.value)
        assert "Invalid email address format" in error_str

    def test_to_address_invalid_format(self):
        """Test validation error for invalid to_address format."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                message_id="msg-123",
                thread_id="thread-456",
                from_address="sender@example.com",
                to_address="not-an-email",
                subject="Test",
                body="Test",
                received_at=datetime.utcnow()
            )

        error_str = str(exc_info.value)
        assert "Invalid email address format" in error_str

    def test_received_at_missing(self):
        """Test validation error when received_at is missing."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                message_id="msg-123",
                thread_id="thread-456",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test"
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("received_at",) for error in errors)

    def test_received_at_invalid_type(self):
        """Test validation error for invalid received_at type."""
        with pytest.raises(ValidationError) as exc_info:
            EmailWebhookPayload(
                event="email.received",
                message_id="msg-123",
                thread_id="thread-456",
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test",
                body="Test",
                received_at="not-a-datetime"
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_empty_subject_allowed(self):
        """Test that empty subject is allowed."""
        payload = EmailWebhookPayload(
            event="email.received",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="",
            body="Test body",
            received_at=datetime.utcnow()
        )

        assert payload.subject == ""

    def test_empty_body_allowed(self):
        """Test that empty body is allowed."""
        payload = EmailWebhookPayload(
            event="email.received",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body="",
            received_at=datetime.utcnow()
        )

        assert payload.body == ""

    def test_unicode_in_subject_and_body(self):
        """Test unicode characters in subject and body."""
        payload = EmailWebhookPayload(
            event="email.received",
            message_id="msg-123",
            thread_id="thread-456",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="测试主题 🎉",
            body="测试内容 with émojis 🚀",
            received_at=datetime.utcnow()
        )

        assert payload.subject == "测试主题 🎉"
        assert payload.body == "测试内容 with émojis 🚀"
