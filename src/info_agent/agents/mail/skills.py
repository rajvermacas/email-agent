"""
Mail Agent skill definitions.

Defines the A2A skills that the Mail Agent provides.
"""

from info_agent.a2a.models import AgentSkill, SkillInputSchema


SEND_EMAIL_SKILL = AgentSkill(
    id="send_email",
    name="Send Email",
    description="Sends an email to a recipient",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "to_address": {
                "type": "string",
                "format": "email",
                "description": "Recipient email address",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Email body content (plain text)",
            },
            "from_address": {
                "type": "string",
                "format": "email",
                "description": "Sender email address (optional, uses default if not provided)",
            },
            "cc_addresses": {
                "type": "array",
                "items": {"type": "string", "format": "email"},
                "description": "CC email addresses (optional)",
            },
            "in_reply_to": {
                "type": "string",
                "description": "Message-ID to reply to (optional, for threading)",
            },
            "thread_id": {
                "type": "string",
                "description": "Thread ID for conversation tracking (optional)",
            },
        },
        required=["to_address", "subject", "body"],
    ),
    tags=["email", "send", "communication"],
)


CHECK_INBOX_SKILL = AgentSkill(
    id="check_inbox",
    name="Check Inbox",
    description="Checks the inbox for new or unread emails",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "address": {
                "type": "string",
                "format": "email",
                "description": "Email address to check inbox for",
            },
            "unread_only": {
                "type": "boolean",
                "description": "Only return unread emails (default: true)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 20)",
            },
            "thread_id": {
                "type": "string",
                "description": "Filter by thread ID (optional)",
            },
        },
        required=["address"],
    ),
    tags=["email", "inbox", "check"],
)


GET_THREAD_SKILL = AgentSkill(
    id="get_thread",
    name="Get Email Thread",
    description="Retrieves all emails in a conversation thread",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "thread_id": {
                "type": "string",
                "description": "Thread identifier",
            },
        },
        required=["thread_id"],
    ),
    tags=["email", "thread", "conversation"],
)


SEARCH_EMAILS_SKILL = AgentSkill(
    id="search_emails",
    name="Search Emails",
    description="Searches emails by content or metadata",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "query": {
                "type": "string",
                "description": "Search query (searches subject and body)",
            },
            "address": {
                "type": "string",
                "format": "email",
                "description": "Filter by recipient/sender address (optional)",
            },
            "mailbox": {
                "type": "string",
                "enum": ["inbox", "sent"],
                "description": "Mailbox to search (optional)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default: 50)",
            },
        },
        required=["query"],
    ),
    tags=["email", "search"],
)


MAIL_AGENT_SKILLS = [
    SEND_EMAIL_SKILL,
    CHECK_INBOX_SKILL,
    GET_THREAD_SKILL,
    SEARCH_EMAILS_SKILL,
]
