"""
Request models for Info-Agent API.

This module defines Pydantic models for all API request payloads.
All fields use strict validation with no implicit defaults for required data.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CreateWorkflowRequest(BaseModel):
    """
    Request to create a new workflow.

    A workflow represents a complete information retrieval task,
    which involves sending emails, receiving responses, and
    potentially validating the collected information.
    """

    name: str = Field(
        ...,  # Required
        min_length=1,
        max_length=255,
        description="Human-readable name for the workflow",
        examples=["Q4 Financial Report Collection"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional detailed description of the workflow purpose",
        examples=["Collect Q4 2024 financial reports from all department heads"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Workflow name cannot be empty or whitespace only")
        return stripped


class UploadFilesRequest(BaseModel):
    """
    Metadata for file upload request.

    Files are uploaded via multipart form data, this model validates
    the accompanying metadata.
    """

    file_type: str = Field(
        ...,  # Required
        description="Type of file being uploaded",
        examples=["instructions", "faq", "escalation", "validation"],
    )

    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, v: str) -> str:
        """Validate file type is one of the allowed values."""
        allowed_types = {"instructions", "faq", "escalation", "validation", "attachment"}
        if v.lower() not in allowed_types:
            raise ValueError(
                f"Invalid file_type: {v}. Must be one of: {', '.join(sorted(allowed_types))}"
            )
        return v.lower()


class ApproveWorkflowRequest(BaseModel):
    """
    Request to approve or reject an execution plan.

    After the Supervisor Agent generates an execution plan, the user
    must approve it before execution begins.
    """

    approved: bool = Field(
        ...,  # Required
        description="Whether to approve (true) or reject (false) the plan",
    )
    feedback: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional feedback explaining the decision",
        examples=["Please add a follow-up reminder after 48 hours"],
    )

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, v: str | None) -> str | None:
        """Ensure feedback is meaningful if provided."""
        if v is not None:
            stripped = v.strip()
            if not stripped:
                return None
            return stripped
        return v


class EmailWebhookPayload(BaseModel):
    """
    Incoming email notification from Mock Email Server.

    This payload is sent by the Mock Email Server when a new email
    arrives, allowing the Supervisor Agent to process responses.
    """

    event: str = Field(
        ...,  # Required
        description="Event type",
        examples=["email.received"],
    )
    message_id: str = Field(
        ...,  # Required
        min_length=1,
        description="Unique identifier for the email message",
        examples=["msg-abc123"],
    )
    thread_id: str = Field(
        ...,  # Required
        min_length=1,
        description="Thread identifier for email conversation",
        examples=["thread-xyz789"],
    )
    from_address: str = Field(
        ...,  # Required
        description="Sender's email address",
        examples=["john.doe@example.com"],
    )
    to_address: str = Field(
        ...,  # Required
        description="Recipient's email address",
        examples=["system@info-agent.local"],
    )
    subject: str = Field(
        ...,  # Required
        description="Email subject line",
        examples=["Re: Information Request"],
    )
    body: str = Field(
        ...,  # Required
        description="Email body text",
        examples=["Please find the requested documents attached."],
    )
    attachments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of attachment metadata",
        examples=[[{"filename": "report.pdf", "size": 1024, "mime_type": "application/pdf"}]],
    )
    received_at: datetime = Field(
        ...,  # Required
        description="Timestamp when email was received",
    )

    @field_validator("event")
    @classmethod
    def validate_event(cls, v: str) -> str:
        """Validate event type."""
        allowed_events = {"email.received", "email.sent", "email.bounced"}
        if v not in allowed_events:
            raise ValueError(
                f"Invalid event type: {v}. Must be one of: {', '.join(sorted(allowed_events))}"
            )
        return v

    @field_validator("from_address", "to_address")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Basic email format validation."""
        if "@" not in v:
            raise ValueError(f"Invalid email address format: {v}")
        return v.lower()
