"""
Unit tests for Mail Agent state definitions.

Tests the TypedDict structures used for Mail Agent state management
according to A2A protocol specification.
"""

import pytest

from info_agent.agents.mail.state import (
    EmailTaskState,
    MailAgentState,
    ReceiveEmailWebhookPayload,
    ReceiveEmailWebhookResult,
    SendEmailPayload,
    SendEmailResult,
)


class TestEmailTaskState:
    """Tests for EmailTaskState TypedDict."""

    def test_email_task_state_send_email_fields(self):
        """Test EmailTaskState with send-email specific fields."""
        state: EmailTaskState = {
            "to_address": "recipient@example.com",
            "subject": "Test Subject",
            "instructions": "Write a professional email",
            "thread_id": None,
        }

        assert state["to_address"] == "recipient@example.com"
        assert state["subject"] == "Test Subject"
        assert state["instructions"] == "Write a professional email"
        assert state["thread_id"] is None

    def test_email_task_state_receive_webhook_fields(self):
        """Test EmailTaskState with receive-email-webhook specific fields."""
        state: EmailTaskState = {
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Meeting Request",
            "body_text": "Email body content",
            "message_id": "msg-123",
            "thread_id": "thread-456",
            "attachments": [],
        }

        assert state["from_address"] == "sender@example.com"
        assert state["to_address"] == "recipient@example.com"
        assert state["subject"] == "Meeting Request"
        assert state["body_text"] == "Email body content"
        assert state["message_id"] == "msg-123"
        assert state["thread_id"] == "thread-456"
        assert state["attachments"] == []

    def test_email_task_state_with_composed_data(self):
        """Test EmailTaskState with composed email data."""
        state: EmailTaskState = {
            "to_address": "recipient@example.com",
            "instructions": "Write an email",
            "composed_body": "Dear recipient,\n\nThis is a professional email.\n\nBest regards",
            "composed_subject": "Professional Communication",
        }

        assert state["composed_body"] is not None
        assert state["composed_subject"] == "Professional Communication"

    def test_email_task_state_with_parsed_data(self):
        """Test EmailTaskState with parsed data from webhook."""
        parsed_data = {
            "intent": "meeting_request",
            "key_points": ["Meeting next week", "Q3 Review"],
            "requires_response": True,
        }

        state: EmailTaskState = {
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Meeting",
            "body_text": "Let's meet",
            "message_id": "msg-123",
            "parsed_data": parsed_data,
        }

        assert state["parsed_data"] == parsed_data
        assert state["parsed_data"]["intent"] == "meeting_request"
        assert state["parsed_data"]["requires_response"] is True

    def test_email_task_state_with_attachments(self):
        """Test EmailTaskState with attachment metadata."""
        attachments = [
            {"filename": "report.pdf", "size": 12345, "mime_type": "application/pdf"},
            {"filename": "data.xlsx", "size": 67890, "mime_type": "application/vnd.ms-excel"},
        ]

        state: EmailTaskState = {
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Reports",
            "body_text": "Please find attached",
            "message_id": "msg-123",
            "attachments": attachments,
        }

        assert len(state["attachments"]) == 2
        assert state["attachments"][0]["filename"] == "report.pdf"
        assert state["attachments"][1]["size"] == 67890


