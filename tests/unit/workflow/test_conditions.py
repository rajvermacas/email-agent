"""
Unit tests for workflow conditions.
"""

import pytest
from datetime import datetime, timedelta

from info_agent.workflow.state import (
    SupervisorState,
    WorkflowStatus,
    create_initial_state,
)
from info_agent.workflow.conditions import (
    check_approval_status,
    determine_next_action,
    check_response_type,
    check_faq_match,
    evaluate_retry_count,
    check_validation_result,
    should_continue_workflow,
)


class TestCheckApprovalStatus:
    """Tests for check_approval_status condition."""

    def test_returns_approved_when_plan_approved(self) -> None:
        """Test returns approved when plan is approved."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan_approved"] = True

        result = check_approval_status(state)

        assert result == "approved"

    def test_returns_rejected_when_rejection_reason(self) -> None:
        """Test returns rejected when rejection reason set."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan_approved"] = False
        state["plan_rejection_reason"] = "Need more details"

        result = check_approval_status(state)

        assert result == "rejected"

    def test_returns_cancelled_when_cancelled(self) -> None:
        """Test returns cancelled when workflow cancelled."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.CANCELLED

        result = check_approval_status(state)

        assert result == "cancelled"

    def test_defaults_to_approved_when_awaiting(self) -> None:
        """Test defaults to approved when in awaiting state."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.AWAITING_APPROVAL
        state["plan_approved"] = False
        state["plan_rejection_reason"] = None

        result = check_approval_status(state)

        # For workflow testing, defaults to approved
        assert result == "approved"


class TestDetermineNextAction:
    """Tests for determine_next_action condition."""

    def test_returns_send_email_for_email_step(self) -> None:
        """Test returns send_email for email step."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan"] = [
            {"step_number": 1, "action": "send_initial_request", "agent": "mail-agent"},
        ]
        state["current_step"] = 0

        result = determine_next_action(state)

        assert result == "send_email"

    def test_returns_validate_for_validation_step(self) -> None:
        """Test returns validate for validation step."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan"] = [
            {"step_number": 1, "action": "validate_document", "agent": "validation-agent"},
        ]
        state["current_step"] = 0

        result = determine_next_action(state)

        assert result == "validate"

    def test_returns_complete_when_no_steps_left(self) -> None:
        """Test returns complete when no more steps."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan"] = [
            {"step_number": 1, "action": "send_email", "agent": "mail-agent"},
        ]
        state["current_step"] = 1  # Past last step

        result = determine_next_action(state)

        assert result == "complete"

    def test_returns_complete_for_empty_plan(self) -> None:
        """Test returns complete for empty plan."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan"] = []
        state["current_step"] = 0

        result = determine_next_action(state)

        assert result == "complete"


class TestCheckResponseType:
    """Tests for check_response_type condition."""

    def test_returns_error_when_error_present(self) -> None:
        """Test returns error when error in state."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["error"] = "Connection failed"

        result = check_response_type(state)

        assert result == "error"

    def test_returns_document_received(self) -> None:
        """Test returns document_received when documents present."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["received_documents"] = [{"id": "doc-1"}]

        result = check_response_type(state)

        assert result == "document_received"

    def test_returns_clarification_needed(self) -> None:
        """Test returns clarification_needed when unanswered."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["clarification_history"] = [
            {"id": "clar-1", "question": "What format?", "answered_at": None}
        ]

        result = check_response_type(state)

        assert result == "clarification_needed"

    def test_returns_timeout_when_expired(self) -> None:
        """Test returns timeout when waiting period expired."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        old_time = datetime.utcnow() - timedelta(hours=50)
        state["waiting_since"] = old_time.isoformat()
        state["timeout_hours"] = 48

        result = check_response_type(state)

        assert result == "timeout"

    def test_returns_document_received_when_response_received(self) -> None:
        """Test returns document_received when response_received is True."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["response_received"] = True
        state["waiting_since"] = datetime.utcnow().isoformat()

        result = check_response_type(state)

        assert result == "document_received"


class TestCheckFaqMatch:
    """Tests for check_faq_match condition."""

    def test_returns_found_in_faq(self) -> None:
        """Test returns found_in_faq when match found."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["clarification_history"] = [
            {"id": "clar-1", "question": "Format?", "faq_match": True}
        ]

        result = check_faq_match(state)

        assert result == "found_in_faq"

    def test_returns_not_in_faq(self) -> None:
        """Test returns not_in_faq when no match."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["clarification_history"] = [
            {"id": "clar-1", "question": "Random?", "faq_match": False}
        ]

        result = check_faq_match(state)

        assert result == "not_in_faq"

    def test_returns_not_in_faq_when_no_history(self) -> None:
        """Test returns not_in_faq when no clarifications."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["clarification_history"] = []

        result = check_faq_match(state)

        assert result == "not_in_faq"


class TestEvaluateRetryCount:
    """Tests for evaluate_retry_count condition."""

    def test_returns_retry_when_under_limit(self) -> None:
        """Test returns retry when under limit."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["retry_count"] = 1
        state["max_retries"] = 3

        result = evaluate_retry_count(state)

        assert result == "retry"

    def test_returns_escalate_when_at_limit(self) -> None:
        """Test returns escalate when at limit."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["retry_count"] = 3
        state["max_retries"] = 3

        result = evaluate_retry_count(state)

        assert result == "escalate"

    def test_returns_escalate_when_over_limit(self) -> None:
        """Test returns escalate when over limit."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["retry_count"] = 5
        state["max_retries"] = 3

        result = evaluate_retry_count(state)

        assert result == "escalate"

    def test_uses_default_max_retries(self) -> None:
        """Test uses default max retries of 3."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["retry_count"] = 2

        result = evaluate_retry_count(state)

        assert result == "retry"


class TestCheckValidationResult:
    """Tests for check_validation_result condition."""

    def test_returns_passed_when_passed(self) -> None:
        """Test returns passed when validation passed."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["validation_result"] = {"passed": True, "score": 1.0}

        result = check_validation_result(state)

        assert result == "passed"

    def test_returns_failed_when_failed(self) -> None:
        """Test returns failed when validation failed."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["validation_result"] = {"passed": False, "score": 0.5}

        result = check_validation_result(state)

        assert result == "failed"

    def test_returns_failed_when_no_result(self) -> None:
        """Test returns failed when no result."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["validation_result"] = None

        result = check_validation_result(state)

        assert result == "failed"


class TestShouldContinueWorkflow:
    """Tests for should_continue_workflow function."""

    def test_returns_true_for_planning(self) -> None:
        """Test returns True for planning status."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.PLANNING

        result = should_continue_workflow(state)

        assert result is True

    def test_returns_true_for_executing(self) -> None:
        """Test returns True for executing status."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.EXECUTING

        result = should_continue_workflow(state)

        assert result is True

    def test_returns_false_for_completed(self) -> None:
        """Test returns False for completed status."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.COMPLETED

        result = should_continue_workflow(state)

        assert result is False

    def test_returns_false_for_failed(self) -> None:
        """Test returns False for failed status."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.FAILED

        result = should_continue_workflow(state)

        assert result is False

    def test_returns_false_for_cancelled(self) -> None:
        """Test returns False for cancelled status."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.CANCELLED

        result = should_continue_workflow(state)

        assert result is False
