"""
Unit tests for REST API.
"""

import pytest
from fastapi.testclient import TestClient

from info_agent.email_server.models import Email, EmailAddress, EmailStatus
from info_agent.email_server.rest_api import create_email_server_app
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.webhooks import WebhookManager


@pytest.fixture
def storage() -> EmailStorage:
    """Create test storage."""
    return EmailStorage()


@pytest.fixture
def webhook_manager() -> WebhookManager:
    """Create test webhook manager."""
    return WebhookManager()


@pytest.fixture
def client(storage: EmailStorage, webhook_manager: WebhookManager) -> TestClient:
    """Create test client."""
    app = create_email_server_app(storage, webhook_manager)
    return TestClient(app)


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check returns healthy."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["email_count"] == 0


class TestEmailListAPI:
    """Tests for email list endpoint."""

    def test_list_empty_mailbox(self, client: TestClient) -> None:
        """Test listing empty mailbox."""
        response = client.get(
            "/api/emails", params={"address": "user@example.com", "mailbox": "inbox"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["emails"] == []

    def test_list_with_emails(
        self, client: TestClient, storage: EmailStorage
    ) -> None:
        """Test listing mailbox with emails."""
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="user@example.com")],
            subject="Test",
            mailbox="inbox",
        )
        storage.store(email)

        response = client.get(
            "/api/emails", params={"address": "user@example.com", "mailbox": "inbox"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["emails"]) == 1

    def test_list_pagination(
        self, client: TestClient, storage: EmailStorage
    ) -> None:
        """Test pagination in list."""
        for i in range(10):
            storage.store(
                Email(
                    from_address=EmailAddress(address="sender@example.com"),
                    to_addresses=[EmailAddress(address="user@example.com")],
                    mailbox="inbox",
                )
            )

        response = client.get(
            "/api/emails",
            params={
                "address": "user@example.com",
                "mailbox": "inbox",
                "page": 1,
                "page_size": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert len(data["emails"]) == 5
        assert data["has_more"] is True


class TestEmailGetAPI:
    """Tests for getting individual emails."""

    def test_get_email(self, client: TestClient, storage: EmailStorage) -> None:
        """Test getting an email by ID."""
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="Test Subject",
        )
        storage.store(email)

        response = client.get(f"/api/emails/{email.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["subject"] == "Test Subject"

    def test_get_nonexistent_email(self, client: TestClient) -> None:
        """Test getting nonexistent email returns 404."""
        response = client.get("/api/emails/nonexistent-id")

        assert response.status_code == 404


class TestEmailSearchAPI:
    """Tests for email search endpoint."""

    def test_search_emails(self, client: TestClient, storage: EmailStorage) -> None:
        """Test searching emails."""
        storage.store(
            Email(
                from_address=EmailAddress(address="sender@example.com"),
                subject="Important meeting tomorrow",
            )
        )
        storage.store(
            Email(
                from_address=EmailAddress(address="sender@example.com"),
                subject="Random topic",
            )
        )

        response = client.get("/api/emails/search", params={"query": "meeting"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestEmailSendAPI:
    """Tests for sending emails."""

    def test_send_email(self, client: TestClient, storage: EmailStorage) -> None:
        """Test sending an email."""
        response = client.post(
            "/api/emails",
            json={
                "from_address": "sender@example.com",
                "to_addresses": ["recipient@example.com"],
                "subject": "Test Subject",
                "body_text": "Test body",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["subject"] == "Test Subject"
        assert data["status"] == "sent"


class TestEmailMarkReadAPI:
    """Tests for marking emails as read."""

    def test_mark_as_read(self, client: TestClient, storage: EmailStorage) -> None:
        """Test marking email as read."""
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            status=EmailStatus.RECEIVED,
        )
        storage.store(email)

        response = client.post(f"/api/emails/{email.id}/read")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "read"

    def test_mark_nonexistent_as_read(self, client: TestClient) -> None:
        """Test marking nonexistent email as read returns 404."""
        response = client.post("/api/emails/nonexistent-id/read")

        assert response.status_code == 404


class TestEmailDeleteAPI:
    """Tests for deleting emails."""

    def test_delete_email(self, client: TestClient, storage: EmailStorage) -> None:
        """Test deleting an email."""
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
        )
        storage.store(email)

        response = client.delete(f"/api/emails/{email.id}")

        assert response.status_code == 204
        assert storage.get(email.id) is None

    def test_delete_nonexistent_email(self, client: TestClient) -> None:
        """Test deleting nonexistent email returns 404."""
        response = client.delete("/api/emails/nonexistent-id")

        assert response.status_code == 404


class TestThreadAPI:
    """Tests for thread endpoint."""

    def test_get_thread(self, client: TestClient, storage: EmailStorage) -> None:
        """Test getting emails in a thread."""
        original = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="Original",
        )
        storage.store(original)

        reply = Email(
            from_address=EmailAddress(address="recipient@example.com"),
            in_reply_to=original.message_id,
            subject="Re: Original",
        )
        storage.store(reply)

        response = client.get(f"/api/emails/threads/{original.thread_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_nonexistent_thread(self, client: TestClient) -> None:
        """Test getting nonexistent thread returns 404."""
        response = client.get("/api/emails/threads/nonexistent-id")

        assert response.status_code == 404


class TestStatsAPI:
    """Tests for stats endpoint."""

    def test_get_stats(self, client: TestClient, storage: EmailStorage) -> None:
        """Test getting storage stats."""
        storage.store(
            Email(from_address=EmailAddress(address="sender@example.com"))
        )

        response = client.get("/api/emails/stats/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_emails"] == 1


class TestWebhookListAPI:
    """Tests for webhook list endpoint."""

    def test_list_webhooks(
        self, client: TestClient, webhook_manager: WebhookManager
    ) -> None:
        """Test listing webhooks."""
        webhook_manager.register(url="https://example.com/webhook")

        response = client.get("/api/webhooks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestWebhookRegisterAPI:
    """Tests for webhook registration endpoint."""

    def test_register_webhook(self, client: TestClient) -> None:
        """Test registering a webhook."""
        response = client.post(
            "/api/webhooks", params={"url": "https://example.com/webhook"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com/webhook"


class TestWebhookGetAPI:
    """Tests for getting individual webhooks."""

    def test_get_webhook(
        self, client: TestClient, webhook_manager: WebhookManager
    ) -> None:
        """Test getting a webhook."""
        webhook = webhook_manager.register(url="https://example.com/webhook")

        response = client.get(f"/api/webhooks/{webhook.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://example.com/webhook"

    def test_get_nonexistent_webhook(self, client: TestClient) -> None:
        """Test getting nonexistent webhook returns 404."""
        response = client.get("/api/webhooks/nonexistent-id")

        assert response.status_code == 404


class TestWebhookUpdateAPI:
    """Tests for updating webhooks."""

    def test_update_webhook(
        self, client: TestClient, webhook_manager: WebhookManager
    ) -> None:
        """Test updating a webhook."""
        webhook = webhook_manager.register(url="https://example.com/webhook")

        response = client.patch(
            f"/api/webhooks/{webhook.id}",
            params={"url": "https://new.com/webhook"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://new.com/webhook"


class TestWebhookDeleteAPI:
    """Tests for deleting webhooks."""

    def test_delete_webhook(
        self, client: TestClient, webhook_manager: WebhookManager
    ) -> None:
        """Test deleting a webhook."""
        webhook = webhook_manager.register(url="https://example.com/webhook")

        response = client.delete(f"/api/webhooks/{webhook.id}")

        assert response.status_code == 204

    def test_delete_nonexistent_webhook(self, client: TestClient) -> None:
        """Test deleting nonexistent webhook returns 404."""
        response = client.delete("/api/webhooks/nonexistent-id")

        assert response.status_code == 404


class TestWebhookEventTypesAPI:
    """Tests for event types endpoint."""

    def test_get_event_types(self, client: TestClient) -> None:
        """Test getting webhook event types."""
        response = client.get("/api/webhooks/events/types")

        assert response.status_code == 200
        data = response.json()
        assert "email.received" in data
        assert "email.sent" in data


class TestWebUI:
    """Tests for web UI endpoint."""

    def test_web_ui(self, client: TestClient) -> None:
        """Test web UI returns HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Mock Email Server" in response.text
