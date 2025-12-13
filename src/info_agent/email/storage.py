"""
SQLite storage implementation for emails.

This module provides async SQLite-based storage for email messages using aiosqlite.
All operations are asynchronous and include comprehensive logging.

Usage:
    from info_agent.email.storage import EmailStorage

    storage = EmailStorage(db_path="data/emails.db")
    await storage.init_db()
    await storage.save_email(email)
"""

import json
from datetime import datetime
from pathlib import Path

import aiosqlite

from info_agent.config import get_settings
from info_agent.email.models import EmailAttachment, StoredEmail
from info_agent.utils.exceptions import StorageError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class EmailStorage:
    """
    Async SQLite storage for email messages.

    Provides methods for storing, retrieving, and managing email messages
    with support for inboxes, threads, and attachments.
    """

    def __init__(self, db_path: str | None = None) -> None:
        """
        Initialize email storage.

        Args:
            db_path: Path to SQLite database file. If None, uses config.

        Raises:
            StorageError: If database path is invalid.
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.email_db_path

        if not db_path:
            raise StorageError(
                message="Database path is required",
                operation="init",
                entity_type="email",
                details={"db_path": db_path},
            )

        self.db_path = Path(db_path)
        logger.info("EmailStorage initialized", db_path=str(self.db_path))

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("Database directory ensured", directory=str(self.db_path.parent))

    async def init_db(self) -> None:
        """
        Initialize database schema with tables and indexes.

        Creates the emails table with appropriate indexes for efficient querying.

        Raises:
            StorageError: If database initialization fails.
        """
        logger.info("Initializing email database", db_path=str(self.db_path))

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create emails table
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS emails (
                        id TEXT PRIMARY KEY,
                        inbox TEXT NOT NULL,
                        thread_id TEXT,
                        from_address TEXT NOT NULL,
                        to_address TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        body_text TEXT NOT NULL,
                        attachments TEXT NOT NULL,
                        received_at TEXT NOT NULL,
                        read INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                logger.debug("Emails table created/verified")

                # Create indexes for efficient querying
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_emails_inbox ON emails(inbox)"
                )
                logger.debug("Index created on inbox column")

                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(thread_id)"
                )
                logger.debug("Index created on thread_id column")

                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at)"
                )
                logger.debug("Index created on received_at column")

                await db.commit()
                logger.info("Email database initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e), error_type=type(e).__name__)
            raise StorageError(
                message=f"Failed to initialize database: {e}",
                operation="init_db",
                entity_type="email",
                details={"db_path": str(self.db_path), "error": str(e)},
            ) from e

    async def save_email(self, email: StoredEmail) -> None:
        """
        Save an email to the database.

        Args:
            email: Email to save.

        Raises:
            StorageError: If save operation fails.
        """
        logger.info(
            "Saving email",
            message_id=email.id,
            inbox=email.inbox,
            from_address=email.from_address,
            subject=email.subject,
        )

        if not email.id:
            raise StorageError(
                message="Email ID is required",
                operation="save",
                entity_type="email",
                details={"email": email.model_dump()},
            )

        try:
            # Serialize attachments to JSON
            attachments_json = json.dumps(
                [att.model_dump() for att in email.attachments]
            )
            logger.debug(
                "Serialized attachments",
                message_id=email.id,
                attachment_count=len(email.attachments),
            )

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO emails (
                        id, inbox, thread_id, from_address, to_address,
                        subject, body_text, attachments, received_at, read
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        email.id,
                        email.inbox,
                        email.thread_id,
                        email.from_address,
                        email.to_address,
                        email.subject,
                        email.body_text,
                        attachments_json,
                        email.received_at.isoformat(),
                        1 if email.read else 0,
                    ),
                )
                await db.commit()
                logger.info("Email saved successfully", message_id=email.id)

        except Exception as e:
            logger.error(
                "Failed to save email",
                message_id=email.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise StorageError(
                message=f"Failed to save email: {e}",
                operation="save",
                entity_type="email",
                entity_id=email.id,
                details={"error": str(e)},
            ) from e

    async def get_email(self, message_id: str) -> StoredEmail | None:
        """
        Retrieve an email by message ID.

        Args:
            message_id: Unique message ID.

        Returns:
            StoredEmail if found, None otherwise.

        Raises:
            StorageError: If retrieval fails.
        """
        logger.debug("Retrieving email", message_id=message_id)

        if not message_id:
            raise StorageError(
                message="Message ID is required",
                operation="get",
                entity_type="email",
                details={"message_id": message_id},
            )

        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM emails WHERE id = ?", (message_id,)
                ) as cursor:
                    row = await cursor.fetchone()

                    if row is None:
                        logger.debug("Email not found", message_id=message_id)
                        return None

                    # Deserialize attachments
                    attachments_data = json.loads(row["attachments"])
                    attachments = [
                        EmailAttachment(**att) for att in attachments_data
                    ]

                    email = StoredEmail(
                        id=row["id"],
                        inbox=row["inbox"],
                        thread_id=row["thread_id"],
                        from_address=row["from_address"],
                        to_address=row["to_address"],
                        subject=row["subject"],
                        body_text=row["body_text"],
                        attachments=attachments,
                        received_at=datetime.fromisoformat(row["received_at"]),
                        read=bool(row["read"]),
                    )

                    logger.info("Email retrieved successfully", message_id=message_id)
                    return email

        except Exception as e:
            logger.error(
                "Failed to retrieve email",
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise StorageError(
                message=f"Failed to retrieve email: {e}",
                operation="get",
                entity_type="email",
                entity_id=message_id,
                details={"error": str(e)},
            ) from e

    async def list_emails_by_inbox(self, inbox: str) -> list[StoredEmail]:
        """
        List all emails for a specific inbox.

        Args:
            inbox: Email address of the inbox.

        Returns:
            List of emails ordered by received_at descending.

        Raises:
            StorageError: If listing fails.
        """
        logger.debug("Listing emails for inbox", inbox=inbox)

        if not inbox:
            raise StorageError(
                message="Inbox is required",
                operation="list",
                entity_type="email",
                details={"inbox": inbox},
            )

        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM emails WHERE inbox = ? ORDER BY received_at DESC",
                    (inbox,),
                ) as cursor:
                    rows = await cursor.fetchall()

                    emails = []
                    for row in rows:
                        attachments_data = json.loads(row["attachments"])
                        attachments = [
                            EmailAttachment(**att) for att in attachments_data
                        ]

                        email = StoredEmail(
                            id=row["id"],
                            inbox=row["inbox"],
                            thread_id=row["thread_id"],
                            from_address=row["from_address"],
                            to_address=row["to_address"],
                            subject=row["subject"],
                            body_text=row["body_text"],
                            attachments=attachments,
                            received_at=datetime.fromisoformat(row["received_at"]),
                            read=bool(row["read"]),
                        )
                        emails.append(email)

                    logger.info(
                        "Emails listed successfully", inbox=inbox, count=len(emails)
                    )
                    return emails

        except Exception as e:
            logger.error(
                "Failed to list emails",
                inbox=inbox,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise StorageError(
                message=f"Failed to list emails: {e}",
                operation="list",
                entity_type="email",
                details={"inbox": inbox, "error": str(e)},
            ) from e

    async def list_inboxes(self) -> list[str]:
        """
        List all unique inbox addresses that have received emails.

        Returns:
            List of inbox email addresses.

        Raises:
            StorageError: If listing fails.
        """
        logger.debug("Listing all inboxes")

        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT DISTINCT inbox FROM emails ORDER BY inbox"
                ) as cursor:
                    rows = await cursor.fetchall()
                    inboxes = [row[0] for row in rows]

                    logger.info("Inboxes listed successfully", count=len(inboxes))
                    return inboxes

        except Exception as e:
            logger.error(
                "Failed to list inboxes", error=str(e), error_type=type(e).__name__
            )
            raise StorageError(
                message=f"Failed to list inboxes: {e}",
                operation="list_inboxes",
                entity_type="email",
                details={"error": str(e)},
            ) from e

    async def delete_email(self, message_id: str) -> None:
        """
        Delete an email by message ID.

        Args:
            message_id: Unique message ID.

        Raises:
            StorageError: If deletion fails.
        """
        logger.info("Deleting email", message_id=message_id)

        if not message_id:
            raise StorageError(
                message="Message ID is required",
                operation="delete",
                entity_type="email",
                details={"message_id": message_id},
            )

        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("DELETE FROM emails WHERE id = ?", (message_id,))
                await db.commit()

                if cursor.rowcount == 0:
                    logger.warning("Email not found for deletion", message_id=message_id)
                else:
                    logger.info("Email deleted successfully", message_id=message_id)

        except Exception as e:
            logger.error(
                "Failed to delete email",
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise StorageError(
                message=f"Failed to delete email: {e}",
                operation="delete",
                entity_type="email",
                entity_id=message_id,
                details={"error": str(e)},
            ) from e

    async def mark_as_read(self, message_id: str) -> None:
        """
        Mark an email as read.

        Args:
            message_id: Unique message ID.

        Raises:
            StorageError: If update fails.
        """
        logger.info("Marking email as read", message_id=message_id)

        if not message_id:
            raise StorageError(
                message="Message ID is required",
                operation="mark_as_read",
                entity_type="email",
                details={"message_id": message_id},
            )

        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "UPDATE emails SET read = 1 WHERE id = ?", (message_id,)
                )
                await db.commit()

                if cursor.rowcount == 0:
                    logger.warning("Email not found for marking as read", message_id=message_id)
                else:
                    logger.info("Email marked as read successfully", message_id=message_id)

        except Exception as e:
            logger.error(
                "Failed to mark email as read",
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise StorageError(
                message=f"Failed to mark email as read: {e}",
                operation="mark_as_read",
                entity_type="email",
                entity_id=message_id,
                details={"error": str(e)},
            ) from e
