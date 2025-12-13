"""
Workflow state definitions for the Info-Agent system.

This module defines the state schema used by LangGraph to manage
the workflow execution state.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    ESCALATED = "escalated"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailThread(BaseModel):
    """Email thread tracking."""

    id: str = Field(..., description="Thread ID")
    subject: str = Field(..., description="Email subject")
    target_email: str = Field(..., description="Target recipient email")
    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="Messages in thread"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Thread creation time"
    )
    last_activity_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last activity time"
    )


class ClarificationEntry(BaseModel):
    """Clarification question and response tracking."""

    id: str = Field(..., description="Clarification ID")
    question: str = Field(..., description="Question asked")
    source_email: str = Field(..., description="Email that asked the question")
    faq_match: bool = Field(
        default=False, description="Whether question matched FAQ"
    )
    answer: str | None = Field(default=None, description="Answer provided")
    answered_by: str | None = Field(
        default=None, description="Who provided the answer"
    )
    escalated: bool = Field(default=False, description="Whether escalated")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When question was asked"
    )
    answered_at: datetime | None = Field(
        default=None, description="When answer was provided"
    )


class ReceivedDocument(BaseModel):
    """Document received from target person."""

    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME content type")
    size_bytes: int = Field(..., description="File size in bytes")
    storage_path: str = Field(..., description="Path to stored file")
    received_at: datetime = Field(
        default_factory=datetime.utcnow, description="When document was received"
    )
    from_email: str = Field(..., description="Who sent the document")
    email_id: str = Field(..., description="Email message ID")


class PlanStep(BaseModel):
    """Execution plan step."""

    step_number: int = Field(..., description="Step number in sequence")
    action: str = Field(..., description="Action to perform")
    agent: str = Field(..., description="Agent to use")
    skill: str = Field(..., description="Skill to invoke")
    description: str = Field(..., description="Human-readable description")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the action"
    )
    status: str = Field(default="pending", description="Step status")
    result: dict[str, Any] | None = Field(default=None, description="Step result")
    started_at: datetime | None = Field(default=None, description="When step started")
    completed_at: datetime | None = Field(
        default=None, description="When step completed"
    )


class AuditEntry(BaseModel):
    """Audit log entry."""

    id: str = Field(..., description="Audit entry ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp"
    )
    event_type: str = Field(..., description="Type of event")
    actor: str = Field(..., description="Who/what triggered the event")
    description: str = Field(..., description="Event description")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional details"
    )


class SupervisorState(TypedDict, total=False):
    """
    Main workflow state for the Supervisor Agent.

    This TypedDict defines all state that flows through the LangGraph
    workflow. All fields are optional (total=False) to allow partial
    state updates.
    """

    # Workflow identity
    workflow_id: str

    # Input files content
    instructions: str
    faq: str
    escalation_rules: str
    validation_criteria: str

    # Parsed requirements
    target_email: str
    target_name: str
    requested_info: str
    timeout_hours: int
    retry_count: int
    max_retries: int

    # Escalation contacts
    escalation_contact: str
    clarification_contact: str

    # Execution state
    status: WorkflowStatus
    plan: list[dict[str, Any]]
    current_step: int
    plan_approved: bool
    plan_rejection_reason: str | None

    # Available agents (from registry)
    available_agents: list[dict[str, Any]]

    # Communication tracking
    email_threads: list[dict[str, Any]]
    clarification_history: list[dict[str, Any]]

    # Response tracking
    waiting_since: str | None
    response_received: bool
    response_type: str | None

    # Results
    received_documents: list[dict[str, Any]]
    validation_result: dict[str, Any] | None
    final_report: dict[str, Any] | None

    # Audit
    audit_log: list[dict[str, Any]]
    created_at: str
    updated_at: str

    # Error tracking
    error: str | None
    error_details: dict[str, Any] | None


def create_initial_state(
    workflow_id: str,
    instructions: str,
    faq: str,
    escalation_rules: str,
    validation_criteria: str,
) -> SupervisorState:
    """
    Create initial workflow state.

    Args:
        workflow_id: Unique workflow identifier.
        instructions: Raw instructions file content.
        faq: Raw FAQ file content.
        escalation_rules: Raw escalation rules file content.
        validation_criteria: Raw validation criteria file content.

    Returns:
        Initial SupervisorState with all fields set to defaults.
    """
    logger.info("Creating initial workflow state for workflow_id=%s", workflow_id)

    now = datetime.utcnow().isoformat()

    state: SupervisorState = {
        # Workflow identity
        "workflow_id": workflow_id,
        # Input files
        "instructions": instructions,
        "faq": faq,
        "escalation_rules": escalation_rules,
        "validation_criteria": validation_criteria,
        # Parsed requirements (to be filled by parse_inputs)
        "target_email": "",
        "target_name": "",
        "requested_info": "",
        "timeout_hours": 48,
        "retry_count": 0,
        "max_retries": 3,
        # Escalation contacts
        "escalation_contact": "",
        "clarification_contact": "",
        # Execution state
        "status": WorkflowStatus.PLANNING,
        "plan": [],
        "current_step": 0,
        "plan_approved": False,
        "plan_rejection_reason": None,
        # Available agents
        "available_agents": [],
        # Communication
        "email_threads": [],
        "clarification_history": [],
        # Response tracking
        "waiting_since": None,
        "response_received": False,
        "response_type": None,
        # Results
        "received_documents": [],
        "validation_result": None,
        "final_report": None,
        # Audit
        "audit_log": [
            {
                "id": f"{workflow_id}-init",
                "timestamp": now,
                "event_type": "workflow_created",
                "actor": "system",
                "description": "Workflow initialized",
                "details": {},
            }
        ],
        "created_at": now,
        "updated_at": now,
        # Errors
        "error": None,
        "error_details": None,
    }

    logger.info("Initial state created with status=%s", state["status"])

    return state


def add_audit_entry(
    state: SupervisorState,
    event_type: str,
    actor: str,
    description: str,
    details: dict[str, Any] | None = None,
) -> SupervisorState:
    """
    Add an audit log entry to the state.

    Args:
        state: Current workflow state.
        event_type: Type of event being logged.
        actor: Who/what triggered the event.
        description: Human-readable description.
        details: Additional event details.

    Returns:
        Updated state with new audit entry.
    """
    import uuid

    now = datetime.utcnow().isoformat()

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": now,
        "event_type": event_type,
        "actor": actor,
        "description": description,
        "details": details or {},
    }

    audit_log = list(state.get("audit_log", []))
    audit_log.append(entry)

    logger.debug(
        "Added audit entry: event_type=%s, actor=%s, description=%s",
        event_type,
        actor,
        description,
    )

    return {**state, "audit_log": audit_log, "updated_at": now}


def update_status(
    state: SupervisorState,
    new_status: WorkflowStatus,
    reason: str | None = None,
) -> SupervisorState:
    """
    Update workflow status with audit logging.

    Args:
        state: Current workflow state.
        new_status: New status to set.
        reason: Optional reason for status change.

    Returns:
        Updated state with new status.
    """
    old_status = state.get("status", WorkflowStatus.PLANNING)

    logger.info(
        "Status change: %s -> %s (reason=%s)",
        old_status,
        new_status,
        reason,
    )

    updated = add_audit_entry(
        state,
        event_type="status_change",
        actor="supervisor",
        description=f"Status changed from {old_status} to {new_status}",
        details={"old_status": str(old_status), "new_status": str(new_status), "reason": reason},
    )

    return {**updated, "status": new_status}
