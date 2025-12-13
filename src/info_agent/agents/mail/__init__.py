"""
Mail Agent module for Info-Agent.

This module provides the complete Mail Agent implementation for handling
email operations via the A2A protocol. The agent supports email composition
using LLM, sending emails via SMTP, and processing incoming email webhooks.

Key Components:
    - MailAgent: Main agent class implementing A2A protocol
    - EmailComposer: LLM-powered email composition
    - EmailParser: LLM-powered email parsing
    - SMTPClient: Async SMTP client for sending emails
    - State types: TypedDict definitions for agent state

Skills:
    - send-email: Compose and send professional emails using LLM
    - receive-email-webhook: Process incoming email webhooks and extract data

Usage:
    from info_agent.agents.mail import MailAgent
    from info_agent.config import get_settings

    # Initialize agent
    settings = get_settings()
    agent = MailAgent(settings)

    # Start agent and register with A2A registry
    await agent.start()

    # Handle task requests
    from info_agent.a2a import A2ATaskRequest

    request = A2ATaskRequest(
        task_id="task-123",
        skill_id="send-email",
        payload={
            "to_address": "client@example.com",
            "instructions": "Write a meeting request for next week"
        }
    )
    response = await agent.handle_task(request)

    # Shutdown
    await agent.shutdown()
"""

from info_agent.agents.mail.agent import MailAgent
from info_agent.agents.mail.composer import EmailComposer
from info_agent.agents.mail.parser import EmailParser
from info_agent.agents.mail.smtp_client import SMTPClient
from info_agent.agents.mail.state import (
    EmailTaskState,
    MailAgentState,
    ReceiveEmailWebhookPayload,
    ReceiveEmailWebhookResult,
    SendEmailPayload,
    SendEmailResult,
)

__all__ = [
    # Main agent
    "MailAgent",
    # Components
    "EmailComposer",
    "EmailParser",
    "SMTPClient",
    # State types
    "MailAgentState",
    "EmailTaskState",
    "SendEmailPayload",
    "SendEmailResult",
    "ReceiveEmailWebhookPayload",
    "ReceiveEmailWebhookResult",
]
