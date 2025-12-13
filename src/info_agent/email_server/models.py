"""
Email models and data structures.

Defines the core data models for emails in the mock email server.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from info_agent.utils.helpers import generate_uuid, get_current_timestamp


class EmailStatus(str, Enum):
    """Status of an email in the system."""

    RECEIVED = "received"
    SENT = "sent"
    PENDING = "pending"
    FAILED = "failed"
    DELIVERED = "delivered"
    READ = "read"


class EmailAddress(BaseModel):
    """
    Email address with optional display name.

    Attributes:
        address: The email address.
        name: Optional display name for the address.
    """

    address: EmailStr
    name: str | None = None

    def __str__(self) -> str:
        """Return formatted email address string."""
        if self.name:
            return f"{self.name} <{self.address}>"
        return self.address

    @classmethod
    def from_string(cls, email_str: str) -> "EmailAddress":
        """
        Parse email address from string format.

        Supports formats:
        - simple@email.com
        - Name <simple@email.com>

        Args:
            email_str: Email string to parse.

        Returns:
            EmailAddress instance.

        Raises:
            ValueError: If email string cannot be parsed.
        """
        email_str = email_str.strip()

        if "<" in email_str and ">" in email_str:
            # Format: Name <email@domain.com>
            name_part = email_str.split("<")[0].strip()
            address_part = email_str.split("<")[1].split(">")[0].strip()
            return cls(address=address_part, name=name_part if name_part else None)

        # Simple format: email@domain.com
        return cls(address=email_str, name=None)


class Attachment(BaseModel):
    """
    Email attachment.

    Attributes:
        filename: Name of the attached file.
        content_type: MIME type of the attachment.
        content: Base64-encoded content of the attachment.
        size: Size of the attachment in bytes.
    """

    filename: str
    content_type: str = "application/octet-stream"
    content: str  # Base64 encoded
    size: int = 0


class Email(BaseModel):
    """
    Email message model.

    Represents a complete email message with all metadata.

    Attributes:
        id: Unique identifier for the email.
        from_address: Sender email address.
        to_addresses: List of recipient addresses.
        cc_addresses: List of CC addresses.
        bcc_addresses: List of BCC addresses.
        subject: Email subject line.
        body_text: Plain text body.
        body_html: HTML body (optional).
        attachments: List of attachments.
        headers: Additional email headers.
        status: Current status of the email.
        created_at: Timestamp when email was created.
        updated_at: Timestamp of last update.
        read_at: Timestamp when email was read.
        message_id: RFC 2822 Message-ID header.
        in_reply_to: Message-ID of email being replied to.
        references: List of related message IDs.
        thread_id: Thread identifier for grouping related emails.
        mailbox: Mailbox the email belongs to (inbox, sent, etc.).
        metadata: Additional metadata for the email.
    """

    id: str = Field(default_factory=generate_uuid)
    from_address: EmailAddress
    to_addresses: list[EmailAddress] = Field(default_factory=list)
    cc_addresses: list[EmailAddress] = Field(default_factory=list)
    bcc_addresses: list[EmailAddress] = Field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    status: EmailStatus = EmailStatus.RECEIVED
    created_at: str = Field(default_factory=get_current_timestamp)
    updated_at: str = Field(default_factory=get_current_timestamp)
    read_at: str | None = None
    message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    thread_id: str | None = None
    mailbox: str = "inbox"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_as_read(self) -> None:
        """Mark the email as read."""
        self.status = EmailStatus.READ
        self.read_at = get_current_timestamp()
        self.updated_at = get_current_timestamp()

    def mark_as_delivered(self) -> None:
        """Mark the email as delivered."""
        self.status = EmailStatus.DELIVERED
        self.updated_at = get_current_timestamp()

    def mark_as_failed(self, reason: str | None = None) -> None:
        """
        Mark the email as failed.

        Args:
            reason: Optional reason for failure.
        """
        self.status = EmailStatus.FAILED
        self.updated_at = get_current_timestamp()
        if reason:
            self.metadata["failure_reason"] = reason

    def get_recipients(self) -> list[EmailAddress]:
        """
        Get all recipients of the email.

        Returns:
            Combined list of to, cc, and bcc addresses.
        """
        return self.to_addresses + self.cc_addresses + self.bcc_addresses

    def get_recipient_addresses(self) -> list[str]:
        """
        Get all recipient email addresses as strings.

        Returns:
            List of email address strings.
        """
        return [addr.address for addr in self.get_recipients()]

    def model_post_init(self, __context: Any) -> None:
        """Generate message_id if not provided."""
        if not self.message_id:
            self.message_id = f"<{self.id}@mock-email-server>"

        if not self.thread_id:
            # Use in_reply_to for threading, or create new thread
            if self.in_reply_to:
                # Extract thread ID from in_reply_to
                self.thread_id = self.in_reply_to.strip("<>").split("@")[0]
            else:
                self.thread_id = self.id


class EmailCreateRequest(BaseModel):
    """
    Request model for creating/sending an email.

    Attributes:
        from_address: Sender email address string.
        to_addresses: List of recipient email strings.
        cc_addresses: List of CC email strings.
        bcc_addresses: List of BCC email strings.
        subject: Email subject.
        body_text: Plain text body.
        body_html: Optional HTML body.
        attachments: List of attachments.
        headers: Additional headers.
        in_reply_to: Message-ID being replied to.
        metadata: Additional metadata.
    """

    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str] = Field(default_factory=list)
    bcc_addresses: list[str] = Field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    in_reply_to: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_email(self) -> Email:
        """
        Convert request to Email model.

        Returns:
            Email instance.
        """
        return Email(
            from_address=EmailAddress.from_string(self.from_address),
            to_addresses=[EmailAddress.from_string(addr) for addr in self.to_addresses],
            cc_addresses=[EmailAddress.from_string(addr) for addr in self.cc_addresses],
            bcc_addresses=[
                EmailAddress.from_string(addr) for addr in self.bcc_addresses
            ],
            subject=self.subject,
            body_text=self.body_text,
            body_html=self.body_html,
            attachments=self.attachments,
            headers=self.headers,
            in_reply_to=self.in_reply_to,
            metadata=self.metadata,
            status=EmailStatus.PENDING,
            mailbox="sent",
        )


class EmailListResponse(BaseModel):
    """
    Response model for email list operations.

    Attributes:
        emails: List of emails.
        total: Total count of emails matching query.
        page: Current page number.
        page_size: Number of emails per page.
        has_more: Whether more pages exist.
    """

    emails: list[Email]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class WebhookConfig(BaseModel):
    """
    Webhook configuration model.

    Attributes:
        id: Unique identifier for the webhook.
        url: URL to send webhook events to.
        events: List of event types to subscribe to.
        secret: Optional secret for signing webhook payloads.
        active: Whether the webhook is active.
        created_at: Timestamp when webhook was created.
        metadata: Additional webhook metadata.
    """

    id: str = Field(default_factory=generate_uuid)
    url: str
    events: list[str] = Field(default_factory=lambda: ["email.received"])
    secret: str | None = None
    active: bool = True
    created_at: str = Field(default_factory=get_current_timestamp)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebhookEvent(BaseModel):
    """
    Webhook event payload.

    Attributes:
        id: Unique event identifier.
        event_type: Type of event (email.received, email.sent, etc.).
        timestamp: When the event occurred.
        data: Event-specific data.
    """

    id: str = Field(default_factory=generate_uuid)
    event_type: str
    timestamp: str = Field(default_factory=get_current_timestamp)
    data: dict[str, Any] = Field(default_factory=dict)
