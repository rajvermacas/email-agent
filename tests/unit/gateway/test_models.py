"""
Unit tests for gateway models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from info_agent.gateway.models import (
    ComponentHealth,
    EmailMessage,
    EmailThread,
    EmailWebhookPayload,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PlanStep,
    SSEEvent,
    SSEEventType,
    WorkflowApproveRequest,
    WorkflowAuditEntry,
    WorkflowAuditResponse,
    WorkflowCancelRequest,
    WorkflowCreateRequest,
    WorkflowEmailsResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowStatus,
    AgentWebhookPayload,
    WebhookResponse,
    FileUploadResponse,
    WorkflowFilesResponse,
)


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_all_statuses_defined(self) -> None:
        """Test all expected statuses are defined."""
        expected = [
            "pending",
            "planning",
            "awaiting_approval",
            "executing",
            "waiting_for_response",
            "escalated",
            "validating",
            "completed",
            "failed",
            "cancelled",
        ]

        for status in expected:
            assert WorkflowStatus(status) is not None

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"


class TestWorkflowCreateRequest:
    """Tests for WorkflowCreateRequest model."""

    def test_valid_request(self) -> None:
        """Test creating a valid request."""
        request = WorkflowCreateRequest(
            instructions="Send email to test@example.com",
            faq="Q: Format? A: Excel",
            escalation_rules="Escalate after 48 hours",
            validation_criteria="Must have 10 rows",
        )

        assert request.instructions == "Send email to test@example.com"
        assert request.faq == "Q: Format? A: Excel"

    def test_minimal_request(self) -> None:
        """Test creating request with only required fields."""
        request = WorkflowCreateRequest(
            instructions="Send email",
        )

        assert request.instructions == "Send email"
        assert request.faq == ""
        assert request.workflow_id is None

    def test_with_custom_id(self) -> None:
        """Test creating request with custom workflow ID."""
        request = WorkflowCreateRequest(
            instructions="Send email",
            workflow_id="custom-wf-123",
        )

        assert request.workflow_id == "custom-wf-123"

    def test_empty_instructions_fails(self) -> None:
        """Test that empty instructions fails validation."""
        with pytest.raises(ValidationError):
            WorkflowCreateRequest(instructions="")


class TestWorkflowApproveRequest:
    """Tests for WorkflowApproveRequest model."""

    def test_approve(self) -> None:
        """Test approval request."""
        request = WorkflowApproveRequest(approved=True)

        assert request.approved is True
        assert request.feedback is None

    def test_reject_with_feedback(self) -> None:
        """Test rejection with feedback."""
        request = WorkflowApproveRequest(
            approved=False,
            feedback="Need more details",
        )

        assert request.approved is False
        assert request.feedback == "Need more details"


class TestWorkflowCancelRequest:
    """Tests for WorkflowCancelRequest model."""

    def test_cancel_with_reason(self) -> None:
        """Test cancellation with reason."""
        request = WorkflowCancelRequest(reason="No longer needed")

        assert request.reason == "No longer needed"

    def test_cancel_without_reason(self) -> None:
        """Test cancellation without reason."""
        request = WorkflowCancelRequest()

        assert request.reason is None


class TestPlanStep:
    """Tests for PlanStep model."""

    def test_valid_step(self) -> None:
        """Test creating a valid plan step."""
        step = PlanStep(
            step_number=1,
            action="send_email",
            agent="mail-agent",
            skill="send_email",
            description="Send email to target",
            parameters={"to": "test@example.com"},
        )

        assert step.step_number == 1
        assert step.action == "send_email"
        assert step.status == "pending"

    def test_default_values(self) -> None:
        """Test default values."""
        step = PlanStep(
            step_number=1,
            action="test",
            agent="test-agent",
            skill="test_skill",
            description="Test step",
        )

        assert step.parameters == {}
        assert step.status == "pending"


class TestWorkflowResponse:
    """Tests for WorkflowResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid response."""
        now = datetime.utcnow()
        response = WorkflowResponse(
            workflow_id="wf-123",
            status=WorkflowStatus.EXECUTING,
            created_at=now,
            updated_at=now,
        )

        assert response.workflow_id == "wf-123"
        assert response.status == WorkflowStatus.EXECUTING
        assert response.plan is None

    def test_with_plan(self) -> None:
        """Test response with plan."""
        now = datetime.utcnow()
        plan = [
            PlanStep(
                step_number=1,
                action="test",
                agent="test-agent",
                skill="test_skill",
                description="Test",
            )
        ]

        response = WorkflowResponse(
            workflow_id="wf-123",
            status=WorkflowStatus.AWAITING_APPROVAL,
            created_at=now,
            updated_at=now,
            plan=plan,
        )

        assert len(response.plan) == 1
        assert response.plan[0].action == "test"


class TestWorkflowListResponse:
    """Tests for WorkflowListResponse model."""

    def test_empty_list(self) -> None:
        """Test empty workflow list."""
        response = WorkflowListResponse(
            workflows=[],
            total=0,
        )

        assert len(response.workflows) == 0
        assert response.total == 0

    def test_with_workflows(self) -> None:
        """Test list with workflows."""
        now = datetime.utcnow()
        workflows = [
            WorkflowResponse(
                workflow_id="wf-1",
                status=WorkflowStatus.COMPLETED,
                created_at=now,
                updated_at=now,
            ),
            WorkflowResponse(
                workflow_id="wf-2",
                status=WorkflowStatus.EXECUTING,
                created_at=now,
                updated_at=now,
            ),
        ]

        response = WorkflowListResponse(
            workflows=workflows,
            total=2,
            offset=0,
            limit=10,
        )

        assert len(response.workflows) == 2
        assert response.total == 2


class TestWorkflowAuditEntry:
    """Tests for WorkflowAuditEntry model."""

    def test_valid_entry(self) -> None:
        """Test creating a valid audit entry."""
        entry = WorkflowAuditEntry(
            timestamp=datetime.utcnow(),
            event_type="workflow.created",
            description="Workflow created",
        )

        assert entry.event_type == "workflow.created"
        assert entry.metadata == {}

    def test_with_metadata(self) -> None:
        """Test entry with metadata."""
        entry = WorkflowAuditEntry(
            timestamp=datetime.utcnow(),
            event_type="email.sent",
            description="Email sent",
            metadata={"to": "test@example.com"},
        )

        assert entry.metadata["to"] == "test@example.com"


class TestWorkflowAuditResponse:
    """Tests for WorkflowAuditResponse model."""

    def test_empty_audit(self) -> None:
        """Test empty audit log."""
        response = WorkflowAuditResponse(
            workflow_id="wf-123",
            entries=[],
            total=0,
        )

        assert len(response.entries) == 0


class TestEmailThread:
    """Tests for EmailThread model."""

    def test_valid_thread(self) -> None:
        """Test creating a valid email thread."""
        thread = EmailThread(
            thread_id="thread-123",
            subject="Information Request",
            participants=["a@test.com", "b@test.com"],
            message_count=3,
            last_message_at=datetime.utcnow(),
        )

        assert thread.thread_id == "thread-123"
        assert len(thread.participants) == 2


class TestEmailMessage:
    """Tests for EmailMessage model."""

    def test_valid_message(self) -> None:
        """Test creating a valid email message."""
        message = EmailMessage(
            message_id="msg-123",
            thread_id="thread-123",
            from_address="sender@test.com",
            to_address="receiver@test.com",
            subject="Test Subject",
            body="Test body",
            sent_at=datetime.utcnow(),
        )

        assert message.message_id == "msg-123"
        assert message.is_reply is False
        assert message.attachments == []


class TestEmailWebhookPayload:
    """Tests for EmailWebhookPayload model."""

    def test_valid_payload(self) -> None:
        """Test creating a valid email webhook payload."""
        payload = EmailWebhookPayload(
            event_type="email.received",
            message_id="msg-123",
            thread_id="thread-123",
            inbox="test@example.com",
            from_address="sender@test.com",
            to_address="test@example.com",
            subject="Test",
            received_at=datetime.utcnow(),
        )

        assert payload.event_type == "email.received"
        assert payload.has_attachments is False


class TestAgentWebhookPayload:
    """Tests for AgentWebhookPayload model."""

    def test_valid_payload(self) -> None:
        """Test creating a valid agent webhook payload."""
        payload = AgentWebhookPayload(
            event_type="task.completed",
            agent_id="mail-agent",
            task_id="task-123",
            timestamp=datetime.utcnow(),
        )

        assert payload.event_type == "task.completed"
        assert payload.result is None

    def test_with_result(self) -> None:
        """Test payload with result."""
        payload = AgentWebhookPayload(
            event_type="task.completed",
            agent_id="mail-agent",
            task_id="task-123",
            result={"success": True},
            timestamp=datetime.utcnow(),
        )

        assert payload.result["success"] is True


class TestWebhookResponse:
    """Tests for WebhookResponse model."""

    def test_success(self) -> None:
        """Test success response."""
        response = WebhookResponse(success=True)

        assert response.success is True
        assert response.message == "OK"

    def test_with_message(self) -> None:
        """Test response with custom message."""
        response = WebhookResponse(
            success=True,
            message="Email webhook processed",
        )

        assert response.message == "Email webhook processed"


class TestComponentHealth:
    """Tests for ComponentHealth model."""

    def test_healthy(self) -> None:
        """Test healthy component."""
        health = ComponentHealth(
            status="ok",
            latency_ms=5.2,
        )

        assert health.status == "ok"
        assert health.error is None

    def test_unhealthy(self) -> None:
        """Test unhealthy component."""
        health = ComponentHealth(
            status="down",
            error="Connection refused",
        )

        assert health.status == "down"
        assert health.error == "Connection refused"


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_healthy_response(self) -> None:
        """Test healthy system response."""
        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp=datetime.utcnow(),
            components={
                "supervisor": ComponentHealth(status="ok"),
                "database": ComponentHealth(status="ok"),
            },
        )

        assert response.status == "healthy"
        assert len(response.components) == 2


class TestSSEEventType:
    """Tests for SSEEventType enum."""

    def test_lifecycle_events(self) -> None:
        """Test lifecycle event types."""
        assert SSEEventType.RUN_STARTED.value == "RUN_STARTED"
        assert SSEEventType.RUN_FINISHED.value == "RUN_FINISHED"
        assert SSEEventType.RUN_ERROR.value == "RUN_ERROR"

    def test_custom_events(self) -> None:
        """Test custom Info-Agent event types."""
        assert SSEEventType.PLAN_GENERATED.value == "PLAN_GENERATED"
        assert SSEEventType.EMAIL_SENT.value == "EMAIL_SENT"
        assert SSEEventType.VALIDATION_COMPLETE.value == "VALIDATION_COMPLETE"


class TestSSEEvent:
    """Tests for SSEEvent model."""

    def test_valid_event(self) -> None:
        """Test creating a valid SSE event."""
        event = SSEEvent(
            event_type=SSEEventType.RUN_STARTED,
            workflow_id="wf-123",
            data={"status": "executing"},
        )

        assert event.event_type == SSEEventType.RUN_STARTED
        assert event.workflow_id == "wf-123"

    def test_to_sse_format(self) -> None:
        """Test converting to SSE wire format."""
        event = SSEEvent(
            event_type=SSEEventType.RUN_STARTED,
            workflow_id="wf-123",
            data={"status": "executing"},
        )

        sse_str = event.to_sse_format()

        assert "event: RUN_STARTED" in sse_str
        assert "data:" in sse_str
        assert "wf-123" in sse_str
        assert sse_str.endswith("\n\n")


class TestFileUploadResponse:
    """Tests for FileUploadResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid file upload response."""
        response = FileUploadResponse(
            file_id="file-123",
            filename="test.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size=1024,
            uploaded_at=datetime.utcnow(),
        )

        assert response.file_id == "file-123"
        assert response.filename == "test.xlsx"


class TestWorkflowFilesResponse:
    """Tests for WorkflowFilesResponse model."""

    def test_empty_files(self) -> None:
        """Test response with no files."""
        response = WorkflowFilesResponse(
            workflow_id="wf-123",
        )

        assert len(response.files) == 0


class TestErrorDetail:
    """Tests for ErrorDetail model."""

    def test_valid_error(self) -> None:
        """Test creating a valid error detail."""
        error = ErrorDetail(
            code="WORKFLOW_NOT_FOUND",
            message="Workflow not found",
        )

        assert error.code == "WORKFLOW_NOT_FOUND"
        assert error.details is None

    def test_with_details(self) -> None:
        """Test error with details."""
        error = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid input",
            details={"field": "instructions", "error": "required"},
        )

        assert error.details["field"] == "instructions"


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid error response."""
        response = ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="Something went wrong",
            ),
            request_id="req-123",
        )

        assert response.error.code == "INTERNAL_ERROR"
        assert response.request_id == "req-123"
