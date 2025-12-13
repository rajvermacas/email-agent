"""
Unit tests for email FastAPI routes.

Tests the API endpoints from src/info_agent/email/api.py:
- List inboxes endpoint
- List inbox messages endpoint
- Get specific message endpoint
- Create message endpoint
- Reply to message endpoint
- Delete message endpoint

Uses mocked storage and webhook components with FastAPI TestClient.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from info_agent.email.api import create_email_router
from info_agent.email.models import (
    CreateEmailRequest,
    EmailAttachment,
    EmailReplyRequest,
    StoredEmail,
)
from info_agent.email.storage import EmailStorage
from info_agent.email.webhook import WebhookNotifier
from info_agent.utils.exceptions import EmailError, StorageError


@pytest.fixture
def mock_storage():
    """Create mock EmailStorage instance."""
    storage = Mock(spec=EmailStorage)
    storage.list_inboxes = AsyncMock()
    storage.list_emails_by_inbox = AsyncMock()
    storage.get_email = AsyncMock()
    storage.save_email = AsyncMock()
    storage.delete_email = AsyncMock()
    return storage


@pytest.fixture
def mock_webhook_notifier():
    """Create mock WebhookNotifier instance."""
    notifier = Mock(spec=WebhookNotifier)
    notifier.notify = AsyncMock()
    return notifier


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
def test_email_2():
    """Create a second test stored email."""
    return StoredEmail(
        id="msg-test456",
        inbox="user@example.com",
        thread_id=None,
        from_address="sender2@example.com",
        to_address="user@example.com",
        subject="Another Email",
        body_text="Another test email.",
        attachments=[],
        received_at=datetime(2025, 12, 13, 11, 0, 0, tzinfo=timezone.utc),
        read=True,
    )


class TestCreateEmailRouter:
    """Tests for create_email_router function."""

    def test_create_router_with_storage_only(self, mock_storage):
        """Test creating router with storage only."""
        router = create_email_router(storage=mock_storage)

        assert router is not None
        assert router.prefix == "/emails"
        assert "emails" in router.tags

    def test_create_router_with_storage_and_webhook(
        self, mock_storage, mock_webhook_notifier
    ):
        """Test creating router with both storage and webhook."""
        router = create_email_router(
            storage=mock_storage,
            webhook_notifier=mock_webhook_notifier
        )

        assert router is not None

    def test_create_router_without_storage_fails(self):
        """Test that creating router without storage raises EmailError."""
        with pytest.raises(EmailError) as exc_info:
            create_email_router(storage=None)

        assert exc_info.value.code == "EMAIL_ERROR"
        assert "Storage is required" in exc_info.value.message


class TestListInboxesEndpoint:
    """Tests for GET /emails/inboxes endpoint."""

    @pytest.mark.asyncio
    async def test_list_inboxes_success(self, mock_storage):
        """Test successfully listing all inboxes."""
        mock_storage.list_inboxes.return_value = [
            "user1@example.com",
            "user2@example.com",
            "user3@example.com",
        ]

        router = create_email_router(storage=mock_storage)

        # Get the endpoint function
        endpoint = router.routes[0].endpoint

        result = await endpoint()

        assert result == {
            "inboxes": [
                "user1@example.com",
                "user2@example.com",
                "user3@example.com",
            ],
            "count": 3,
        }
        mock_storage.list_inboxes.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_inboxes_empty(self, mock_storage):
        """Test listing inboxes when none exist."""
        mock_storage.list_inboxes.return_value = []

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[0].endpoint

        result = await endpoint()

        assert result == {"inboxes": [], "count": 0}

    @pytest.mark.asyncio
    async def test_list_inboxes_storage_error(self, mock_storage):
        """Test handling of storage error."""
        mock_storage.list_inboxes.side_effect = StorageError(
            message="Database error",
            operation="list_inboxes",
            entity_type="email",
        )

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[0].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint()

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_list_inboxes_unexpected_error(self, mock_storage):
        """Test handling of unexpected error."""
        mock_storage.list_inboxes.side_effect = Exception("Unexpected error")

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[0].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint()

        assert exc_info.value.status_code == 500


class TestListInboxMessagesEndpoint:
    """Tests for GET /emails/inboxes/{inbox}/messages endpoint."""

    @pytest.mark.asyncio
    async def test_list_inbox_messages_success(self, mock_storage, test_email, test_email_2):
        """Test successfully listing messages for an inbox."""
        mock_storage.list_emails_by_inbox.return_value = [test_email, test_email_2]

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[1].endpoint

        result = await endpoint(inbox="user@example.com")

        assert result["inbox"] == "user@example.com"
        assert result["count"] == 2
        assert len(result["messages"]) == 2
        assert result["messages"][0]["id"] == "msg-test123"
        assert result["messages"][1]["id"] == "msg-test456"

        mock_storage.list_emails_by_inbox.assert_called_once_with("user@example.com")

    @pytest.mark.asyncio
    async def test_list_inbox_messages_empty_inbox(self, mock_storage):
        """Test listing messages for inbox with no messages."""
        mock_storage.list_emails_by_inbox.return_value = []

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[1].endpoint

        result = await endpoint(inbox="empty@example.com")

        assert result["inbox"] == "empty@example.com"
        assert result["count"] == 0
        assert result["messages"] == []

    @pytest.mark.asyncio
    async def test_list_inbox_messages_empty_parameter(self, mock_storage):
        """Test that empty inbox parameter raises error."""
        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[1].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(inbox="")

        assert exc_info.value.status_code == 400
        assert "Inbox parameter is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_inbox_messages_storage_error(self, mock_storage):
        """Test handling of storage error."""
        mock_storage.list_emails_by_inbox.side_effect = StorageError(
            message="Database error",
            operation="list",
            entity_type="email",
        )

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[1].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(inbox="user@example.com")

        assert exc_info.value.status_code == 500


class TestGetMessageEndpoint:
    """Tests for GET /emails/messages/{message_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_message_success(self, mock_storage, test_email):
        """Test successfully getting a message."""
        mock_storage.get_email.return_value = test_email

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[2].endpoint

        result = await endpoint(message_id="msg-test123")

        assert result["id"] == "msg-test123"
        assert result["subject"] == "Test Email"
        assert result["from_address"] == "sender@example.com"

        mock_storage.get_email.assert_called_once_with("msg-test123")

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, mock_storage):
        """Test getting non-existent message."""
        mock_storage.get_email.return_value = None

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[2].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="nonexistent")

        assert exc_info.value.status_code == 404
        assert "Message not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_message_empty_id(self, mock_storage):
        """Test that empty message ID raises error."""
        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[2].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="")

        assert exc_info.value.status_code == 400
        assert "Message ID parameter is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_message_storage_error(self, mock_storage):
        """Test handling of storage error."""
        mock_storage.get_email.side_effect = StorageError(
            message="Database error",
            operation="get",
            entity_type="email",
        )

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[2].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="msg-test123")

        assert exc_info.value.status_code == 500


