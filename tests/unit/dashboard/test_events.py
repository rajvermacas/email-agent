"""
Unit tests for AG-UI events.
"""

import json
import pytest
from datetime import datetime, timezone

from info_agent.dashboard.events import (
    AGUIEvent,
    AGUIEventType,
    create_run_started_event,
    create_run_finished_event,
    create_run_error_event,
    create_text_message_event,
    create_tool_call_event,
    create_state_delta_event,
    create_plan_event,
    create_step_event,
    create_email_event,
    create_validation_event,
)


class TestAGUIEventType:
    """Tests for AGUIEventType enum."""

    def test_lifecycle_events(self) -> None:
        """Test lifecycle event types."""
        assert AGUIEventType.RUN_STARTED.value == "RUN_STARTED"
        assert AGUIEventType.RUN_FINISHED.value == "RUN_FINISHED"
        assert AGUIEventType.RUN_ERROR.value == "RUN_ERROR"

    def test_text_message_events(self) -> None:
        """Test text message event types."""
        assert AGUIEventType.TEXT_MESSAGE_START.value == "TEXT_MESSAGE_START"
        assert AGUIEventType.TEXT_MESSAGE_CONTENT.value == "TEXT_MESSAGE_CONTENT"
        assert AGUIEventType.TEXT_MESSAGE_END.value == "TEXT_MESSAGE_END"

    def test_tool_call_events(self) -> None:
        """Test tool call event types."""
        assert AGUIEventType.TOOL_CALL_START.value == "TOOL_CALL_START"
        assert AGUIEventType.TOOL_CALL_ARGS.value == "TOOL_CALL_ARGS"
        assert AGUIEventType.TOOL_CALL_END.value == "TOOL_CALL_END"

    def test_state_events(self) -> None:
        """Test state event types."""
        assert AGUIEventType.STATE_SNAPSHOT.value == "STATE_SNAPSHOT"
        assert AGUIEventType.STATE_DELTA.value == "STATE_DELTA"

    def test_custom_events(self) -> None:
        """Test custom Info-Agent event types."""
        assert AGUIEventType.PLAN_GENERATED.value == "PLAN_GENERATED"
        assert AGUIEventType.EMAIL_SENT.value == "EMAIL_SENT"
        assert AGUIEventType.VALIDATION_COMPLETE.value == "VALIDATION_COMPLETE"


