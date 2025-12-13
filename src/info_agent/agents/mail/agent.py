"""
Mail Agent implementing A2A protocol for email operations.

This module provides the main Mail Agent class that implements the A2A protocol
for email-related operations. The agent handles two primary skills:
1. send-email: Compose and send emails using LLM
2. receive-email-webhook: Process incoming email webhooks

The agent registers itself with the A2A registry on startup and handles
task requests according to the A2A protocol specification.

All operations are async using FastAPI and httpx.
No fallback/default values - missing data raises exceptions.

Usage:
    from info_agent.agents.mail.agent import MailAgent
    from info_agent.config import get_settings

    settings = get_settings()
    agent = MailAgent(settings)

    # Start the agent (registers with A2A registry)
    await agent.start()

    # Process tasks
    result = await agent.handle_task(task_request)

    # Shutdown
    await agent.shutdown()
"""

import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from info_agent.a2a import A2ATaskRequest, A2ATaskResponse, AgentCard, AgentSkill
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


class MailAgent:
    """
    Mail Agent for handling email operations via A2A protocol.

    This agent provides two skills:
    1. send-email: Compose professional emails using LLM and send via SMTP
    2. receive-email-webhook: Process incoming email webhooks and extract data

    The agent follows the A2A protocol for task handling and integrates
    with the A2A registry for service discovery.

    Attributes:
        settings: Application settings.
        smtp_client: SMTP client for sending emails.
        composer: Email composer using LLM.
        parser: Email parser using LLM.
        app: FastAPI application for A2A endpoints.
        agent_card: A2A agent card describing capabilities.
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
        logger.info("Initializing Mail Agent")

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

        # Create FastAPI app for A2A endpoints
        logger.info("Creating FastAPI app")
        self.app = self._create_app()

        # Create agent card
        logger.info("Creating agent card")
        self.agent_card = self._create_agent_card()

        logger.info(
            "Mail Agent initialized",
            agent_name=self.AGENT_NAME,
            version=self.AGENT_VERSION,
        )

    def _create_app(self) -> FastAPI:
        """
        Create FastAPI application with A2A endpoints.

        Returns:
            Configured FastAPI application.
        """
        logger.debug("Creating FastAPI application")

        app = FastAPI(
            title=f"{self.AGENT_NAME} A2A Server",
            description=self.AGENT_DESCRIPTION,
            version=self.AGENT_VERSION,
        )

        # A2A Protocol Endpoints
        @app.get("/.well-known/agent.json")
        async def get_agent_card() -> dict[str, Any]:
            """Get agent card describing capabilities."""
            logger.info("Agent card requested")
            return self.agent_card.model_dump()

        @app.post("/tasks")
        async def create_task(request: A2ATaskRequest) -> A2ATaskResponse:
            """Handle A2A task requests."""
            logger.info(
                "Task request received",
                task_id=request.task_id,
                skill_id=request.skill_id,
            )
            try:
                result = await self.handle_task(request)
                return result
            except Exception as e:
                logger.error(
                    "Task handling failed",
                    task_id=request.task_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise HTTPException(
                    status_code=500,
                    detail=str(e),
                )

        @app.get("/tasks/{task_id}")
        async def get_task_status(task_id: str) -> A2ATaskResponse:
            """Get status of a specific task."""
            logger.info("Task status requested", task_id=task_id)

            if task_id not in self._active_tasks:
                logger.error("Task not found", task_id=task_id)
                raise HTTPException(
                    status_code=404,
                    detail=f"Task not found: {task_id}",
                )

            state = self._active_tasks[task_id]

            return A2ATaskResponse(
                task_id=state["task_id"],
                status=state["status"],
                result=state.get("result"),
                error=state.get("error"),
            )

        @app.get("/health")
        async def health_check() -> dict[str, str]:
            """Health check endpoint."""
            logger.debug("Health check requested")
            return {"status": "healthy"}

        logger.debug("FastAPI application created")
        return app

    def _create_agent_card(self) -> AgentCard:
        """
        Create A2A agent card describing capabilities.

        Returns:
            AgentCard instance.
        """
        logger.debug("Creating agent card")

        skills = [
            AgentSkill(
                id="send-email",
                name="Send Email",
                description="Compose and send professional emails using LLM-powered composition",
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
            defaultInputModes=["data"],
            defaultOutputModes=["data"],
        )

        logger.debug("Agent card created", skills_count=len(skills))
        return card

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

    async def handle_task(self, request: A2ATaskRequest) -> A2ATaskResponse:
        """
        Handle an A2A task request.

        Routes the task to the appropriate skill handler based on skill_id.

        Args:
            request: A2A task request.

        Returns:
            A2A task response with result or error.

        Raises:
            A2AError: If skill is not supported or task handling fails.
        """
        logger.info(
            "Handling task",
            task_id=request.task_id,
            skill_id=request.skill_id,
        )

        # Create initial state
        state: MailAgentState = {
            "task_id": request.task_id,
            "skill_id": request.skill_id,  # type: ignore
            "status": "submitted",
            "email_task": {},  # type: ignore
            "result": None,
            "error": None,
            "payload": request.payload,
        }

        self._active_tasks[request.task_id] = state

        try:
            # Update status to working
            state["status"] = "working"

            # Route to skill handler
            if request.skill_id == "send-email":
                result = await self._handle_send_email(request.payload)
                state["result"] = result
                state["status"] = "completed"

            elif request.skill_id == "receive-email-webhook":
                result = await self._handle_receive_email_webhook(request.payload)
                state["result"] = result
                state["status"] = "completed"

            else:
                logger.error("Unsupported skill", skill_id=request.skill_id)
                raise A2AError(
                    message=f"Unsupported skill: {request.skill_id}",
                    agent_name=self.AGENT_NAME,
                    task_id=request.task_id,
                    skill_id=request.skill_id,
                )

            logger.info(
                "Task completed successfully",
                task_id=request.task_id,
                skill_id=request.skill_id,
            )

            return A2ATaskResponse(
                task_id=request.task_id,
                status="completed",
                result=state["result"],
            )

        except Exception as e:
            logger.error(
                "Task handling failed",
                task_id=request.task_id,
                error=str(e),
                error_type=type(e).__name__,
            )

            state["status"] = "failed"
            state["error"] = str(e)

            return A2ATaskResponse(
                task_id=request.task_id,
                status="failed",
                error=str(e),
            )

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

        # Compose email using LLM
        logger.info("Composing email with LLM")
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

        # Send email via SMTP
        logger.info("Sending email via SMTP")
        message_id = await self.smtp_client.send_email(
            to_address=send_payload["to_address"],
            subject=composed["subject"],
            body_text=composed["body"],
            thread_id=send_payload["thread_id"],
        )

        logger.info("Email sent successfully", message_id=message_id)

        # Create result
        result: SendEmailResult = {
            "message_id": message_id,
            "to_address": send_payload["to_address"],
            "subject": composed["subject"],
            "body_preview": composed["body"][:200],
            "sent_at": datetime.utcnow().isoformat(),
        }

        return result

    async def _handle_receive_email_webhook(
        self,
        payload: dict[str, Any],
    ) -> ReceiveEmailWebhookResult:
        """
        Handle receive-email-webhook skill.

        Parses incoming email and extracts structured data.

        Args:
            payload: Webhook payload with email data.

        Returns:
            Receive email webhook result with parsed data.

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
        required_fields = ["event", "message_id", "from_address", "to_address", "subject", "body", "received_at"]
        for field in required_fields:
            if not webhook_payload.get(field):  # type: ignore
                logger.error(f"Missing required field: {field}")
                raise ValidationError(
                    message=f"Missing required field: {field}",
                    field=field,
                )

        # Parse email content using LLM
        logger.info("Parsing email content with LLM")
        parsed_data = await self.parser.parse_email(
            from_address=webhook_payload["from_address"],
            subject=webhook_payload["subject"],
            body=webhook_payload["body"],
        )

        logger.info(
            "Email parsed successfully",
            intent=parsed_data.get("intent"),
            requires_response=parsed_data.get("requires_response"),
        )

        # Create result
        result: ReceiveEmailWebhookResult = {
            "message_id": webhook_payload["message_id"],
            "from_address": webhook_payload["from_address"],
            "subject": webhook_payload["subject"],
            "parsed_data": parsed_data,
            "processed_at": datetime.utcnow().isoformat(),
        }

        return result
