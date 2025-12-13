"""
Request and response models for the FastAPI Gateway.

This module defines Pydantic models for API request validation
and response serialization.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Status of a workflow."""

    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    ESCALATED = "escalated"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# Workflow Request Models
# =============================================================================


class WorkflowCreateRequest(BaseModel):
    """Request to create a new workflow."""

    instructions: str = Field(
        ...,
        min_length=1,
        description="Instructions for the information request",
    )
    faq: str = Field(
        default="",
        description="FAQ content for answering clarification questions",
    )
    escalation_rules: str = Field(
        default="",
        description="Rules for escalation when target doesn't respond",
    )
    validation_criteria: str = Field(
        default="",
        description="Criteria for validating received documents",
    )
    workflow_id: str | None = Field(
        default=None,
        description="Optional custom workflow ID. If not provided, one is generated.",
    )


class WorkflowApproveRequest(BaseModel):
    """Request to approve a workflow plan."""

    approved: bool = Field(
        ...,
        description="Whether the plan is approved",
    )
    feedback: str | None = Field(
        default=None,
        description="Optional feedback for plan iteration",
    )


class WorkflowCancelRequest(BaseModel):
    """Request to cancel a workflow."""

    reason: str | None = Field(
        default=None,
        description="Optional reason for cancellation",
    )


# =============================================================================
# Workflow Response Models
# =============================================================================


class PlanStep(BaseModel):
    """A single step in an execution plan."""

    step_number: int = Field(..., description="Step number (1-indexed)")
    action: str = Field(..., description="Action identifier")
    agent: str = Field(..., description="Agent that will execute this step")
    skill: str = Field(..., description="Skill to invoke")
    description: str = Field(..., description="Human-readable description")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the skill",
    )
    status: str = Field(default="pending", description="Step status")


class WorkflowResponse(BaseModel):
    """Response for workflow operations."""

    workflow_id: str = Field(..., description="Workflow identifier")
    status: WorkflowStatus = Field(..., description="Current workflow status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    plan: list[PlanStep] | None = Field(
        default=None,
        description="Execution plan (if available)",
    )
    current_step: int | None = Field(
        default=None,
        description="Current step number (if executing)",
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="Workflow result (if completed)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (if failed)",
    )


class WorkflowListResponse(BaseModel):
    """Response for listing workflows."""

    workflows: list[WorkflowResponse] = Field(
        default_factory=list,
        description="List of workflows",
    )
    total: int = Field(..., description="Total number of workflows")
    offset: int = Field(default=0, description="Offset for pagination")
    limit: int = Field(default=10, description="Limit for pagination")


class WorkflowAuditEntry(BaseModel):
    """An entry in the workflow audit log."""

    timestamp: datetime = Field(..., description="Entry timestamp")
    event_type: str = Field(..., description="Event type")
    description: str = Field(..., description="Event description")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


class WorkflowAuditResponse(BaseModel):
    """Response for workflow audit log."""

    workflow_id: str = Field(..., description="Workflow identifier")
    entries: list[WorkflowAuditEntry] = Field(
        default_factory=list,
        description="Audit log entries",
    )
    total: int = Field(..., description="Total number of entries")


# =============================================================================
# Email Models
# =============================================================================


class EmailThread(BaseModel):
    """Email thread information."""

    thread_id: str = Field(..., description="Thread identifier")
    subject: str = Field(..., description="Email subject")
    participants: list[str] = Field(
        default_factory=list,
        description="Email addresses of participants",
    )
    message_count: int = Field(..., description="Number of messages in thread")
    last_message_at: datetime = Field(..., description="Last message timestamp")


class EmailMessage(BaseModel):
    """Email message information."""

    message_id: str = Field(..., description="Message identifier")
    thread_id: str = Field(..., description="Thread identifier")
    from_address: str = Field(..., description="Sender email address")
    to_address: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")
    sent_at: datetime = Field(..., description="Send timestamp")
    is_reply: bool = Field(default=False, description="Whether this is a reply")
    attachments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Attachment metadata",
    )