class TestAGUIEvent:
    """Tests for AGUIEvent model."""

    def test_create_event(self) -> None:
        """Test creating an event."""
        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
            data={"status": "executing"},
        )

        assert event.type == AGUIEventType.RUN_STARTED
        assert event.workflow_id == "wf-123"
        assert event.data["status"] == "executing"
        assert event.timestamp is not None

    def test_event_with_optional_fields(self) -> None:
        """Test event with optional fields."""
        event = AGUIEvent(
            type=AGUIEventType.TOOL_CALL_START,
            workflow_id="wf-123",
            run_id="run-456",
            tool_call_id="call-789",
            data={"tool_name": "send_email"},
        )

        assert event.run_id == "run-456"
        assert event.tool_call_id == "call-789"

    def test_to_sse(self) -> None:
        """Test conversion to SSE format."""
        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
            data={"status": "executing"},
        )

        sse = event.to_sse()

        assert "event: RUN_STARTED\n" in sse
        assert "data: " in sse
        assert "wf-123" in sse
        assert sse.endswith("\n\n")

    def test_to_sse_includes_all_fields(self) -> None:
        """Test SSE includes all relevant fields."""
        event = AGUIEvent(
            type=AGUIEventType.TOOL_CALL_START,
            workflow_id="wf-123",
            run_id="run-456",
            tool_call_id="call-789",
            data={"tool_name": "validate"},
        )

        sse = event.to_sse()
        data_line = sse.split("data: ")[1].split("\n")[0]
        data = json.loads(data_line)

        assert data["type"] == "TOOL_CALL_START"
        assert data["workflow_id"] == "wf-123"
        assert data["run_id"] == "run-456"
        assert data["tool_call_id"] == "call-789"
        assert data["tool_name"] == "validate"

    def test_to_json(self) -> None:
        """Test conversion to JSON."""
        event = AGUIEvent(
            type=AGUIEventType.STATE_DELTA,
            workflow_id="wf-123",
            data={"delta": {"status": "completed"}},
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["type"] == "STATE_DELTA"
        assert data["workflow_id"] == "wf-123"
        assert data["delta"]["status"] == "completed"

    def test_default_timestamp(self) -> None:
        """Test default timestamp is UTC now."""
        before = datetime.now(timezone.utc)
        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        after = datetime.now(timezone.utc)

        assert before <= event.timestamp <= after


class TestCreateRunStartedEvent:
    """Tests for create_run_started_event."""

    def test_basic_event(self) -> None:
        """Test creating basic run started event."""
        event = create_run_started_event(workflow_id="wf-123")

        assert event.type == AGUIEventType.RUN_STARTED
        assert event.workflow_id == "wf-123"
        assert event.data["status"] == "executing"

    def test_with_run_id(self) -> None:
        """Test with run ID."""
        event = create_run_started_event(
            workflow_id="wf-123",
            run_id="run-456",
        )

        assert event.run_id == "run-456"

    def test_with_custom_status(self) -> None:
        """Test with custom status."""
        event = create_run_started_event(
            workflow_id="wf-123",
            status="planning",
        )

        assert event.data["status"] == "planning"

    def test_with_metadata(self) -> None:
        """Test with metadata."""
        event = create_run_started_event(
            workflow_id="wf-123",
            metadata={"source": "test"},
        )

        assert event.data["metadata"]["source"] == "test"


class TestCreateRunFinishedEvent:
    """Tests for create_run_finished_event."""

    def test_basic_event(self) -> None:
        """Test creating basic run finished event."""
        event = create_run_finished_event(workflow_id="wf-123")

        assert event.type == AGUIEventType.RUN_FINISHED
        assert event.data["status"] == "completed"

    def test_with_result(self) -> None:
        """Test with result data."""
        event = create_run_finished_event(
            workflow_id="wf-123",
            result={"validation_passed": True},
        )

        assert event.data["result"]["validation_passed"] is True


class TestCreateRunErrorEvent:
    """Tests for create_run_error_event."""

    def test_basic_error(self) -> None:
        """Test creating basic error event."""
        event = create_run_error_event(
            workflow_id="wf-123",
            error="Something went wrong",
        )

        assert event.type == AGUIEventType.RUN_ERROR
        assert event.data["error"] == "Something went wrong"

    def test_with_error_code(self) -> None:
        """Test with error code."""
        event = create_run_error_event(
            workflow_id="wf-123",
            error="Validation failed",
            error_code="VALIDATION_ERROR",
        )

        assert event.data["error_code"] == "VALIDATION_ERROR"

    def test_with_details(self) -> None:
        """Test with error details."""
        event = create_run_error_event(
            workflow_id="wf-123",
            error="Timeout",
            details={"elapsed_seconds": 300},
        )

        assert event.data["details"]["elapsed_seconds"] == 300


class TestCreateTextMessageEvent:
    """Tests for create_text_message_event."""

    def test_content_event(self) -> None:
        """Test creating text content event."""
        event = create_text_message_event(
            workflow_id="wf-123",
            message_id="msg-456",
            content="Processing your request...",
        )

        assert event.type == AGUIEventType.TEXT_MESSAGE_CONTENT
        assert event.message_id == "msg-456"
        assert event.data["content"] == "Processing your request..."
        assert event.data["role"] == "assistant"

    def test_start_event(self) -> None:
        """Test creating text start event."""
        event = create_text_message_event(
            workflow_id="wf-123",
            message_id="msg-456",
            content="",
            event_type=AGUIEventType.TEXT_MESSAGE_START,
        )

        assert event.type == AGUIEventType.TEXT_MESSAGE_START


class TestCreateToolCallEvent:
    """Tests for create_tool_call_event."""

    def test_start_event(self) -> None:
        """Test creating tool call start event."""
        event = create_tool_call_event(
            workflow_id="wf-123",
            tool_call_id="call-456",
            tool_name="send_email",
        )

        assert event.type == AGUIEventType.TOOL_CALL_START
        assert event.tool_call_id == "call-456"
        assert event.data["tool_name"] == "send_email"

    def test_with_arguments(self) -> None:
        """Test with tool arguments."""
        event = create_tool_call_event(
            workflow_id="wf-123",
            tool_call_id="call-456",
            tool_name="send_email",
            event_type=AGUIEventType.TOOL_CALL_ARGS,
            arguments={"to": "test@example.com"},
        )

        assert event.type == AGUIEventType.TOOL_CALL_ARGS
        assert event.data["arguments"]["to"] == "test@example.com"

    def test_with_result(self) -> None:
        """Test with tool result."""
        event = create_tool_call_event(
            workflow_id="wf-123",
            tool_call_id="call-456",
            tool_name="send_email",
            event_type=AGUIEventType.TOOL_CALL_END,
            result={"success": True},
        )

        assert event.type == AGUIEventType.TOOL_CALL_END
        assert event.data["result"]["success"] is True


class TestCreateStateDeltaEvent:
    """Tests for create_state_delta_event."""

    def test_basic_delta(self) -> None:
        """Test creating basic state delta event."""
        event = create_state_delta_event(
            workflow_id="wf-123",
            delta={"status": "completed"},
        )

        assert event.type == AGUIEventType.STATE_DELTA
        assert event.data["delta"]["status"] == "completed"

    def test_with_path(self) -> None:
        """Test with state path."""
        event = create_state_delta_event(
            workflow_id="wf-123",
            delta={"value": 42},
            path="workflow.current_step",
        )

        assert event.data["path"] == "workflow.current_step"


class TestCreatePlanEvent:
    """Tests for create_plan_event."""

    def test_plan_generated(self) -> None:
        """Test creating plan generated event."""
        plan = [
            {"step_number": 1, "action": "send_email"},
            {"step_number": 2, "action": "wait"},
        ]

        event = create_plan_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.PLAN_GENERATED,
            plan=plan,
        )

        assert event.type == AGUIEventType.PLAN_GENERATED
        assert len(event.data["plan"]) == 2

    def test_plan_rejected(self) -> None:
        """Test creating plan rejected event."""
        event = create_plan_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.PLAN_REJECTED,
            feedback="Need more details",
        )

        assert event.type == AGUIEventType.PLAN_REJECTED
        assert event.data["feedback"] == "Need more details"


