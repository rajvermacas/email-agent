"""
Unit tests for the workflow state module.

Tests the SupervisorState TypedDict, state factory functions,
and audit logging functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from info_agent.workflow.state import (
    WorkflowStatus,
    AuditLogEntry,
    PlanStep,
    EmailAttachment,
    SupervisorState,
    create_initial_state,
    add_audit_entry,
)


class TestWorkflowStatus:
    """Tests for the WorkflowStatus enum."""

    def test_workflow_status_values(self):
        """Test that all workflow status values are defined correctly."""
        assert WorkflowStatus.CREATED.value == "created"
        assert WorkflowStatus.PLANNING.value == "planning"
        assert WorkflowStatus.AWAITING_APPROVAL.value == "awaiting_approval"
        assert WorkflowStatus.EXECUTING.value == "executing"
        assert WorkflowStatus.WAITING_FOR_RESPONSE.value == "waiting_for_response"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"

    def test_workflow_status_is_string(self):
        """Test that WorkflowStatus inherits from str."""
        assert isinstance(WorkflowStatus.CREATED, str)
        assert isinstance(WorkflowStatus.PLANNING, str)

    def test_workflow_status_membership(self):
        """Test that status values can be checked for membership."""
        status = "created"
        assert status in [s.value for s in WorkflowStatus]

        invalid_status = "invalid_status"
        assert invalid_status not in [s.value for s in WorkflowStatus]


class TestAuditLogEntry:
    """Tests for the AuditLogEntry pydantic model."""

    def test_audit_log_entry_required_fields(self):
        """Test creating AuditLogEntry with required fields."""
        entry = AuditLogEntry(
            timestamp="2025-01-15T10:30:00Z",
            action="test_action",
            details="Test action description",
        )

        assert entry.timestamp == "2025-01-15T10:30:00Z"
        assert entry.action == "test_action"
        assert entry.details == "Test action description"
        assert entry.metadata is None

    def test_audit_log_entry_with_metadata(self):
        """Test creating AuditLogEntry with metadata."""
        entry = AuditLogEntry(
            timestamp="2025-01-15T10:30:00Z",
            action="workflow_created",
            details="Workflow created",
            metadata={"workflow_id": "wf-123", "user": "test_user"},
        )

        assert entry.metadata == {"workflow_id": "wf-123", "user": "test_user"}

    def test_audit_log_entry_missing_required_field(self):
        """Test that AuditLogEntry raises error when required fields missing."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            AuditLogEntry(
                timestamp="2025-01-15T10:30:00Z",
                action="test_action",
                # Missing details
            )

    def test_audit_log_entry_serialization(self):
        """Test that AuditLogEntry can be serialized to dict."""
        entry = AuditLogEntry(
            timestamp="2025-01-15T10:30:00Z",
            action="send_email",
            details="Email sent to user",
            metadata={"recipient": "user@example.com"},
        )

        entry_dict = entry.model_dump()

        assert entry_dict["timestamp"] == "2025-01-15T10:30:00Z"
        assert entry_dict["action"] == "send_email"
        assert entry_dict["details"] == "Email sent to user"
        assert entry_dict["metadata"] == {"recipient": "user@example.com"}


class TestPlanStep:
    """Tests for the PlanStep TypedDict."""

    def test_plan_step_creation(self):
        """Test creating a PlanStep."""
        step: PlanStep = {
            "step": 1,
            "action": "send_email",
            "description": "Send request email to target",
            "status": "pending",
        }

        assert step["step"] == 1
        assert step["action"] == "send_email"
        assert step["description"] == "Send request email to target"
        assert step["status"] == "pending"

    def test_plan_step_with_different_statuses(self):
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
    """Tests for the EmailAttachment TypedDict."""

    def test_email_attachment_creation(self):
        """Test creating an EmailAttachment."""
        attachment: EmailAttachment = {
            "filename": "document.pdf",
            "size": 1024,
            "mime_type": "application/pdf",
            "content_path": "/tmp/attachments/document.pdf",
        }

        assert attachment["filename"] == "document.pdf"
        assert attachment["size"] == 1024
        assert attachment["mime_type"] == "application/pdf"
        assert attachment["content_path"] == "/tmp/attachments/document.pdf"

    def test_email_attachment_without_content_path(self):
        """Test EmailAttachment with None content_path."""
        attachment: EmailAttachment = {
            "filename": "image.png",
            "size": 2048,
            "mime_type": "image/png",
            "content_path": None,
        }

        assert attachment["content_path"] is None


