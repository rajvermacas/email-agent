"""
Email storage implementation.

Provides in-memory storage for emails with query capabilities.
"""

import threading
from collections import defaultdict
from typing import Any

import structlog

from info_agent.email_server.models import Email, EmailStatus
from info_agent.utils.exceptions import EmailServerError

logger = structlog.get_logger(__name__)


class EmailStorage:
    """
    Thread-safe in-memory email storage.

    Provides storage and retrieval of emails with indexing
    for efficient queries by mailbox, thread, and address.

    Attributes:
        _emails: Dictionary mapping email ID to Email object.
        _mailboxes: Dictionary mapping (address, mailbox) to list of email IDs.
        _threads: Dictionary mapping thread ID to list of email IDs.
        _lock: Threading lock for thread-safe operations.
    """

    def __init__(self) -> None:
        """Initialize empty email storage."""
        self._emails: dict[str, Email] = {}
        self._mailboxes: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._threads: dict[str, list[str]] = defaultdict(list)
        self._lock = threading.RLock()

        logger.info("email_storage_initialized")

    def store(self, email: Email) -> Email:
        """
        Store an email in storage.

        Args:
            email: Email to store.

        Returns:
            Stored email with any updates.

        Raises:
            EmailServerError: If storage fails.
        """
        with self._lock:
            try:
                logger.debug(
                    "storing_email",
                    email_id=email.id,
                    from_address=email.from_address.address,
                    to_addresses=[a.address for a in email.to_addresses],
                    subject=email.subject[:50] if email.subject else "",
                )

                # Store the email
                self._emails[email.id] = email

                # Index by mailbox for each recipient
                for recipient in email.to_addresses:
                    key = (recipient.address.lower(), email.mailbox)
                    if email.id not in self._mailboxes[key]:
                        self._mailboxes[key].append(email.id)

                # Index by thread
                if email.thread_id:
                    if email.id not in self._threads[email.thread_id]:
                        self._threads[email.thread_id].append(email.id)

                # Also index for sender in sent mailbox
                if email.mailbox == "sent":
                    sender_key = (email.from_address.address.lower(), "sent")
                    if email.id not in self._mailboxes[sender_key]:
                        self._mailboxes[sender_key].append(email.id)

                logger.info(
                    "email_stored",
                    email_id=email.id,
                    mailbox=email.mailbox,
                    thread_id=email.thread_id,
                )

                return email

            except Exception as e:
                logger.error("email_storage_failed", email_id=email.id, error=str(e))
                raise EmailServerError(
                    message=f"Failed to store email: {e}",
                    details={"email_id": email.id, "error": str(e)},
                ) from e

    def get(self, email_id: str) -> Email | None:
        """
        Retrieve an email by ID.

        Args:
            email_id: ID of email to retrieve.

        Returns:
            Email if found, None otherwise.
        """
        with self._lock:
            email = self._emails.get(email_id)
            if email:
                logger.debug("email_retrieved", email_id=email_id)
            else:
                logger.debug("email_not_found", email_id=email_id)
            return email

    def get_by_message_id(self, message_id: str) -> Email | None:
        """
        Retrieve an email by Message-ID header.

        Args:
            message_id: Message-ID to search for.

        Returns:
            Email if found, None otherwise.
        """
        with self._lock:
            for email in self._emails.values():
                if email.message_id == message_id:
                    logger.debug("email_found_by_message_id", message_id=message_id)
                    return email

            logger.debug("email_not_found_by_message_id", message_id=message_id)
            return None

    def list_by_mailbox(
        self,
        address: str,
        mailbox: str = "inbox",
        page: int = 1,
        page_size: int = 20,
        status: EmailStatus | None = None,
    ) -> tuple[list[Email], int]:
        """
        List emails in a mailbox for an address.

        Args:
            address: Email address to get mailbox for.
            mailbox: Mailbox name (inbox, sent, etc.).
            page: Page number (1-indexed).
            page_size: Number of emails per page.
            status: Optional status filter.

        Returns:
            Tuple of (list of emails, total count).
        """
        with self._lock:
            key = (address.lower(), mailbox)
            email_ids = self._mailboxes.get(key, [])

            # Get emails and filter by status if needed
            emails = []
            for email_id in email_ids:
                email = self._emails.get(email_id)
                if email:
                    if status is None or email.status == status:
                        emails.append(email)

            # Sort by created_at descending (newest first)
            emails.sort(key=lambda e: e.created_at, reverse=True)

            total = len(emails)

            # Paginate
            start = (page - 1) * page_size
            end = start + page_size
            paginated = emails[start:end]

            logger.debug(
                "emails_listed",
                address=address,
                mailbox=mailbox,
                total=total,
                page=page,
                returned=len(paginated),
            )

            return paginated, total

    def list_by_thread(self, thread_id: str) -> list[Email]:
        """
        List all emails in a thread.

        Args:
            thread_id: Thread ID to get emails for.

        Returns:
            List of emails in the thread, sorted by creation time.
        """
        with self._lock:
            email_ids = self._threads.get(thread_id, [])
            emails = []

            for email_id in email_ids:
                email = self._emails.get(email_id)
                if email:
                    emails.append(email)

            # Sort by created_at ascending (oldest first)
            emails.sort(key=lambda e: e.created_at)

            logger.debug(
                "thread_emails_listed",
                thread_id=thread_id,
                count=len(emails),
            )

            return emails

    def search(
        self,
        query: str,
        address: str | None = None,
        mailbox: str | None = None,
        limit: int = 50,
    ) -> list[Email]:
        """
        Search emails by subject or body content.

        Args:
            query: Search query string.
            address: Optional address to filter by.
            mailbox: Optional mailbox to filter by.
            limit: Maximum results to return.

        Returns:
            List of matching emails.
        """
        with self._lock:
            query_lower = query.lower()
            results = []

            for email in self._emails.values():
                # Check address filter
                if address:
                    recipient_addresses = [
                        a.address.lower() for a in email.to_addresses
                    ]
                    sender_address = email.from_address.address.lower()
                    if (
                        address.lower() not in recipient_addresses
                        and address.lower() != sender_address
                    ):
                        continue

                # Check mailbox filter
                if mailbox and email.mailbox != mailbox:
                    continue

                # Search in subject and body
                if (
                    query_lower in email.subject.lower()
                    or query_lower in email.body_text.lower()
                ):
                    results.append(email)

                if len(results) >= limit:
                    break

            # Sort by relevance (subject match first) then by date
            results.sort(
                key=lambda e: (
                    0 if query_lower in e.subject.lower() else 1,
                    e.created_at,
                ),
                reverse=True,
            )

            logger.debug(
                "email_search_completed",
                query=query[:50],
                results_count=len(results),
            )

            return results

    def update(self, email: Email) -> Email:
        """
        Update an existing email.

        Args:
            email: Email with updated fields.

        Returns:
            Updated email.

        Raises:
            EmailServerError: If email not found.
        """
        with self._lock:
            if email.id not in self._emails:
                logger.error("email_update_failed_not_found", email_id=email.id)
                raise EmailServerError(
                    message=f"Email not found: {email.id}",
                    details={"email_id": email.id},
                )

            self._emails[email.id] = email
            logger.debug("email_updated", email_id=email.id)
            return email

    def delete(self, email_id: str) -> bool:
        """
        Delete an email by ID.

        Args:
            email_id: ID of email to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            email = self._emails.pop(email_id, None)
            if not email:
                logger.debug("email_delete_not_found", email_id=email_id)
                return False

            # Remove from mailbox indexes
            for key in list(self._mailboxes.keys()):
                if email_id in self._mailboxes[key]:
                    self._mailboxes[key].remove(email_id)

            # Remove from thread index
            if email.thread_id and email_id in self._threads[email.thread_id]:
                self._threads[email.thread_id].remove(email_id)

            logger.info("email_deleted", email_id=email_id)
            return True

    def count(self) -> int:
        """
        Get total number of stored emails.

        Returns:
            Count of emails in storage.
        """
        with self._lock:
            return len(self._emails)

    def count_by_mailbox(self, address: str, mailbox: str = "inbox") -> int:
        """
        Count emails in a mailbox.

        Args:
            address: Email address.
            mailbox: Mailbox name.

        Returns:
            Count of emails in mailbox.
        """
        with self._lock:
            key = (address.lower(), mailbox)
            return len(self._mailboxes.get(key, []))

    def count_unread(self, address: str, mailbox: str = "inbox") -> int:
        """
        Count unread emails in a mailbox.

        Args:
            address: Email address.
            mailbox: Mailbox name.

        Returns:
            Count of unread emails.
        """
        with self._lock:
            key = (address.lower(), mailbox)
            email_ids = self._mailboxes.get(key, [])

            count = 0
            for email_id in email_ids:
                email = self._emails.get(email_id)
                if email and email.status not in [EmailStatus.READ]:
                    count += 1

            return count

    def clear(self) -> int:
        """
        Clear all stored emails.

        Returns:
            Number of emails cleared.
        """
        with self._lock:
            count = len(self._emails)
            self._emails.clear()
            self._mailboxes.clear()
            self._threads.clear()
            logger.info("email_storage_cleared", count=count)
            return count

    def get_stats(self) -> dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats.
        """
        with self._lock:
            status_counts: dict[str, int] = defaultdict(int)
            for email in self._emails.values():
                status_counts[email.status.value] += 1

            return {
                "total_emails": len(self._emails),
                "total_mailboxes": len(self._mailboxes),
                "total_threads": len(self._threads),
                "status_counts": dict(status_counts),
            }
