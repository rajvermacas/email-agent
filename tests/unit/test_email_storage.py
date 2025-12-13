"""
Unit tests for email storage.

Tests the EmailStorage class from src/info_agent/email/storage.py:
- Database initialization
- Email CRUD operations
- Inbox listing
- Error handling
- Thread management

Uses mocked aiosqlite to avoid actual database operations.
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

from info_agent.email.models import EmailAttachment, StoredEmail
from info_agent.email.storage import EmailStorage
from info_agent.utils.exceptions import StorageError


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock()
    settings.email_db_path = "/tmp/test_emails.db"
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
        id="msg-test456",
        inbox="user@example.com",
        thread_id=None,
        from_address="sender@example.com",
        to_address="user@example.com",
        subject="Simple Email",
        body_text="Simple body.",
        attachments=[],
        received_at=datetime(2025, 12, 13, 11, 0, 0, tzinfo=timezone.utc),
        read=True,
    )


class TestEmailStorageInit:
    """Tests for EmailStorage initialization."""

    @patch("info_agent.email.storage.get_settings")
    def test_init_with_default_path(self, mock_get_settings, mock_settings):
        """Test initialization with default path from settings."""
        mock_get_settings.return_value = mock_settings

        storage = EmailStorage()

        assert storage.db_path == Path("/tmp/test_emails.db")
        mock_get_settings.assert_called_once()

    def test_init_with_explicit_path(self):
        """Test initialization with explicit database path."""
        storage = EmailStorage(db_path="/custom/path/emails.db")

        assert storage.db_path == Path("/custom/path/emails.db")

    def test_init_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        db_path = tmp_path / "subdir" / "emails.db"

        storage = EmailStorage(db_path=str(db_path))

        assert storage.db_path.parent.exists()
        assert storage.db_path.parent.is_dir()

    def test_init_empty_path_fails(self):
        """Test that empty database path raises StorageError."""
        with pytest.raises(StorageError) as exc_info:
            EmailStorage(db_path="")

        assert exc_info.value.code == "STORAGE_ERROR"
        assert "Database path is required" in exc_info.value.message

    def test_init_none_path_without_settings_fails(self):
        """Test that None path without settings raises error."""
        with patch("info_agent.email.storage.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.email_db_path = ""
            mock_get_settings.return_value = mock_settings

            with pytest.raises(StorageError) as exc_info:
                EmailStorage()

            assert exc_info.value.code == "STORAGE_ERROR"
            assert "Database path is required" in exc_info.value.message


class TestEmailStorageInitDb:
    """Tests for database initialization."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables_and_indexes(self, tmp_path):
        """Test that init_db creates all necessary tables and indexes."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Mock aiosqlite connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            await storage.init_db()

        # Verify table creation
        execute_calls = mock_conn.execute.call_args_list
        assert len(execute_calls) == 4  # 1 table + 3 indexes

        # Check table creation SQL
        table_sql = execute_calls[0][0][0]
        assert "CREATE TABLE IF NOT EXISTS emails" in table_sql
        assert "id TEXT PRIMARY KEY" in table_sql
        assert "inbox TEXT NOT NULL" in table_sql
        assert "thread_id TEXT" in table_sql

        # Check index creation
        index_sqls = [call[0][0] for call in execute_calls[1:]]
        assert any("idx_emails_inbox" in sql for sql in index_sqls)
        assert any("idx_emails_thread" in sql for sql in index_sqls)
        assert any("idx_emails_received" in sql for sql in index_sqls)

        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_db_failure_raises_storage_error(self, tmp_path):
        """Test that database initialization failure raises StorageError."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        with patch("aiosqlite.connect", side_effect=Exception("Database error")):
            with pytest.raises(StorageError) as exc_info:
                await storage.init_db()

            assert exc_info.value.code == "STORAGE_ERROR"
            assert "Failed to initialize database" in exc_info.value.message
            assert exc_info.value.operation == "init_db"