class TestCreateInitialState:
    """Tests for the create_initial_state function."""

    @patch("info_agent.workflow.state.datetime")
    def test_create_initial_state_basic(self, mock_datetime):
        """Test creating initial state with basic parameters."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:30:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state = create_initial_state(
            workflow_id="wf-test-123",
            workflow_name="Test Workflow",
            instructions="Please request financial reports from John.",
            instructions_filename="request.txt",
        )

        # Verify workflow identification
        assert state["workflow_id"] == "wf-test-123"
        assert state["workflow_name"] == "Test Workflow"

        # Verify input data
        assert state["instructions"] == "Please request financial reports from John."
        assert state["instructions_filename"] == "request.txt"

        # Verify parsed requirements (empty until parsed)
        assert state["target_email"] == ""
        assert state["target_name"] == ""
        assert state["requested_info"] == ""

        # Verify execution state
        assert state["status"] == WorkflowStatus.CREATED.value
        assert state["plan"] == []
        assert state["current_step"] == 0
        assert state["plan_approved"] is False
        assert state["plan_rejected"] is False
        assert state["plan_cancelled"] is False
        assert state["approval_feedback"] is None

    @patch("info_agent.workflow.state.datetime")
    def test_create_initial_state_communication_tracking(self, mock_datetime):
        """Test that communication tracking fields are initialized to None."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:30:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test instructions",
            instructions_filename="test.txt",
        )

        assert state["email_thread_id"] is None
        assert state["sent_email_id"] is None
        assert state["sent_email_subject"] is None
        assert state["sent_email_body"] is None

    @patch("info_agent.workflow.state.datetime")
    def test_create_initial_state_results(self, mock_datetime):
        """Test that result fields are initialized correctly."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:30:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test instructions",
            instructions_filename="test.txt",
        )

        assert state["received_response"] is None
        assert state["received_response_subject"] is None
        assert state["received_attachments"] == []

    @patch("info_agent.workflow.state.datetime")
    def test_create_initial_state_audit_log(self, mock_datetime):
        """Test that initial audit log is created correctly."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:30:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state = create_initial_state(
            workflow_id="wf-test-456",
            workflow_name="My Workflow",
            instructions="Test",
            instructions_filename="test.txt",
        )

        assert len(state["audit_log"]) == 1

        first_entry = state["audit_log"][0]
        assert first_entry["timestamp"] == "2025-01-15T10:30:00Z"
        assert first_entry["action"] == "workflow_created"
        assert "My Workflow" in first_entry["details"]
        assert first_entry["metadata"]["workflow_id"] == "wf-test-456"

    @patch("info_agent.workflow.state.datetime")
    def test_create_initial_state_metadata(self, mock_datetime):
        """Test that metadata fields are set correctly."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:30:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        assert state["created_at"] == "2025-01-15T10:30:00Z"
        assert state["updated_at"] == "2025-01-15T10:30:00Z"

    @patch("info_agent.workflow.state.datetime")
    def test_create_initial_state_error_handling(self, mock_datetime):
        """Test that error handling fields are initialized correctly."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:30:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state = create_initial_state(
            workflow_id="wf-123",
            workflow_name="Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        assert state["error"] is None
        assert state["error_step"] is None
        assert state["retry_count"] == 0


