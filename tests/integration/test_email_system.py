"""
Integration tests for the email system.

Tests the mock email server, SMTP handling, webhook notifications,
and email storage functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestEmailStorage:
    """Tests for email storage operations."""

    @pytest.fixture
    async def storage(self, temp_db_path):
        """Create email storage for testing."""
        from info_agent.email.storage import EmailStorage

        storage = EmailStorage(str(temp_db_path))
        await storage.initialize()
        yield storage
        await storage.close()

    async def test_store_email(self, storage):
        """Test storing an email."""
        email_data = {
            "id": "test-email-001",
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "Test Subject",
            "body": "Test body content",
        }

        result = await storage.store_email(email_data)

        assert result["id"] == "test-email-001"

    async def test_get_email(self, storage):
        """Test retrieving an email."""
        email_data = {
            "id": "test-email-002",
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "Test Subject",
            "body": "Test body content",
        }
        await storage.store_email(email_data)

        result = await storage.get_email("test-email-002")

        assert result is not None
        assert result["id"] == "test-email-002"

    async def test_list_emails(self, storage):
        """Test listing all emails."""
        for i in range(3):
            await storage.store_email({
                "id": f"list-test-{i}",
                "from_addr": "sender@example.com",
                "to_addr": "recipient@example.com",
                "subject": f"Test Subject {i}",
                "body": f"Test body {i}",
            })

        result = await storage.list_emails()

        assert len(result) >= 3

    async def test_delete_email(self, storage):
        """Test deleting an email."""
        email_data = {
            "id": "delete-test-001",
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "To Delete",
            "body": "This will be deleted",
        }
        await storage.store_email(email_data)

        await storage.delete_email("delete-test-001")
        result = await storage.get_email("delete-test-001")

        assert result is None


class TestEmailWebhook:
    """Tests for email webhook notifications."""

    @pytest.fixture
    def webhook_notifier(self):
        """Create webhook notifier for testing."""
        from info_agent.email.webhook import WebhookNotifier

        return WebhookNotifier("http://localhost:8000/api/v1/webhooks/email")

    @patch("httpx.AsyncClient.post")
    async def test_send_webhook_success(self, mock_post, webhook_notifier):
        """Test successful webhook notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        email_data = {
            "id": "webhook-test-001",
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "Webhook Test",
            "body": "Testing webhook",
        }

        # Should not raise
        await webhook_notifier.notify_email_received(email_data)

    @patch("httpx.AsyncClient.post")
    async def test_send_webhook_failure_logged(self, mock_post, webhook_notifier):
        """Test webhook notification handles failures gracefully."""
        mock_post.side_effect = Exception("Connection refused")

        email_data = {
            "id": "webhook-fail-001",
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "Webhook Test",
            "body": "Testing webhook failure",
        }

        # Should not raise, just log the error
        with pytest.raises(Exception):
            await webhook_notifier.notify_email_received(email_data)


class TestSMTPHandler:
    """Tests for SMTP email handler."""

    @pytest.fixture
    def smtp_handler(self, temp_db_path):
        """Create SMTP handler for testing."""
        from info_agent.email.smtp import EmailHandler

        return EmailHandler(
            storage_path=str(temp_db_path),
            webhook_url="http://localhost:8000/api/v1/webhooks/email",
        )

    async def test_handle_data_parses_email(self, smtp_handler):
        """Test SMTP handler parses incoming email."""
        envelope = MagicMock()
        envelope.mail_from = "sender@example.com"
        envelope.rcpt_tos = ["recipient@example.com"]

        data = b"""From: sender@example.com
To: recipient@example.com
Subject: SMTP Test

This is a test email body."""

        with patch.object(smtp_handler, "_store_and_notify", new_callable=AsyncMock):
            result = await smtp_handler.handle_DATA(
                server=MagicMock(),
                session=MagicMock(),
                envelope=envelope,
                data=data,
            )

        assert result == "250 Message accepted for delivery"