class TestMailAgentState:
    """Tests for MailAgentState TypedDict."""

    def test_mail_agent_state_minimal_required_fields(self):
        """Test MailAgentState with minimal required fields."""
        state: MailAgentState = {
            "task_id": "task-123",
            "skill_id": "send-email",
            "status": "submitted",
            "email_task": {
                "to_address": "recipient@example.com",
                "instructions": "Send an email",
            },
            "result": None,
            "error": None,
            "payload": None,
        }

        assert state["task_id"] == "task-123"
        assert state["skill_id"] == "send-email"
        assert state["status"] == "submitted"
        assert state["email_task"]["to_address"] == "recipient@example.com"
        assert state["result"] is None
        assert state["error"] is None

    def test_mail_agent_state_send_email_skill(self):
        """Test MailAgentState for send-email skill."""
        state: MailAgentState = {
            "task_id": "task-send-123",
            "skill_id": "send-email",
            "status": "working",
            "email_task": {
                "to_address": "client@example.com",
                "subject": "Meeting Request",
                "instructions": "Request a meeting next week",
                "thread_id": None,
            },
            "result": None,
            "error": None,
            "payload": {
                "to_address": "client@example.com",
                "instructions": "Request a meeting next week",
            },
        }

        assert state["skill_id"] == "send-email"
        assert state["status"] == "working"
        assert state["email_task"]["to_address"] == "client@example.com"
        assert state["payload"] is not None

    def test_mail_agent_state_receive_webhook_skill(self):
        """Test MailAgentState for receive-email-webhook skill."""
        state: MailAgentState = {
            "task_id": "task-webhook-456",
            "skill_id": "receive-email-webhook",
            "status": "working",
            "email_task": {
                "from_address": "sender@example.com",
                "to_address": "recipient@example.com",
                "subject": "Re: Meeting Request",
                "body_text": "Yes, let's meet on Tuesday",
                "message_id": "msg-789",
            },
            "result": None,
            "error": None,
            "payload": {
                "event": "email.received",
                "message_id": "msg-789",
                "from_address": "sender@example.com",
                "to_address": "recipient@example.com",
                "subject": "Re: Meeting Request",
                "body": "Yes, let's meet on Tuesday",
                "received_at": "2025-12-13T10:30:00Z",
            },
        }

        assert state["skill_id"] == "receive-email-webhook"
        assert state["email_task"]["from_address"] == "sender@example.com"
        assert state["payload"]["event"] == "email.received"

    def test_mail_agent_state_completed_with_result(self):
        """Test MailAgentState in completed status with result."""
        result = {
            "message_id": "msg-sent-123",
            "to_address": "client@example.com",
            "subject": "Meeting Request",
            "body_preview": "Dear Client,\n\nI would like to request...",
            "sent_at": "2025-12-13T11:00:00Z",
        }

        state: MailAgentState = {
            "task_id": "task-completed-789",
            "skill_id": "send-email",
            "status": "completed",
            "email_task": {
                "to_address": "client@example.com",
                "instructions": "Request a meeting",
                "composed_subject": "Meeting Request",
                "composed_body": "Dear Client,\n\nI would like to request a meeting.",
            },
            "result": result,
            "error": None,
            "payload": None,
        }

        assert state["status"] == "completed"
        assert state["result"] is not None
        assert state["result"]["message_id"] == "msg-sent-123"
        assert state["error"] is None

    def test_mail_agent_state_failed_with_error(self):
        """Test MailAgentState in failed status with error message."""
        state: MailAgentState = {
            "task_id": "task-failed-999",
            "skill_id": "send-email",
            "status": "failed",
            "email_task": {
                "to_address": "invalid-email",
                "instructions": "Send email",
            },
            "result": None,
            "error": "SMTP connection failed: Connection refused",
            "payload": None,
        }

        assert state["status"] == "failed"
        assert state["error"] is not None
        assert "SMTP connection failed" in state["error"]
        assert state["result"] is None

    def test_mail_agent_state_all_status_values(self):
        """Test MailAgentState with all possible status values."""
        valid_statuses = ["submitted", "working", "completed", "failed", "cancelled"]

        for status in valid_statuses:
            state: MailAgentState = {
                "task_id": f"task-{status}",
                "skill_id": "send-email",
                "status": status,  # type: ignore
                "email_task": {
                    "to_address": "test@example.com",
                    "instructions": "Test",
                },
                "result": None,
                "error": None,
                "payload": None,
            }

            assert state["status"] == status


class TestSendEmailPayload:
    """Tests for SendEmailPayload TypedDict."""

    def test_send_email_payload_minimal(self):
        """Test SendEmailPayload with minimal required fields."""
        payload: SendEmailPayload = {
            "to_address": "recipient@example.com",
            "instructions": "Write a professional email requesting information",
        }

        assert payload["to_address"] == "recipient@example.com"
        assert payload["instructions"] == "Write a professional email requesting information"

    def test_send_email_payload_with_subject(self):
        """Test SendEmailPayload with custom subject."""
        payload: SendEmailPayload = {
            "to_address": "team@example.com",
            "instructions": "Inform team about project update",
            "subject": "Project Update - Q4 2025",
        }

        assert payload["subject"] == "Project Update - Q4 2025"

    def test_send_email_payload_with_thread_id(self):
        """Test SendEmailPayload with thread ID for threading."""
        payload: SendEmailPayload = {
            "to_address": "client@example.com",
            "instructions": "Follow up on previous email",
            "subject": "Re: Meeting Request",
            "thread_id": "thread-original-123",
        }

        assert payload["thread_id"] == "thread-original-123"

    def test_send_email_payload_null_optional_fields(self):
        """Test SendEmailPayload with explicit None for optional fields."""
        payload: SendEmailPayload = {
            "to_address": "user@example.com",
            "instructions": "Send invitation",
            "subject": None,
            "thread_id": None,
        }

        assert payload["subject"] is None
        assert payload["thread_id"] is None


