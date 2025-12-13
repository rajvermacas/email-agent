"""
Pydantic models for email data structures.

This module defines all data models used in the email module:
- StoredEmail: Complete email data as stored in the database
- CreateEmailRequest: Request payload for creating/simulating incoming emails
- EmailReplyRequest: Request payload for replying to emails
- WebhookPayload: Payload sent to webhook endpoints on email events

All models use strict validation with no fallback defaults.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EmailAttachment(BaseModel):
    """
    Email attachment metadata.

    Attributes:
        filename: Name of the attached file.
        content_type: MIME type of the attachment.
        size: Size of the attachment in bytes.
        content: Base64-encoded content of the attachment.
    """

    filename: str = Field(..., description="Filename of the attachment", min_length=1)
    content_type: str = Field(..., description="MIME type of the attachment", min_length=1)
    size: int = Field(..., description="Size in bytes", ge=0)
    content: str = Field(..., description="Base64-encoded content", min_length=1)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename is not empty."""
        if not v.strip():
            raise ValueError("Filename cannot be empty or whitespace")
        return v.strip()

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate content_type is not empty."""
        if not v.strip():
            raise ValueError("Content type cannot be empty or whitespace")
        return v.strip()


class StoredEmail(BaseModel):
    """
    Complete email data as stored in the database.

    Attributes:
        id: Unique message ID.
        inbox: Email address of the inbox (recipient).
        thread_id: Thread identifier for grouping related emails.
        from_address: Sender email address.
        to_address: Recipient email address.
        subject: Email subject line.
        body_text: Plain text body of the email.
        attachments: List of email attachments.
        received_at: Timestamp when email was received.
        read: Whether the email has been marked as read.
    """

    id: str = Field(..., description="Unique message ID", min_length=1)
    inbox: str = Field(..., description="Inbox email address", min_length=1)
    thread_id: str | None = Field(None, description="Thread ID for grouping emails")
    from_address: str = Field(..., description="Sender email address", min_length=1)
    to_address: str = Field(..., description="Recipient email address", min_length=1)
    subject: str = Field(..., description="Email subject", min_length=1)
    body_text: str = Field(..., description="Plain text email body", min_length=1)
    attachments: list[EmailAttachment] = Field(
        default_factory=list, description="List of attachments"
    )
    received_at: datetime = Field(..., description="Timestamp when email was received")
    read: bool = Field(default=False, description="Whether email has been read")

    @field_validator("id", "inbox", "from_address", "to_address", "subject", "body_text")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    @field_validator("inbox", "from_address", "to_address")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        """Basic email address validation."""
        v = v.strip()
        if "@" not in v:
            raise ValueError(f"Invalid email address: {v}")
        local, domain = v.rsplit("@", 1)
        if not local or not domain:
            raise ValueError(f"Invalid email address: {v}")
        if "." not in domain:
            raise ValueError(f"Invalid email domain: {domain}")
        return v

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "id": "msg-123456",
                "inbox": "user@example.com",
                "thread_id": "thread-abc",
                "from_address": "sender@example.com",
                "to_address": "user@example.com",
                "subject": "Test Email",
                "body_text": "This is a test email.",
                "attachments": [],
                "received_at": "2025-12-13T10:30:00Z",
                "read": False,
            }
        }


class CreateEmailRequest(BaseModel):
    """
    Request payload for creating/simulating incoming emails.

    Attributes:
        from_address: Sender email address.
        to_address: Recipient email address.
        subject: Email subject line.
        body_text: Plain text body of the email.
        thread_id: Optional thread ID for grouping.
        attachments: Optional list of attachments.
    """

    from_address: str = Field(..., description="Sender email address", min_length=1)
    to_address: str = Field(..., description="Recipient email address", min_length=1)
    subject: str = Field(..., description="Email subject", min_length=1)
    body_text: str = Field(..., description="Plain text email body", min_length=1)
    thread_id: str | None = Field(None, description="Optional thread ID")
    attachments: list[EmailAttachment] = Field(
        default_factory=list, description="Optional attachments"
    )

    @field_validator("from_address", "to_address", "subject", "body_text")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    @field_validator("from_address", "to_address")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        """Basic email address validation."""
        v = v.strip()
        if "@" not in v:
            raise ValueError(f"Invalid email address: {v}")
        local, domain = v.rsplit("@", 1)
        if not local or not domain:
            raise ValueError(f"Invalid email address: {v}")
        if "." not in domain:
            raise ValueError(f"Invalid email domain: {domain}")
        return v

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "from_address": "sender@example.com",
                "to_address": "user@example.com",
                "subject": "Test Email",
                "body_text": "This is a test email.",
                "thread_id": "thread-abc",
                "attachments": [],
            }
        }


class EmailReplyRequest(BaseModel):
    """
    Request payload for replying to emails.

    Attributes:
        body_text: Plain text body of the reply.
        attachments: Optional list of attachments.
    """

    body_text: str = Field(..., description="Plain text reply body", min_length=1)
    attachments: list[EmailAttachment] = Field(
        default_factory=list, description="Optional attachments"
    )

    @field_validator("body_text")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate body_text is not empty or whitespace."""
        if not v.strip():
            raise ValueError("Reply body cannot be empty or whitespace")
        return v.strip()

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {"body_text": "Thank you for your email.", "attachments": []}
        }


class WebhookPayload(BaseModel):
    """
    Payload sent to webhook endpoints on email events.

    Attributes:
        event: Type of event (e.g., "email.received").
        message_id: Unique message ID.
        thread_id: Thread identifier.
        from_address: Sender email address.
        to_address: Recipient email address.
        subject: Email subject line.
        body: Plain text body of the email.
        attachments: List of attachment metadata.
        received_at: Timestamp when email was received.
    """

    event: str = Field(..., description="Event type", min_length=1)
    message_id: str = Field(..., description="Unique message ID", min_length=1)
    thread_id: str | None = Field(None, description="Thread ID")
    from_address: str = Field(..., description="Sender email address", min_length=1)
    to_address: str = Field(..., description="Recipient email address", min_length=1)
    subject: str = Field(..., description="Email subject", min_length=1)
    body: str = Field(..., description="Email body", min_length=1)
    attachments: list[dict[str, Any]] = Field(
        default_factory=list, description="Attachment metadata"
    )
    received_at: str = Field(..., description="ISO format timestamp", min_length=1)

    @field_validator("event", "message_id", "from_address", "to_address", "subject", "body")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "event": "email.received",
                "message_id": "msg-123456",
                "thread_id": "thread-abc",
                "from_address": "sender@example.com",
                "to_address": "user@example.com",
                "subject": "Test Email",
                "body": "This is a test email.",
                "attachments": [],
                "received_at": "2025-12-13T10:30:00Z",
            }
        }