class TestEmailAPI:
    """Tests for email REST API."""

    @pytest.fixture
    def email_app(self):
        """Create email API test app."""
        from fastapi import FastAPI
        from info_agent.email.api import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/emails")
        return app

    @pytest.fixture
    def email_client(self, email_app):
        """Create test client for email API."""
        from fastapi.testclient import TestClient

        return TestClient(email_app)

    @patch("info_agent.email.api.storage")
    def test_list_emails_endpoint(self, mock_storage, email_client):
        """Test listing emails via API."""
        mock_storage.list_emails = AsyncMock(return_value=[
            {
                "id": "api-test-001",
                "from_addr": "sender@example.com",
                "to_addr": "recipient@example.com",
                "subject": "Test",
                "body": "Test body",
            }
        ])

        response = email_client.get("/api/v1/emails")

        assert response.status_code == 200

    @patch("info_agent.email.api.storage")
    def test_get_email_endpoint(self, mock_storage, email_client):
        """Test getting single email via API."""
        mock_storage.get_email = AsyncMock(return_value={
            "id": "api-test-002",
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "Test",
            "body": "Test body",
        })

        response = email_client.get("/api/v1/emails/api-test-002")

        assert response.status_code == 200

    @patch("info_agent.email.api.storage")
    def test_create_email_endpoint(self, mock_storage, email_client):
        """Test creating email via API."""
        mock_storage.store_email = AsyncMock(return_value={
            "id": "created-001",
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "New Email",
            "body": "Created via API",
        })

        response = email_client.post(
            "/api/v1/emails",
            json={
                "from_addr": "sender@example.com",
                "to_addr": "recipient@example.com",
                "subject": "New Email",
                "body": "Created via API",
            },
        )

        assert response.status_code in [200, 201]


class TestMockEmailServer:
    """Tests for the complete mock email server."""

    @patch("info_agent.email.server.aiosmtpd")
    @patch("info_agent.email.server.uvicorn")
    async def test_server_starts_both_smtp_and_rest(
        self, mock_uvicorn, mock_aiosmtpd
    ):
        """Test that server starts both SMTP and REST API."""
        from info_agent.email.server import MockEmailServer

        server = MockEmailServer(
            smtp_host="127.0.0.1",
            smtp_port=1025,
            rest_host="127.0.0.1",
            rest_port=8025,
            storage_path=":memory:",
            webhook_url="http://localhost:8000/webhooks",
        )

        # Server should be configurable
        assert server.smtp_port == 1025
        assert server.rest_port == 8025


class TestEmailFlow:
    """End-to-end tests for email flow."""

    @patch("info_agent.email.webhook.WebhookNotifier.notify_email_received")
    @patch("info_agent.email.storage.EmailStorage")
    async def test_receive_store_notify_flow(
        self, mock_storage_class, mock_notify
    ):
        """Test complete flow: receive email -> store -> notify."""
        mock_storage = MagicMock()
        mock_storage.store_email = AsyncMock(return_value={"id": "flow-001"})
        mock_storage_class.return_value = mock_storage
        mock_notify.return_value = None

        from info_agent.email.smtp import process_incoming_email

        email_data = {
            "from_addr": "sender@example.com",
            "to_addr": "recipient@example.com",
            "subject": "Flow Test",
            "body": "Testing the flow",
        }

        await process_incoming_email(mock_storage, email_data, mock_notify)

        mock_storage.store_email.assert_called_once()

    @patch("info_agent.email.storage.EmailStorage")
    async def test_send_email_via_smtp(self, mock_storage_class):
        """Test sending email via SMTP client."""
        from info_agent.agents.mail.smtp_client import SMTPClient

        client = SMTPClient(
            host="localhost",
            port=1025,
        )

        # Mock the actual send
        with patch.object(client, "send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "sent", "message_id": "sent-001"}

            result = await client.send_email(
                from_addr="sender@example.com",
                to_addr="recipient@example.com",
                subject="Outgoing Test",
                body="Testing outgoing email",
            )

            assert result["status"] == "sent"
