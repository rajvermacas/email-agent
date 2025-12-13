"""
Mail Agent executor implementation.

Implements the A2A agent for email operations.
"""

from typing import Any

import structlog

from info_agent.a2a.executor import (
    BaseAgentExecutor,
    EventQueue,
    RequestContext,
)
from info_agent.a2a.models import AgentCard
from info_agent.agents.mail.skills import MAIL_AGENT_SKILLS
from info_agent.email_server.models import Email, EmailAddress, EmailStatus
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.webhooks import WebhookManager
from info_agent.utils.exceptions import A2AError
from info_agent.utils.helpers import generate_uuid, get_current_timestamp

logger = structlog.get_logger(__name__)


def create_mail_agent_card(
    agent_id: str = "mail-agent",
    endpoint: str = "http://localhost:8001/a2a",
) -> AgentCard:
    """
    Create the agent card for the Mail Agent.

    Args:
        agent_id: Unique agent identifier.
        endpoint: A2A endpoint URL.

    Returns:
        Configured AgentCard.
    """
    return AgentCard(
        id=agent_id,
        name="Mail Agent",
        description="A2A agent for handling email operations including sending, receiving, and managing email threads",
        endpoint=endpoint,
        skills=MAIL_AGENT_SKILLS,
        capabilities=["streaming"],
        metadata={
            "version": "1.0.0",
            "author": "Info-Agent Team",
        },
    )


