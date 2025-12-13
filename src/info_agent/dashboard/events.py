"""
AG-UI Event definitions for Info-Agent.

This module defines the event types and data structures for
AG-UI protocol events used in real-time dashboard updates.
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AGUIEventType(str, Enum):
    """AG-UI event types following the AG-UI protocol specification."""

    # Lifecycle events
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"

    # Text message events
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"

    # Tool call events
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"

    # State events
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"

    # Custom Info-Agent events
    PLAN_GENERATED = "PLAN_GENERATED"
    PLAN_APPROVED = "PLAN_APPROVED"
    PLAN_REJECTED = "PLAN_REJECTED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_RECEIVED = "EMAIL_RECEIVED"
    CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"
    CLARIFICATION_RESOLVED = "CLARIFICATION_RESOLVED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_COMPLETE = "VALIDATION_COMPLETE"
    TIMEOUT_WARNING = "TIMEOUT_WARNING"


class AGUIEvent(BaseModel):
    """
    AG-UI protocol event.

    This model represents a single event in the AG-UI event stream,
    following the AG-UI protocol specification for real-time updates.
    """

    type: AGUIEventType = Field(..., description="Event type")
    workflow_id: str = Field(..., description="Workflow identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC)",
    )
    run_id: str | None = Field(
        default=None,
        description="Run identifier (for tracking execution sessions)",
    )
    message_id: str | None = Field(
        default=None,
        description="Message identifier (for text messages)",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="Tool call identifier",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data payload",
    )

    def to_sse(self) -> str:
        """
        Convert event to Server-Sent Events format.

        Returns:
            SSE-formatted string ready for transmission.
        """
        event_data = {
            "type": self.type.value,
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.run_id:
            event_data["run_id"] = self.run_id
        if self.message_id:
            event_data["message_id"] = self.message_id
        if self.tool_call_id:
            event_data["tool_call_id"] = self.tool_call_id

        event_data.update(self.data)

        return f"event: {self.type.value}\ndata: {json.dumps(event_data)}\n\n"

    def to_json(self) -> str:
        """
        Convert event to JSON string.

        Returns:
            JSON-formatted string.
        """
        return json.dumps(
            {
                "type": self.type.value,
                "workflow_id": self.workflow_id,
                "timestamp": self.timestamp.isoformat(),
                "run_id": self.run_id,
                "message_id": self.message_id,
                "tool_call_id": self.tool_call_id,
                **self.data,
            }
        )


# =============================================================================
# Event Factory Functions
# =============================================================================


def create_run_started_event(
    workflow_id: str,
    run_id: str | None = None,
    status: str = "executing",
    metadata: dict[str, Any] | None = None,
) -> AGUIEvent:
    """
    Create a RUN_STARTED event.

    Args:
        workflow_id: Workflow identifier.
        run_id: Optional run identifier.
        status: Initial status.
        metadata: Optional additional metadata.

    Returns:
        AGUIEvent for run started.
    """
    logger.debug("Creating RUN_STARTED event for workflow: %s", workflow_id)

    data = {"status": status}
    if metadata:
        data["metadata"] = metadata

    return AGUIEvent(
        type=AGUIEventType.RUN_STARTED,
        workflow_id=workflow_id,
        run_id=run_id,
        data=data,
    )


def create_run_finished_event(
    workflow_id: str,
    run_id: str | None = None,
    status: str = "completed",
    result: dict[str, Any] | None = None,
) -> AGUIEvent:
    """
    Create a RUN_FINISHED event.

    Args:
        workflow_id: Workflow identifier.
        run_id: Optional run identifier.
        status: Final status.
        result: Optional result data.

    Returns:
        AGUIEvent for run finished.
    """
    logger.debug("Creating RUN_FINISHED event for workflow: %s", workflow_id)

    data = {"status": status}
    if result:
        data["result"] = result

    return AGUIEvent(
        type=AGUIEventType.RUN_FINISHED,
        workflow_id=workflow_id,
        run_id=run_id,
        data=data,
    )


def create_run_error_event(
    workflow_id: str,
    error: str,
    run_id: str | None = None,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> AGUIEvent:
    """
    Create a RUN_ERROR event.

    Args:
        workflow_id: Workflow identifier.
        error: Error message.
        run_id: Optional run identifier.
        error_code: Optional error code.
        details: Optional error details.

    Returns:
        AGUIEvent for run error.
    """
    logger.debug("Creating RUN_ERROR event for workflow: %s", workflow_id)

    data = {"error": error}
    if error_code:
        data["error_code"] = error_code
    if details:
        data["details"] = details

    return AGUIEvent(
        type=AGUIEventType.RUN_ERROR,
        workflow_id=workflow_id,
        run_id=run_id,
        data=data,
    )


def create_text_message_event(
    workflow_id: str,
    message_id: str,
    content: str,
    event_type: AGUIEventType = AGUIEventType.TEXT_MESSAGE_CONTENT,
    role: str = "assistant",
) -> AGUIEvent:
    """
    Create a text message event.

    Args:
        workflow_id: Workflow identifier.
        message_id: Message identifier.
        content: Message content.
        event_type: Type of text message event.
        role: Message role (assistant, user, system).

    Returns:
        AGUIEvent for text message.
    """
    logger.debug(
        "Creating %s event for workflow: %s",
        event_type.value,
        workflow_id,
    )

    return AGUIEvent(
        type=event_type,
        workflow_id=workflow_id,
        message_id=message_id,
        data={
            "content": content,
            "role": role,
        },
    )


def create_tool_call_event(
    workflow_id: str,
    tool_call_id: str,
    tool_name: str,
    event_type: AGUIEventType = AGUIEventType.TOOL_CALL_START,
    arguments: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> AGUIEvent:
    """
    Create a tool call event.

    Args:
        workflow_id: Workflow identifier.
        tool_call_id: Tool call identifier.
        tool_name: Name of the tool being called.
        event_type: Type of tool call event.
        arguments: Tool arguments (for TOOL_CALL_ARGS).
        result: Tool result (for TOOL_CALL_END).

    Returns:
        AGUIEvent for tool call.
    """
    logger.debug(
        "Creating %s event for workflow: %s, tool: %s",
        event_type.value,
        workflow_id,
        tool_name,
    )

    data = {"tool_name": tool_name}
    if arguments:
        data["arguments"] = arguments
    if result:
        data["result"] = result

    return AGUIEvent(
        type=event_type,
        workflow_id=workflow_id,
        tool_call_id=tool_call_id,
        data=data,
    )


def create_state_delta_event(
    workflow_id: str,
    delta: dict[str, Any],
    path: str | None = None,
) -> AGUIEvent:
    """
    Create a STATE_DELTA event.

    Args:
        workflow_id: Workflow identifier.
        delta: State changes.
        path: Optional path to the changed state.

    Returns:
        AGUIEvent for state delta.
    """
    logger.debug("Creating STATE_DELTA event for workflow: %s", workflow_id)

    data = {"delta": delta}
    if path:
        data["path"] = path

    return AGUIEvent(
        type=AGUIEventType.STATE_DELTA,
        workflow_id=workflow_id,
        data=data,
    )


def create_plan_event(
    workflow_id: str,
    event_type: AGUIEventType,
    plan: list[dict[str, Any]] | None = None,
    feedback: str | None = None,
) -> AGUIEvent:
    """
    Create a plan-related event.

    Args:
        workflow_id: Workflow identifier.
        event_type: Type of plan event.
        plan: Execution plan (for PLAN_GENERATED).
        feedback: Feedback (for PLAN_REJECTED).

    Returns:
        AGUIEvent for plan.
    """
    logger.debug(
        "Creating %s event for workflow: %s",
        event_type.value,
        workflow_id,
    )

    data: dict[str, Any] = {}
    if plan:
        data["plan"] = plan
    if feedback:
        data["feedback"] = feedback

    return AGUIEvent(
        type=event_type,
        workflow_id=workflow_id,
        data=data,
    )


def create_step_event(
    workflow_id: str,
    event_type: AGUIEventType,
    step_number: int,
    action: str,
    agent: str,
    skill: str,
    description: str = "",
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> AGUIEvent:
    """
    Create a step-related event.

    Args:
        workflow_id: Workflow identifier.
        event_type: Type of step event.
        step_number: Step number.
        action: Action being performed.
        agent: Agent executing the step.
        skill: Skill being invoked.
        description: Step description.
        result: Step result (for STEP_COMPLETED).
        error: Error message (for STEP_FAILED).

    Returns:
        AGUIEvent for step.
    """
    logger.debug(
        "Creating %s event for workflow: %s, step: %d",
        event_type.value,
        workflow_id,
        step_number,
    )

    data = {
        "step_number": step_number,
        "action": action,
        "agent": agent,
        "skill": skill,
        "description": description,
    }
    if result:
        data["result"] = result
    if error:
        data["error"] = error

    return AGUIEvent(
        type=event_type,
        workflow_id=workflow_id,
        data=data,
    )


def create_email_event(
    workflow_id: str,
    event_type: AGUIEventType,
    message_id: str,
    thread_id: str,
    from_address: str,
    to_address: str,
    subject: str,
    body_preview: str = "",
    has_attachments: bool = False,
) -> AGUIEvent:
    """
    Create an email-related event.

    Args:
        workflow_id: Workflow identifier.
        event_type: Type of email event (EMAIL_SENT or EMAIL_RECEIVED).
        message_id: Email message ID.
        thread_id: Email thread ID.
        from_address: Sender address.
        to_address: Recipient address.
        subject: Email subject.
        body_preview: Preview of email body.
        has_attachments: Whether email has attachments.

    Returns:
        AGUIEvent for email.
    """
    logger.debug(
        "Creating %s event for workflow: %s",
        event_type.value,
        workflow_id,
    )

    return AGUIEvent(
        type=event_type,
        workflow_id=workflow_id,
        data={
            "message_id": message_id,
            "thread_id": thread_id,
            "from_address": from_address,
            "to_address": to_address,
            "subject": subject,
            "body_preview": body_preview,
            "has_attachments": has_attachments,
        },
    )


def create_validation_event(
    workflow_id: str,
    event_type: AGUIEventType,
    document_id: str | None = None,
    document_name: str | None = None,
    passed: bool | None = None,
    score: float | None = None,
    issues: list[str] | None = None,
    recommendations: list[str] | None = None,
) -> AGUIEvent:
    """
    Create a validation-related event.

    Args:
        workflow_id: Workflow identifier.
        event_type: Type of validation event.
        document_id: Document identifier.
        document_name: Document name.
        passed: Whether validation passed.
        score: Validation score (0.0 to 1.0).
        issues: List of validation issues.
        recommendations: List of recommendations.

    Returns:
        AGUIEvent for validation.
    """
    logger.debug(
        "Creating %s event for workflow: %s",
        event_type.value,
        workflow_id,
    )

    data: dict[str, Any] = {}
    if document_id:
        data["document_id"] = document_id
    if document_name:
        data["document_name"] = document_name
    if passed is not None:
        data["passed"] = passed
    if score is not None:
        data["score"] = score
    if issues:
        data["issues"] = issues
    if recommendations:
        data["recommendations"] = recommendations

    return AGUIEvent(
        type=event_type,
        workflow_id=workflow_id,
        data=data,
    )


logger.info("AG-UI events module initialized")