class TestReceiveEmailWebhookPayload:
    """Tests for ReceiveEmailWebhookPayload TypedDict."""

    def test_receive_webhook_payload_complete(self):
        """Test ReceiveEmailWebhookPayload with all fields."""
        payload: ReceiveEmailWebhookPayload = {
            "event": "email.received",
            "message_id": "msg-webhook-123",
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Important Information",
            "body": "Here is the information you requested...",
            "thread_id": "thread-456",
            "attachments": [
                {"filename": "document.pdf", "size": 54321, "mime_type": "application/pdf"}
            ],
            "received_at": "2025-12-13T14:30:00Z",
        }

        assert payload["event"] == "email.received"
        assert payload["message_id"] == "msg-webhook-123"
        assert payload["from_address"] == "sender@example.com"
        assert payload["to_address"] == "recipient@example.com"
        assert payload["subject"] == "Important Information"
        assert payload["body"] == "Here is the information you requested..."
        assert payload["thread_id"] == "thread-456"
        assert len(payload["attachments"]) == 1
        assert payload["received_at"] == "2025-12-13T14:30:00Z"

    def test_receive_webhook_payload_no_thread_id(self):
        """Test ReceiveEmailWebhookPayload without thread ID."""
        payload: ReceiveEmailWebhookPayload = {
            "event": "email.received",
            "message_id": "msg-new-789",
            "from_address": "newcontact@example.com",
            "to_address": "me@example.com",
            "subject": "New Inquiry",
            "body": "I have a question...",
            "thread_id": None,
            "attachments": [],
            "received_at": "2025-12-13T15:00:00Z",
        }

        assert payload["thread_id"] is None
        assert payload["attachments"] == []

    def test_receive_webhook_payload_multiple_attachments(self):
        """Test ReceiveEmailWebhookPayload with multiple attachments."""
        attachments = [
            {"filename": "report.pdf", "size": 12345},
            {"filename": "data.csv", "size": 67890},
            {"filename": "image.png", "size": 98765},
        ]

        payload: ReceiveEmailWebhookPayload = {
            "event": "email.received",
            "message_id": "msg-multi-attach",
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Files Attached",
            "body": "Please find the files attached",
            "thread_id": None,
            "attachments": attachments,
            "received_at": "2025-12-13T16:00:00Z",
        }

        assert len(payload["attachments"]) == 3
        assert payload["attachments"][0]["filename"] == "report.pdf"
        assert payload["attachments"][2]["filename"] == "image.png"


class TestSendEmailResult:
    """Tests for SendEmailResult TypedDict."""

    def test_send_email_result_complete(self):
        """Test SendEmailResult with all required fields."""
        result: SendEmailResult = {
            "message_id": "<unique-123@smtp.example.com>",
            "to_address": "client@example.com",
            "subject": "Meeting Request",
            "body_preview": "Dear Client,\n\nI would like to schedule a meeting to discuss our project progress. Would next Tuesday at 2 PM work for your schedule?\n\nBest regards,\nJohn",
            "sent_at": "2025-12-13T10:45:30Z",
        }

        assert result["message_id"] == "<unique-123@smtp.example.com>"
        assert result["to_address"] == "client@example.com"
        assert result["subject"] == "Meeting Request"
        assert "Dear Client" in result["body_preview"]
        assert result["sent_at"] == "2025-12-13T10:45:30Z"

    def test_send_email_result_body_preview_truncation(self):
        """Test SendEmailResult with truncated body preview."""
        long_body = "A" * 300  # Simulate long body
        preview = long_body[:200]  # Standard preview length

        result: SendEmailResult = {
            "message_id": "<msg-long@smtp.example.com>",
            "to_address": "user@example.com",
            "subject": "Long Email",
            "body_preview": preview,
            "sent_at": "2025-12-13T11:00:00Z",
        }

        assert len(result["body_preview"]) == 200
        assert result["body_preview"] == "A" * 200

    def test_send_email_result_different_timestamp_formats(self):
        """Test SendEmailResult with ISO timestamp."""
        result: SendEmailResult = {
            "message_id": "<msg-time@smtp.example.com>",
            "to_address": "test@example.com",
            "subject": "Test",
            "body_preview": "Test email body",
            "sent_at": "2025-12-13T17:30:45.123456Z",
        }

        assert "2025-12-13" in result["sent_at"]
        assert "17:30:45" in result["sent_at"]


