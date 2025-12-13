"""
Unit tests for Supervisor state helpers.

Tests the state management functions and helpers used by the Supervisor Agent.
"""

import pytest
from datetime import datetime
from info_agent.agents.supervisor.state import (
    SupervisorState,
    WorkflowStatus,
    PlanStep,
    EmailAttachment,
    AuditLogEntry,
    create_initial_state,
    add_audit_entry,
)


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_workflow_status_values(self):
        """Test all workflow status values are defined."""
        expected_statuses = [
            "created",
            "planning",
            "awaiting_approval",
            "executing",
            "waiting_for_response",
            "completed",
            "failed",
            "cancelled",
        ]

        for status in expected_statuses:
            assert hasattr(WorkflowStatus, status.upper())
            assert WorkflowStatus[status.upper()].value == status

    def test_workflow_status_is_string_enum(self):
        """Test WorkflowStatus values are strings."""
        assert isinstance(WorkflowStatus.CREATED.value, str)
        assert isinstance(WorkflowStatus.PLANNING.value, str)
        assert isinstance(WorkflowStatus.COMPLETED.value, str)


class TestPlanStep:
    """Tests for PlanStep TypedDict."""

    def test_plan_step_structure(self):
        """Test PlanStep has correct structure."""
        step: PlanStep = {
            "step": 1,
            "action": "send_email",
            "description": "Send email to request information",
            "status": "pending",
        }

        assert step["step"] == 1
        assert step["action"] == "send_email"
        assert step["description"] == "Send email to request information"
        assert step["status"] == "pending"

    def test_plan_step_all_statuses(self):
        """Test PlanStep with different status values."""
        statuses = ["pending", "in_progress", "completed", "failed"]

        for status in statuses:
            step: PlanStep = {
                "step": 1,
                "action": "test_action",
                "description": "Test",
                "status": status,
            }
            assert step["status"] == status


class TestEmailAttachment:
    """Tests for EmailAttachment TypedDict."""

    def test_email_attachment_complete(self):
        """Test EmailAttachment with all fields."""
        attachment: EmailAttachment = {
            "filename": "report.pdf",
            "size": 12345,
            "mime_type": "application/pdf",
            "content_path": "/tmp/attachments/report.pdf",
        }

        assert attachment["filename"] == "report.pdf"
        assert attachment["size"] == 12345
        assert attachment["mime_type"] == "application/pdf"
        assert attachment["content_path"] == "/tmp/attachments/report.pdf"

    def test_email_attachment_no_content_path(self):
        """Test EmailAttachment without content_path."""
        attachment: EmailAttachment = {
            "filename": "data.csv",
            "size": 54321,
            "mime_type": "text/csv",
            "content_path": None,
        }

        assert attachment["content_path"] is None


class TestAuditLogEntry:
    """Tests for AuditLogEntry model."""

    def test_audit_log_entry_minimal(self):
        """Test AuditLogEntry with minimal fields."""
        entry = AuditLogEntry(
            timestamp="2025-12-13T10:00:00Z",
            action="workflow_created",
            details="Workflow created successfully",
        )

        assert entry.timestamp == "2025-12-13T10:00:00Z"
        assert entry.action == "workflow_created"
        assert entry.details == "Workflow created successfully"
        assert entry.metadata is None

    def test_audit_log_entry_with_metadata(self):
        """Test AuditLogEntry with metadata."""
        metadata = {
            "workflow_id": "wf-123",
            "user_id": "user-456",
        }

        entry = AuditLogEntry(
            timestamp="2025-12-13T11:00:00Z",
            action="plan_approved",
            details="User approved execution plan",
            metadata=metadata,
        )

        assert entry.metadata == metadata
        assert entry.metadata["workflow_id"] == "wf-123"