class TestCreateMessageEndpoint:
    """Tests for POST /emails/messages endpoint."""

    @pytest.mark.asyncio
    async def test_create_message_success(self, mock_storage):
        """Test successfully creating a message."""
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test Subject",
            body_text="Test body",
        )

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[3].endpoint

        result = await endpoint(request=request)

        assert result["from_address"] == "sender@example.com"
        assert result["to_address"] == "recipient@example.com"
        assert result["subject"] == "Test Subject"
        assert result["body_text"] == "Test body"
        assert result["inbox"] == "recipient@example.com"
        assert "id" in result
        assert result["id"].startswith("msg-")

        mock_storage.save_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_message_with_webhook(
        self, mock_storage, mock_webhook_notifier
    ):
        """Test creating message with webhook notification."""
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body_text="Body",
        )

        router = create_email_router(
            storage=mock_storage,
            webhook_notifier=mock_webhook_notifier
        )
        endpoint = router.routes[3].endpoint

        result = await endpoint(request=request)

        # Verify webhook was called
        mock_webhook_notifier.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_message_webhook_failure_does_not_fail_request(
        self, mock_storage, mock_webhook_notifier
    ):
        """Test that webhook failure doesn't fail message creation."""
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body_text="Body",
        )

        # Make webhook fail
        mock_webhook_notifier.notify.side_effect = Exception("Webhook failed")

        router = create_email_router(
            storage=mock_storage,
            webhook_notifier=mock_webhook_notifier
        )
        endpoint = router.routes[3].endpoint

        # Should not raise exception
        result = await endpoint(request=request)

        assert "id" in result
        mock_storage.save_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_message_with_thread_id(self, mock_storage):
        """Test creating message with thread ID."""
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Reply",
            body_text="Reply body",
            thread_id="thread-123",
        )

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[3].endpoint

        result = await endpoint(request=request)

        assert result["thread_id"] == "thread-123"

    @pytest.mark.asyncio
    async def test_create_message_storage_error(self, mock_storage):
        """Test handling of storage error."""
        request = CreateEmailRequest(
            from_address="sender@example.com",
            to_address="recipient@example.com",
            subject="Test",
            body_text="Body",
        )

        mock_storage.save_email.side_effect = StorageError(
            message="Database error",
            operation="save",
            entity_type="email",
        )

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[3].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(request=request)

        assert exc_info.value.status_code == 500


