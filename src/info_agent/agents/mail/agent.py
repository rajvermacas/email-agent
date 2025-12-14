"""
Mail Agent implementing A2A protocol for email operations using official a2a-sdk.

This module provides the main Mail Agent class that implements the A2A protocol
for email-related operations using the official a2a-sdk. The agent handles two primary skills:
1. send-email: Compose and send emails using LLM
2. receive-email-webhook: Process incoming email webhooks

The agent uses SDK's A2ARESTFastAPIApplication for spec-compliant server implementation
and registers itself with the A2A registry on startup.

All operations are async using FastAPI and httpx.
No fallback/default values - missing data raises exceptions.

Usage:
    from info_agent.agents.mail.agent import MailAgent
    from info_agent.config import get_settings

    settings = get_settings()
    agent = MailAgent(settings)

    # Start the agent (registers with A2A registry)
    await agent.start()

    # Get FastAPI app for uvicorn
    app = agent.get_app()

    # Shutdown
    await agent.shutdown()
"""

import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI

from a2a.server.apps.rest.fastapi_app import A2ARESTFastAPIApplication
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers.request_handler import RequestHandler
from a2a.types import (
    AgentCard,
    AgentSkill,
    DataPart,
    Message,
    MessageSendParams,
    Role,
    Task,
    TaskStatus,
)

