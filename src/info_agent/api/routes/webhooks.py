"""
Webhook endpoints for Info-Agent Gateway.

This module provides webhook endpoints to receive notifications from
external services, particularly the Mock Email Server.

Endpoints:
- POST /webhooks/email - Receive email notification from Mock Email Server
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status

from info_agent.api.models.requests import EmailWebhookPayload
from info_agent.config import get_settings
from info_agent.utils.exceptions import WorkflowError, WorkflowNotFoundError
from info_agent.utils.logging import bind_context, clear_context, get_logger
from info_agent.workflow.checkpointer import get_workflow_state
from info_agent.workflow.graph import get_compiled_workflow, resume_workflow

logger = get_logger(__name__)


def create_webhook_router() -> APIRouter:
    """
    Create the webhook router.

    Returns:
        APIRouter instance with webhook endpoints.
    """
    logger.info("Creating webhook router")

    router = APIRouter(
        prefix="/webhooks",
        tags=["Webhooks"],
        responses={
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "Internal server error"
            },
        },
    )

    @router.post(
        "/email",
        status_code=status.HTTP_202_ACCEPTED,
        summary="Email notification webhook",
        description="Receive email notifications from the Mock Email Server",
    )
    async def email_webhook(payload: EmailWebhookPayload) -> dict[str, Any]:
        """
        Receive email notification webhook from Mock Email Server.

        When an email is received by the Mock Email Server, it sends a
        webhook notification to this endpoint. The workflow processes
        the email and updates its state accordingly.

        Args:
            payload: Email webhook payload with email details.

        Returns:
            Dictionary with acceptance status and workflow information.

        Raises:
            HTTPException: If payload validation fails or processing errors occur.
        """
        logger.info(
            "Email webhook received",
            event=payload.event,
            message_id=payload.message_id,
            thread_id=payload.thread_id,
            from_address=payload.from_address,
            to_address=payload.to_address,
        )

        # Validate event type
        if payload.event != "email.received":
            logger.warning(
                "Email webhook ignored - unsupported event type",
                event=payload.event,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported event type: {payload.event}",
            )

        # Validate required fields
        if not payload.message_id:
            logger.error("Email webhook failed - missing message_id")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="message_id is required",
            )

        if not payload.thread_id:
            logger.error("Email webhook failed - missing thread_id")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="thread_id is required",
            )

        # Find workflow by thread_id
        workflow_id = await _find_workflow_by_thread_id(payload.thread_id)

        if workflow_id is None:
            logger.warning(
                "Email webhook ignored - no workflow found for thread",
                thread_id=payload.thread_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No workflow found for email thread: {payload.thread_id}",
            )

        # Bind workflow context for logging
        bind_context(workflow_id=workflow_id, thread_id=payload.thread_id)

        try:
            logger.info(
                "Processing email for workflow",
                workflow_id=workflow_id,
                subject=payload.subject,
            )

            # Prepare state updates with email response
            state_updates = {
                "received_response": payload.body,
                "received_response_subject": payload.subject,
                "received_attachments": [
                    {
                        "filename": att.get("filename", ""),
                        "size": att.get("size", 0),
                        "mime_type": att.get("mime_type", ""),
                        "content_path": att.get("content_path"),
                    }
                    for att in payload.attachments
                ],
                "updated_at": datetime.utcnow().isoformat(),
            }

            logger.debug(
                "Resuming workflow with email response",
                workflow_id=workflow_id,
                attachment_count=len(payload.attachments),
            )

            # Resume workflow with the email response
            try:
                result = await resume_workflow(
                    workflow_id=workflow_id,
                    updates=state_updates,
                )

                logger.info(
                    "Workflow resumed successfully with email",
                    workflow_id=workflow_id,
                    final_status=result.get("status", "unknown"),
                )

                return {
                    "status": "accepted",
                    "message": "Email received and workflow updated",
                    "workflow_id": workflow_id,
                    "thread_id": payload.thread_id,
                    "message_id": payload.message_id,
                    "workflow_status": result.get("status", "unknown"),
                }

            except WorkflowNotFoundError as e:
                logger.error(
                    "Workflow not found during resume",
                    workflow_id=workflow_id,
                    error=str(e),
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow not found: {workflow_id}",
                ) from e

            except WorkflowError as e:
                logger.error(
                    "Workflow processing failed",
                    workflow_id=workflow_id,
                    error=str(e),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Workflow processing failed: {e.message}",
                ) from e

            except Exception as e:
                logger.error(
                    "Unexpected error resuming workflow",
                    workflow_id=workflow_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process email: {str(e)}",
                ) from e

        finally:
            # Clear logging context
            clear_context()

    logger.info("Webhook router created successfully")
    return router


async def _find_workflow_by_thread_id(thread_id: str) -> str | None:
    """
    Find workflow ID by email thread ID.

    This searches through all workflow checkpoints to find a workflow
    that has the given email thread ID.

    Args:
        thread_id: Email thread ID to search for.

    Returns:
        Workflow ID if found, None otherwise.
    """
    logger.debug("Searching for workflow by thread_id", thread_id=thread_id)

    try:
        settings = get_settings()
        compiled_workflow = get_compiled_workflow()

        # List all workflow threads from the checkpoint database
        from info_agent.workflow.checkpointer import list_workflow_threads

        workflow_ids = await list_workflow_threads(settings.checkpoint_db_path)

        logger.debug(
            "Searching through workflows",
            total_workflows=len(workflow_ids),
            target_thread_id=thread_id,
        )

        # Search through each workflow for matching thread_id
        for workflow_id in workflow_ids:
            logger.debug("Checking workflow", workflow_id=workflow_id)

            state = await get_workflow_state(compiled_workflow, workflow_id)

            if state is None:
                logger.debug(
                    "Workflow has no state, skipping",
                    workflow_id=workflow_id,
                )
                continue

            # Check if this workflow has the matching thread_id
            state_thread_id = state.get("email_thread_id")

            if state_thread_id == thread_id:
                logger.info(
                    "Found workflow for thread",
                    workflow_id=workflow_id,
                    thread_id=thread_id,
                )
                return workflow_id

            logger.debug(
                "Thread ID mismatch, continuing search",
                workflow_id=workflow_id,
                state_thread_id=state_thread_id,
            )

        logger.warning(
            "No workflow found for thread_id",
            thread_id=thread_id,
            workflows_checked=len(workflow_ids),
        )
        return None

    except Exception as e:
        logger.error(
            "Error searching for workflow by thread_id",
            thread_id=thread_id,
            error=str(e),
        )
        return None