class WorkflowEmailsResponse(BaseModel):
    """Response for workflow email history."""

    workflow_id: str = Field(..., description="Workflow identifier")
    threads: list[EmailThread] = Field(
        default_factory=list,
        description="Email threads",
    )
    messages: list[EmailMessage] = Field(
        default_factory=list,
        description="All email messages",
    )


# =============================================================================
# Webhook Models
# =============================================================================


class EmailWebhookPayload(BaseModel):
    """Payload for email webhook notifications."""

    event_type: str = Field(
        ...,
        description="Event type (e.g., 'email.received', 'email.sent')",
    )
    message_id: str = Field(..., description="Message identifier")
    thread_id: str = Field(..., description="Thread identifier")
    inbox: str = Field(..., description="Inbox email address")
    from_address: str = Field(..., description="Sender email address")
    to_address: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body_preview: str = Field(
        default="",
        description="Preview of email body",
    )
    has_attachments: bool = Field(
        default=False,
        description="Whether email has attachments",
    )
    received_at: datetime = Field(..., description="Receive timestamp")


class AgentWebhookPayload(BaseModel):
    """Payload for agent webhook notifications."""

    event_type: str = Field(
        ...,
        description="Event type (e.g., 'task.completed', 'task.failed')",
    )
    agent_id: str = Field(..., description="Agent identifier")
    task_id: str = Field(..., description="Task identifier")
    workflow_id: str | None = Field(
        default=None,
        description="Associated workflow identifier",
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="Task result (if completed)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (if failed)",
    )
    timestamp: datetime = Field(..., description="Event timestamp")


class WebhookResponse(BaseModel):
    """Response for webhook processing."""

    success: bool = Field(..., description="Whether the webhook was processed")
    message: str = Field(default="OK", description="Response message")


# =============================================================================
# Health Models
# =============================================================================


class ComponentHealth(BaseModel):
    """Health status of a component."""

    status: str = Field(..., description="Component status (ok, degraded, down)")
    latency_ms: float | None = Field(
        default=None,
        description="Response latency in milliseconds",
    )
    error: str | None = Field(
        default=None,
        description="Error message (if any)",
    )


class HealthResponse(BaseModel):
    """Response for health check."""

    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(..., description="Health check timestamp")
    components: dict[str, ComponentHealth] = Field(
        default_factory=dict,
        description="Health status of individual components",
    )


# =============================================================================
# SSE Event Models
# =============================================================================


class SSEEventType(str, Enum):
    """Types of SSE events for AG-UI streaming."""

    # Lifecycle events
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"

    # Content events
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"

    # Tool events
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
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_RECEIVED = "EMAIL_RECEIVED"
    CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_COMPLETE = "VALIDATION_COMPLETE"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"


class SSEEvent(BaseModel):
    """Server-Sent Event for AG-UI streaming."""

    event_type: SSEEventType = Field(..., description="Event type")
    workflow_id: str = Field(..., description="Workflow identifier")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Event data",
    )

    def to_sse_format(self) -> str:
        """Convert to SSE wire format."""
        import json

        event_data = {
            "type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp.isoformat(),
            **self.data,
        }
        return f"event: {self.event_type.value}\ndata: {json.dumps(event_data)}\n\n"


# =============================================================================
# File Upload Models
# =============================================================================


class FileUploadResponse(BaseModel):
    """Response for file upload."""

    file_id: str = Field(..., description="Uploaded file identifier")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="File content type")
    size: int = Field(..., description="File size in bytes")
    uploaded_at: datetime = Field(..., description="Upload timestamp")


class WorkflowFilesResponse(BaseModel):
    """Response for listing workflow files."""

    workflow_id: str = Field(..., description="Workflow identifier")
    files: list[FileUploadResponse] = Field(
        default_factory=list,
        description="Uploaded files",
    )


# =============================================================================
# Error Models
# =============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )


class ErrorResponse(BaseModel):
    """Response for error cases."""

    error: ErrorDetail = Field(..., description="Error details")
    request_id: str | None = Field(
        default=None,
        description="Request identifier for debugging",
    )


logger.info("Gateway models module initialized")