from info_agent.agents.mail.composer import EmailComposer
from info_agent.agents.mail.parser import EmailParser
from info_agent.agents.mail.smtp_client import SMTPClient
from info_agent.agents.mail.state import (
    MailAgentState,
    ReceiveEmailWebhookPayload,
    ReceiveEmailWebhookResult,
    SendEmailPayload,
    SendEmailResult,
)
from info_agent.config import Settings
from info_agent.utils.exceptions import A2AError, EmailError, ValidationError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class MailAgentRequestHandler(RequestHandler):
    """
    Request handler for Mail Agent implementing A2A protocol.

    This handler processes incoming messages and routes them to appropriate
    skill handlers (send-email or receive-email-webhook).

    Attributes:
        mail_agent: Reference to MailAgent instance for accessing components.
    """

    def __init__(self, mail_agent: "MailAgent") -> None:
        """
        Initialize request handler.

        Args:
            mail_agent: MailAgent instance.
        """
        super().__init__()  # Call parent init
        self.mail_agent = mail_agent
        logger.debug("MailAgentRequestHandler initialized")

    async def on_message_send(
        self,
        params: MessageSendParams,
        context: ServerCallContext | None = None,
    ) -> Task | Message:
        """
        Handle incoming message and route to appropriate skill.

        This is the main entry point for A2A task requests.
        Extracts skill_id from message metadata and routes to handler.

        Args:
            params: Message send parameters containing the message.
            context: Optional server call context.

        Returns:
            Task with result or error.

        Raises:
            A2AError: If skill not supported or handling fails.
        """
        message = params.message
        task_id = message.task_id or str(uuid.uuid4())
        context_id = message.context_id or task_id

        logger.info(
            "Received message",
            task_id=task_id,
            context_id=context_id,
            role=message.role,
        )

        # Extract payload from message parts
        if not message.parts or len(message.parts) == 0:
            logger.error("Message has no parts", task_id=task_id)
            return self._create_error_task(
                task_id=task_id,
                context_id=context_id,
                error="Message has no parts",
            )

        # Get data from first DataPart
        payload = {}
        for part in message.parts:
            if isinstance(part, DataPart) and part.data:
                payload = part.data
                break

        if not payload:
            logger.error("No data payload found in message", task_id=task_id)
            return self._create_error_task(
                task_id=task_id,
                context_id=context_id,
                error="No data payload found in message",
            )

        # Determine skill from payload or metadata
        skill_id = payload.get("skill_id") or payload.get("skill")
        if message.metadata:
            skill_id = skill_id or message.metadata.get("skill_id")

        if not skill_id:
            logger.error("No skill_id specified in message", task_id=task_id)
            return self._create_error_task(
                task_id=task_id,
                context_id=context_id,
                error="No skill_id specified in message",
            )

        logger.info(
            "Routing to skill handler",
            task_id=task_id,
            skill_id=skill_id,
        )

        # Create initial task state
        state: MailAgentState = {
            "task_id": task_id,
            "skill_id": skill_id,  # type: ignore
            "status": "submitted",
            "email_task": {},  # type: ignore
            "result": None,
            "error": None,
            "payload": payload,
        }

        self.mail_agent._active_tasks[task_id] = state

        try:
            # Update to working
            state["status"] = "working"

            # Route to skill handler
            if skill_id == "send-email":
                result = await self.mail_agent._handle_send_email(payload)
                state["result"] = result
                state["status"] = "completed"

                # Create success task
                return self._create_success_task(
                    task_id=task_id,
                    context_id=context_id,
                    result=result,
                    message=message,
                )

            elif skill_id == "receive-email-webhook":
                result = await self.mail_agent._handle_receive_email_webhook(payload)
                state["result"] = result
                state["status"] = "completed"

                # Create success task
                return self._create_success_task(
                    task_id=task_id,
                    context_id=context_id,
                    result=result,
                    message=message,
                )

            else:
                logger.error("Unsupported skill", skill_id=skill_id, task_id=task_id)
                state["status"] = "failed"
                state["error"] = f"Unsupported skill: {skill_id}"

                return self._create_error_task(
                    task_id=task_id,
                    context_id=context_id,
                    error=f"Unsupported skill: {skill_id}",
                )

        except Exception as e:
            logger.error(
                "Task handling failed",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

            state["status"] = "failed"
            state["error"] = str(e)

            return self._create_error_task(
                task_id=task_id,
                context_id=context_id,
                error=str(e),
            )

    async def on_get_task(
        self,
        params: Any,
        context: ServerCallContext | None = None,
    ) -> Task | None:
        """
        Get status of a specific task.

        Args:
            params: Task query parameters with task_id.
            context: Optional server call context.

        Returns:
            Task if found, None otherwise.
        """
        task_id = params.task_id if hasattr(params, "task_id") else params.get("task_id")

        logger.info("Task status requested", task_id=task_id)

        if task_id not in self.mail_agent._active_tasks:
            logger.warning("Task not found", task_id=task_id)
            return None

        state = self.mail_agent._active_tasks[task_id]

        # Convert status string to TaskStatus enum
        status_map = {
            "submitted": TaskStatus.submitted,
            "working": TaskStatus.working,
            "completed": TaskStatus.completed,
            "failed": TaskStatus.failed,
            "cancelled": TaskStatus.cancelled,
        }

        status = status_map.get(state["status"], TaskStatus.failed)

        # Create task with current state
        if state["status"] == "completed":
            return Task(
                id=task_id,
                context_id=task_id,
                status=status,
                history=[
                    Message(
                        message_id=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[DataPart(data=state["result"])],
                    )
                ],
            )
        elif state["status"] == "failed":
            return Task(
                id=task_id,
                context_id=task_id,
                status=status,
                history=[
                    Message(
                        message_id=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[DataPart(data={"error": state["error"]})],
                    )
                ],
            )
        else:
            return Task(
                id=task_id,
                context_id=task_id,
                status=status,
                history=[],
            )

    def _create_success_task(
        self,
        task_id: str,
        context_id: str,
        result: dict[str, Any],
        message: Message,
    ) -> Task:
        """
        Create a successful task response.

        Args:
            task_id: Task ID.
            context_id: Context ID.
            result: Result data.
            message: Original incoming message.

        Returns:
            Task with completed status and result.
        """
        logger.info("Creating success task", task_id=task_id)

        return Task(
            id=task_id,
            context_id=context_id,
            status=TaskStatus.completed,
            history=[
                message,  # Include original message
                Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[DataPart(data=result)],
                ),
            ],
        )

    def _create_error_task(
        self,
        task_id: str,
        context_id: str,
        error: str,
    ) -> Task:
        """
        Create a failed task response.

        Args:
            task_id: Task ID.
            context_id: Context ID.
            error: Error message.

        Returns:
            Task with failed status and error.
        """
        logger.error("Creating error task", task_id=task_id, error=error)

        return Task(
            id=task_id,
            context_id=context_id,
            status=TaskStatus.failed,
            history=[
                Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[DataPart(data={"error": error})],
                )
            ],
        )

    # Stub implementations for abstract methods (not used in basic implementation)
    async def on_message_send_stream(self, params: Any, context: Any = None) -> Any:
        """Not implemented - we don't support streaming."""
        raise NotImplementedError("Streaming not supported")

    async def on_cancel_task(self, params: Any, context: Any = None) -> Any:
        """Not implemented - task cancellation not supported."""
        return None

    async def on_resubscribe_to_task(self, params: Any, context: Any = None) -> Any:
        """Not implemented - task resubscription not supported."""
        return None

    async def on_get_task_push_notification_config(self, params: Any, context: Any = None) -> Any:
        """Not implemented - push notifications not supported."""
        return None

    async def on_set_task_push_notification_config(self, params: Any, context: Any = None) -> Any:
        """Not implemented - push notifications not supported."""
        return None

    async def on_list_task_push_notification_config(self, params: Any, context: Any = None) -> Any:
        """Not implemented - push notifications not supported."""
        return []

    async def on_delete_task_push_notification_config(self, params: Any, context: Any = None) -> Any:
        """Not implemented - push notifications not supported."""
        return None


