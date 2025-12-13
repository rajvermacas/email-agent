"""
Unit tests for email storage.
"""

import pytest

from info_agent.email_server.models import Email, EmailAddress, EmailStatus
from info_agent.email_server.storage import EmailStorage
from info_agent.utils.exceptions import EmailServerError


class TestEmailStorageStore:
    """Tests for storing emails."""

    def test_store_email(self) -> None:
        """Test storing a basic email."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="recipient@example.com")],
            subject="Test",
            body_text="Body",
        )

        result = storage.store(email)

        assert result.id == email.id
        assert storage.count() == 1

    def test_store_multiple_emails(self) -> None:
        """Test storing multiple emails."""
        storage = EmailStorage()

        for i in range(5):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                to_addresses=[EmailAddress(address=f"recipient{i}@example.com")],
            )
            storage.store(email)

        assert storage.count() == 5

    def test_store_indexes_by_mailbox(self) -> None:
        """Test email is indexed by mailbox."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="recipient@example.com")],
            mailbox="inbox",
        )

        storage.store(email)

        count = storage.count_by_mailbox("recipient@example.com", "inbox")
        assert count == 1

    def test_store_indexes_by_thread(self) -> None:
        """Test email is indexed by thread."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="recipient@example.com")],
        )

        stored = storage.store(email)
        thread_emails = storage.list_by_thread(stored.thread_id)

        assert len(thread_emails) == 1


class TestEmailStorageGet:
    """Tests for retrieving emails."""

    def test_get_existing_email(self) -> None:
        """Test getting an existing email."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="Test Subject",
        )
        storage.store(email)

        result = storage.get(email.id)

        assert result is not None
        assert result.subject == "Test Subject"

    def test_get_nonexistent_email(self) -> None:
        """Test getting a nonexistent email."""
        storage = EmailStorage()

        result = storage.get("nonexistent-id")

        assert result is None

    def test_get_by_message_id(self) -> None:
        """Test getting email by message ID."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
        )
        storage.store(email)

        result = storage.get_by_message_id(email.message_id)

        assert result is not None
        assert result.id == email.id

    def test_get_by_message_id_not_found(self) -> None:
        """Test getting email by nonexistent message ID."""
        storage = EmailStorage()

        result = storage.get_by_message_id("<nonexistent@example.com>")

        assert result is None


class TestEmailStorageListByMailbox:
    """Tests for listing emails by mailbox."""

    def test_list_by_mailbox(self) -> None:
        """Test listing emails in a mailbox."""
        storage = EmailStorage()

        for i in range(3):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                to_addresses=[EmailAddress(address="user@example.com")],
                subject=f"Email {i}",
                mailbox="inbox",
            )
            storage.store(email)

        emails, total = storage.list_by_mailbox("user@example.com", "inbox")

        assert total == 3
        assert len(emails) == 3

    def test_list_by_mailbox_pagination(self) -> None:
        """Test pagination when listing emails."""
        storage = EmailStorage()

        for i in range(10):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                to_addresses=[EmailAddress(address="user@example.com")],
                mailbox="inbox",
            )
            storage.store(email)

        emails, total = storage.list_by_mailbox(
            "user@example.com", "inbox", page=1, page_size=5
        )

        assert total == 10
        assert len(emails) == 5

    def test_list_by_mailbox_page_2(self) -> None:
        """Test getting second page."""
        storage = EmailStorage()

        for i in range(10):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                to_addresses=[EmailAddress(address="user@example.com")],
                mailbox="inbox",
            )
            storage.store(email)

        emails, total = storage.list_by_mailbox(
            "user@example.com", "inbox", page=2, page_size=5
        )

        assert total == 10
        assert len(emails) == 5

    def test_list_by_mailbox_filter_status(self) -> None:
        """Test filtering by status."""
        storage = EmailStorage()

        for i in range(3):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                to_addresses=[EmailAddress(address="user@example.com")],
                status=EmailStatus.RECEIVED if i < 2 else EmailStatus.READ,
                mailbox="inbox",
            )
            storage.store(email)

        emails, total = storage.list_by_mailbox(
            "user@example.com", "inbox", status=EmailStatus.RECEIVED
        )

        assert total == 2

    def test_list_by_mailbox_case_insensitive(self) -> None:
        """Test address matching is case insensitive."""
        storage = EmailStorage()

        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="User@Example.COM")],
            mailbox="inbox",
        )
        storage.store(email)

        emails, total = storage.list_by_mailbox("user@example.com", "inbox")

        assert total == 1


class TestEmailStorageListByThread:
    """Tests for listing emails by thread."""

    def test_list_by_thread(self) -> None:
        """Test listing emails in a thread."""
        storage = EmailStorage()

        original = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="recipient@example.com")],
            subject="Original",
        )
        storage.store(original)

        reply = Email(
            from_address=EmailAddress(address="recipient@example.com"),
            to_addresses=[EmailAddress(address="sender@example.com")],
            in_reply_to=original.message_id,
            subject="Re: Original",
        )
        storage.store(reply)

        thread_emails = storage.list_by_thread(original.thread_id)

        assert len(thread_emails) == 2

    def test_list_by_thread_sorted(self) -> None:
        """Test thread emails are sorted by creation time."""
        storage = EmailStorage()

        original = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="First",
        )
        storage.store(original)

        reply = Email(
            from_address=EmailAddress(address="recipient@example.com"),
            in_reply_to=original.message_id,
            subject="Second",
        )
        storage.store(reply)

        thread_emails = storage.list_by_thread(original.thread_id)

        assert thread_emails[0].subject == "First"
        assert thread_emails[1].subject == "Second"


class TestEmailStorageSearch:
    """Tests for email search."""

    def test_search_by_subject(self) -> None:
        """Test searching by subject."""
        storage = EmailStorage()

        email1 = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="Important meeting tomorrow",
        )
        email2 = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="Random topic",
        )
        storage.store(email1)
        storage.store(email2)

        results = storage.search("meeting")

        assert len(results) == 1
        assert "meeting" in results[0].subject.lower()

    def test_search_by_body(self) -> None:
        """Test searching by body content."""
        storage = EmailStorage()

        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="Test",
            body_text="Please review the attached document",
        )
        storage.store(email)

        results = storage.search("document")

        assert len(results) == 1

    def test_search_case_insensitive(self) -> None:
        """Test search is case insensitive."""
        storage = EmailStorage()

        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="IMPORTANT Notice",
        )
        storage.store(email)

        results = storage.search("important")

        assert len(results) == 1

    def test_search_with_address_filter(self) -> None:
        """Test search with address filter."""
        storage = EmailStorage()

        email1 = Email(
            from_address=EmailAddress(address="alice@example.com"),
            to_addresses=[EmailAddress(address="bob@example.com")],
            subject="Meeting notes",
        )
        email2 = Email(
            from_address=EmailAddress(address="charlie@example.com"),
            to_addresses=[EmailAddress(address="dave@example.com")],
            subject="Meeting agenda",
        )
        storage.store(email1)
        storage.store(email2)

        results = storage.search("meeting", address="bob@example.com")

        assert len(results) == 1

    def test_search_limit(self) -> None:
        """Test search respects limit."""
        storage = EmailStorage()

        for i in range(10):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                subject=f"Test email {i}",
            )
            storage.store(email)

        results = storage.search("test", limit=5)

        assert len(results) == 5


class TestEmailStorageUpdate:
    """Tests for updating emails."""

    def test_update_email(self) -> None:
        """Test updating an email."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            subject="Original Subject",
        )
        storage.store(email)

        email.subject = "Updated Subject"
        storage.update(email)

        retrieved = storage.get(email.id)
        assert retrieved.subject == "Updated Subject"

    def test_update_nonexistent_raises(self) -> None:
        """Test updating nonexistent email raises error."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
        )

        with pytest.raises(EmailServerError) as exc_info:
            storage.update(email)

        assert "not found" in str(exc_info.value).lower()


class TestEmailStorageDelete:
    """Tests for deleting emails."""

    def test_delete_email(self) -> None:
        """Test deleting an email."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
        )
        storage.store(email)

        result = storage.delete(email.id)

        assert result is True
        assert storage.count() == 0

    def test_delete_nonexistent(self) -> None:
        """Test deleting nonexistent email returns False."""
        storage = EmailStorage()

        result = storage.delete("nonexistent-id")

        assert result is False

    def test_delete_removes_from_indexes(self) -> None:
        """Test delete removes email from indexes."""
        storage = EmailStorage()
        email = Email(
            from_address=EmailAddress(address="sender@example.com"),
            to_addresses=[EmailAddress(address="recipient@example.com")],
            mailbox="inbox",
        )
        storage.store(email)

        storage.delete(email.id)

        count = storage.count_by_mailbox("recipient@example.com", "inbox")
        assert count == 0