class TestAddAuditEntry:
    """Tests for the add_audit_entry function."""

    @patch("info_agent.workflow.state.datetime")
    def test_add_audit_entry_basic(self, mock_datetime):
        """Test adding a basic audit entry."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state: SupervisorState = {
            "workflow_id": "wf-123",
            "audit_log": [
                {
                    "timestamp": "2025-01-15T10:00:00Z",
                    "action": "workflow_created",
                    "details": "Initial entry",
                    "metadata": None,
                }
            ],
        }  # type: ignore

        new_log = add_audit_entry(
            state,
            action="parse_inputs",
            details="Parsed instruction files",
        )

        assert len(new_log) == 2
        assert new_log[0]["action"] == "workflow_created"

        new_entry = new_log[1]
        assert new_entry["timestamp"] == "2025-01-15T11:00:00Z"
        assert new_entry["action"] == "parse_inputs"
        assert new_entry["details"] == "Parsed instruction files"
        assert new_entry["metadata"] is None

    @patch("info_agent.workflow.state.datetime")
    def test_add_audit_entry_with_metadata(self, mock_datetime):
        """Test adding audit entry with metadata."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state: SupervisorState = {
            "workflow_id": "wf-123",
            "audit_log": [],
        }  # type: ignore

        new_log = add_audit_entry(
            state,
            action="send_email",
            details="Email sent to recipient",
            metadata={
                "recipient": "user@example.com",
                "message_id": "msg-123",
            },
        )

        assert len(new_log) == 1
        entry = new_log[0]
        assert entry["action"] == "send_email"
        assert entry["metadata"]["recipient"] == "user@example.com"
        assert entry["metadata"]["message_id"] == "msg-123"

    @patch("info_agent.workflow.state.datetime")
    def test_add_audit_entry_preserves_original_log(self, mock_datetime):
        """Test that add_audit_entry doesn't mutate the original log."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        original_log = [
            {
                "timestamp": "2025-01-15T10:00:00Z",
                "action": "workflow_created",
                "details": "Initial",
                "metadata": None,
            }
        ]

        state: SupervisorState = {
            "workflow_id": "wf-123",
            "audit_log": original_log,
        }  # type: ignore

        new_log = add_audit_entry(
            state,
            action="new_action",
            details="New action",
        )

        # Original log should be unchanged
        assert len(original_log) == 1
        assert original_log[0]["action"] == "workflow_created"

        # New log should have both entries
        assert len(new_log) == 2

    @patch("info_agent.workflow.state.datetime")
    def test_add_audit_entry_empty_initial_log(self, mock_datetime):
        """Test adding audit entry when initial log is empty."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state: SupervisorState = {
            "workflow_id": "wf-123",
            "audit_log": [],
        }  # type: ignore

        new_log = add_audit_entry(
            state,
            action="first_action",
            details="First entry",
        )

        assert len(new_log) == 1
        assert new_log[0]["action"] == "first_action"

    @patch("info_agent.workflow.state.datetime")
    def test_add_audit_entry_missing_audit_log_field(self, mock_datetime):
        """Test add_audit_entry handles missing audit_log field."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state: SupervisorState = {
            "workflow_id": "wf-123",
        }  # type: ignore

        new_log = add_audit_entry(
            state,
            action="test_action",
            details="Test",
        )

        assert len(new_log) == 1
        assert new_log[0]["action"] == "test_action"

    @patch("info_agent.workflow.state.datetime")
    def test_add_audit_entry_multiple_additions(self, mock_datetime):
        """Test adding multiple audit entries in sequence."""
        mock_times = [
            "2025-01-15T10:00:00Z",
            "2025-01-15T11:00:00Z",
            "2025-01-15T12:00:00Z",
        ]
        mock_now = Mock()
        mock_datetime.utcnow.return_value = mock_now

        state: SupervisorState = {
            "workflow_id": "wf-123",
            "audit_log": [],
        }  # type: ignore

        # Add first entry
        mock_now.isoformat.return_value = mock_times[0]
        log1 = add_audit_entry(state, "action1", "First action")

        # Add second entry
        state["audit_log"] = log1
        mock_now.isoformat.return_value = mock_times[1]
        log2 = add_audit_entry(state, "action2", "Second action")

        # Add third entry
        state["audit_log"] = log2
        mock_now.isoformat.return_value = mock_times[2]
        log3 = add_audit_entry(state, "action3", "Third action")

        assert len(log3) == 3
        assert log3[0]["action"] == "action1"
        assert log3[1]["action"] == "action2"
        assert log3[2]["action"] == "action3"
        assert log3[0]["timestamp"] == mock_times[0]
        assert log3[1]["timestamp"] == mock_times[1]
        assert log3[2]["timestamp"] == mock_times[2]


class TestIntegrationScenarios:
    """Integration-style tests for state management."""

    @patch("info_agent.workflow.state.datetime")
    def test_typical_workflow_state_progression(self, mock_datetime):
        """Test typical progression of workflow state."""
        mock_now = Mock()
        mock_datetime.utcnow.return_value = mock_now

        # Create initial state
        mock_now.isoformat.return_value = "2025-01-15T10:00:00Z"
        state = create_initial_state(
            workflow_id="wf-integration-test",
            workflow_name="Integration Test Workflow",
            instructions="Request Q4 reports from finance@example.com",
            instructions_filename="request.txt",
        )

        assert state["status"] == WorkflowStatus.CREATED.value
        assert len(state["audit_log"]) == 1

        # Simulate parsing inputs
        mock_now.isoformat.return_value = "2025-01-15T10:01:00Z"
        state["target_email"] = "finance@example.com"
        state["target_name"] = "Finance Team"
        state["requested_info"] = "Q4 Financial Reports"
        state["status"] = WorkflowStatus.PLANNING.value
        state["audit_log"] = add_audit_entry(
            state,
            action="parse_inputs",
            details="Extracted requirements from instructions",
            metadata={"target_email": "finance@example.com"},
        )

        assert len(state["audit_log"]) == 2
        assert state["status"] == WorkflowStatus.PLANNING.value

        # Simulate plan generation
        mock_now.isoformat.return_value = "2025-01-15T10:02:00Z"
        state["plan"] = [
            {
                "step": 1,
                "action": "send_email",
                "description": "Send request email",
                "status": "pending",
            },
            {
                "step": 2,
                "action": "wait_response",
                "description": "Wait for response",
                "status": "pending",
            },
        ]
        state["status"] = WorkflowStatus.AWAITING_APPROVAL.value
        state["audit_log"] = add_audit_entry(
            state,
            action="generate_plan",
            details="Generated execution plan with 2 steps",
            metadata={"step_count": 2},
        )

        assert len(state["audit_log"]) == 3
        assert len(state["plan"]) == 2

    @patch("info_agent.workflow.state.datetime")
    def test_error_state_tracking(self, mock_datetime):
        """Test tracking errors in workflow state."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        state = create_initial_state(
            workflow_id="wf-error-test",
            workflow_name="Error Test",
            instructions="Test",
            instructions_filename="test.txt",
        )

        # Simulate an error
        state["status"] = WorkflowStatus.FAILED.value
        state["error"] = "LLM invocation failed"
        state["error_step"] = "parse_inputs"
        state["retry_count"] = 1
        state["audit_log"] = add_audit_entry(
            state,
            action="error",
            details="LLM invocation failed during parse_inputs",
            metadata={
                "error": "LLM invocation failed",
                "step": "parse_inputs",
            },
        )

        assert state["status"] == WorkflowStatus.FAILED.value
        assert state["error"] == "LLM invocation failed"
        assert state["error_step"] == "parse_inputs"
        assert state["retry_count"] == 1
        assert len(state["audit_log"]) == 2
