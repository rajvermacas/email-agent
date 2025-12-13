"""
Unit tests for webhook routes.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from info_agent.gateway.app import create_app_sync
from info_agent.supervisor.agent import SupervisorAgent


class TestEmailWebhook:
    """Tests for email webhook endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_email_received_webhook(self, client: TestClient) -> None:
        """Test email received webhook processing."""
        payload = {
            "event_type": "email.received",
            "message_id": "msg-123",
            "thread_id": "thread-123",
            "inbox": "test@example.com",
            "from_address": "sender@test.com",
            "to_address": "test@example.com",
            "subject": "Test Subject",
            "body_preview": "Test body preview",
            "has_attachments": False,
            "received_at": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "email.received" in data["message"]

    def test_email_sent_webhook(self, client: TestClient) -> None:
        """Test email sent webhook processing."""
        payload = {
            "event_type": "email.sent",
            "message_id": "msg-456",
            "thread_id": "thread-456",
            "inbox": "sender@example.com",
            "from_address": "sender@example.com",
            "to_address": "receiver@test.com",
            "subject": "Outgoing Test",
            "body_preview": "Test body",
            "has_attachments": True,
            "received_at": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_email_bounced_webhook(self, client: TestClient) -> None:
        """Test email bounced webhook processing."""
        payload = {
            "event_type": "email.bounced",
            "message_id": "msg-789",
            "thread_id": "thread-789",
            "inbox": "sender@example.com",
            "from_address": "sender@example.com",
            "to_address": "invalid@test.com",
            "subject": "Failed Delivery",
            "body_preview": "",
            "has_attachments": False,
            "received_at": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_email_webhook_invalid_payload(self, client: TestClient) -> None:
        """Test email webhook with invalid payload."""
        payload = {
            "event_type": "email.received",
            # Missing required fields
        }

        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == 422  # Validation error

    def test_email_webhook_no_supervisor(self) -> None:
        """Test email webhook when supervisor not available."""
        app = create_app_sync()
        app.state.supervisor = None
        client = TestClient(app)

        payload = {
            "event_type": "email.received",
            "message_id": "msg-123",
            "thread_id": "thread-123",
            "inbox": "test@example.com",
            "from_address": "sender@test.com",
            "to_address": "test@example.com",
            "subject": "Test",
            "received_at": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == 503


class TestAgentWebhook:
    """Tests for agent webhook endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_task_completed_webhook(self, client: TestClient) -> None:
        """Test task completed webhook processing."""
        payload = {
            "event_type": "task.completed",
            "agent_id": "mail-agent",
            "task_id": "task-123",
            "workflow_id": "wf-123",
            "result": {"success": True, "message_id": "msg-123"},
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/agent", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task.completed" in data["message"]

    def test_task_failed_webhook(self, client: TestClient) -> None:
        """Test task failed webhook processing."""
        payload = {
            "event_type": "task.failed",
            "agent_id": "validation-agent",
            "task_id": "task-456",
            "error": "Connection timeout",
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/agent", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_task_progress_webhook(self, client: TestClient) -> None:
        """Test task progress webhook processing."""
        payload = {
            "event_type": "task.progress",
            "agent_id": "mail-agent",
            "task_id": "task-789",
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/agent", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_agent_webhook_invalid_payload(self, client: TestClient) -> None:
        """Test agent webhook with invalid payload."""
        payload = {
            "event_type": "task.completed",
            # Missing required fields
        }

        response = client.post("/webhooks/agent", json=payload)

        assert response.status_code == 422  # Validation error

    def test_agent_webhook_no_supervisor(self) -> None:
        """Test agent webhook when supervisor not available."""
        app = create_app_sync()
        app.state.supervisor = None
        client = TestClient(app)

        payload = {
            "event_type": "task.completed",
            "agent_id": "mail-agent",
            "task_id": "task-123",
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/agent", json=payload)

        assert response.status_code == 503

    def test_unknown_event_type(self, client: TestClient) -> None:
        """Test webhook with unknown event type."""
        payload = {
            "event_type": "unknown.event",
            "agent_id": "mail-agent",
            "task_id": "task-123",
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = client.post("/webhooks/agent", json=payload)

        # Unknown events should still be accepted
        assert response.status_code == 200
