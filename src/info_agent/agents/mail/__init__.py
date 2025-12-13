"""
Mail Agent package.

Provides an A2A worker agent for email operations including:
- Sending emails to external parties
- Receiving and processing email responses
- Managing email threads and conversations
"""

from info_agent.agents.mail.executor import MailAgentExecutor, create_mail_agent_card
from info_agent.agents.mail.skills import (
    CHECK_INBOX_SKILL,
    GET_THREAD_SKILL,
    MAIL_AGENT_SKILLS,
    SEARCH_EMAILS_SKILL,
    SEND_EMAIL_SKILL,
)

__all__ = [
    "MailAgentExecutor",
    "create_mail_agent_card",
    "MAIL_AGENT_SKILLS",
    "SEND_EMAIL_SKILL",
    "CHECK_INBOX_SKILL",
    "GET_THREAD_SKILL",
    "SEARCH_EMAILS_SKILL",
]
