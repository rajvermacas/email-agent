"""
Webhook routes for the Gateway.

This module provides endpoints for receiving webhook notifications
from external services like the mock email server.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException

from info_agent.gateway.models import (
    AgentWebhookPayload,
    EmailWebhookPayload,
    WebhookResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/email", response_model=WebhookResponse)
async def receive_email_webhook(
    payload: EmailWebhookPayload,
    request: Request,
) -> WebhookResponse:
    """
    Receive email webhook notifications from the mock email server.

    This endpoint is called when new emails arrive or are sent.
    The supervisor uses this to track email threads and trigger
    workflow state transitions.

    Args:
        payload: Email webhook payload.
        request: FastAPI request with app state.

    Returns:
        WebhookResponse indicating success or failure.

    Raises:
        HTTPException: If webhook processing fails.
    """
    logger.info(
        "Received email webhook: event_type=%s, message_id=%s, inbox=%s",
        payload.event_type,
        payload.message_id,
        payload.inbox,
    )

    try:
        supervisor = getattr(request.app.state, "supervisor", None)
        if supervisor is None:
            logger.error("Supervisor not available for webhook processing")
            raise HTTPException(
                status_code=503,
                detail="Supervisor not available",
            )

        # Process the email webhook
        await _process_email_webhook(supervisor, payload)

        logger.info(
            "Email webhook processed successfully: message_id=%s",
            payload.message_id,
        )

        return WebhookResponse(
            success=True,
            message=f"Email webhook processed: {payload.event_type}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process email webhook: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {e}",
        ) from e


@router.post("/agent", response_model=WebhookResponse)
async def receive_agent_webhook(
    payload: AgentWebhookPayload,
    request: Request,
) -> WebhookResponse:
    """
    Receive agent webhook notifications from worker agents.

    This endpoint is called when worker agents complete tasks
    or need to report status updates.

    Args:
        payload: Agent webhook payload.
        request: FastAPI request with app state.

    Returns:
        WebhookResponse indicating success or failure.

    Raises:
        HTTPException: If webhook processing fails.
    """
    logger.info(
        "Received agent webhook: event_type=%s, agent_id=%s, task_id=%s",
        payload.event_type,
        payload.agent_id,
        payload.task_id,
    )

    try:
        supervisor = getattr(request.app.state, "supervisor", None)
        if supervisor is None:
            logger.error("Supervisor not available for webhook processing")
            raise HTTPException(
                status_code=503,
                detail="Supervisor not available",
            )

        # Process the agent webhook
        await _process_agent_webhook(supervisor, payload)

        logger.info(
            "Agent webhook processed successfully: task_id=%s",
            payload.task_id,
        )

        return WebhookResponse(
            success=True,
            message=f"Agent webhook processed: {payload.event_type}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process agent webhook: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {e}",
        ) from e


async def _process_email_webhook(
    supervisor,
    payload: EmailWebhookPayload,
) -> None:
    """
    Process an email webhook payload.

    Args:
        supervisor: SupervisorAgent instance.
        payload: Email webhook payload.
    """
    logger.debug(
        "Processing email webhook: event_type=%s, from=%s, to=%s",
        payload.event_type,
        payload.from_address,
        payload.to_address,
    )

    event_type = payload.event_type

    if event_type == "email.received":
        logger.info(
            "New email received: from=%s, subject=%s",
            payload.from_address,
            payload.subject,
        )
        # In a full implementation, this would:
        # 1. Find the workflow associated with this email thread
        # 2. Parse the email content
        # 3. Determine if it's a clarification question or document
        # 4. Trigger appropriate workflow state transition

    elif event_type == "email.sent":
        logger.info(
            "Email sent: to=%s, subject=%s",
            payload.to_address,
            payload.subject,
        )
        # Log sent email for audit trail

    elif event_type == "email.bounced":
        logger.warning(
            "Email bounced: to=%s, subject=%s",
            payload.to_address,
            payload.subject,
        )
        # Handle bounce - might need to escalate

    else:
        logger.warning("Unknown email event type: %s", event_type)


async def _process_agent_webhook(
    supervisor,
    payload: AgentWebhookPayload,
) -> None:
    """
    Process an agent webhook payload.

    Args:
        supervisor: SupervisorAgent instance.
        payload: Agent webhook payload.
    """
    logger.debug(
        "Processing agent webhook: event_type=%s, agent=%s, task=%s",
        payload.event_type,
        payload.agent_id,
        payload.task_id,
    )

    event_type = payload.event_type

    if event_type == "task.completed":
        logger.info(
            "Task completed: agent=%s, task=%s",
            payload.agent_id,
            payload.task_id,
        )
        # In a full implementation, this would:
        # 1. Find the workflow associated with this task
        # 2. Update workflow state with task result
        # 3. Trigger next workflow step

    elif event_type == "task.failed":
        logger.error(
            "Task failed: agent=%s, task=%s, error=%s",
            payload.agent_id,
            payload.task_id,
            payload.error,
        )
        # Handle task failure - might need to retry or escalate

    elif event_type == "task.progress":
        logger.debug(
            "Task progress: agent=%s, task=%s",
            payload.agent_id,
            payload.task_id,
        )
        # Update progress indicator in UI

    else:
        logger.warning("Unknown agent event type: %s", event_type)


logger.info("Webhook routes module initialized")
