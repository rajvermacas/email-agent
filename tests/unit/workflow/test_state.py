"""
Unit tests for workflow state definitions.
"""

import pytest
from datetime import datetime

from info_agent.workflow.state import (
    WorkflowStatus,
    EmailThread,
    ClarificationEntry,
    ReceivedDocument,
    PlanStep,
    AuditEntry,
    SupervisorState,
    create_initial_state,
    add_audit_entry,
    update_status,
)


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_planning_value(self) -> None:
        """Test PLANNING status value."""
        assert WorkflowStatus.PLANNING.value == "planning"

    def test_awaiting_approval_value(self) -> None:
        """Test AWAITING_APPROVAL status value."""
        assert WorkflowStatus.AWAITING_APPROVAL.value == "awaiting_approval"

    def test_executing_value(self) -> None:
        """Test EXECUTING status value."""
        assert WorkflowStatus.EXECUTING.value == "executing"

    def test_waiting_for_response_value(self) -> None:
        """Test WAITING_FOR_RESPONSE status value."""
        assert WorkflowStatus.WAITING_FOR_RESPONSE.value == "waiting_for_response"

    def test_escalated_value(self) -> None:
        """Test ESCALATED status value."""
        assert WorkflowStatus.ESCALATED.value == "escalated"

    def test_validating_value(self) -> None:
        """Test VALIDATING status value."""
        assert WorkflowStatus.VALIDATING.value == "validating"

    def test_completed_value(self) -> None:
        """Test COMPLETED status value."""
        assert WorkflowStatus.COMPLETED.value == "completed"

    def test_failed_value(self) -> None:
        """Test FAILED status value."""
        assert WorkflowStatus.FAILED.value == "failed"

    def test_cancelled_value(self) -> None:
        """Test CANCELLED status value."""
        assert WorkflowStatus.CANCELLED.value == "cancelled"


class TestEmailThread:
    """Tests for EmailThread model."""

    def test_create_thread(self) -> None:
        """Test creating email thread."""
        thread = EmailThread(
            id="thread-1",
            subject="Test Subject",
            target_email="test@example.com",
        )

        assert thread.id == "thread-1"
        assert thread.subject == "Test Subject"
        assert thread.target_email == "test@example.com"
        assert thread.messages == []
        assert thread.created_at is not None

    def test_thread_with_messages(self) -> None:
        """Test thread with messages."""
        messages = [
            {"id": "msg-1", "content": "Hello"},
            {"id": "msg-2", "content": "Hi there"},
        ]
        thread = EmailThread(
            id="thread-1",
            subject="Test",
            target_email="test@example.com",
            messages=messages,
        )

        assert len(thread.messages) == 2
        assert thread.messages[0]["id"] == "msg-1"


class TestClarificationEntry:
    """Tests for ClarificationEntry model."""

    def test_create_entry(self) -> None:
        """Test creating clarification entry."""
        entry = ClarificationEntry(
            id="clar-1",
            question="What format should I use?",
            source_email="user@example.com",
        )

        assert entry.id == "clar-1"
        assert entry.question == "What format should I use?"
        assert entry.source_email == "user@example.com"
        assert entry.faq_match is False
        assert entry.answer is None
        assert entry.escalated is False

    def test_entry_with_answer(self) -> None:
        """Test entry with FAQ answer."""
        entry = ClarificationEntry(
            id="clar-1",
            question="What format?",
            source_email="user@example.com",
            faq_match=True,
            answer="Use Excel format",
            answered_by="faq",
            answered_at=datetime.utcnow(),
        )

        assert entry.faq_match is True
        assert entry.answer == "Use Excel format"
        assert entry.answered_by == "faq"


class TestReceivedDocument:
    """Tests for ReceivedDocument model."""

    def test_create_document(self) -> None:
        """Test creating document record."""
        doc = ReceivedDocument(
            id="doc-1",
            filename="recipes.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=15000,
            storage_path="/data/attachments/doc-1.xlsx",
            from_email="sender@example.com",
            email_id="email-123",
        )

        assert doc.id == "doc-1"
        assert doc.filename == "recipes.xlsx"
        assert doc.size_bytes == 15000
        assert doc.from_email == "sender@example.com"


