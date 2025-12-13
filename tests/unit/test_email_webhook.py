"""
Unit tests for email webhook notifier.

Tests the WebhookNotifier class from src/info_agent/email/webhook.py:
- Initialization with URL validation
- Sending webhook notifications
- HTTP error handling
- Timeout handling
- Connection error handling

Uses mocked httpx to avoid actual HTTP requests.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import httpx

from info_agent.email.models import EmailAttachment, StoredEmail
from info_agent.email.webhook import WebhookNotifier
from info_agent.utils.exceptions import EmailError


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock()
    settings.email_webhook_url = "http://localhost:8000/webhooks/email"
    return settings


@pytest.fixture
def test_attachment():
    """Create a test email attachment."""
    return EmailAttachment(
        filename="test.pdf",
        content_type="application/pdf",
        size=1024,
        content="YmFzZTY0IGNvbnRlbnQ=",
    )


@pytest.fixture
def test_email(test_attachment):
    """Create a test stored email."""
    return StoredEmail(
        id="msg-test123",
        inbox="user@example.com",
        thread_id="thread-abc",
        from_address="sender@example.com",
        to_address="user@example.com",
        subject="Test Email",
        body_text="This is a test email.",
        attachments=[test_attachment],
        received_at=datetime(2025, 12, 13, 10, 30, 0, tzinfo=timezone.utc),
        read=False,
    )


@pytest.fixture
def test_email_no_attachments():
    """Create a test stored email without attachments."""
    return StoredEmail(
        id="msg-simple",
        inbox="user@example.com",
        thread_id=None,
        from_address="sender@example.com",
        to_address="user@example.com",
        subject="Simple Email",
        body_text="Simple body.",
        attachments=[],
        received_at=datetime(2025, 12, 13, 11, 0, 0, tzinfo=timezone.utc),
        read=False,
    )


class TestWebhookNotifierInit:
    """Tests for WebhookNotifier initialization."""

    def test_init_with_explicit_url(self):
        """Test initialization with explicit webhook URL."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        assert notifier.webhook_url == "http://example.com/webhook"
        assert notifier.timeout == 30.0

    @patch("info_agent.email.webhook.get_settings")
    def test_init_with_settings_url(self, mock_get_settings, mock_settings):
        """Test initialization with URL from settings."""
        mock_get_settings.return_value = mock_settings

        notifier = WebhookNotifier()

        assert notifier.webhook_url == "http://localhost:8000/webhooks/email"
        mock_get_settings.assert_called_once()

    def test_init_empty_url_fails(self):
        """Test that empty webhook URL raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            WebhookNotifier(webhook_url="")

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Webhook URL is required" in exc_info.value.message

    def test_init_none_url_without_settings_fails(self):
        """Test that None URL without valid settings raises EmailError."""
        with patch("info_agent.email.webhook.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.email_webhook_url = ""
            mock_get_settings.return_value = mock_settings

            with pytest.raises(EmailError) as exc_info:
                WebhookNotifier()

            assert exc_info.value.code == "EMAIL_ERROR"
            assert "Webhook URL is required" in exc_info.value.message

    def test_init_invalid_url_scheme_fails(self):
        """Test that URL without http/https scheme raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            WebhookNotifier(webhook_url="ftp://example.com/webhook")

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "must start with http:// or https://" in exc_info.value.message

    def test_init_missing_scheme_fails(self):
        """Test that URL without scheme raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            WebhookNotifier(webhook_url="example.com/webhook")

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "must start with http:// or https://" in exc_info.value.message

    def test_init_https_url_valid(self):
        """Test that HTTPS URLs are accepted."""
        notifier = WebhookNotifier(webhook_url="https://example.com/webhook")

        assert notifier.webhook_url == "https://example.com/webhook"


@patch("info_agent.email.webhook.logger")
class TestWebhookNotifierNotify:
    """Tests for sending webhook notifications."""

    @pytest.mark.asyncio
    async def test_notify_success(self, mock_logger, test_email):
        """Test successfully sending webhook notification."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.123

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await notifier.notify(test_email)

        # Verify HTTP request
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://example.com/webhook"

        # Verify payload
        payload = call_args[1]["json"]
        assert payload["event"] == "email.received"
        assert payload["message_id"] == "msg-test123"
        assert payload["thread_id"] == "thread-abc"
        assert payload["from_address"] == "sender@example.com"
        assert payload["to_address"] == "user@example.com"
        assert payload["subject"] == "Test Email"
        assert payload["body"] == "This is a test email."
        assert len(payload["attachments"]) == 1
        assert payload["received_at"] == "2025-12-13T10:30:00+00:00"

        # Verify headers
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_notify_with_no_attachments(self, mock_logger, test_email_no_attachments):
        """Test sending webhook for email without attachments."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await notifier.notify(test_email_no_attachments)

        # Verify payload has empty attachments
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["attachments"] == []
        assert payload["thread_id"] is None

    @pytest.mark.asyncio
    async def test_notify_empty_email_id_fails(self, mock_logger, test_email):
        """Test that email without ID raises EmailError."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        # Manually set ID to empty after construction
        test_email.id = ""

        with pytest.raises(EmailError) as exc_info:
            await notifier.notify(test_email)

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Email ID is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_notify_http_error_status(self, mock_logger, test_email):
        """Test handling of HTTP error status codes."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.elapsed.total_seconds.return_value = 0.1

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Should not raise exception, just log warning
            await notifier.notify(test_email)

        # Verify request was still made
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_timeout_error(self, mock_logger, test_email):
        """Test handling of request timeout."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("Request timed out")

        mock_client = AsyncMock()
        mock_client.post = mock_post

        with patch("httpx.AsyncClient") as mock_async_client_class:
            mock_async_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(EmailError) as exc_info:
                await notifier.notify(test_email)

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "timed out after 30.0s" in exc_info.value.message
        assert exc_info.value.email_id == "msg-test123"
        assert exc_info.value.details["webhook_url"] == "http://example.com/webhook"
        assert exc_info.value.details["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_notify_connection_error(self, mock_logger, test_email):
        """Test handling of connection errors."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        mock_client = AsyncMock()
        mock_client.post = mock_post

        with patch("httpx.AsyncClient") as mock_async_client_class:
            mock_async_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(EmailError) as exc_info:
                await notifier.notify(test_email)

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Failed to connect to webhook URL" in exc_info.value.message
        assert exc_info.value.email_id == "msg-test123"

    @pytest.mark.asyncio
    async def test_notify_http_error(self, mock_logger, test_email):
        """Test handling of generic HTTP errors."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        async def mock_post(*args, **kwargs):
            raise httpx.HTTPError("HTTP protocol error")

        mock_client = AsyncMock()
        mock_client.post = mock_post

        with patch("httpx.AsyncClient") as mock_async_client_class:
            mock_async_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(EmailError) as exc_info:
                await notifier.notify(test_email)

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "HTTP error during webhook notification" in exc_info.value.message
        assert exc_info.value.email_id == "msg-test123"

    @pytest.mark.asyncio
    async def test_notify_unexpected_error(self, mock_logger, test_email):
        """Test handling of unexpected errors."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        async def mock_post(*args, **kwargs):
            raise Exception("Unexpected error")

        mock_client = AsyncMock()
        mock_client.post = mock_post

        with patch("httpx.AsyncClient") as mock_async_client_class:
            mock_async_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(EmailError) as exc_info:
                await notifier.notify(test_email)

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Unexpected error during webhook notification" in exc_info.value.message
        assert exc_info.value.email_id == "msg-test123"

    @pytest.mark.asyncio
    async def test_notify_uses_configured_timeout(self, mock_logger, test_email):
        """Test that configured timeout is used in HTTP client."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient") as mock_async_client_class:
            mock_async_client_class.return_value = mock_client

            await notifier.notify(test_email)

            # Verify AsyncClient was created with timeout
            mock_async_client_class.assert_called_once_with(timeout=30.0)

    @pytest.mark.asyncio
    async def test_notify_payload_structure(self, mock_logger, test_email):
        """Test that webhook payload has correct structure."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await notifier.notify(test_email)

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]

        # Verify all required fields are present
        assert "event" in payload
        assert "message_id" in payload
        assert "thread_id" in payload
        assert "from_address" in payload
        assert "to_address" in payload
        assert "subject" in payload
        assert "body" in payload
        assert "attachments" in payload
        assert "received_at" in payload

        # Verify attachment structure
        assert len(payload["attachments"]) == 1
        attachment = payload["attachments"][0]
        assert "filename" in attachment
        assert "content_type" in attachment
        assert "size" in attachment
        assert "content" in attachment

    @pytest.mark.asyncio
    async def test_notify_4xx_error_response(self, mock_logger, test_email):
        """Test handling of 4xx client error responses."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request - Invalid payload"
        mock_response.elapsed.total_seconds.return_value = 0.1

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Should not raise exception for error status codes
            await notifier.notify(test_email)

        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_201_accepted_response(self, mock_logger, test_email):
        """Test handling of 201 Created response."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.elapsed.total_seconds.return_value = 0.1

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await notifier.notify(test_email)

        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_202_accepted_response(self, mock_logger, test_email):
        """Test handling of 202 Accepted response."""
        notifier = WebhookNotifier(webhook_url="http://example.com/webhook")

        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.elapsed.total_seconds.return_value = 0.1

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await notifier.notify(test_email)

        mock_client.post.assert_called_once()
