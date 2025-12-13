"""
Webhook manager for email server.

Handles webhook registration, event dispatching, and delivery.
"""

import asyncio
import hashlib
import hmac
import threading
from typing import Any

import httpx
import structlog

from info_agent.email_server.models import Email, WebhookConfig, WebhookEvent
from info_agent.utils.exceptions import EmailServerError
from info_agent.utils.helpers import generate_uuid, safe_json_dumps

logger = structlog.get_logger(__name__)


class WebhookManager:
    """
    Manages webhook registrations and event delivery.

    Provides thread-safe webhook management with async delivery
    and retry capabilities.

    Attributes:
        _webhooks: Dictionary mapping webhook ID to WebhookConfig.
        _lock: Threading lock for thread-safe operations.
        _delivery_timeout: Timeout for webhook delivery in seconds.
        _max_retries: Maximum delivery retries.
    """

    # Event types supported by the webhook system
    EVENT_EMAIL_RECEIVED = "email.received"
    EVENT_EMAIL_SENT = "email.sent"
    EVENT_EMAIL_DELIVERED = "email.delivered"
    EVENT_EMAIL_FAILED = "email.failed"
    EVENT_EMAIL_READ = "email.read"

    ALL_EVENTS = [
        EVENT_EMAIL_RECEIVED,
        EVENT_EMAIL_SENT,
        EVENT_EMAIL_DELIVERED,
        EVENT_EMAIL_FAILED,
        EVENT_EMAIL_READ,
    ]

    def __init__(
        self,
        delivery_timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize webhook manager.

        Args:
            delivery_timeout: Timeout for webhook delivery in seconds.
            max_retries: Maximum number of delivery retries.
        """
        self._webhooks: dict[str, WebhookConfig] = {}
        self._lock = threading.RLock()
        self._delivery_timeout = delivery_timeout
        self._max_retries = max_retries
        self._pending_deliveries: list[asyncio.Task[Any]] = []

        logger.info(
            "webhook_manager_initialized",
            delivery_timeout=delivery_timeout,
            max_retries=max_retries,
        )

    def register(
        self,
        url: str,
        events: list[str] | None = None,
        secret: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WebhookConfig:
        """
        Register a new webhook.

        Args:
            url: URL to send webhook events to.
            events: List of event types to subscribe to.
            secret: Optional secret for signing payloads.
            metadata: Additional webhook metadata.

        Returns:
            Created WebhookConfig.

        Raises:
            EmailServerError: If registration fails.
        """
        with self._lock:
            if not url:
                raise EmailServerError(
                    message="Webhook URL is required",
                    details={"url": url},
                )

            # Validate event types
            if events:
                for event in events:
                    if event not in self.ALL_EVENTS:
                        raise EmailServerError(
                            message=f"Invalid event type: {event}",
                            details={
                                "event": event,
                                "valid_events": self.ALL_EVENTS,
                            },
                        )

            webhook = WebhookConfig(
                url=url,
                events=events or [self.EVENT_EMAIL_RECEIVED],
                secret=secret,
                metadata=metadata or {},
            )

            self._webhooks[webhook.id] = webhook

            logger.info(
                "webhook_registered",
                webhook_id=webhook.id,
                url=url,
                events=webhook.events,
            )

            return webhook

    def unregister(self, webhook_id: str) -> bool:
        """
        Unregister a webhook.

        Args:
            webhook_id: ID of webhook to unregister.

        Returns:
            True if unregistered, False if not found.
        """
        with self._lock:
            webhook = self._webhooks.pop(webhook_id, None)
            if webhook:
                logger.info("webhook_unregistered", webhook_id=webhook_id)
                return True

            logger.debug("webhook_not_found", webhook_id=webhook_id)
            return False

    def get(self, webhook_id: str) -> WebhookConfig | None:
        """
        Get a webhook by ID.

        Args:
            webhook_id: ID of webhook to retrieve.

        Returns:
            WebhookConfig if found, None otherwise.
        """
        with self._lock:
            return self._webhooks.get(webhook_id)

    def list_all(self, active_only: bool = False) -> list[WebhookConfig]:
        """
        List all registered webhooks.

        Args:
            active_only: If True, only return active webhooks.

        Returns:
            List of WebhookConfig objects.
        """
        with self._lock:
            all_webhooks = [w for w in self._webhooks.values()]
            if active_only:
                all_webhooks = [w for w in all_webhooks if w.active]
            return all_webhooks

    def update(
        self,
        webhook_id: str,
        url: str | None = None,
        events: list[str] | None = None,
        active: bool | None = None,
    ) -> WebhookConfig | None:
        """
        Update a webhook configuration.

        Args:
            webhook_id: ID of webhook to update.
            url: New URL (optional).
            events: New event list (optional).
            active: New active status (optional).

        Returns:
            Updated WebhookConfig if found, None otherwise.
        """
        with self._lock:
            webhook = self._webhooks.get(webhook_id)
            if not webhook:
                return None

            if url is not None:
                webhook.url = url
            if events is not None:
                webhook.events = events
            if active is not None:
                webhook.active = active

            logger.info(
                "webhook_updated",
                webhook_id=webhook_id,
                url=webhook.url,
                active=webhook.active,
            )

            return webhook

    def _sign_payload(self, payload: str, secret: str) -> str:
        """
        Sign a webhook payload with HMAC-SHA256.

        Args:
            payload: JSON payload string.
            secret: Secret key for signing.

        Returns:
            Hex-encoded signature.
        """
        signature = hmac.new(
            key=secret.encode("utf-8"),
            msg=payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"

    def _get_subscribed_webhooks(self, event_type: str) -> list[WebhookConfig]:
        """
        Get webhooks subscribed to an event type.

        Args:
            event_type: Event type to filter by.

        Returns:
            List of subscribed webhooks.
        """
        with self._lock:
            return [
                w
                for w in self._webhooks.values()
                if w.active and event_type in w.events
            ]

    async def _deliver_webhook(
        self,
        webhook: WebhookConfig,
        event: WebhookEvent,
        retry_count: int = 0,
    ) -> bool:
        """
        Deliver a webhook event to a single webhook.

        Args:
            webhook: Webhook to deliver to.
            event: Event to deliver.
            retry_count: Current retry attempt.

        Returns:
            True if delivered successfully, False otherwise.
        """
        payload = event.model_dump_json()

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": webhook.id,
            "X-Event-ID": event.id,
            "X-Event-Type": event.event_type,
        }

        if webhook.secret:
            headers["X-Signature"] = self._sign_payload(payload, webhook.secret)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook.url,
                    content=payload,
                    headers=headers,
                    timeout=self._delivery_timeout,
                )

                if response.status_code < 300:
                    logger.info(
                        "webhook_delivered",
                        webhook_id=webhook.id,
                        event_id=event.id,
                        status_code=response.status_code,
                    )
                    return True

                logger.warning(
                    "webhook_delivery_failed",
                    webhook_id=webhook.id,
                    event_id=event.id,
                    status_code=response.status_code,
                    response_text=response.text[:200] if response.text else "",
                )

        except httpx.TimeoutException:
            logger.warning(
                "webhook_delivery_timeout",
                webhook_id=webhook.id,
                event_id=event.id,
                retry_count=retry_count,
            )

        except Exception as e:
            logger.error(
                "webhook_delivery_error",
                webhook_id=webhook.id,
                event_id=event.id,
                error=str(e),
            )

        # Retry if attempts remaining
        if retry_count < self._max_retries:
            await asyncio.sleep(2**retry_count)  # Exponential backoff
            return await self._deliver_webhook(webhook, event, retry_count + 1)

        return False

    async def dispatch(self, event_type: str, data: dict[str, Any]) -> int:
        """
        Dispatch an event to all subscribed webhooks.

        Args:
            event_type: Type of event.
            data: Event data.

        Returns:
            Number of webhooks notified.
        """
        webhooks = self._get_subscribed_webhooks(event_type)
        if not webhooks:
            logger.debug("no_webhooks_subscribed", event_type=event_type)
            return 0

        event = WebhookEvent(
            event_type=event_type,
            data=data,
        )

        logger.info(
            "dispatching_webhook_event",
            event_id=event.id,
            event_type=event_type,
            webhook_count=len(webhooks),
        )

        # Dispatch to all webhooks concurrently
        tasks = [self._deliver_webhook(webhook, event) for webhook in webhooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)

        logger.info(
            "webhook_dispatch_completed",
            event_id=event.id,
            total=len(webhooks),
            success=success_count,
        )

        return success_count

    def dispatch_sync(self, event_type: str, data: dict[str, Any]) -> int:
        """
        Synchronous wrapper for dispatch.

        Args:
            event_type: Type of event.
            data: Event data.

        Returns:
            Number of webhooks notified.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.dispatch(event_type, data))

    def dispatch_email_event(
        self,
        event_type: str,
        email: Email,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Dispatch an email-related event.

        Args:
            event_type: Type of event.
            email: Email that triggered the event.
            extra_data: Additional event data.
        """
        data = {
            "email_id": email.id,
            "message_id": email.message_id,
            "from": str(email.from_address),
            "to": [str(addr) for addr in email.to_addresses],
            "subject": email.subject,
            "status": email.status.value,
            "thread_id": email.thread_id,
        }

        if extra_data:
            data.update(extra_data)

        # Run in background to not block caller
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.dispatch(event_type, data))
        except RuntimeError:
            # No running loop, use sync version
            self.dispatch_sync(event_type, data)

    def count(self) -> int:
        """
        Get count of registered webhooks.

        Returns:
            Number of registered webhooks.
        """
        with self._lock:
            return len(self._webhooks)

    def clear(self) -> int:
        """
        Clear all registered webhooks.

        Returns:
            Number of webhooks cleared.
        """
        with self._lock:
            count = len(self._webhooks)
            self._webhooks.clear()
            logger.info("webhooks_cleared", count=count)
            return count