class TestPlanStep:
    """Tests for PlanStep model."""

    def test_create_step(self) -> None:
        """Test creating plan step."""
        step = PlanStep(
            step_number=1,
            action="send_initial_request",
            agent="mail-agent",
            skill="send_email",
            description="Send email to target",
        )

        assert step.step_number == 1
        assert step.action == "send_initial_request"
        assert step.agent == "mail-agent"
        assert step.skill == "send_email"
        assert step.status == "pending"
        assert step.result is None

    def test_step_with_parameters(self) -> None:
        """Test step with parameters."""
        step = PlanStep(
            step_number=1,
            action="send_email",
            agent="mail-agent",
            skill="send_email",
            description="Send email",
            parameters={"to": "user@example.com", "subject": "Request"},
        )

        assert step.parameters["to"] == "user@example.com"


class TestAuditEntry:
    """Tests for AuditEntry model."""

    def test_create_entry(self) -> None:
        """Test creating audit entry."""
        entry = AuditEntry(
            id="audit-1",
            event_type="workflow_created",
            actor="system",
            description="Workflow initialized",
        )

        assert entry.id == "audit-1"
        assert entry.event_type == "workflow_created"
        assert entry.actor == "system"
        assert entry.description == "Workflow initialized"
        assert entry.details == {}

    def test_entry_with_details(self) -> None:
        """Test entry with details."""
        entry = AuditEntry(
            id="audit-1",
            event_type="email_sent",
            actor="mail-agent",
            description="Email sent",
            details={"recipient": "user@example.com", "thread_id": "thread-1"},
        )

        assert entry.details["recipient"] == "user@example.com"


class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_create_basic_state(self) -> None:
        """Test creating basic initial state."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Send email to test@example.com",
            faq="Q: Format? A: Excel",
            escalation_rules="Escalate to admin@example.com",
            validation_criteria="Must have 10 rows",
        )

        assert state["workflow_id"] == "wf-123"
        assert state["instructions"] == "Send email to test@example.com"
        assert state["faq"] == "Q: Format? A: Excel"
        assert state["status"] == WorkflowStatus.PLANNING
        assert state["plan_approved"] is False

    def test_default_values(self) -> None:
        """Test default values are set."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        assert state["timeout_hours"] == 48
        assert state["retry_count"] == 0
        assert state["max_retries"] == 3
        assert state["current_step"] == 0
        assert state["plan"] == []
        assert state["email_threads"] == []
        assert state["received_documents"] == []
        assert state["error"] is None

    def test_initial_audit_entry(self) -> None:
        """Test initial audit entry is created."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        assert len(state["audit_log"]) == 1
        assert state["audit_log"][0]["event_type"] == "workflow_created"
        assert state["audit_log"][0]["actor"] == "system"

    def test_timestamps_set(self) -> None:
        """Test timestamps are set."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        assert state["created_at"] is not None
        assert state["updated_at"] is not None


class TestAddAuditEntry:
    """Tests for add_audit_entry function."""

    def test_add_entry(self) -> None:
        """Test adding audit entry."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        updated = add_audit_entry(
            state,
            event_type="test_event",
            actor="test_actor",
            description="Test description",
        )

        assert len(updated["audit_log"]) == 2
        assert updated["audit_log"][1]["event_type"] == "test_event"
        assert updated["audit_log"][1]["actor"] == "test_actor"

    def test_add_entry_with_details(self) -> None:
        """Test adding entry with details."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        updated = add_audit_entry(
            state,
            event_type="email_sent",
            actor="mail-agent",
            description="Email sent",
            details={"recipient": "user@example.com"},
        )

        assert updated["audit_log"][1]["details"]["recipient"] == "user@example.com"

    def test_updates_timestamp(self) -> None:
        """Test that updated_at is updated."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        original_updated = state["updated_at"]

        # Small delay to ensure different timestamp
        import time
        time.sleep(0.01)

        updated = add_audit_entry(
            state,
            event_type="test",
            actor="test",
            description="Test",
        )

        assert updated["updated_at"] != original_updated


class TestUpdateStatus:
    """Tests for update_status function."""

    def test_update_status(self) -> None:
        """Test updating status."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        updated = update_status(state, WorkflowStatus.EXECUTING)

        assert updated["status"] == WorkflowStatus.EXECUTING

    def test_update_status_with_reason(self) -> None:
        """Test updating status with reason."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        updated = update_status(
            state, WorkflowStatus.FAILED, "Connection timeout"
        )

        assert updated["status"] == WorkflowStatus.FAILED

    def test_creates_audit_entry(self) -> None:
        """Test that status change creates audit entry."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        updated = update_status(state, WorkflowStatus.EXECUTING)

        # Should have 2 entries: initial + status change
        assert len(updated["audit_log"]) == 2
        assert updated["audit_log"][1]["event_type"] == "status_change"
