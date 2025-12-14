"""
SQLite checkpointing for LangGraph workflows.

This module provides SQLite-based state persistence for LangGraph,
allowing workflows to be resumed after restarts.
"""

import logging
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph

from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


async def create_checkpointer(db_path: str) -> AsyncSqliteSaver:
    """
    Create async SQLite checkpointer for LangGraph.

    This function initializes the SQLite database using AsyncSqliteSaver's
    built-in schema management.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Configured AsyncSqliteSaver instance.

    Raises:
        StorageError: If database initialization fails.
    """
    logger.info(f"Initializing async SQLite checkpointer at {db_path}")

    # Ensure directory exists
    path = Path(db_path)
    parent = path.parent
    logger.debug(f"Ensuring parent directory exists: {parent}")
    parent.mkdir(parents=True, exist_ok=True)

    # Create async connection using aiosqlite
    logger.debug("Creating async SQLite connection")
    conn = await aiosqlite.connect(db_path)

    # Enable WAL mode for better concurrent access
    await conn.execute("PRAGMA journal_mode=WAL")

    # Create AsyncSqliteSaver with the connection
    # Note: AsyncSqliteSaver.from_conn_string is a context manager, so we use direct connection
    logger.debug("Creating AsyncSqliteSaver with aiosqlite connection")
    checkpointer = AsyncSqliteSaver(conn)

    # Setup the database schema (AsyncSqliteSaver manages its own schema)
    await checkpointer.setup()

    logger.info(f"Async SQLite checkpointer initialized successfully at {db_path}")

    return checkpointer


async def _create_checkpoint_tables(conn: aiosqlite.Connection) -> None:
    """
    Create checkpoint tables and indexes.

    Args:
        conn: Async SQLite database connection.
    """
    logger.debug("Creating checkpoints table")

    await conn.execute("""
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
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id
        ON checkpoints(thread_id)
    """)

    logger.debug("Creating checkpoint writes table")
    await conn.execute("""
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

    await conn.commit()
    logger.debug("Checkpoint tables created successfully")


async def compile_workflow_with_checkpointer(
    workflow: StateGraph,
    db_path: str,
) -> Any:
    """
    Compile a LangGraph workflow with async SQLite checkpointing.

    Args:
        workflow: LangGraph StateGraph to compile.
        db_path: Path to the SQLite database file.

    Returns:
        Compiled workflow with async checkpointing enabled.
    """
    logger.info(f"Compiling workflow with async checkpointer at {db_path}")

    checkpointer = await create_checkpointer(db_path)

    compiled = workflow.compile(checkpointer=checkpointer)

    logger.info("Workflow compiled successfully with async checkpointing")

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

    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        threads = [row[0] for row in rows]
        logger.debug(f"Found {len(threads)} workflow threads")
        return threads


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

    async with aiosqlite.connect(db_path) as conn:
        # Delete from checkpoint_writes first (foreign key-like relationship)
        cursor = await conn.execute(
            "DELETE FROM checkpoint_writes WHERE thread_id = ?",
            (thread_id,)
        )
        writes_deleted = cursor.rowcount

        # Delete from checkpoints
        cursor = await conn.execute(
            "DELETE FROM checkpoints WHERE thread_id = ?",
            (thread_id,)
        )
        checkpoints_deleted = cursor.rowcount

        await conn.commit()

        if checkpoints_deleted > 0:
            logger.info(
                f"Deleted thread {thread_id}: "
                f"{checkpoints_deleted} checkpoints, {writes_deleted} writes"
            )
            return True

        logger.debug(f"Thread {thread_id} not found")
        return False
