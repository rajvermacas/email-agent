"""
Webhook notifier for email events.

This module provides functionality to send webhook notifications when email
events occur (e.g., new email received). Uses httpx for async HTTP requests
with timeout and retry handling.

Usage:
    from info_agent.email.webhook import WebhookNotifier

    notifier = WebhookNotifier(webhook_url="http://example.com/webhook")
    await notifier.notify(email)
"""

from datetime import datetime

import httpx

from info_agent.config import get_settings
from info_agent.email.models import StoredEmail, WebhookPayload
from info_agent.utils.exceptions import EmailError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class WebhookNotifier:
    """
    Async webhook notifier for email events.

    Sends HTTP POST requests to configured webhook URLs when email events occur.
    Includes timeout handling and comprehensive logging.
    """

    def __init__(self, webhook_url: str | None = None) -> None:
        """
        Initialize webhook notifier.

        Args:
            webhook_url: URL to send webhook notifications to. If None, uses config.

        Raises:
            EmailError: If webhook URL is not provided or invalid.
        """
        if webhook_url is None:
            settings = get_settings()
            webhook_url = settings.email_webhook_url

        if not webhook_url:
            raise EmailError(
                message="Webhook URL is required",
                details={"webhook_url": webhook_url},
            )

        if not webhook_url.startswith(("http://", "https://")):
            raise EmailError(
                message="Webhook URL must start with http:// or https://",
                details={"webhook_url": webhook_url},
            )

        self.webhook_url = webhook_url
        self.timeout = 30.0  # 30 seconds timeout
        logger.info(
            "WebhookNotifier initialized",
            webhook_url=self.webhook_url,
            timeout=self.timeout,
        )

    async def notify(self, email: StoredEmail) -> None:
        """
        Send webhook notification for an email event.

        Args:
            email: Email that triggered the event.

        Raises:
            EmailError: If webhook notification fails.
        """
        logger.info(
            "Sending webhook notification",
            webhook_url=self.webhook_url,
            message_id=email.id,
            from_address=email.from_address,
            to_address=email.to_address,
            subject=email.subject,
        )

        if not email.id:
            raise EmailError(
                message="Email ID is required for webhook notification",
                details={"email": email.model_dump()},
            )

        # Create webhook payload
        payload = WebhookPayload(
            event="email.received",
            message_id=email.id,
            thread_id=email.thread_id,
            from_address=email.from_address,
            to_address=email.to_address,
            subject=email.subject,
            body=email.body_text,
            attachments=[att.model_dump() for att in email.attachments],
            received_at=email.received_at.isoformat(),
        )

        logger.debug(
            "Webhook payload created",
            message_id=email.id,
            event=payload.event,
            attachment_count=len(payload.attachments),
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(
                    "Sending HTTP POST to webhook",
                    webhook_url=self.webhook_url,
                    message_id=email.id,
                )

                response = await client.post(
                    self.webhook_url,
                    json=payload.model_dump(),
                    headers={"Content-Type": "application/json"},
                )

                logger.info(
                    "Webhook notification sent",
                    webhook_url=self.webhook_url,
                    message_id=email.id,
                    status_code=response.status_code,
                    response_time_ms=response.elapsed.total_seconds() * 1000,
                )

                # Log response details
                if response.status_code >= 400:
                    logger.warning(
                        "Webhook returned error status",
                        webhook_url=self.webhook_url,
                        message_id=email.id,
                        status_code=response.status_code,
                        response_body=response.text[:500],  # Log first 500 chars
                    )
                else:
                    logger.debug(
                        "Webhook accepted successfully",
                        webhook_url=self.webhook_url,
                        message_id=email.id,
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException as e:
            logger.error(
                "Webhook notification timed out",
                webhook_url=self.webhook_url,
                message_id=email.id,
                timeout=self.timeout,
                error=str(e),
            )
            raise EmailError(
                message=f"Webhook notification timed out after {self.timeout}s",
                email_id=email.id,
                details={
                    "webhook_url": self.webhook_url,
                    "timeout": self.timeout,
                    "error": str(e),
                },
            ) from e

        except httpx.ConnectError as e:
            logger.error(
                "Failed to connect to webhook URL",
                webhook_url=self.webhook_url,
                message_id=email.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Failed to connect to webhook URL: {e}",
                email_id=email.id,
                details={
                    "webhook_url": self.webhook_url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

        except httpx.HTTPError as e:
            logger.error(
                "HTTP error during webhook notification",
                webhook_url=self.webhook_url,
                message_id=email.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"HTTP error during webhook notification: {e}",
                email_id=email.id,
                details={
                    "webhook_url": self.webhook_url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

        except Exception as e:
            logger.error(
                "Unexpected error during webhook notification",
                webhook_url=self.webhook_url,
                message_id=email.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Unexpected error during webhook notification: {e}",
                email_id=email.id,
                details={
                    "webhook_url": self.webhook_url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e
