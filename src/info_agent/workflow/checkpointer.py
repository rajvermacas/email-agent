"""
SQLite checkpointer for LangGraph workflow persistence.

This module provides checkpoint storage for workflow state persistence
using the official langgraph-checkpoint-sqlite package.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger(__name__)


class CheckpointStorage:
    """
    SQLite storage for checkpoints.

    This is a simpler storage layer that can be used for custom
    checkpoint management or as a lightweight alternative.
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize checkpoint storage.

        Args:
            db_path: Path to SQLite database file.

        Raises:
            ValueError: If db_path is empty.
        """
        if not db_path:
            raise ValueError("db_path is required")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Initializing checkpoint storage at %s", self.db_path)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        logger.debug("Initializing checkpoint database schema")

        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    type TEXT,
                    checkpoint BLOB NOT NULL,
                    metadata BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_id
                ON checkpoints(thread_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoint_ns
                ON checkpoints(thread_id, checkpoint_ns)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS writes (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    type TEXT,
                    value BLOB,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                )
            """)

            conn.commit()
            logger.info("Checkpoint database schema initialized")
        finally:
            conn.close()

    def save_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        checkpoint_data: bytes,
        metadata: bytes | None = None,
        parent_checkpoint_id: str | None = None,
    ) -> None:
        """
        Save a checkpoint.

        Args:
            thread_id: Thread identifier.
            checkpoint_ns: Checkpoint namespace.
            checkpoint_id: Checkpoint identifier.
            checkpoint_data: Serialized checkpoint data.
            metadata: Optional serialized metadata.
            parent_checkpoint_id: Optional parent checkpoint ID.
        """
        logger.debug(
            "Saving checkpoint: thread_id=%s, checkpoint_id=%s",
            thread_id,
            checkpoint_id,
        )

        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints
                (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                 checkpoint, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    parent_checkpoint_id,
                    checkpoint_data,
                    metadata,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            logger.debug("Checkpoint saved successfully")
        finally:
            conn.close()

    def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
        checkpoint_id: str | None = None,
    ) -> tuple[bytes, bytes | None, str | None] | None:
        """
        Load a checkpoint.

        Args:
            thread_id: Thread identifier.
            checkpoint_ns: Checkpoint namespace.
            checkpoint_id: Optional specific checkpoint ID.

        Returns:
            Tuple of (checkpoint_data, metadata, parent_id) or None.
        """
        logger.debug(
            "Loading checkpoint: thread_id=%s, checkpoint_id=%s",
            thread_id,
            checkpoint_id,
        )

        conn = self._get_connection()
        try:
            if checkpoint_id:
                row = conn.execute(
                    """
                    SELECT checkpoint, metadata, parent_checkpoint_id
                    FROM checkpoints
                    WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                    """,
                    (thread_id, checkpoint_ns, checkpoint_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT checkpoint, metadata, parent_checkpoint_id
                    FROM checkpoints
                    WHERE thread_id = ? AND checkpoint_ns = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (thread_id, checkpoint_ns),
                ).fetchone()

            if row:
                logger.debug("Checkpoint loaded successfully")
                return row["checkpoint"], row["metadata"], row["parent_checkpoint_id"]

            logger.debug("No checkpoint found")
            return None
        finally:
            conn.close()

    def list_checkpoints(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        List checkpoints for a thread.

        Args:
            thread_id: Thread identifier.
            checkpoint_ns: Checkpoint namespace.
            limit: Maximum number of results.

        Returns:
            List of checkpoint metadata.
        """
        logger.debug("Listing checkpoints for thread_id=%s", thread_id)

        conn = self._get_connection()
        try:
            query = """
                SELECT checkpoint_id, parent_checkpoint_id, created_at
                FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ?
                ORDER BY created_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            rows = conn.execute(query, (thread_id, checkpoint_ns)).fetchall()

            result = [
                {
                    "checkpoint_id": row["checkpoint_id"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

            logger.debug("Found %d checkpoints", len(result))
            return result
        finally:
            conn.close()

    def delete_checkpoints(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
    ) -> int:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Thread identifier.
            checkpoint_ns: Checkpoint namespace.

        Returns:
            Number of deleted checkpoints.
        """
        logger.info("Deleting checkpoints for thread_id=%s", thread_id)

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                DELETE FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ?
                """,
                (thread_id, checkpoint_ns),
            )
            conn.commit()
            count = cursor.rowcount
            logger.info("Deleted %d checkpoints", count)
            return count
        finally:
            conn.close()

    def save_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        writes: list[tuple[str, str, str, bytes]],
    ) -> None:
        """
        Save pending writes.

        Args:
            thread_id: Thread identifier.
            checkpoint_ns: Checkpoint namespace.
            checkpoint_id: Checkpoint identifier.
            writes: List of (task_id, channel, type, value) tuples.
        """
        if not writes:
            return

        logger.debug(
            "Saving %d writes for checkpoint_id=%s",
            len(writes),
            checkpoint_id,
        )

        conn = self._get_connection()
        try:
            for idx, (task_id, channel, type_, value) in enumerate(writes):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO writes
                    (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type_, value),
                )
            conn.commit()
        finally:
            conn.close()

    def load_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> list[tuple[str, str, str, bytes]]:
        """
        Load pending writes.

        Args:
            thread_id: Thread identifier.
            checkpoint_ns: Checkpoint namespace.
            checkpoint_id: Checkpoint identifier.

        Returns:
            List of (task_id, channel, type, value) tuples.
        """
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT task_id, channel, type, value
                FROM writes
                WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                ORDER BY idx
                """,
                (thread_id, checkpoint_ns, checkpoint_id),
            ).fetchall()

            return [
                (row["task_id"], row["channel"], row["type"], row["value"])
                for row in rows
            ]
        finally:
            conn.close()


def create_checkpointer(db_path: str | Path) -> SqliteSaver:
    """
    Create a synchronous SQLite checkpoint saver.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Configured SqliteSaver instance.

    Raises:
        ValueError: If db_path is empty.
    """
    if not db_path:
        raise ValueError("db_path is required")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Creating sync checkpointer with db_path=%s", db_path)

    # Use the official SqliteSaver from langgraph-checkpoint-sqlite
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


async def create_async_checkpointer(db_path: str | Path) -> tuple[AsyncSqliteSaver, Any]:
    """
    Create an async SQLite checkpoint saver for async workflows.

    Note: This returns both the checkpointer and its context manager.
    The context manager must be kept alive for the checkpointer to work.
    Call ctx_manager.__aexit__(None, None, None) when done.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Tuple of (AsyncSqliteSaver, context_manager).

    Raises:
        ValueError: If db_path is empty.
    """
    if not db_path:
        raise ValueError("db_path is required")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Creating async checkpointer with db_path=%s", db_path)

    # Use the official AsyncSqliteSaver from langgraph-checkpoint-sqlite
    # Note: This returns a context manager that needs to be entered
    ctx_manager = AsyncSqliteSaver.from_conn_string(str(db_path))
    checkpointer = await ctx_manager.__aenter__()
    return checkpointer, ctx_manager