class TestReplyToMessageEndpoint:
    """Tests for POST /emails/messages/{message_id}/reply endpoint."""

    @pytest.mark.asyncio
    async def test_reply_to_message_success(self, mock_storage, test_email):
        """Test successfully replying to a message."""
        mock_storage.get_email.return_value = test_email

        request = EmailReplyRequest(body_text="This is my reply.")

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[4].endpoint

        result = await endpoint(message_id="msg-test123", request=request)

        # Verify reply structure
        assert result["from_address"] == "user@example.com"  # Original to
        assert result["to_address"] == "sender@example.com"  # Original from
        assert result["subject"] == "Re: Test Email"
        assert result["body_text"] == "This is my reply."
        assert result["thread_id"] == "thread-abc"  # Original thread
        assert result["inbox"] == "sender@example.com"
        assert "id" in result

        # Verify both get and save were called
        mock_storage.get_email.assert_called_once_with("msg-test123")
        assert mock_storage.save_email.call_count == 1

    @pytest.mark.asyncio
    async def test_reply_to_message_creates_thread_id(self, mock_storage):
        """Test that reply creates thread ID from original message ID if none exists."""
        original_email = StoredEmail(
            id="msg-original",
            inbox="user@example.com",
            thread_id=None,  # No thread ID
            from_address="sender@example.com",
            to_address="user@example.com",
            subject="Original",
            body_text="Original body",
            received_at=datetime.now(timezone.utc),
        )
        mock_storage.get_email.return_value = original_email

        request = EmailReplyRequest(body_text="Reply")

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[4].endpoint

        result = await endpoint(message_id="msg-original", request=request)

        # Should use original message ID as thread ID
        assert result["thread_id"] == "msg-original"

    @pytest.mark.asyncio
    async def test_reply_to_message_not_found(self, mock_storage):
        """Test replying to non-existent message."""
        mock_storage.get_email.return_value = None

        request = EmailReplyRequest(body_text="Reply")

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[4].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="nonexistent", request=request)

        assert exc_info.value.status_code == 404
        assert "Original message not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_reply_to_message_empty_id(self, mock_storage):
        """Test that empty message ID raises error."""
        request = EmailReplyRequest(body_text="Reply")

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[4].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="", request=request)

        assert exc_info.value.status_code == 400
        assert "Message ID parameter is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_reply_to_message_with_webhook(
        self, mock_storage, mock_webhook_notifier, test_email
    ):
        """Test replying with webhook notification."""
        mock_storage.get_email.return_value = test_email

        request = EmailReplyRequest(body_text="Reply")

        router = create_email_router(
            storage=mock_storage,
            webhook_notifier=mock_webhook_notifier
        )
        endpoint = router.routes[4].endpoint

        result = await endpoint(message_id="msg-test123", request=request)

        # Verify webhook was called with reply
        mock_webhook_notifier.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_reply_to_message_storage_error(self, mock_storage, test_email):
        """Test handling of storage error."""
        mock_storage.get_email.return_value = test_email
        mock_storage.save_email.side_effect = StorageError(
            message="Database error",
            operation="save",
            entity_type="email",
        )

        request = EmailReplyRequest(body_text="Reply")

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[4].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="msg-test123", request=request)

        assert exc_info.value.status_code == 500


class TestDeleteMessageEndpoint:
    """Tests for DELETE /emails/messages/{message_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_message_success(self, mock_storage):
        """Test successfully deleting a message."""
        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[5].endpoint

        result = await endpoint(message_id="msg-test123")

        # DELETE endpoint should return None (204 No Content)
        assert result is None

        mock_storage.delete_email.assert_called_once_with("msg-test123")

    @pytest.mark.asyncio
    async def test_delete_message_empty_id(self, mock_storage):
        """Test that empty message ID raises error."""
        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[5].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="")

        assert exc_info.value.status_code == 400
        assert "Message ID parameter is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_message_storage_error(self, mock_storage):
        """Test handling of storage error."""
        mock_storage.delete_email.side_effect = StorageError(
            message="Database error",
            operation="delete",
            entity_type="email",
        )

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[5].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="msg-test123")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_message_unexpected_error(self, mock_storage):
        """Test handling of unexpected error."""
        mock_storage.delete_email.side_effect = Exception("Unexpected error")

        router = create_email_router(storage=mock_storage)
        endpoint = router.routes[5].endpoint

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(message_id="msg-test123")

        assert exc_info.value.status_code == 500