class MailAgentExecutor(BaseAgentExecutor):
    """
    Mail Agent executor.

    Handles email-related tasks by interacting with the email storage.

    Attributes:
        _storage: Email storage for managing emails.
        _webhook_manager: Webhook manager for notifications.
        _default_from_address: Default sender address.
    """

    def __init__(
        self,
        storage: EmailStorage,
        webhook_manager: WebhookManager | None = None,
        default_from_address: str = "agent@info-agent.example.com",
        agent_id: str = "mail-agent",
        endpoint: str = "http://localhost:8001/a2a",
    ) -> None:
        """
        Initialize Mail Agent executor.

        Args:
            storage: Email storage instance.
            webhook_manager: Optional webhook manager.
            default_from_address: Default sender email address.
            agent_id: Agent identifier.
            endpoint: A2A endpoint URL.
        """
        agent_card = create_mail_agent_card(agent_id, endpoint)
        super().__init__(agent_card)

        self._storage = storage
        self._webhook_manager = webhook_manager
        self._default_from_address = default_from_address

        logger.info(
            "mail_agent_executor_initialized",
            agent_id=agent_id,
            default_from=default_from_address,
        )

    @property
    def storage(self) -> EmailStorage:
        """Get email storage."""
        return self._storage

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute a mail agent task.

        Routes to the appropriate skill handler.

        Args:
            context: Request context.
            event_queue: Event queue for responses.
        """
        skill_id = context.task.skill_id

        logger.info(
            "executing_mail_skill",
            skill_id=skill_id,
            task_id=context.task.id,
        )

        if skill_id == "send_email":
            await self._handle_send_email(context, event_queue)
        elif skill_id == "check_inbox":
            await self._handle_check_inbox(context, event_queue)
        elif skill_id == "get_thread":
            await self._handle_get_thread(context, event_queue)
        elif skill_id == "search_emails":
            await self._handle_search_emails(context, event_queue)
        else:
            await event_queue.send_error(f"Unknown skill: {skill_id}")

    async def _handle_send_email(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle send_email skill.

        Args:
            context: Request context.
            event_queue: Event queue.
        """
        # Extract input parameters
        to_address = context.get_input("to_address")
        subject = context.get_input("subject")
        body = context.get_input("body")
        from_address = context.get_input("from_address", self._default_from_address)
        cc_addresses = context.get_input("cc_addresses", [])
        in_reply_to = context.get_input("in_reply_to")
        thread_id = context.get_input("thread_id")

        # Validate required fields
        if not to_address:
            await event_queue.send_error("to_address is required")
            return

        if not subject:
            await event_queue.send_error("subject is required")
            return

        if not body:
            await event_queue.send_error("body is required")
            return

        await event_queue.send_status("Composing email...")

        try:
            # Create email
            email = Email(
                from_address=EmailAddress(address=from_address),
                to_addresses=[EmailAddress(address=to_address)],
                cc_addresses=[EmailAddress(address=cc) for cc in cc_addresses],
                subject=subject,
                body_text=body,
                in_reply_to=in_reply_to,
                status=EmailStatus.SENT,
                mailbox="sent",
            )

            # Override thread_id if provided
            if thread_id:
                email.thread_id = thread_id

            await event_queue.send_status("Sending email...")

            # Store the sent email
            stored_email = self._storage.store(email)

            # Also store in recipient's inbox for the mock server
            inbox_copy = email.model_copy()
            inbox_copy.id = generate_uuid()  # New ID for inbox copy
            inbox_copy.mailbox = "inbox"
            inbox_copy.status = EmailStatus.DELIVERED
            self._storage.store(inbox_copy)

            # Dispatch webhook if configured
            if self._webhook_manager:
                self._webhook_manager.dispatch_email_event(
                    WebhookManager.EVENT_EMAIL_SENT,
                    stored_email,
                )

            logger.info(
                "email_sent",
                email_id=stored_email.id,
                to_address=to_address,
                subject=subject[:50],
            )

            # Return result
            await event_queue.send_data({
                "success": True,
                "email_id": stored_email.id,
                "message_id": stored_email.message_id,
                "thread_id": stored_email.thread_id,
                "to_address": to_address,
                "subject": subject,
                "sent_at": stored_email.created_at,
            })

        except Exception as e:
            logger.error("send_email_failed", error=str(e))
            await event_queue.send_error(f"Failed to send email: {e}")

    async def _handle_check_inbox(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle check_inbox skill.

        Args:
            context: Request context.
            event_queue: Event queue.
        """
        address = context.get_input("address")
        unread_only = context.get_input("unread_only", True)
        limit = context.get_input("limit", 20)
        thread_id = context.get_input("thread_id")

        if not address:
            await event_queue.send_error("address is required")
            return

        await event_queue.send_status(f"Checking inbox for {address}...")

        try:
            # Get status filter
            status_filter = None
            if unread_only:
                status_filter = EmailStatus.DELIVERED

            emails, total = self._storage.list_by_mailbox(
                address=address,
                mailbox="inbox",
                page_size=limit,
                status=status_filter,
            )

            # Filter by thread if specified
            if thread_id:
                emails = [e for e in emails if e.thread_id == thread_id]

            # Format emails for response
            email_summaries = []
            for email in emails:
                email_summaries.append({
                    "id": email.id,
                    "from_address": email.from_address.address,
                    "subject": email.subject,
                    "preview": email.body_text[:100] if email.body_text else "",
                    "status": email.status.value,
                    "thread_id": email.thread_id,
                    "received_at": email.created_at,
                })

            logger.info(
                "inbox_checked",
                address=address,
                total=len(email_summaries),
            )

            await event_queue.send_data({
                "address": address,
                "total_emails": len(email_summaries),
                "emails": email_summaries,
                "unread_only": unread_only,
            })

        except Exception as e:
            logger.error("check_inbox_failed", error=str(e))
            await event_queue.send_error(f"Failed to check inbox: {e}")

    async def _handle_get_thread(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle get_thread skill.

        Args:
            context: Request context.
            event_queue: Event queue.
        """
        thread_id = context.get_input("thread_id")

        if not thread_id:
            await event_queue.send_error("thread_id is required")
            return

        await event_queue.send_status(f"Loading thread {thread_id}...")

        try:
            emails = self._storage.list_by_thread(thread_id)

            if not emails:
                await event_queue.send_error(f"Thread not found: {thread_id}")
                return

            # Format thread emails
            thread_emails = []
            for email in emails:
                thread_emails.append({
                    "id": email.id,
                    "from_address": email.from_address.address,
                    "to_addresses": [a.address for a in email.to_addresses],
                    "subject": email.subject,
                    "body": email.body_text,
                    "status": email.status.value,
                    "mailbox": email.mailbox,
                    "created_at": email.created_at,
                })

            logger.info(
                "thread_retrieved",
                thread_id=thread_id,
                message_count=len(thread_emails),
            )

            await event_queue.send_data({
                "thread_id": thread_id,
                "message_count": len(thread_emails),
                "messages": thread_emails,
            })

        except Exception as e:
            logger.error("get_thread_failed", error=str(e))
            await event_queue.send_error(f"Failed to get thread: {e}")

    async def _handle_search_emails(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle search_emails skill.

        Args:
            context: Request context.
            event_queue: Event queue.
        """
        query = context.get_input("query")
        address = context.get_input("address")
        mailbox = context.get_input("mailbox")
        limit = context.get_input("limit", 50)

        if not query:
            await event_queue.send_error("query is required")
            return

        await event_queue.send_status(f"Searching for: {query}...")

        try:
            results = self._storage.search(
                query=query,
                address=address,
                mailbox=mailbox,
                limit=limit,
            )

            # Format search results
            search_results = []
            for email in results:
                search_results.append({
                    "id": email.id,
                    "from_address": email.from_address.address,
                    "subject": email.subject,
                    "preview": email.body_text[:150] if email.body_text else "",
                    "mailbox": email.mailbox,
                    "thread_id": email.thread_id,
                    "created_at": email.created_at,
                })

            logger.info(
                "emails_searched",
                query=query[:50],
                results_count=len(search_results),
            )

            await event_queue.send_data({
                "query": query,
                "result_count": len(search_results),
                "results": search_results,
            })

        except Exception as e:
            logger.error("search_emails_failed", error=str(e))
            await event_queue.send_error(f"Search failed: {e}")

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status with storage stats.
        """
        base_health = await super().health_check()

        # Add storage stats
        storage_stats = self._storage.get_stats()
        base_health["storage"] = storage_stats

        return base_health