class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_create_initial_state_basic(self):
        """Test creating initial state with required parameters."""
        state = create_initial_state(
            workflow_id="wf-test-123",
            workflow_name="Test Workflow",
            instructions="Please collect information from john@example.com",
            instructions_filename="request.txt",
        )

        # Check identification fields
        assert state["workflow_id"] == "wf-test-123"
        assert state["workflow_name"] == "Test Workflow"

        # Check input data
        assert state["instructions"] == "Please collect information from john@example.com"
        assert state["instructions_filename"] == "request.txt"

        # Check initial execution state
        assert state["status"] == WorkflowStatus.CREATED.value
        assert state["plan"] == []
        assert state["current_step"] == 0
        assert state["plan_approved"] is False
        assert state["plan_rejected"] is False
        assert state["plan_cancelled"] is False

        # Check parsed requirements are empty
        assert state["target_email"] == ""
        assert state["target_name"] == ""
        assert state["requested_info"] == ""

        # Check communication tracking is initialized
        assert state["email_thread_id"] is None
        assert state["sent_email_id"] is None

        # Check results are empty
        assert state["received_response"] is None
        assert state["received_attachments"] == []

        # Check audit log has initial entry
        assert len(state["audit_log"]) == 1
        assert state["audit_log"][0]["action"] == "workflow_created"

        # Check timestamps are set
        assert state["created_at"] is not None
        assert state["updated_at"] is not None

        # Check error handling
        assert state["error"] is None
        assert state["error_step"] is None
        assert state["retry_count"] == 0

    def test_create_initial_state_timestamps(self):
        """Test initial state has valid ISO timestamps."""
        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test instructions",
            instructions_filename="test.txt",
        )

        # Timestamps should be valid ISO format
        created_at = datetime.fromisoformat(state["created_at"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00"))

        assert created_at is not None
        assert updated_at is not None
        assert state["created_at"] == state["updated_at"]

    def test_create_initial_state_audit_log_structure(self):
        """Test initial audit log entry structure."""
        state = create_initial_state(
            workflow_id="wf-audit-test",
            workflow_name="Audit Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        audit_entry = state["audit_log"][0]

        assert "timestamp" in audit_entry
        assert "action" in audit_entry
        assert "details" in audit_entry
        assert "metadata" in audit_entry

        assert audit_entry["action"] == "workflow_created"
        assert "Audit Test" in audit_entry["details"]
        assert audit_entry["metadata"]["workflow_id"] == "wf-audit-test"


class TestAddAuditEntry:
    """Tests for add_audit_entry function."""

    def test_add_audit_entry_basic(self):
        """Test adding audit entry without metadata."""
        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        initial_count = len(state["audit_log"])

        new_log = add_audit_entry(
            state=state,
            action="plan_generated",
            details="Execution plan generated successfully",
        )

        # Should return new list (immutable)
        assert len(new_log) == initial_count + 1
        assert len(state["audit_log"]) == initial_count  # Original unchanged

        # Check new entry
        new_entry = new_log[-1]
        assert new_entry["action"] == "plan_generated"
        assert new_entry["details"] == "Execution plan generated successfully"
        assert new_entry["metadata"] is None

    def test_add_audit_entry_with_metadata(self):
        """Test adding audit entry with metadata."""
        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        metadata = {
            "email_id": "msg-123",
            "recipient": "client@example.com",
        }

        new_log = add_audit_entry(
            state=state,
            action="email_sent",
            details="Email sent to client",
            metadata=metadata,
        )

        new_entry = new_log[-1]
        assert new_entry["metadata"] == metadata
        assert new_entry["metadata"]["email_id"] == "msg-123"

    def test_add_audit_entry_preserves_order(self):
        """Test adding multiple entries preserves order."""
        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        # Add multiple entries
        log1 = add_audit_entry(state, "action1", "First action")
        state["audit_log"] = log1

        log2 = add_audit_entry(state, "action2", "Second action")
        state["audit_log"] = log2

        log3 = add_audit_entry(state, "action3", "Third action")

        # Check order
        assert len(log3) == 4  # Initial + 3 new
        assert log3[0]["action"] == "workflow_created"
        assert log3[1]["action"] == "action1"
        assert log3[2]["action"] == "action2"
        assert log3[3]["action"] == "action3"

    def test_add_audit_entry_includes_timestamp(self):
        """Test audit entry includes valid timestamp."""
        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        new_log = add_audit_entry(
            state=state,
            action="test_action",
            details="Test details",
        )

        new_entry = new_log[-1]
        assert "timestamp" in new_entry

        # Should be valid ISO format
        timestamp = datetime.fromisoformat(new_entry["timestamp"].replace("Z", "+00:00"))
        assert timestamp is not None

    def test_add_audit_entry_immutability(self):
        """Test add_audit_entry doesn't mutate original state."""
        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        original_log_length = len(state["audit_log"])
        original_log = state["audit_log"].copy()

        # Add entry
        new_log = add_audit_entry(state, "new_action", "New action")

        # Original should be unchanged
        assert len(state["audit_log"]) == original_log_length
        assert state["audit_log"] == original_log

        # New log should have additional entry
        assert len(new_log) == original_log_length + 1


class TestSupervisorStateStructure:
    """Tests for SupervisorState structure and completeness."""

    def test_supervisor_state_all_fields_present(self):
        """Test SupervisorState has all expected fields."""
        state = create_initial_state(
            workflow_id="wf-complete-test",
            workflow_name="Complete Test",
            instructions="Full test of all fields",
            instructions_filename="complete.txt",
        )

        # All these fields should exist
        expected_fields = [
            # Identification
            "workflow_id",
            "workflow_name",
            # Input data
            "instructions",
            "instructions_filename",
            # Parsed requirements
            "target_email",
            "target_name",
            "requested_info",
            # Execution state
            "status",
            "plan",
            "current_step",
            "plan_approved",
            "plan_rejected",
            "plan_cancelled",
            "approval_feedback",
            # Communication tracking
            "email_thread_id",
            "sent_email_id",
            "sent_email_subject",
            "sent_email_body",
            # Results
            "received_response",
            "received_response_subject",
            "received_attachments",
            # Audit and metadata
            "audit_log",
            "created_at",
            "updated_at",
            # Error handling
            "error",
            "error_step",
            "retry_count",
        ]

        for field in expected_fields:
            assert field in state, f"Missing field: {field}"

    def test_supervisor_state_can_be_updated(self):
        """Test SupervisorState fields can be updated."""
        state = create_initial_state(
            workflow_id="wf-update-test",
            workflow_name="Update Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        # Update various fields
        state["target_email"] = "client@example.com"
        state["target_name"] = "John Doe"
        state["requested_info"] = "Q3 Reports"
        state["status"] = WorkflowStatus.PLANNING.value
        state["plan"] = [
            {"step": 1, "action": "send_email", "description": "Send email", "status": "pending"}
        ]
        state["current_step"] = 1
        state["plan_approved"] = True

        # Verify updates
        assert state["target_email"] == "client@example.com"
        assert state["target_name"] == "John Doe"
        assert state["requested_info"] == "Q3 Reports"
        assert state["status"] == WorkflowStatus.PLANNING.value
        assert len(state["plan"]) == 1
        assert state["current_step"] == 1
        assert state["plan_approved"] is True
