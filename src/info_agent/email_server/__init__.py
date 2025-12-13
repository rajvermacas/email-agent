"""
Mock Email Server package.

Provides a complete email server implementation for development and testing:
- SMTP server for sending/receiving emails
- REST API for programmatic access
- Webhook support for real-time notifications
- Web UI for viewing emails
"""

from info_agent.email_server.models import Email, EmailAddress, EmailStatus
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.smtp_server import MockSMTPServer
from info_agent.email_server.rest_api import create_email_api
from info_agent.email_server.webhooks import WebhookManager

__all__ = [
    "Email",
    "EmailAddress",
    "EmailStatus",
    "EmailStorage",
    "MockSMTPServer",
    "create_email_api",
    "WebhookManager",
]
