"""
Unit tests for webhook manager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from info_agent.email_server.models import Email, EmailAddress
from info_agent.email_server.webhooks import WebhookManager
from info_agent.utils.exceptions import EmailServerError


class TestWebhookManagerRegister:
    """Tests for webhook registration."""

    def test_register_webhook(self) -> None:
        """Test registering a webhook."""
        manager = WebhookManager()

        webhook = manager.register(
            url="https://example.com/webhook",
            events=["email.received"],
        )

        assert webhook.url == "https://example.com/webhook"
        assert "email.received" in webhook.events
        assert webhook.active is True

    def test_register_with_secret(self) -> None:
        """Test registering webhook with secret."""
        manager = WebhookManager()

        webhook = manager.register(
            url="https://example.com/webhook",
            secret="my-secret",
        )

        assert webhook.secret == "my-secret"

    def test_register_empty_url_raises(self) -> None:
        """Test empty URL raises error."""
        manager = WebhookManager()

        with pytest.raises(EmailServerError) as exc_info:
            manager.register(url="")

        assert "required" in str(exc_info.value).lower()

    def test_register_invalid_event_raises(self) -> None:
        """Test invalid event type raises error."""
        manager = WebhookManager()

        with pytest.raises(EmailServerError) as exc_info:
            manager.register(
                url="https://example.com/webhook",
                events=["invalid.event"],
            )

        assert "invalid event" in str(exc_info.value).lower()

    def test_register_default_events(self) -> None:
        """Test default event subscription."""
        manager = WebhookManager()

        webhook = manager.register(url="https://example.com/webhook")

        assert "email.received" in webhook.events

    def test_register_with_metadata(self) -> None:
        """Test registering with metadata."""
        manager = WebhookManager()

        webhook = manager.register(
            url="https://example.com/webhook",
            metadata={"source": "test"},
        )

        assert webhook.metadata["source"] == "test"


class TestWebhookManagerUnregister:
    """Tests for webhook unregistration."""

    def test_unregister_webhook(self) -> None:
        """Test unregistering a webhook."""
        manager = WebhookManager()
        webhook = manager.register(url="https://example.com/webhook")

        result = manager.unregister(webhook.id)

        assert result is True
        assert manager.get(webhook.id) is None

    def test_unregister_nonexistent(self) -> None:
        """Test unregistering nonexistent webhook."""
        manager = WebhookManager()

        result = manager.unregister("nonexistent-id")

        assert result is False


class TestWebhookManagerGet:
    """Tests for getting webhooks."""

    def test_get_webhook(self) -> None:
        """Test getting a webhook by ID."""
        manager = WebhookManager()
        webhook = manager.register(url="https://example.com/webhook")

        result = manager.get(webhook.id)

        assert result is not None
        assert result.id == webhook.id

    def test_get_nonexistent(self) -> None:
        """Test getting nonexistent webhook."""
        manager = WebhookManager()

        result = manager.get("nonexistent-id")

        assert result is None


class TestWebhookManagerList:
    """Tests for listing webhooks."""

    def test_list_all(self) -> None:
        """Test listing all webhooks."""
        manager = WebhookManager()
        manager.register(url="https://example.com/hook1")
        manager.register(url="https://example.com/hook2")

        webhooks = manager.list_all()

        assert len(webhooks) == 2

    def test_list_active_only(self) -> None:
        """Test listing only active webhooks."""
        manager = WebhookManager()
        hook1 = manager.register(url="https://example.com/hook1")
        manager.register(url="https://example.com/hook2")

        manager.update(hook1.id, active=False)

        webhooks = manager.list_all(active_only=True)

        assert len(webhooks) == 1


class TestWebhookManagerUpdate:
    """Tests for updating webhooks."""

    def test_update_url(self) -> None:
        """Test updating webhook URL."""
        manager = WebhookManager()
        webhook = manager.register(url="https://example.com/webhook")

        updated = manager.update(webhook.id, url="https://new.com/webhook")

        assert updated.url == "https://new.com/webhook"

    def test_update_events(self) -> None:
        """Test updating webhook events."""
        manager = WebhookManager()
        webhook = manager.register(url="https://example.com/webhook")

        updated = manager.update(webhook.id, events=["email.sent"])

        assert "email.sent" in updated.events

    def test_update_active(self) -> None:
        """Test deactivating webhook."""
        manager = WebhookManager()
        webhook = manager.register(url="https://example.com/webhook")

        updated = manager.update(webhook.id, active=False)

        assert updated.active is False

    def test_update_nonexistent(self) -> None:
        """Test updating nonexistent webhook."""
        manager = WebhookManager()

        result = manager.update("nonexistent-id", url="https://new.com/webhook")

        assert result is None


class TestWebhookManagerSignature:
    """Tests for webhook signature generation."""

    def test_sign_payload(self) -> None:
        """Test signing a payload."""
        manager = WebhookManager()
        payload = '{"test": "data"}'
        secret = "my-secret"

        signature = manager._sign_payload(payload, secret)

        assert signature.startswith("sha256=")
        assert len(signature) > 7  # More than just "sha256="

    def test_sign_payload_consistent(self) -> None:
        """Test signature is consistent for same inputs."""
        manager = WebhookManager()
        payload = '{"test": "data"}'
        secret = "my-secret"

        sig1 = manager._sign_payload(payload, secret)
        sig2 = manager._sign_payload(payload, secret)

        assert sig1 == sig2


class TestWebhookManagerDispatch:
    """Tests for webhook event dispatch."""

    @pytest.mark.asyncio
    async def test_dispatch_to_subscribed(self) -> None:
        """Test dispatching to subscribed webhooks."""
        manager = WebhookManager()
        manager.register(
            url="https://example.com/webhook",
            events=["email.received"],
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client.return_value = mock_instance

            count = await manager.dispatch("email.received", {"email_id": "123"})

            assert count == 1

    @pytest.mark.asyncio
    async def test_dispatch_no_subscribers(self) -> None:
        """Test dispatching with no subscribers."""
        manager = WebhookManager()

        count = await manager.dispatch("email.received", {"email_id": "123"})

        assert count == 0

    @pytest.mark.asyncio
    async def test_dispatch_only_to_matching_events(self) -> None:
        """Test dispatch only reaches matching event subscriptions."""
        manager = WebhookManager()
        manager.register(
            url="https://example.com/webhook",
            events=["email.sent"],  # Different event
        )

        count = await manager.dispatch("email.received", {"email_id": "123"})

        assert count == 0

    @pytest.mark.asyncio
    async def test_dispatch_skips_inactive(self) -> None:
        """Test dispatch skips inactive webhooks."""
        manager = WebhookManager()
        webhook = manager.register(
            url="https://example.com/webhook",
            events=["email.received"],
        )
        manager.update(webhook.id, active=False)

        count = await manager.dispatch("email.received", {"email_id": "123"})

        assert count == 0


class TestWebhookManagerEmailEvents:
    """Tests for email-specific event dispatching."""

    def test_dispatch_email_event(self) -> None:
        """Test dispatching email event."""
        manager = WebhookManager()

        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="recipient@example.com")],
            subject="Test Subject",
        )

        # This should not raise
        manager.dispatch_email_event(
            WebhookManager.EVENT_EMAIL_RECEIVED,
            email,
        )


class TestWebhookManagerCounts:
    """Tests for webhook count methods."""

    def test_count(self) -> None:
        """Test counting webhooks."""
        manager = WebhookManager()
        manager.register(url="https://example.com/hook1")
        manager.register(url="https://example.com/hook2")

        assert manager.count() == 2

    def test_clear(self) -> None:
        """Test clearing webhooks."""
        manager = WebhookManager()
        manager.register(url="https://example.com/hook1")
        manager.register(url="https://example.com/hook2")

        count = manager.clear()

        assert count == 2
        assert manager.count() == 0


class TestWebhookManagerEventTypes:
    """Tests for event type constants."""

    def test_all_events_defined(self) -> None:
        """Test all expected events are defined."""
        assert WebhookManager.EVENT_EMAIL_RECEIVED == "email.received"
        assert WebhookManager.EVENT_EMAIL_SENT == "email.sent"
        assert WebhookManager.EVENT_EMAIL_DELIVERED == "email.delivered"
        assert WebhookManager.EVENT_EMAIL_FAILED == "email.failed"
        assert WebhookManager.EVENT_EMAIL_READ == "email.read"

    def test_all_events_list(self) -> None:
        """Test ALL_EVENTS list is complete."""
        assert len(WebhookManager.ALL_EVENTS) == 5
        assert "email.received" in WebhookManager.ALL_EVENTS
        assert "email.sent" in WebhookManager.ALL_EVENTS