class TestEmailStorageSave:
    """Tests for saving emails."""

    @pytest.mark.asyncio
    async def test_save_email_success(self, tmp_path, test_email):
        """Test successfully saving an email."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Mock aiosqlite connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            await storage.save_email(test_email)

        # Verify SQL execution
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT OR REPLACE INTO emails" in sql
        assert params[0] == "msg-test123"
        assert params[1] == "user@example.com"
        assert params[2] == "thread-abc"
        assert params[3] == "sender@example.com"
        assert params[4] == "user@example.com"
        assert params[5] == "Test Email"
        assert params[6] == "This is a test email."
        # params[7] is JSON attachments
        assert "2025-12-13T10:30:00+00:00" in params[8]
        assert params[9] == 0  # read=False

        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_email_serializes_attachments(self, tmp_path, test_email):
        """Test that attachments are properly serialized to JSON."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            await storage.save_email(test_email)

        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        attachments_json = params[7]

        # Verify JSON serialization
        attachments = json.loads(attachments_json)
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "test.pdf"
        assert attachments[0]["content_type"] == "application/pdf"
        assert attachments[0]["size"] == 1024
        assert attachments[0]["content"] == "YmFzZTY0IGNvbnRlbnQ="

    @pytest.mark.asyncio
    async def test_save_email_empty_attachments(self, tmp_path, test_email_no_attachments):
        """Test saving email with empty attachments list."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            await storage.save_email(test_email_no_attachments)

        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        attachments_json = params[7]

        assert attachments_json == "[]"

    @pytest.mark.asyncio
    async def test_save_email_validates_id_on_save(self, tmp_path, test_email):
        """Test that save validates email ID is not empty."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Manually set ID to empty string after construction
        test_email.id = ""

        with pytest.raises(StorageError) as exc_info:
            await storage.save_email(test_email)

        assert exc_info.value.code == "STORAGE_ERROR"
        assert "Email ID is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_save_email_database_error_raises_storage_error(self, tmp_path, test_email):
        """Test that database errors are wrapped in StorageError."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        with patch("aiosqlite.connect", side_effect=Exception("Database connection failed")):
            with pytest.raises(StorageError) as exc_info:
                await storage.save_email(test_email)

            assert exc_info.value.code == "STORAGE_ERROR"
            assert "Failed to save email" in exc_info.value.message
            assert exc_info.value.operation == "save"
            assert exc_info.value.entity_id == "msg-test123"


class TestEmailStorageGet:
    """Tests for retrieving emails."""

    @pytest.mark.asyncio
    async def test_get_email_success(self, tmp_path, test_email):
        """Test successfully retrieving an email using actual database."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Initialize database and save test email
        await storage.init_db()
        await storage.save_email(test_email)

        # Retrieve the email
        result = await storage.get_email("msg-test123")

        assert result is not None
        assert result.id == "msg-test123"
        assert result.inbox == "user@example.com"
        assert result.thread_id == "thread-abc"
        assert result.subject == "Test Email"
        assert len(result.attachments) == 1
        assert result.attachments[0].filename == "test.pdf"
        assert result.read is False

    @pytest.mark.asyncio
    async def test_get_email_not_found(self, tmp_path):
        """Test retrieving non-existent email returns None."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.row_factory = None
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            result = await storage.get_email("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_email_empty_message_id_fails(self, tmp_path):
        """Test that empty message ID raises StorageError."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        with pytest.raises(StorageError) as exc_info:
            await storage.get_email("")

        assert exc_info.value.code == "STORAGE_ERROR"
        assert "Message ID is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_email_database_error_raises_storage_error(self, tmp_path):
        """Test that database errors are wrapped in StorageError."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        with patch("aiosqlite.connect", side_effect=Exception("Database error")):
            with pytest.raises(StorageError) as exc_info:
                await storage.get_email("msg-test123")

            assert exc_info.value.code == "STORAGE_ERROR"
            assert "Failed to retrieve email" in exc_info.value.message
            assert exc_info.value.entity_id == "msg-test123"


class TestEmailStorageListByInbox:
    """Tests for listing emails by inbox."""

    @pytest.mark.asyncio
    async def test_list_emails_by_inbox_success(self, tmp_path):
        """Test successfully listing emails for an inbox using actual database."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Initialize database
        await storage.init_db()

        # Create and save test emails
        email1 = StoredEmail(
            id="msg-1",
            inbox="user@example.com",
            thread_id=None,
            from_address="sender1@example.com",
            to_address="user@example.com",
            subject="Email 1",
            body_text="Body 1",
            attachments=[],
            received_at=datetime(2025, 12, 13, 10, 0, 0, tzinfo=timezone.utc),
            read=True,
        )
        email2 = StoredEmail(
            id="msg-2",
            inbox="user@example.com",
            thread_id="thread-abc",
            from_address="sender2@example.com",
            to_address="user@example.com",
            subject="Email 2",
            body_text="Body 2",
            attachments=[],
            received_at=datetime(2025, 12, 13, 11, 0, 0, tzinfo=timezone.utc),
            read=False,
        )
        await storage.save_email(email1)
        await storage.save_email(email2)

        # List emails
        result = await storage.list_emails_by_inbox("user@example.com")

        # Results should be ordered by received_at DESC (newest first)
        assert len(result) == 2
        assert result[0].id == "msg-2"  # Newer email first
        assert result[0].read is False
        assert result[1].id == "msg-1"
        assert result[1].read is True

    @pytest.mark.asyncio
    async def test_list_emails_by_inbox_empty_result(self, tmp_path):
        """Test listing emails for inbox with no emails."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Initialize database
        await storage.init_db()

        # List emails for inbox that has no emails
        result = await storage.list_emails_by_inbox("empty@example.com")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_emails_by_inbox_empty_inbox_fails(self, tmp_path):
        """Test that empty inbox raises StorageError."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        with pytest.raises(StorageError) as exc_info:
            await storage.list_emails_by_inbox("")

        assert exc_info.value.code == "STORAGE_ERROR"
        assert "Inbox is required" in exc_info.value.message


