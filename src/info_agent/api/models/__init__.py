"""
Pydantic models for API requests and responses.

This module exports all request and response models used by the API layer.
"""

from info_agent.api.models.requests import (
    CreateWorkflowRequest,
    UploadFilesRequest,
    ApproveWorkflowRequest,
    EmailWebhookPayload,
)
from info_agent.api.models.responses import (
    WorkflowResponse,
    WorkflowStatusResponse,
    WorkflowListResponse,
    FileUploadResponse,
    HealthResponse,
    ErrorResponse,
    ComponentHealth,
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
    "ComponentHealth",
]
