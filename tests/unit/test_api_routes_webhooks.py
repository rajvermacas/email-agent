"""
Unit tests for webhook API routes.

Tests the webhook routes defined in src/info_agent/api/routes/webhooks.py
with mocked dependencies and comprehensive coverage of all edge cases.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi import status
from fastapi.testclient import TestClient
from fastapi import FastAPI

from info_agent.api.routes.webhooks import create_webhook_router
from info_agent.api.models.requests import EmailWebhookPayload
from info_agent.utils.exceptions import WorkflowError, WorkflowNotFoundError


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock()
    settings.checkpoint_db_path = "/tmp/test/checkpoints.db"
    return settings


@pytest.fixture
def app_with_webhook_router():
    """Create FastAPI app with webhook router for testing."""
    app = FastAPI()
    router = create_webhook_router()
    app.include_router(router)
    return app


@pytest.fixture
def client(app_with_webhook_router):
    """Create test client for webhook routes."""
    return TestClient(app_with_webhook_router)


@pytest.fixture
def valid_email_payload():
    """Create a valid email webhook payload."""
    return {
        "event": "email.received",
        "message_id": "msg-123",
        "thread_id": "thread-456",
        "from_address": "sender@example.com",
        "to_address": "recipient@example.com",
        "subject": "Re: Information Request",
        "body": "Here is the requested information.",
        "attachments": [],
        "received_at": datetime.utcnow().isoformat()
    }


class TestEmailWebhookEndpoint:
    """Tests for POST /webhooks/email endpoint."""

    @patch("info_agent.api.routes.webhooks.clear_context")
    @patch("info_agent.api.routes.webhooks.bind_context")
    @patch("info_agent.api.routes.webhooks.resume_workflow")
    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_success(
        self,
        mock_get_settings,
        mock_find_workflow,
        mock_resume_workflow,
        mock_bind_context,
        mock_clear_context,
        client,
        valid_email_payload,
        mock_settings
    ):
        """Test successful email webhook processing."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = "wf-123"
        mock_resume_workflow.return_value = {
            "status": "completed",
            "workflow_id": "wf-123"
        }

        response = client.post("/webhooks/email", json=valid_email_payload)

        assert response.status_code == status.HTTP_202_ACCEPTED

        data = response.json()
        assert data["status"] == "accepted"
        assert data["workflow_id"] == "wf-123"
        assert data["thread_id"] == "thread-456"
        assert data["message_id"] == "msg-123"
        assert data["workflow_status"] == "completed"

        # Verify workflow resume was called with correct data
        mock_resume_workflow.assert_called_once()
        call_args = mock_resume_workflow.call_args
        assert call_args[1]["workflow_id"] == "wf-123"
        assert "received_response" in call_args[1]["updates"]
        assert call_args[1]["updates"]["received_response"] == "Here is the requested information."

    @patch("info_agent.api.routes.webhooks.clear_context")
    @patch("info_agent.api.routes.webhooks.bind_context")
    @patch("info_agent.api.routes.webhooks.resume_workflow")
    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_with_attachments(
        self,
        mock_get_settings,
        mock_find_workflow,
        mock_resume_workflow,
        mock_bind_context,
        mock_clear_context,
        client,
        mock_settings
    ):
        """Test email webhook with attachments."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = "wf-123"
        mock_resume_workflow.return_value = {"status": "completed"}

        payload = {
            "event": "email.received",
            "message_id": "msg-123",
            "thread_id": "thread-456",
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Test",
            "body": "Test body",
            "attachments": [
                {
                    "filename": "report.pdf",
                    "size": 1024,
                    "mime_type": "application/pdf",
                    "content_path": "/tmp/report.pdf"
                },
                {
                    "filename": "data.csv",
                    "size": 512,
                    "mime_type": "text/csv",
                    "content_path": "/tmp/data.csv"
                }
            ],
            "received_at": datetime.utcnow().isoformat()
        }

        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == status.HTTP_202_ACCEPTED

        # Verify attachments were passed to resume_workflow
        call_args = mock_resume_workflow.call_args
        attachments = call_args[1]["updates"]["received_attachments"]
        assert len(attachments) == 2
        assert attachments[0]["filename"] == "report.pdf"
        assert attachments[1]["size"] == 512

    @pytest.mark.asyncio
    async def test_email_webhook_unsupported_event(self, client):
        """Test email webhook with unsupported event type."""
        payload = {
            "event": "email.sent",
            "message_id": "msg-123",
            "thread_id": "thread-456",
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Test",
            "body": "Test",
            "received_at": datetime.utcnow().isoformat()
        }

        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported event type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_email_webhook_missing_message_id(self, client):
        """Test email webhook with missing message_id."""
        payload = {
            "event": "email.received",
            "message_id": "",
            "thread_id": "thread-456",
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Test",
            "body": "Test",
            "received_at": datetime.utcnow().isoformat()
        }

        # This should fail validation before reaching the endpoint
        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_email_webhook_missing_thread_id(self, client):
        """Test email webhook with missing thread_id."""
        payload = {
            "event": "email.received",
            "message_id": "msg-123",
            "thread_id": "",
            "from_address": "sender@example.com",
            "to_address": "recipient@example.com",
            "subject": "Test",
            "body": "Test",
            "received_at": datetime.utcnow().isoformat()
        }

        # This should fail validation before reaching the endpoint
        response = client.post("/webhooks/email", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_workflow_not_found(
        self,
        mock_get_settings,
        mock_find_workflow,
        client,
        valid_email_payload,
        mock_settings
    ):
        """Test email webhook when no workflow found for thread."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = None

        response = client.post("/webhooks/email", json=valid_email_payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "No workflow found" in response.json()["detail"]

    @patch("info_agent.api.routes.webhooks.clear_context")
    @patch("info_agent.api.routes.webhooks.bind_context")
    @patch("info_agent.api.routes.webhooks.resume_workflow")
    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_workflow_not_found_during_resume(
        self,
        mock_get_settings,
        mock_find_workflow,
        mock_resume_workflow,
        mock_bind_context,
        mock_clear_context,
        client,
        valid_email_payload,
        mock_settings
    ):
        """Test email webhook when workflow is not found during resume."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = "wf-123"
        mock_resume_workflow.side_effect = WorkflowNotFoundError(workflow_id="wf-123")

        response = client.post("/webhooks/email", json=valid_email_payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Workflow not found" in response.json()["detail"]

    @patch("info_agent.api.routes.webhooks.clear_context")
    @patch("info_agent.api.routes.webhooks.bind_context")
    @patch("info_agent.api.routes.webhooks.resume_workflow")
    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_workflow_error(
        self,
        mock_get_settings,
        mock_find_workflow,
        mock_resume_workflow,
        mock_bind_context,
        mock_clear_context,
        client,
        valid_email_payload,
        mock_settings
    ):
        """Test email webhook when workflow processing fails."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = "wf-123"
        mock_resume_workflow.side_effect = WorkflowError(
            message="Processing failed",
            workflow_id="wf-123"
        )

        response = client.post("/webhooks/email", json=valid_email_payload)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Workflow processing failed" in response.json()["detail"]

    @patch("info_agent.api.routes.webhooks.clear_context")
    @patch("info_agent.api.routes.webhooks.bind_context")
    @patch("info_agent.api.routes.webhooks.resume_workflow")
    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_unexpected_error(
        self,
        mock_get_settings,
        mock_find_workflow,
        mock_resume_workflow,
        mock_bind_context,
        mock_clear_context,
        client,
        valid_email_payload,
        mock_settings
    ):
        """Test email webhook with unexpected error."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = "wf-123"
        mock_resume_workflow.side_effect = RuntimeError("Unexpected error")

        response = client.post("/webhooks/email", json=valid_email_payload)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to process email" in response.json()["detail"]

    @patch("info_agent.api.routes.webhooks.clear_context")
    @patch("info_agent.api.routes.webhooks.bind_context")
    @patch("info_agent.api.routes.webhooks.resume_workflow")
    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_clears_context_on_success(
        self,
        mock_get_settings,
        mock_find_workflow,
        mock_resume_workflow,
        mock_bind_context,
        mock_clear_context,
        client,
        valid_email_payload,
        mock_settings
    ):
        """Test that context is cleared after successful processing."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = "wf-123"
        mock_resume_workflow.return_value = {"status": "completed"}

        response = client.post("/webhooks/email", json=valid_email_payload)

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_clear_context.assert_called_once()

    @patch("info_agent.api.routes.webhooks.clear_context")
    @patch("info_agent.api.routes.webhooks.bind_context")
    @patch("info_agent.api.routes.webhooks.resume_workflow")
    @patch("info_agent.api.routes.webhooks._find_workflow_by_thread_id")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_email_webhook_clears_context_on_error(
        self,
        mock_get_settings,
        mock_find_workflow,
        mock_resume_workflow,
        mock_bind_context,
        mock_clear_context,
        client,
        valid_email_payload,
        mock_settings
    ):
        """Test that context is cleared even when error occurs."""
        mock_get_settings.return_value = mock_settings
        mock_find_workflow.return_value = "wf-123"
        mock_resume_workflow.side_effect = RuntimeError("Error")

        response = client.post("/webhooks/email", json=valid_email_payload)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_clear_context.assert_called_once()


class TestFindWorkflowByThreadId:
    """Tests for _find_workflow_by_thread_id helper function."""

    @patch("info_agent.workflow.checkpointer.get_workflow_state")
    @patch("info_agent.workflow.checkpointer.list_workflow_threads")
    @patch("info_agent.api.routes.webhooks.get_compiled_workflow")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_find_workflow_by_thread_id_found(
        self,
        mock_get_settings,
        mock_get_compiled_workflow,
        mock_list_threads,
        mock_get_state,
        mock_settings
    ):
        """Test finding workflow by thread_id when it exists."""
        from info_agent.api.routes.webhooks import _find_workflow_by_thread_id

        mock_get_settings.return_value = mock_settings
        mock_compiled_workflow = Mock()
        mock_get_compiled_workflow.return_value = mock_compiled_workflow

        # Mock workflow list
        mock_list_threads.return_value = ["wf-1", "wf-2", "wf-3"]

        # Mock states - wf-2 has matching thread_id
        mock_get_state.side_effect = [
            {"email_thread_id": "thread-111"},
            {"email_thread_id": "thread-456"},  # Match
            {"email_thread_id": "thread-789"}
        ]

        result = await _find_workflow_by_thread_id("thread-456")

        assert result == "wf-2"
        assert mock_get_state.call_count == 2  # Should stop after finding match

    @patch("info_agent.workflow.checkpointer.get_workflow_state")
    @patch("info_agent.workflow.checkpointer.list_workflow_threads")
    @patch("info_agent.api.routes.webhooks.get_compiled_workflow")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_find_workflow_by_thread_id_not_found(
        self,
        mock_get_settings,
        mock_get_compiled_workflow,
        mock_list_threads,
        mock_get_state,
        mock_settings
    ):
        """Test finding workflow by thread_id when it doesn't exist."""
        from info_agent.api.routes.webhooks import _find_workflow_by_thread_id

        mock_get_settings.return_value = mock_settings
        mock_compiled_workflow = Mock()
        mock_get_compiled_workflow.return_value = mock_compiled_workflow

        # Mock workflow list
        mock_list_threads.return_value = ["wf-1", "wf-2"]

        # Mock states - none match
        mock_get_state.side_effect = [
            {"email_thread_id": "thread-111"},
            {"email_thread_id": "thread-222"}
        ]

        result = await _find_workflow_by_thread_id("thread-456")

        assert result is None
        assert mock_get_state.call_count == 2

    @patch("info_agent.workflow.checkpointer.get_workflow_state")
    @patch("info_agent.workflow.checkpointer.list_workflow_threads")
    @patch("info_agent.api.routes.webhooks.get_compiled_workflow")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_find_workflow_by_thread_id_no_workflows(
        self,
        mock_get_settings,
        mock_get_compiled_workflow,
        mock_list_threads,
        mock_get_state,
        mock_settings
    ):
        """Test finding workflow when no workflows exist."""
        from info_agent.api.routes.webhooks import _find_workflow_by_thread_id

        mock_get_settings.return_value = mock_settings
        mock_compiled_workflow = Mock()
        mock_get_compiled_workflow.return_value = mock_compiled_workflow

        # Mock empty workflow list
        mock_list_threads.return_value = []

        result = await _find_workflow_by_thread_id("thread-456")

        assert result is None
        mock_get_state.assert_not_called()

    @patch("info_agent.workflow.checkpointer.get_workflow_state")
    @patch("info_agent.workflow.checkpointer.list_workflow_threads")
    @patch("info_agent.api.routes.webhooks.get_compiled_workflow")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_find_workflow_by_thread_id_with_none_state(
        self,
        mock_get_settings,
        mock_get_compiled_workflow,
        mock_list_threads,
        mock_get_state,
        mock_settings
    ):
        """Test finding workflow when some workflows have no state."""
        from info_agent.api.routes.webhooks import _find_workflow_by_thread_id

        mock_get_settings.return_value = mock_settings
        mock_compiled_workflow = Mock()
        mock_get_compiled_workflow.return_value = mock_compiled_workflow

        # Mock workflow list
        mock_list_threads.return_value = ["wf-1", "wf-2", "wf-3"]

        # Mock states - wf-2 has no state, wf-3 has matching thread
        mock_get_state.side_effect = [
            {"email_thread_id": "thread-111"},
            None,  # No state
            {"email_thread_id": "thread-456"}  # Match
        ]

        result = await _find_workflow_by_thread_id("thread-456")

        assert result == "wf-3"
        assert mock_get_state.call_count == 3

    @patch("info_agent.workflow.checkpointer.get_workflow_state")
    @patch("info_agent.workflow.checkpointer.list_workflow_threads")
    @patch("info_agent.api.routes.webhooks.get_compiled_workflow")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_find_workflow_by_thread_id_missing_email_thread_id(
        self,
        mock_get_settings,
        mock_get_compiled_workflow,
        mock_list_threads,
        mock_get_state,
        mock_settings
    ):
        """Test finding workflow when state has no email_thread_id."""
        from info_agent.api.routes.webhooks import _find_workflow_by_thread_id

        mock_get_settings.return_value = mock_settings
        mock_compiled_workflow = Mock()
        mock_get_compiled_workflow.return_value = mock_compiled_workflow

        # Mock workflow list
        mock_list_threads.return_value = ["wf-1", "wf-2"]

        # Mock states - wf-1 has no email_thread_id, wf-2 matches
        mock_get_state.side_effect = [
            {"status": "created"},  # No email_thread_id key
            {"email_thread_id": "thread-456"}
        ]

        result = await _find_workflow_by_thread_id("thread-456")

        assert result == "wf-2"

    @patch("info_agent.workflow.checkpointer.get_workflow_state")
    @patch("info_agent.workflow.checkpointer.list_workflow_threads")
    @patch("info_agent.api.routes.webhooks.get_compiled_workflow")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_find_workflow_by_thread_id_error_handling(
        self,
        mock_get_settings,
        mock_get_compiled_workflow,
        mock_list_threads,
        mock_get_state,
        mock_settings
    ):
        """Test error handling in find_workflow_by_thread_id."""
        from info_agent.api.routes.webhooks import _find_workflow_by_thread_id

        mock_get_settings.return_value = mock_settings
        mock_list_threads.side_effect = Exception("Database error")

        result = await _find_workflow_by_thread_id("thread-456")

        assert result is None

    @patch("info_agent.workflow.checkpointer.get_workflow_state")
    @patch("info_agent.workflow.checkpointer.list_workflow_threads")
    @patch("info_agent.api.routes.webhooks.get_compiled_workflow")
    @patch("info_agent.api.routes.webhooks.get_settings")
    @pytest.mark.asyncio
    async def test_find_workflow_first_match_returned(
        self,
        mock_get_settings,
        mock_get_compiled_workflow,
        mock_list_threads,
        mock_get_state,
        mock_settings
    ):
        """Test that first matching workflow is returned."""
        from info_agent.api.routes.webhooks import _find_workflow_by_thread_id

        mock_get_settings.return_value = mock_settings
        mock_compiled_workflow = Mock()
        mock_get_compiled_workflow.return_value = mock_compiled_workflow

        # Mock workflow list
        mock_list_threads.return_value = ["wf-1", "wf-2", "wf-3"]

        # Mock states - both wf-1 and wf-3 match
        mock_get_state.side_effect = [
            {"email_thread_id": "thread-456"},  # First match
            {"email_thread_id": "thread-789"},
            {"email_thread_id": "thread-456"}  # Would also match but not reached
        ]

        result = await _find_workflow_by_thread_id("thread-456")

        assert result == "wf-1"
        assert mock_get_state.call_count == 1  # Stops at first match
