"""
FastAPI router for email REST API.

This module provides REST API endpoints for managing emails:
- List inboxes
- List messages in an inbox
- Get specific message
- Create message (simulate incoming)
- Reply to message
- Delete message

Usage:
    from info_agent.email.api import create_email_router

    router = create_email_router(storage, webhook_notifier)
    app.include_router(router)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from info_agent.email.models import CreateEmailRequest, EmailReplyRequest, StoredEmail
from info_agent.email.storage import EmailStorage
from info_agent.email.webhook import WebhookNotifier
from info_agent.utils.exceptions import EmailError, StorageError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


def create_email_router(
    storage: EmailStorage, webhook_notifier: WebhookNotifier | None = None
) -> APIRouter:
    """
    Create FastAPI router for email endpoints.

    Args:
        storage: Email storage instance.
        webhook_notifier: Optional webhook notifier.

    Returns:
        Configured APIRouter instance.

    Raises:
        EmailError: If storage is not provided.
    """
    if storage is None:
        raise EmailError(
            message="Storage is required for email API",
            details={"storage": storage},
        )

    logger.info(
        "Creating email API router", has_webhook=webhook_notifier is not None
    )

    router = APIRouter(prefix="/emails", tags=["emails"])

    @router.get("/inboxes", summary="List all inboxes")
    async def list_inboxes() -> dict:
        """
        List all inboxes that have received emails.

        Returns:
            Dictionary with list of inbox addresses.
        """
        logger.info("API: Listing all inboxes")
        try:
            inboxes = await storage.list_inboxes()
            logger.info("API: Inboxes listed successfully", count=len(inboxes))
            return {"inboxes": inboxes, "count": len(inboxes)}

        except StorageError as e:
            logger.error(
                "API: Failed to list inboxes",
                error=str(e),
                error_code=e.code,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.to_dict(),
            ) from e

        except Exception as e:
            logger.error(
                "API: Unexpected error listing inboxes",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)},
            ) from e

    @router.get(
        "/inboxes/{inbox}/messages", summary="Get messages for an inbox"
    )
    async def list_inbox_messages(inbox: str) -> dict:
        """
        List all messages for a specific inbox.

        Args:
            inbox: Email address of the inbox.

        Returns:
            Dictionary with list of messages.
        """
        logger.info("API: Listing messages for inbox", inbox=inbox)

        if not inbox:
            logger.warning("API: Empty inbox parameter provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Inbox parameter is required"},
            )

        try:
            emails = await storage.list_emails_by_inbox(inbox)
            logger.info(
                "API: Messages listed successfully", inbox=inbox, count=len(emails)
            )

            return {
                "inbox": inbox,
                "messages": [email.model_dump() for email in emails],
                "count": len(emails),
            }

        except StorageError as e:
            logger.error(
                "API: Failed to list messages",
                inbox=inbox,
                error=str(e),
                error_code=e.code,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.to_dict(),
            ) from e

        except Exception as e:
            logger.error(
                "API: Unexpected error listing messages",
                inbox=inbox,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)},
            ) from e

    @router.get("/messages/{message_id}", summary="Get a specific message")
    async def get_message(message_id: str) -> dict:
        """
        Get a specific email message by ID.

        Args:
            message_id: Unique message identifier.

        Returns:
            Email message data.
        """
        logger.info("API: Getting message", message_id=message_id)

        if not message_id:
            logger.warning("API: Empty message_id parameter provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Message ID parameter is required"},
            )

        try:
            email = await storage.get_email(message_id)

            if email is None:
                logger.warning("API: Message not found", message_id=message_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": f"Message not found: {message_id}"},
                )

            logger.info("API: Message retrieved successfully", message_id=message_id)
            return email.model_dump()

        except HTTPException:
            raise

        except StorageError as e:
            logger.error(
                "API: Failed to get message",
                message_id=message_id,
                error=str(e),
                error_code=e.code,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.to_dict(),
            ) from e

        except Exception as e:
            logger.error(
                "API: Unexpected error getting message",
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)},
            ) from e

    @router.post("/messages", status_code=status.HTTP_201_CREATED, summary="Create a message")
    async def create_message(request: CreateEmailRequest) -> dict:
        """
        Create a new email message (simulate incoming email).

        Args:
            request: Email creation request.

        Returns:
            Created email message data.
        """
        logger.info(
            "API: Creating message",
            from_address=request.from_address,
            to_address=request.to_address,
            subject=request.subject,
        )

        try:
            # Generate unique message ID
            message_id = f"msg-{uuid.uuid4().hex[:16]}"
            logger.debug("Generated message ID", message_id=message_id)

            # Create stored email
            email = StoredEmail(
                id=message_id,
                inbox=request.to_address,
                thread_id=request.thread_id,
                from_address=request.from_address,
                to_address=request.to_address,
                subject=request.subject,
                body_text=request.body_text,
                attachments=request.attachments,
                received_at=datetime.now(timezone.utc),
                read=False,
            )

            # Save to storage
            await storage.save_email(email)
            logger.info("API: Message created and stored", message_id=message_id)

            # Send webhook notification
            if webhook_notifier:
                try:
                    await webhook_notifier.notify(email)
                    logger.info("API: Webhook notification sent", message_id=message_id)
                except Exception as e:
                    # Log webhook error but don't fail the request
                    logger.error(
                        "API: Failed to send webhook notification",
                        message_id=message_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

            return email.model_dump()

        except StorageError as e:
            logger.error(
                "API: Failed to create message",
                error=str(e),
                error_code=e.code,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.to_dict(),
            ) from e

        except Exception as e:
            logger.error(
                "API: Unexpected error creating message",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)},
            ) from e

    @router.post(
        "/messages/{message_id}/reply",
        status_code=status.HTTP_201_CREATED,
        summary="Reply to a message",
    )
    async def reply_to_message(message_id: str, request: EmailReplyRequest) -> dict:
        """
        Reply to an existing email message.

        Args:
            message_id: ID of the message to reply to.
            request: Reply request data.

        Returns:
            Created reply message data.
        """
        logger.info("API: Replying to message", message_id=message_id)

        if not message_id:
            logger.warning("API: Empty message_id parameter provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Message ID parameter is required"},
            )

        try:
            # Get original message
            original = await storage.get_email(message_id)

            if original is None:
                logger.warning("API: Original message not found", message_id=message_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": f"Original message not found: {message_id}"},
                )

            # Generate reply message ID
            reply_id = f"msg-{uuid.uuid4().hex[:16]}"
            logger.debug("Generated reply message ID", reply_id=reply_id)

            # Create reply email
            reply = StoredEmail(
                id=reply_id,
                inbox=original.from_address,  # Reply goes to original sender
                thread_id=original.thread_id or original.id,
                from_address=original.to_address,  # From original recipient
                to_address=original.from_address,  # To original sender
                subject=f"Re: {original.subject}",
                body_text=request.body_text,
                attachments=request.attachments,
                received_at=datetime.now(timezone.utc),
                read=False,
            )

            # Save reply to storage
            await storage.save_email(reply)
            logger.info(
                "API: Reply created and stored",
                reply_id=reply_id,
                original_id=message_id,
            )

            # Send webhook notification for reply
            if webhook_notifier:
                try:
                    await webhook_notifier.notify(reply)
                    logger.info("API: Webhook notification sent for reply", reply_id=reply_id)
                except Exception as e:
                    # Log webhook error but don't fail the request
                    logger.error(
                        "API: Failed to send webhook notification for reply",
                        reply_id=reply_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

            return reply.model_dump()

        except HTTPException:
            raise

        except StorageError as e:
            logger.error(
                "API: Failed to create reply",
                message_id=message_id,
                error=str(e),
                error_code=e.code,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.to_dict(),
            ) from e

        except Exception as e:
            logger.error(
                "API: Unexpected error creating reply",
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)},
            ) from e

    @router.delete(
        "/messages/{message_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a message",
    )
    async def delete_message(message_id: str) -> None:
        """
        Delete an email message.

        Args:
            message_id: ID of the message to delete.
        """
        logger.info("API: Deleting message", message_id=message_id)

        if not message_id:
            logger.warning("API: Empty message_id parameter provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Message ID parameter is required"},
            )

        try:
            await storage.delete_email(message_id)
            logger.info("API: Message deleted successfully", message_id=message_id)

        except StorageError as e:
            logger.error(
                "API: Failed to delete message",
                message_id=message_id,
                error=str(e),
                error_code=e.code,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.to_dict(),
            ) from e

        except Exception as e:
            logger.error(
                "API: Unexpected error deleting message",
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)},
            ) from e

    return router
