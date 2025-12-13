"""
SQLite checkpointing for LangGraph workflows.

This module provides SQLite-based state persistence for LangGraph,
allowing workflows to be resumed after restarts.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


def create_checkpointer(db_path: str) -> SqliteSaver:
    """
    Create SQLite checkpointer for LangGraph.

    This function initializes the SQLite database and creates the
    necessary tables and indexes for checkpoint storage.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Configured SqliteSaver instance.

    Raises:
        StorageError: If database initialization fails.
    """
    logger.info(f"Initializing SQLite checkpointer at {db_path}")

    # Ensure directory exists
    path = Path(db_path)
    parent = path.parent
    logger.debug(f"Ensuring parent directory exists: {parent}")
    parent.mkdir(parents=True, exist_ok=True)

    # Create connection with proper settings
    logger.debug("Creating SQLite connection")
    conn = sqlite3.connect(db_path, check_same_thread=False)

    # Enable WAL mode for better concurrent access
    logger.debug("Enabling WAL mode")
    conn.execute("PRAGMA journal_mode=WAL")

    # Create checkpoint tables if they don't exist
    logger.debug("Creating checkpoint tables")
    _create_checkpoint_tables(conn)

    logger.info(f"SQLite checkpointer initialized successfully at {db_path}")

    return SqliteSaver(conn)


def _create_checkpoint_tables(conn: sqlite3.Connection) -> None:
    """
    Create checkpoint tables and indexes.

    Args:
        conn: SQLite database connection.
    """
    logger.debug("Creating checkpoints table")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_id TEXT NOT NULL,
            parent_id TEXT,
            checkpoint BLOB NOT NULL,
            metadata BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (thread_id, checkpoint_id)
        )
    """)

    logger.debug("Creating checkpoints index")
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id
        ON checkpoints(thread_id)
    """)

    logger.debug("Creating checkpoint writes table")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
            thread_id TEXT NOT NULL,
            checkpoint_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            idx INTEGER NOT NULL,
            channel TEXT NOT NULL,
            value BLOB,
            PRIMARY KEY (thread_id, checkpoint_id, task_id, idx)
        )
    """)

    conn.commit()
    logger.debug("Checkpoint tables created successfully")


def compile_workflow_with_checkpointer(
    workflow: StateGraph,
    db_path: str,
) -> Any:
    """
    Compile a LangGraph workflow with SQLite checkpointing.

    Args:
        workflow: LangGraph StateGraph to compile.
        db_path: Path to the SQLite database file.

    Returns:
        Compiled workflow with checkpointing enabled.
    """
    logger.info(f"Compiling workflow with checkpointer at {db_path}")

    checkpointer = create_checkpointer(db_path)

    compiled = workflow.compile(checkpointer=checkpointer)

    logger.info("Workflow compiled successfully with checkpointing")

    return compiled


async def get_workflow_state(
    compiled_workflow: Any,
    thread_id: str,
) -> dict[str, Any] | None:
    """
    Retrieve the current state of a workflow thread.

    Args:
        compiled_workflow: Compiled LangGraph workflow.
        thread_id: Workflow thread identifier.

    Returns:
        Current state dictionary or None if not found.
    """
    logger.debug(f"Retrieving state for thread {thread_id}")

    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = compiled_workflow.get_state(config)

        if state and state.values:
            logger.debug(f"State retrieved for thread {thread_id}")
            return dict(state.values)

        logger.debug(f"No state found for thread {thread_id}")
        return None

    except Exception as e:
        logger.error(f"Failed to retrieve state for thread {thread_id}: {e}")
        return None


async def list_workflow_threads(db_path: str) -> list[str]:
    """
    List all workflow thread IDs in the database.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of thread IDs.
    """
    logger.debug(f"Listing workflow threads from {db_path}")

    path = Path(db_path)
    if not path.exists():
        logger.debug("Database does not exist, returning empty list")
        return []

    conn = sqlite3.connect(db_path, check_same_thread=False)

    try:
        cursor = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY created_at DESC"
        )
        threads = [row[0] for row in cursor.fetchall()]
        logger.debug(f"Found {len(threads)} workflow threads")
        return threads

    finally:
        conn.close()


async def delete_workflow_thread(
    db_path: str,
    thread_id: str,
) -> bool:
    """
    Delete a workflow thread and all its checkpoints.

    Args:
        db_path: Path to the SQLite database file.
        thread_id: Thread ID to delete.

    Returns:
        True if deleted, False if not found.
    """
    logger.info(f"Deleting workflow thread {thread_id}")

    path = Path(db_path)
    if not path.exists():
        logger.warning(f"Database does not exist: {db_path}")
        return False

    conn = sqlite3.connect(db_path, check_same_thread=False)

    try:
        # Delete from checkpoint_writes first (foreign key-like relationship)
        cursor = conn.execute(
            "DELETE FROM checkpoint_writes WHERE thread_id = ?",
            (thread_id,)
        )
        writes_deleted = cursor.rowcount

        # Delete from checkpoints
        cursor = conn.execute(
            "DELETE FROM checkpoints WHERE thread_id = ?",
            (thread_id,)
        )
        checkpoints_deleted = cursor.rowcount

        conn.commit()

        if checkpoints_deleted > 0:
            logger.info(
                f"Deleted thread {thread_id}: "
                f"{checkpoints_deleted} checkpoints, {writes_deleted} writes"
            )
            return True

        logger.debug(f"Thread {thread_id} not found")
        return False

    finally:
        conn.close()