class TestReceiveEmailWebhookResult:
    """Tests for ReceiveEmailWebhookResult TypedDict."""

    def test_receive_webhook_result_complete(self):
        """Test ReceiveEmailWebhookResult with all fields."""
        parsed_data = {
            "intent": "meeting_request",
            "key_points": ["Meeting on Tuesday", "2 PM time slot", "Project discussion"],
            "action_items": ["Confirm availability", "Prepare project update"],
            "requires_response": True,
            "sentiment": "positive",
            "important_dates": ["Tuesday 2 PM"],
            "contact_info": [],
            "summary": "Client requesting meeting on Tuesday at 2 PM to discuss project",
        }

        result: ReceiveEmailWebhookResult = {
            "message_id": "msg-received-456",
            "from_address": "client@example.com",
            "subject": "Meeting Request",
            "parsed_data": parsed_data,
            "processed_at": "2025-12-13T11:15:00Z",
        }

        assert result["message_id"] == "msg-received-456"
        assert result["from_address"] == "client@example.com"
        assert result["subject"] == "Meeting Request"
        assert result["parsed_data"]["intent"] == "meeting_request"
        assert result["parsed_data"]["requires_response"] is True
        assert len(result["parsed_data"]["key_points"]) == 3
        assert result["processed_at"] == "2025-12-13T11:15:00Z"

    def test_receive_webhook_result_minimal_parsed_data(self):
        """Test ReceiveEmailWebhookResult with minimal parsed data."""
        parsed_data = {
            "intent": "information_query",
            "key_points": ["Request for Q3 reports"],
            "action_items": [],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "User asking for Q3 reports",
        }

        result: ReceiveEmailWebhookResult = {
            "message_id": "msg-query-789",
            "from_address": "manager@example.com",
            "subject": "Q3 Reports",
            "parsed_data": parsed_data,
            "processed_at": "2025-12-13T12:00:00Z",
        }

        assert result["parsed_data"]["action_items"] == []
        assert result["parsed_data"]["important_dates"] == []
        assert result["parsed_data"]["contact_info"] == []

    def test_receive_webhook_result_negative_sentiment(self):
        """Test ReceiveEmailWebhookResult with negative sentiment."""
        parsed_data = {
            "intent": "complaint",
            "key_points": ["Service delay", "Missing features", "Unresponsive support"],
            "action_items": ["Address complaints", "Provide timeline"],
            "requires_response": True,
            "sentiment": "negative",
            "important_dates": [],
            "contact_info": [],
            "summary": "Customer expressing dissatisfaction with service delays",
        }

        result: ReceiveEmailWebhookResult = {
            "message_id": "msg-complaint-999",
            "from_address": "unhappy@example.com",
            "subject": "Service Issues",
            "parsed_data": parsed_data,
            "processed_at": "2025-12-13T13:00:00Z",
        }

        assert result["parsed_data"]["intent"] == "complaint"
        assert result["parsed_data"]["sentiment"] == "negative"
        assert len(result["parsed_data"]["key_points"]) == 3

    def test_receive_webhook_result_urgent_sentiment(self):
        """Test ReceiveEmailWebhookResult with urgent sentiment."""
        parsed_data = {
            "intent": "urgent_request",
            "key_points": ["Critical bug", "Production system down", "Need immediate fix"],
            "action_items": ["Investigate issue", "Deploy hotfix", "Notify stakeholders"],
            "requires_response": True,
            "sentiment": "urgent",
            "important_dates": ["Today", "ASAP"],
            "contact_info": ["+1-555-0123"],
            "summary": "Urgent: Production system down due to critical bug",
        }

        result: ReceiveEmailWebhookResult = {
            "message_id": "msg-urgent-111",
            "from_address": "ops@example.com",
            "subject": "URGENT: Production Down",
            "parsed_data": parsed_data,
            "processed_at": "2025-12-13T14:00:00Z",
        }

        assert result["parsed_data"]["sentiment"] == "urgent"
        assert "ASAP" in result["parsed_data"]["important_dates"]
        assert len(result["parsed_data"]["contact_info"]) == 1