class TestEmailStorageListInboxes:
    """Tests for listing all inboxes."""

    @pytest.mark.asyncio
    async def test_list_inboxes_success(self, tmp_path):
        """Test successfully listing all inboxes using actual database."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Initialize database
        await storage.init_db()

        # Create emails for different inboxes
        for i, inbox in enumerate(["user2@example.com", "user1@example.com", "user3@example.com"]):
            email = StoredEmail(
                id=f"msg-{i}",
                inbox=inbox,
                from_address=f"sender{i}@example.com",
                to_address=inbox,
                subject=f"Email {i}",
                body_text=f"Body {i}",
                received_at=datetime.now(timezone.utc),
            )
            await storage.save_email(email)

        # List inboxes (should be sorted alphabetically)
        result = await storage.list_inboxes()

        assert result == ["user1@example.com", "user2@example.com", "user3@example.com"]

    @pytest.mark.asyncio
    async def test_list_inboxes_empty_result(self, tmp_path):
        """Test listing inboxes when no emails exist."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        # Initialize database
        await storage.init_db()

        # List inboxes with no emails
        result = await storage.list_inboxes()

        assert result == []


class TestEmailStorageDelete:
    """Tests for deleting emails."""

    @pytest.mark.asyncio
    async def test_delete_email_success(self, tmp_path):
        """Test successfully deleting an email."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            await storage.delete_email("msg-test123")

        # Verify SQL execution
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "DELETE FROM emails WHERE id = ?" in sql
        assert params == ("msg-test123",)
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_email_not_found(self, tmp_path):
        """Test deleting non-existent email (rowcount=0)."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 0

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            # Should not raise error, just log warning
            await storage.delete_email("nonexistent")

        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_email_empty_message_id_fails(self, tmp_path):
        """Test that empty message ID raises StorageError."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        with pytest.raises(StorageError) as exc_info:
            await storage.delete_email("")

        assert exc_info.value.code == "STORAGE_ERROR"
        assert "Message ID is required" in exc_info.value.message


class TestEmailStorageMarkAsRead:
    """Tests for marking emails as read."""

    @pytest.mark.asyncio
    async def test_mark_as_read_success(self, tmp_path):
        """Test successfully marking email as read."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            await storage.mark_as_read("msg-test123")

        # Verify SQL execution
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "UPDATE emails SET read = 1 WHERE id = ?" in sql
        assert params == ("msg-test123",)
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_as_read_not_found(self, tmp_path):
        """Test marking non-existent email as read (rowcount=0)."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 0

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()

        with patch("aiosqlite.connect", return_value=mock_conn):
            # Should not raise error, just log warning
            await storage.mark_as_read("nonexistent")

        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_as_read_empty_message_id_fails(self, tmp_path):
        """Test that empty message ID raises StorageError."""
        db_path = tmp_path / "test.db"
        storage = EmailStorage(db_path=str(db_path))

        with pytest.raises(StorageError) as exc_info:
            await storage.mark_as_read("")

        assert exc_info.value.code == "STORAGE_ERROR"
        assert "Message ID is required" in exc_info.value.message