class TestCreateStepEvent:
    """Tests for create_step_event."""

    def test_step_started(self) -> None:
        """Test creating step started event."""
        event = create_step_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.STEP_STARTED,
            step_number=1,
            action="send_email",
            agent="mail-agent",
            skill="send_email",
            description="Send email to target",
        )

        assert event.type == AGUIEventType.STEP_STARTED
        assert event.data["step_number"] == 1
        assert event.data["agent"] == "mail-agent"

    def test_step_completed(self) -> None:
        """Test creating step completed event."""
        event = create_step_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.STEP_COMPLETED,
            step_number=1,
            action="send_email",
            agent="mail-agent",
            skill="send_email",
            result={"message_id": "msg-123"},
        )

        assert event.type == AGUIEventType.STEP_COMPLETED
        assert event.data["result"]["message_id"] == "msg-123"

    def test_step_failed(self) -> None:
        """Test creating step failed event."""
        event = create_step_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.STEP_FAILED,
            step_number=1,
            action="send_email",
            agent="mail-agent",
            skill="send_email",
            error="Connection timeout",
        )

        assert event.type == AGUIEventType.STEP_FAILED
        assert event.data["error"] == "Connection timeout"


class TestCreateEmailEvent:
    """Tests for create_email_event."""

    def test_email_sent(self) -> None:
        """Test creating email sent event."""
        event = create_email_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.EMAIL_SENT,
            message_id="msg-456",
            thread_id="thread-789",
            from_address="sender@test.com",
            to_address="receiver@test.com",
            subject="Information Request",
        )

        assert event.type == AGUIEventType.EMAIL_SENT
        assert event.data["message_id"] == "msg-456"
        assert event.data["from_address"] == "sender@test.com"

    def test_email_received(self) -> None:
        """Test creating email received event."""
        event = create_email_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.EMAIL_RECEIVED,
            message_id="msg-456",
            thread_id="thread-789",
            from_address="receiver@test.com",
            to_address="sender@test.com",
            subject="Re: Information Request",
            has_attachments=True,
        )

        assert event.type == AGUIEventType.EMAIL_RECEIVED
        assert event.data["has_attachments"] is True


class TestCreateValidationEvent:
    """Tests for create_validation_event."""

    def test_validation_started(self) -> None:
        """Test creating validation started event."""
        event = create_validation_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.VALIDATION_STARTED,
            document_id="doc-456",
            document_name="data.xlsx",
        )

        assert event.type == AGUIEventType.VALIDATION_STARTED
        assert event.data["document_id"] == "doc-456"
        assert event.data["document_name"] == "data.xlsx"

    def test_validation_complete_passed(self) -> None:
        """Test creating validation complete event (passed)."""
        event = create_validation_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.VALIDATION_COMPLETE,
            document_id="doc-456",
            passed=True,
            score=1.0,
        )

        assert event.type == AGUIEventType.VALIDATION_COMPLETE
        assert event.data["passed"] is True
        assert event.data["score"] == 1.0

    def test_validation_complete_failed(self) -> None:
        """Test creating validation complete event (failed)."""
        event = create_validation_event(
            workflow_id="wf-123",
            event_type=AGUIEventType.VALIDATION_COMPLETE,
            document_id="doc-456",
            passed=False,
            score=0.5,
            issues=["Missing column: Ingredients"],
            recommendations=["Add the Ingredients column"],
        )

        assert event.data["passed"] is False
        assert len(event.data["issues"]) == 1
        assert len(event.data["recommendations"]) == 1
