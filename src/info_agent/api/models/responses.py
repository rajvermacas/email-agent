"""
Response models for Info-Agent API.

This module defines Pydantic models for all API response payloads.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """
    Possible states of a workflow.

    State transitions:
    - CREATED -> PLANNING (when files uploaded and processing starts)
    - PLANNING -> AWAITING_APPROVAL (when plan is generated)
    - AWAITING_APPROVAL -> EXECUTING (when approved) or PLANNING (when rejected)
    - EXECUTING -> WAITING_FOR_RESPONSE (after email sent)
    - WAITING_FOR_RESPONSE -> COMPLETED (when response received) or FAILED (on error)
    - Any state -> CANCELLED (if cancelled by user)
    - Any state -> FAILED (on unrecoverable error)
    """

    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowResponse(BaseModel):
    """
    Full workflow details response.

    Returned when creating or fetching a single workflow.
    """

    id: str = Field(
        ...,
        description="Unique workflow identifier",
        examples=["wf-abc123"],
    )
    name: str = Field(
        ...,
        description="Human-readable workflow name",
        examples=["Q4 Financial Report Collection"],
    )
    description: str | None = Field(
        default=None,
        description="Detailed workflow description",
    )
    status: WorkflowStatus = Field(
        ...,
        description="Current workflow status",
        examples=[WorkflowStatus.CREATED],
    )
    created_at: datetime = Field(
        ...,
        description="When the workflow was created",
    )
    updated_at: datetime = Field(
        ...,
        description="When the workflow was last updated",
    )


class PlanStep(BaseModel):
    """
    A single step in the execution plan.
    """

    step: int = Field(
        ...,
        ge=1,
        description="Step number (1-indexed)",
    )
    action: str = Field(
        ...,
        description="Action type (e.g., send_email, wait_response)",
    )
    description: str = Field(
        ...,
        description="Human-readable description of the step",
    )
    status: str = Field(
        default="pending",
        description="Step status: pending, in_progress, completed, failed",
    )


class WorkflowStatusResponse(BaseModel):
    """
    Current workflow status with execution details.

    Provides detailed information about workflow progress.
    """

    id: str = Field(
        ...,
        description="Unique workflow identifier",
    )
    status: WorkflowStatus = Field(
        ...,
        description="Current workflow status",
    )
    current_step: int | None = Field(
        default=None,
        description="Current step number in the plan (1-indexed)",
    )
    plan: list[PlanStep] | None = Field(
        default=None,
        description="Execution plan with steps",
    )
    target_email: str | None = Field(
        default=None,
        description="Email address of the target recipient",
    )
    target_name: str | None = Field(
        default=None,
        description="Name of the target recipient",
    )
    requested_info: str | None = Field(
        default=None,
        description="Description of requested information",
    )
    email_thread_id: str | None = Field(
        default=None,
        description="Active email thread ID",
    )
    received_response: str | None = Field(
        default=None,
        description="Content of received email response",
    )
    error: str | None = Field(
        default=None,
        description="Error message if workflow failed",
    )
    updated_at: datetime = Field(
        ...,
        description="When the status was last updated",
    )


class WorkflowListResponse(BaseModel):
    """
    Response for listing workflows.
    """

    workflows: list[WorkflowResponse] = Field(
        ...,
        description="List of workflows",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of workflows",
    )


class UploadedFile(BaseModel):
    """
    Information about an uploaded file.
    """

    filename: str = Field(
        ...,
        description="Original filename",
    )
    file_type: str = Field(
        ...,
        description="Type of file (instructions, faq, etc.)",
    )
    size: int = Field(
        ...,
        ge=0,
        description="File size in bytes",
    )
    uploaded_at: datetime = Field(
        ...,
        description="When the file was uploaded",
    )


class FileUploadResponse(BaseModel):
    """
    Response after file upload.
    """

    message: str = Field(
        ...,
        description="Status message",
        examples=["File uploaded successfully"],
    )
    file: UploadedFile = Field(
        ...,
        description="Uploaded file information",
    )


class FileListResponse(BaseModel):
    """
    Response for listing workflow files.
    """

    workflow_id: str = Field(
        ...,
        description="Workflow identifier",
    )
    files: list[UploadedFile] = Field(
        ...,
        description="List of uploaded files",
    )


class ComponentHealth(BaseModel):
    """
    Health status of a single component.
    """

    status: str = Field(
        ...,
        description="Component status: healthy, degraded, unhealthy",
        examples=["healthy"],
    )
    message: str | None = Field(
        default=None,
        description="Optional status message",
    )
    latency_ms: float | None = Field(
        default=None,
        ge=0,
        description="Response latency in milliseconds",
    )


class HealthResponse(BaseModel):
    """
    System health check response.

    Provides status of all system components.
    """

    status: str = Field(
        ...,
        description="Overall system status: healthy, degraded, unhealthy",
        examples=["healthy"],
    )
    version: str = Field(
        ...,
        description="Application version",
        examples=["0.1.0"],
    )
    components: dict[str, ComponentHealth] = Field(
        ...,
        description="Health status of individual components",
        examples=[{
            "gateway": {"status": "healthy", "latency_ms": 1.5},
            "a2a_registry": {"status": "healthy", "latency_ms": 2.1},
            "mail_agent": {"status": "healthy", "latency_ms": 5.2},
            "email_server": {"status": "healthy", "latency_ms": 3.0},
        }],
    )
    timestamp: datetime = Field(
        ...,
        description="When the health check was performed",
    )


class ErrorDetail(BaseModel):
    """
    Detailed error information.
    """

    code: str = Field(
        ...,
        description="Error code",
        examples=["WORKFLOW_NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error context",
    )


class ErrorResponse(BaseModel):
    """
    Standard error response.

    Used for all API error responses.
    """

    error: ErrorDetail = Field(
        ...,
        description="Error details",
    )