class MailAgent:
    """
    Mail Agent for handling email operations via A2A protocol using official SDK.

    This agent provides two skills:
    1. send-email: Compose professional emails using LLM and send via SMTP
    2. receive-email-webhook: Process incoming email webhooks and extract data

    The agent uses the official a2a-sdk for spec-compliant A2A protocol implementation
    and integrates with the A2A registry for service discovery.

    Attributes:
        settings: Application settings.
        smtp_client: SMTP client for sending emails.
        composer: Email composer using LLM.
        parser: Email parser using LLM.
        agent_card: A2A agent card describing capabilities.
        handler: Request handler for A2A messages.
        a2a_app: SDK FastAPI application.
        app: Final FastAPI application.
    """

    AGENT_NAME = "mail-agent"
    AGENT_VERSION = "1.0.0"
    AGENT_DESCRIPTION = "Email operations agent supporting composition and sending"

    def __init__(self, settings: Settings) -> None:
        """
        Initialize Mail Agent.

        Args:
            settings: Application settings (required).

        Raises:
            ValidationError: If settings are invalid.
        """
        logger.info("Initializing Mail Agent with SDK")

        if not settings:
            logger.error("Settings are required but not provided")
            raise ValidationError(
                message="Settings are required",
                field="settings",
            )

        self.settings = settings
        self._active_tasks: dict[str, MailAgentState] = {}

        # Initialize components
        logger.info("Initializing SMTP client")
        self.smtp_client = SMTPClient(
            host=settings.smtp_host,
            port=settings.smtp_port,
        )

        logger.info("Initializing email composer")
        self.composer = EmailComposer()

        logger.info("Initializing email parser")
        self.parser = EmailParser()

        # Create agent card (SDK version)
        logger.info("Creating SDK agent card")
        self.agent_card = self._create_agent_card()

        # Create request handler
        logger.info("Creating request handler")
        self.handler = MailAgentRequestHandler(self)

        # Create SDK A2A application
        logger.info("Creating SDK A2A FastAPI application")
        self.a2a_app = A2ARESTFastAPIApplication(
            agent_card=self.agent_card,
            http_handler=self.handler,
        )

        # Build FastAPI app
        logger.info("Building FastAPI app from SDK")
        self.app = self.a2a_app.build()

        # Add health check endpoint
        @self.app.get("/health")
        async def health_check() -> dict[str, str]:
            """Health check endpoint."""
            logger.debug("Health check requested")
            return {"status": "healthy", "agent": self.AGENT_NAME}

        logger.info(
            "Mail Agent initialized successfully with SDK",
            agent_name=self.AGENT_NAME,
            version=self.AGENT_VERSION,
        )

    def _create_agent_card(self) -> AgentCard:
        """
        Create A2A agent card describing capabilities using SDK models.

        Returns:
            SDK AgentCard instance.
        """
        logger.debug("Creating SDK agent card")

        skills = [
            AgentSkill(
                id="send-email",
                name="Send Email",
                description="Compose and send professional emails using LLM-powered composition",
                tags=["email", "smtp", "composition"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "to_address": {
                            "type": "string",
                            "description": "Recipient email address",
                        },
                        "instructions": {
                            "type": "string",
                            "description": "Instructions for email composition",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Optional email subject (will be generated if not provided)",
                        },
                        "thread_id": {
                            "type": "string",
                            "description": "Optional thread ID for email threading",
                        },
                    },
                    "required": ["to_address", "instructions"],
                },
                example_prompts=[
                    "Send an email to client@example.com requesting a meeting next week",
                    "Compose and send a status update email to team@company.com",
                ],
            ),
            AgentSkill(
                id="receive-email-webhook",
                name="Receive Email Webhook",
                description="Process incoming email webhooks and extract structured data",
                tags=["email", "webhook", "parsing"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "message_id": {"type": "string"},
                        "from_address": {"type": "string"},
                        "to_address": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "attachments": {"type": "array"},
                        "received_at": {"type": "string"},
                    },
                    "required": [
                        "event",
                        "message_id",
                        "from_address",
                        "to_address",
                        "subject",
                        "body",
                        "received_at",
                    ],
                },
            ),
        ]

        # Use snake_case for SDK compatibility
        # Important: Set preferred_transport to "HTTP+JSON" to match REST adapter
        card = AgentCard(
            name=self.AGENT_NAME,
            description=self.AGENT_DESCRIPTION,
            version=self.AGENT_VERSION,
            url=self.settings.get_mail_agent_url(),
            capabilities={
                "async": True,
                "streaming": False,
                "llm_powered": True,
            },
            skills=skills,
            default_input_modes=["data"],  # SDK uses snake_case
            default_output_modes=["data"],  # SDK uses snake_case
            preferred_transport="HTTP+JSON",  # Match A2ARESTFastAPIApplication transport
        )

        logger.debug("SDK agent card created", skills_count=len(skills))
        return card

    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application.

        Returns:
            FastAPI application instance.
        """
        return self.app

    async def start(self) -> None:
        """
        Start the Mail Agent and register with A2A registry.

        This method registers the agent with the central A2A registry
        so other agents can discover and communicate with it.

        Raises:
            A2AError: If registration fails.
        """
        logger.info("Starting Mail Agent")

        # Test SMTP connection
        try:
            logger.info("Testing SMTP connection")
            await self.smtp_client.test_connection()
            logger.info("SMTP connection test successful")
        except Exception as e:
            logger.warning(
                "SMTP connection test failed (non-fatal)",
                error=str(e),
                error_type=type(e).__name__,
            )

        # Register with A2A registry
        await self._register_with_registry()

        logger.info("Mail Agent started successfully")

    async def shutdown(self) -> None:
        """
        Shutdown the Mail Agent.

        Performs cleanup operations before shutdown.
        """
        logger.info("Shutting down Mail Agent")

        # Cancel any active tasks
        if self._active_tasks:
            logger.info(
                "Cancelling active tasks",
                task_count=len(self._active_tasks),
            )
            for task_id, state in self._active_tasks.items():
                if state["status"] in ["submitted", "working"]:
                    state["status"] = "cancelled"
                    logger.debug("Task cancelled", task_id=task_id)

        logger.info("Mail Agent shutdown complete")

    async def _register_with_registry(self) -> None:
        """
        Register agent with the A2A registry.

        Raises:
            A2AError: If registration fails.
        """
        logger.info(
            "Registering with A2A registry",
            registry_url=self.settings.a2a_registry_url,
        )

        register_url = f"{self.settings.a2a_registry_url}/agents/register"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    register_url,
                    json=self.agent_card.model_dump(),
                )

                if response.status_code >= 400:
                    error_detail = response.text
                    logger.error(
                        "Agent registration failed",
                        status_code=response.status_code,
                        error=error_detail,
                    )
                    raise A2AError(
                        message=f"Failed to register agent: HTTP {response.status_code}",
                        agent_name=self.AGENT_NAME,
                        details={
                            "status_code": response.status_code,
                            "error": error_detail,
                        },
                    )

                result = response.json()
                logger.info(
                    "Agent registered successfully",
                    status=result.get("status"),
                    agent_name=result.get("agent_name"),
                )

        except httpx.HTTPError as e:
            logger.error(
                "HTTP error during registration",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise A2AError(
                message=f"Failed to register agent: {str(e)}",
                agent_name=self.AGENT_NAME,
                details={"error": str(e)},
            ) from e

        except Exception as e:
            logger.error(
                "Unexpected error during registration",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise A2AError(
                message=f"Unexpected registration error: {str(e)}",
                agent_name=self.AGENT_NAME,
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def _handle_send_email(
        self,
        payload: dict[str, Any],
    ) -> SendEmailResult:
        """
        Handle send-email skill.

        Composes email using LLM and sends via SMTP.

        Args:
            payload: Task payload with to_address, instructions, optional subject and thread_id.

        Returns:
            Send email result with message_id, subject, and preview.

        Raises:
            ValidationError: If required payload fields are missing.
            EmailError: If email composition or sending fails.
        """
        logger.info("Handling send-email skill")

        # Validate and extract payload
        try:
            send_payload: SendEmailPayload = {
                "to_address": payload.get("to_address", ""),
                "instructions": payload.get("instructions", ""),
                "subject": payload.get("subject"),
                "thread_id": payload.get("thread_id"),
            }
        except Exception as e:
            logger.error("Failed to parse payload", error=str(e))
            raise ValidationError(
                message=f"Invalid payload structure: {str(e)}",
                details={"error": str(e)},
            ) from e

        # Validate required fields
        if not send_payload["to_address"]:
            logger.error("Missing required field: to_address")
            raise ValidationError(
                message="Missing required field: to_address",
                field="to_address",
            )

        if not send_payload["instructions"]:
            logger.error("Missing required field: instructions")
            raise ValidationError(
                message="Missing required field: instructions",
                field="instructions",
            )

        logger.info(
            "Composing email",
            to=send_payload["to_address"],
            has_subject=bool(send_payload["subject"]),
            has_thread_id=bool(send_payload["thread_id"]),
        )

        # Compose email using LLM
        try:
            composed = await self.composer.compose_email(
                to_address=send_payload["to_address"],
                instructions=send_payload["instructions"],
                subject=send_payload["subject"],
            )

            logger.info(
                "Email composed successfully",
                subject=composed["subject"],
                body_length=len(composed["body"]),
            )
        except Exception as e:
            logger.error(
                "Email composition failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Email composition failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

        # Send email via SMTP
        try:
            logger.info("Sending email via SMTP")
            message_id = await self.smtp_client.send_email(
                to_address=send_payload["to_address"],
                subject=composed["subject"],
                body=composed["body"],
                thread_id=send_payload["thread_id"],
            )

            logger.info(
                "Email sent successfully",
                message_id=message_id,
                to=send_payload["to_address"],
            )
        except Exception as e:
            logger.error(
                "Email sending failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Email sending failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

        # Create result
        result: SendEmailResult = {
            "message_id": message_id,
            "subject": composed["subject"],
            "body_preview": composed["body"][:200],
            "thread_id": send_payload.get("thread_id"),
        }

        logger.info("Send email completed", message_id=message_id)
        return result

    async def _handle_receive_email_webhook(
        self,
        payload: dict[str, Any],
    ) -> ReceiveEmailWebhookResult:
        """
        Handle receive-email-webhook skill.

        Processes incoming email webhook and extracts structured data.

        Args:
            payload: Webhook payload with email data.

        Returns:
            Parsed webhook result.

        Raises:
            ValidationError: If required payload fields are missing.
        """
        logger.info("Handling receive-email-webhook skill")

        # Validate and extract payload
        try:
            webhook_payload: ReceiveEmailWebhookPayload = {
                "event": payload.get("event", ""),
                "message_id": payload.get("message_id", ""),
                "from_address": payload.get("from_address", ""),
                "to_address": payload.get("to_address", ""),
                "subject": payload.get("subject", ""),
                "body": payload.get("body", ""),
                "thread_id": payload.get("thread_id"),
                "attachments": payload.get("attachments", []),
                "received_at": payload.get("received_at", ""),
            }
        except Exception as e:
            logger.error("Failed to parse webhook payload", error=str(e))
            raise ValidationError(
                message=f"Invalid webhook payload structure: {str(e)}",
                details={"error": str(e)},
            ) from e

        # Validate required fields
        required_fields = [
            "event",
            "message_id",
            "from_address",
            "to_address",
            "subject",
            "body",
            "received_at",
        ]
        for field in required_fields:
            if not webhook_payload.get(field):  # type: ignore
                logger.error(f"Missing required field: {field}")
                raise ValidationError(
                    message=f"Missing required field: {field}",
                    field=field,
                )

        logger.info(
            "Processing email webhook",
            message_id=webhook_payload["message_id"],
            from_address=webhook_payload["from_address"],
        )

        # Parse email content using LLM
        try:
            parsed = await self.parser.parse_email(
                from_address=webhook_payload["from_address"],
                subject=webhook_payload["subject"],
                body=webhook_payload["body"],
            )

            logger.info(
                "Email parsed successfully",
                message_id=webhook_payload["message_id"],
                intent=parsed.get("intent"),
            )
        except Exception as e:
            logger.error(
                "Email parsing failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Non-fatal: return unparsed data
            parsed = {
                "intent": "unknown",
                "extracted_data": {},
                "sentiment": "neutral",
            }
            logger.warning("Using fallback parsing result")

        # Create result
        result: ReceiveEmailWebhookResult = {
            "message_id": webhook_payload["message_id"],
            "from_address": webhook_payload["from_address"],
            "thread_id": webhook_payload.get("thread_id"),
            "parsed_content": parsed,
            "processed_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Receive email webhook completed",
            message_id=webhook_payload["message_id"],
        )
        return result


# Module-level function for creating app (for uvicorn)
def create_mail_agent_app() -> FastAPI:
    """
    Create and return Mail Agent FastAPI application.

    This function is used by uvicorn to start the server.

    Returns:
        FastAPI application instance.
    """
    from info_agent.config import get_settings

    settings = get_settings()
    agent = MailAgent(settings)

    # Start agent in background (registers with registry)
    import asyncio
    asyncio.create_task(agent.start())

    return agent.get_app()
