"""
Workflow state definitions for Info-Agent.

This module defines the state schema used by the Supervisor Agent's
LangGraph workflow. The state is persisted via SQLite checkpointing.
"""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """
    Workflow execution status.

    Defines all possible states a workflow can be in during its lifecycle.
    """

    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditLogEntry(BaseModel):
    """
    A single entry in the workflow audit log.

    Tracks all significant actions and state changes.
    """

    timestamp: str = Field(
        ...,
        description="ISO format timestamp of the event",
    )
    action: str = Field(
        ...,
        description="Action type (e.g., parse_inputs, send_email)",
    )
    details: str = Field(
        ...,
        description="Human-readable description of the action",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional structured data about the action",
    )


class PlanStep(TypedDict):
    """
    A single step in the execution plan.
    """

    step: int
    action: str
    description: str
    status: str  # pending, in_progress, completed, failed


class EmailAttachment(TypedDict):
    """
    Email attachment metadata.
    """

    filename: str
    size: int
    mime_type: str
    content_path: str | None


class SupervisorState(TypedDict, total=False):
    """
    State managed by the Supervisor Agent LangGraph workflow.

    This TypedDict defines all the state fields that are persisted
    and passed between workflow nodes. Using total=False allows
    for optional fields that may not be set initially.

    State Categories:
    1. Workflow identification
    2. Input data
    3. Parsed requirements (from LLM)
    4. Execution state
    5. Communication tracking
    6. Results
    7. Audit and metadata
    8. Error handling
    """

    # ===================
    # Workflow Identification
    # ===================
    workflow_id: str
    workflow_name: str

    # ===================
    # Input Data
    # ===================
    instructions: str  # Raw instruction file content
    instructions_filename: str  # Original filename

    # ===================
    # Parsed Requirements (extracted by LLM)
    # ===================
    target_email: str
    target_name: str
    requested_info: str

    # ===================
    # Execution State
    # ===================
    status: str  # WorkflowStatus value
    plan: list[PlanStep]
    current_step: int
    plan_approved: bool
    plan_rejected: bool
    plan_cancelled: bool
    approval_feedback: str | None

    # ===================
    # Communication Tracking
    # ===================
    email_thread_id: str | None
    sent_email_id: str | None
    sent_email_subject: str | None
    sent_email_body: str | None

    # ===================
    # Results
    # ===================
    received_response: str | None
    received_response_subject: str | None
    received_attachments: list[EmailAttachment]

    # ===================
    # Audit and Metadata
    # ===================
    audit_log: list[dict[str, Any]]  # List of AuditLogEntry dicts
    created_at: str  # ISO format
    updated_at: str  # ISO format

    # ===================
    # Error Handling
    # ===================
    error: str | None
    error_step: str | None
    retry_count: int


def create_initial_state(
    workflow_id: str,
    workflow_name: str,
    instructions: str,
    instructions_filename: str,
) -> SupervisorState:
    """
    Create initial workflow state.

    Args:
        workflow_id: Unique workflow identifier.
        workflow_name: Human-readable workflow name.
        instructions: Raw instruction file content.
        instructions_filename: Original filename.

    Returns:
        Initial SupervisorState with default values.
    """
    now = datetime.utcnow().isoformat()

    return SupervisorState(
        # Workflow identification
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        # Input data
        instructions=instructions,
        instructions_filename=instructions_filename,
        # Parsed requirements - empty until parsed
        target_email="",
        target_name="",
        requested_info="",
        # Execution state
        status=WorkflowStatus.CREATED.value,
        plan=[],
        current_step=0,
        plan_approved=False,
        plan_rejected=False,
        plan_cancelled=False,
        approval_feedback=None,
        # Communication tracking
        email_thread_id=None,
        sent_email_id=None,
        sent_email_subject=None,
        sent_email_body=None,
        # Results
        received_response=None,
        received_response_subject=None,
        received_attachments=[],
        # Audit and metadata
        audit_log=[{
            "timestamp": now,
            "action": "workflow_created",
            "details": f"Workflow '{workflow_name}' created",
            "metadata": {"workflow_id": workflow_id},
        }],
        created_at=now,
        updated_at=now,
        # Error handling
        error=None,
        error_step=None,
        retry_count=0,
    )


def add_audit_entry(
    state: SupervisorState,
    action: str,
    details: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Create a new audit log with an added entry.

    This function returns a new list rather than mutating the existing one,
    following LangGraph's immutable state pattern.

    Args:
        state: Current workflow state.
        action: Action type identifier.
        details: Human-readable action description.
        metadata: Optional additional structured data.

    Returns:
        New audit log list with the entry appended.
    """
    new_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "details": details,
        "metadata": metadata,
    }

    return state.get("audit_log", []) + [new_entry]