class TestEmailStorageCounts:
    """Tests for count methods."""

    def test_count(self) -> None:
        """Test counting all emails."""
        storage = EmailStorage()

        for i in range(5):
            storage.store(
                Email(from_address=EmailAddress(address="sender@example.com"))
            )

        assert storage.count() == 5

    def test_count_by_mailbox(self) -> None:
        """Test counting emails in mailbox."""
        storage = EmailStorage()

        for i in range(3):
            storage.store(
                Email(
                    from_address=EmailAddress(address="sender@example.com"),
                    to_addresses=[EmailAddress(address="user@example.com")],
                    mailbox="inbox",
                )
            )

        assert storage.count_by_mailbox("user@example.com", "inbox") == 3

    def test_count_unread(self) -> None:
        """Test counting unread emails."""
        storage = EmailStorage()

        for i in range(3):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                to_addresses=[EmailAddress(address="user@example.com")],
                status=EmailStatus.RECEIVED if i < 2 else EmailStatus.READ,
                mailbox="inbox",
            )
            storage.store(email)

        assert storage.count_unread("user@example.com", "inbox") == 2


class TestEmailStorageClear:
    """Tests for clearing storage."""

    def test_clear(self) -> None:
        """Test clearing all emails."""
        storage = EmailStorage()

        for i in range(5):
            storage.store(
                Email(from_address=EmailAddress(address="sender@example.com"))
            )

        count = storage.clear()

        assert count == 5
        assert storage.count() == 0


class TestEmailStorageStats:
    """Tests for storage statistics."""

    def test_get_stats(self) -> None:
        """Test getting storage stats."""
        storage = EmailStorage()

        for i in range(3):
            email = Email(
                from_address=EmailAddress(address="sender@example.com"),
                status=EmailStatus.RECEIVED if i < 2 else EmailStatus.READ,
            )
            storage.store(email)

        stats = storage.get_stats()

        assert stats["total_emails"] == 3
        assert stats["status_counts"]["received"] == 2
        assert stats["status_counts"]["read"] == 1
