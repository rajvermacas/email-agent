"""
API layer for Info-Agent FastAPI Gateway.

This package provides:
- Request/response models for API validation
- Route handlers for workflow management, webhooks, and health checks
"""

from info_agent.api.models import (
    CreateWorkflowRequest,
    UploadFilesRequest,
    ApproveWorkflowRequest,
    EmailWebhookPayload,
    WorkflowResponse,
    WorkflowStatusResponse,
    WorkflowListResponse,
    FileUploadResponse,
    HealthResponse,
    ErrorResponse,
)

__all__ = [
    # Request models
    "CreateWorkflowRequest",
    "UploadFilesRequest",
    "ApproveWorkflowRequest",
    "EmailWebhookPayload",
    # Response models
    "WorkflowResponse",
    "WorkflowStatusResponse",
    "WorkflowListResponse",
    "FileUploadResponse",
    "HealthResponse",
    "ErrorResponse",
]
