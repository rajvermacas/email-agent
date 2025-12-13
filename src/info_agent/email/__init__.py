"""
Email module for Info-Agent.

This module provides a complete mock email system with:
- SMTP server for receiving emails
- REST API for email management
- SQLite storage for email persistence
- Webhook notifications for email events

Key Components:
    - MockEmailServer: Combined SMTP + REST server
    - EmailStorage: Async SQLite storage
    - WebhookNotifier: Webhook notification sender
    - EmailHandler: SMTP handler for receiving emails

Models:
    - StoredEmail: Complete email data
    - CreateEmailRequest: Request for creating emails
    - EmailReplyRequest: Request for replying to emails
    - WebhookPayload: Webhook notification payload
    - EmailAttachment: Email attachment data

Usage:
    from info_agent.email import MockEmailServer

    server = MockEmailServer()
    await server.start()
"""

from info_agent.email.api import create_email_router
from info_agent.email.models import (
    CreateEmailRequest,
    EmailAttachment,
    EmailReplyRequest,
    StoredEmail,
    WebhookPayload,
)
from info_agent.email.server import MockEmailServer
from info_agent.email.smtp import EmailHandler, start_smtp_server
from info_agent.email.storage import EmailStorage
from info_agent.email.webhook import WebhookNotifier

__all__ = [
    # Server
    "MockEmailServer",
    # Storage
    "EmailStorage",
    # Webhook
    "WebhookNotifier",
    # SMTP
    "EmailHandler",
    "start_smtp_server",
    # API
    "create_email_router",
    # Models
    "StoredEmail",
    "CreateEmailRequest",
    "EmailReplyRequest",
    "WebhookPayload",
    "EmailAttachment",
]
