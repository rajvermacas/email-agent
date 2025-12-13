"""
Unit tests for the workflow checkpointer module.

Tests the SQLite checkpointing functionality for LangGraph workflows,
including database initialization, checkpoint management, and thread operations.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call

from info_agent.workflow.checkpointer import (
    create_checkpointer,
    compile_workflow_with_checkpointer,
    get_workflow_state,
    list_workflow_threads,
    delete_workflow_thread,
    _create_checkpoint_tables,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_checkpoints.db")
        yield db_path


@pytest.fixture
def mock_connection():
    """Create a mock SQLite connection."""
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_cursor = MagicMock()
    mock_conn.execute.return_value = mock_cursor
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def mock_sqlite_saver():
    """Create a mock SqliteSaver."""
    return MagicMock()


@pytest.fixture
def mock_state_graph():
    """Create a mock StateGraph."""
    mock_graph = MagicMock()
    mock_graph.compile.return_value = MagicMock()
    return mock_graph


class TestCreateCheckpointTables:
    """Tests for the _create_checkpoint_tables function."""

    def test_create_checkpoint_tables_success(self, mock_connection):
        """Test successful creation of checkpoint tables."""
        _create_checkpoint_tables(mock_connection)

        # Verify that all required SQL statements were executed
        assert mock_connection.execute.call_count >= 3
        assert mock_connection.commit.call_count == 1

        # Check that checkpoints table was created
        calls = mock_connection.execute.call_args_list
        checkpoints_table_created = any(
            "CREATE TABLE IF NOT EXISTS checkpoints" in str(call)
            for call in calls
        )
        assert checkpoints_table_created

        # Check that checkpoint_writes table was created
        checkpoint_writes_created = any(
            "CREATE TABLE IF NOT EXISTS checkpoint_writes" in str(call)
            for call in calls
        )
        assert checkpoint_writes_created

        # Check that index was created
        index_created = any(
            "CREATE INDEX IF NOT EXISTS" in str(call)
            for call in calls
        )
        assert index_created

    def test_create_checkpoint_tables_structure(self, mock_connection):
        """Test that checkpoint tables have correct structure."""
        _create_checkpoint_tables(mock_connection)

        # Get all execute calls
        calls = [str(call) for call in mock_connection.execute.call_args_list]

        # Verify checkpoints table has required columns
        checkpoints_sql = next(
            (call for call in calls if "CREATE TABLE IF NOT EXISTS checkpoints" in call),
            None
        )
        assert checkpoints_sql is not None
        assert "thread_id" in checkpoints_sql
        assert "checkpoint_id" in checkpoints_sql
        assert "checkpoint BLOB" in checkpoints_sql
        assert "PRIMARY KEY" in checkpoints_sql

        # Verify checkpoint_writes table has required columns
        writes_sql = next(
            (call for call in calls if "CREATE TABLE IF NOT EXISTS checkpoint_writes" in call),
            None
        )
        assert writes_sql is not None
        assert "thread_id" in writes_sql
        assert "checkpoint_id" in writes_sql
        assert "task_id" in writes_sql


class TestCreateCheckpointer:
    """Tests for the create_checkpointer function."""

    @patch("info_agent.workflow.checkpointer.SqliteSaver")
    @patch("info_agent.workflow.checkpointer.sqlite3.connect")
    def test_create_checkpointer_success(
        self, mock_connect, mock_saver_class, temp_db_path, mock_connection, mock_sqlite_saver
    ):
        """Test successful creation of checkpointer."""
        mock_connect.return_value = mock_connection
        mock_saver_class.return_value = mock_sqlite_saver

        result = create_checkpointer(temp_db_path)

        # Verify directory creation
        assert Path(temp_db_path).parent.exists()

        # Verify connection was created
        mock_connect.assert_called_once_with(temp_db_path, check_same_thread=False)

        # Verify WAL mode was enabled
        mock_connection.execute.assert_any_call("PRAGMA journal_mode=WAL")

        # Verify SqliteSaver was instantiated
        mock_saver_class.assert_called_once_with(mock_connection)

        assert result == mock_sqlite_saver

    @patch("info_agent.workflow.checkpointer.SqliteSaver")
    @patch("info_agent.workflow.checkpointer.sqlite3.connect")
    def test_create_checkpointer_creates_parent_directory(
        self, mock_connect, mock_saver_class, mock_connection, mock_sqlite_saver
    ):
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "nested" / "dir" / "checkpoints.db")
            parent_dir = Path(db_path).parent

            assert not parent_dir.exists()

            mock_connect.return_value = mock_connection
            mock_saver_class.return_value = mock_sqlite_saver

            create_checkpointer(db_path)

            assert parent_dir.exists()

    @patch("info_agent.workflow.checkpointer.SqliteSaver")
    @patch("info_agent.workflow.checkpointer.sqlite3.connect")
    @patch("info_agent.workflow.checkpointer._create_checkpoint_tables")
    def test_create_checkpointer_calls_table_creation(
        self, mock_create_tables, mock_connect, mock_saver_class,
        temp_db_path, mock_connection, mock_sqlite_saver
    ):
        """Test that checkpoint tables are created."""
        mock_connect.return_value = mock_connection
        mock_saver_class.return_value = mock_sqlite_saver

        create_checkpointer(temp_db_path)

        mock_create_tables.assert_called_once_with(mock_connection)

    @patch("info_agent.workflow.checkpointer.sqlite3.connect")
    def test_create_checkpointer_database_error(self, mock_connect, temp_db_path):
        """Test error handling when database creation fails."""
        mock_connect.side_effect = sqlite3.Error("Database creation failed")

        with pytest.raises(sqlite3.Error) as exc_info:
            create_checkpointer(temp_db_path)

        assert "Database creation failed" in str(exc_info.value)


class TestCompileWorkflowWithCheckpointer:
    """Tests for the compile_workflow_with_checkpointer function."""

    @patch("info_agent.workflow.checkpointer.create_checkpointer")
    def test_compile_workflow_with_checkpointer_success(
        self, mock_create_checkpointer, temp_db_path, mock_state_graph, mock_sqlite_saver
    ):
        """Test successful workflow compilation with checkpointer."""
        mock_create_checkpointer.return_value = mock_sqlite_saver
        mock_compiled = MagicMock()
        mock_state_graph.compile.return_value = mock_compiled

        result = compile_workflow_with_checkpointer(mock_state_graph, temp_db_path)

        # Verify checkpointer was created
        mock_create_checkpointer.assert_called_once_with(temp_db_path)

        # Verify workflow was compiled with checkpointer
        mock_state_graph.compile.assert_called_once_with(checkpointer=mock_sqlite_saver)

        assert result == mock_compiled

    @patch("info_agent.workflow.checkpointer.create_checkpointer")
    def test_compile_workflow_with_checkpointer_passes_db_path(
        self, mock_create_checkpointer, mock_state_graph
    ):
        """Test that db_path is passed correctly to create_checkpointer."""
        db_path = "/custom/path/to/checkpoints.db"

        compile_workflow_with_checkpointer(mock_state_graph, db_path)

        mock_create_checkpointer.assert_called_once_with(db_path)


class TestGetWorkflowState:
    """Tests for the get_workflow_state function."""

    @pytest.mark.asyncio
    async def test_get_workflow_state_success(self):
        """Test successful retrieval of workflow state."""
        mock_compiled = MagicMock()
        mock_state = MagicMock()
        mock_state.values = {
            "workflow_id": "wf-123",
            "status": "planning",
            "target_email": "user@example.com",
        }
        mock_compiled.get_state.return_value = mock_state

        result = await get_workflow_state(mock_compiled, "wf-123")

        mock_compiled.get_state.assert_called_once_with(
            {"configurable": {"thread_id": "wf-123"}}
        )

        assert result == {
            "workflow_id": "wf-123",
            "status": "planning",
            "target_email": "user@example.com",
        }

    @pytest.mark.asyncio
    async def test_get_workflow_state_not_found(self):
        """Test get_workflow_state when state is not found."""
        mock_compiled = MagicMock()
        mock_compiled.get_state.return_value = None

        result = await get_workflow_state(mock_compiled, "nonexistent-wf")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_workflow_state_empty_values(self):
        """Test get_workflow_state when state has no values."""
        mock_compiled = MagicMock()
        mock_state = MagicMock()
        mock_state.values = None
        mock_compiled.get_state.return_value = mock_state

        result = await get_workflow_state(mock_compiled, "wf-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_workflow_state_exception_handling(self):
        """Test get_workflow_state handles exceptions gracefully."""
        mock_compiled = MagicMock()
        mock_compiled.get_state.side_effect = Exception("Database error")

        result = await get_workflow_state(mock_compiled, "wf-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_workflow_state_correct_thread_id_format(self):
        """Test that thread_id is passed in correct format."""
        mock_compiled = MagicMock()
        mock_state = MagicMock()
        mock_state.values = {"workflow_id": "test-wf"}
        mock_compiled.get_state.return_value = mock_state

        await get_workflow_state(mock_compiled, "test-workflow-id")

        # Verify the config format
        call_args = mock_compiled.get_state.call_args[0][0]
        assert "configurable" in call_args
        assert call_args["configurable"]["thread_id"] == "test-workflow-id"


class TestListWorkflowThreads:
    """Tests for the list_workflow_threads function."""

    @pytest.mark.asyncio
    async def test_list_workflow_threads_success(self, temp_db_path):
        """Test successful listing of workflow threads."""
        # Create a real database with test data
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
            ("wf-1", "cp-1", b"data1")
        )
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
            ("wf-2", "cp-2", b"data2")
        )
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
            ("wf-1", "cp-3", b"data3")
        )
        conn.commit()
        conn.close()

        result = await list_workflow_threads(temp_db_path)

        assert len(result) == 2
        assert "wf-1" in result
        assert "wf-2" in result

    @pytest.mark.asyncio
    async def test_list_workflow_threads_database_not_exists(self, temp_db_path):
        """Test list_workflow_threads when database doesn't exist."""
        nonexistent_path = str(Path(temp_db_path).parent / "nonexistent.db")

        result = await list_workflow_threads(nonexistent_path)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_workflow_threads_empty_database(self, temp_db_path):
        """Test list_workflow_threads with empty database."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB,
                created_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

        result = await list_workflow_threads(temp_db_path)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_workflow_threads_ordered_by_created_at(self, temp_db_path):
        """Test that threads are ordered by created_at DESC."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB,
                created_at TIMESTAMP
            )
        """)
        # Insert in non-chronological order
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("wf-2", "cp-2", b"data2", "2025-01-15 10:00:00")
        )
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("wf-1", "cp-1", b"data1", "2025-01-15 12:00:00")
        )
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("wf-3", "cp-3", b"data3", "2025-01-15 11:00:00")
        )
        conn.commit()
        conn.close()

        result = await list_workflow_threads(temp_db_path)

        # Most recent first
        assert result[0] == "wf-1"
        assert result[1] == "wf-3"
        assert result[2] == "wf-2"


class TestDeleteWorkflowThread:
    """Tests for the delete_workflow_thread function."""

    @pytest.mark.asyncio
    async def test_delete_workflow_thread_success(self, temp_db_path):
        """Test successful deletion of workflow thread."""
        # Create database with test data
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB
            )
        """)
        conn.execute("""
            CREATE TABLE checkpoint_writes (
                thread_id TEXT,
                checkpoint_id TEXT,
                task_id TEXT,
                idx INTEGER,
                channel TEXT,
                value BLOB
            )
        """)
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
            ("wf-delete", "cp-1", b"data1")
        )
        conn.execute(
            "INSERT INTO checkpoint_writes (thread_id, checkpoint_id, task_id, idx, channel, value) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("wf-delete", "cp-1", "task-1", 0, "channel", b"value")
        )
        conn.commit()
        conn.close()

        result = await delete_workflow_thread(temp_db_path, "wf-delete")

        assert result is True

        # Verify data was deleted
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", ("wf-delete",))
        count = cursor.fetchone()[0]
        assert count == 0

        cursor = conn.execute("SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = ?", ("wf-delete",))
        count = cursor.fetchone()[0]
        assert count == 0
        conn.close()

    @pytest.mark.asyncio
    async def test_delete_workflow_thread_not_found(self, temp_db_path):
        """Test delete_workflow_thread when thread doesn't exist."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB
            )
        """)
        conn.execute("""
            CREATE TABLE checkpoint_writes (
                thread_id TEXT,
                checkpoint_id TEXT,
                task_id TEXT,
                idx INTEGER,
                channel TEXT,
                value BLOB
            )
        """)
        conn.commit()
        conn.close()

        result = await delete_workflow_thread(temp_db_path, "nonexistent-wf")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_workflow_thread_database_not_exists(self, temp_db_path):
        """Test delete_workflow_thread when database doesn't exist."""
        nonexistent_path = str(Path(temp_db_path).parent / "nonexistent.db")

        result = await delete_workflow_thread(nonexistent_path, "wf-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_workflow_thread_deletes_writes_first(self, temp_db_path):
        """Test that checkpoint_writes are deleted before checkpoints."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB
            )
        """)
        conn.execute("""
            CREATE TABLE checkpoint_writes (
                thread_id TEXT,
                checkpoint_id TEXT,
                task_id TEXT,
                idx INTEGER,
                channel TEXT,
                value BLOB
            )
        """)
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
            ("wf-test", "cp-1", b"data1")
        )
        conn.execute(
            "INSERT INTO checkpoint_writes (thread_id, checkpoint_id, task_id, idx, channel, value) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("wf-test", "cp-1", "task-1", 0, "channel", b"value")
        )
        conn.commit()
        conn.close()

        result = await delete_workflow_thread(temp_db_path, "wf-test")

        assert result is True

        # Verify both tables are empty for the thread
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", ("wf-test",))
        assert cursor.fetchone()[0] == 0

        cursor = conn.execute("SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = ?", ("wf-test",))
        assert cursor.fetchone()[0] == 0
        conn.close()

    @pytest.mark.asyncio
    async def test_delete_workflow_thread_preserves_other_threads(self, temp_db_path):
        """Test that deleting one thread doesn't affect other threads."""
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB
            )
        """)
        conn.execute("""
            CREATE TABLE checkpoint_writes (
                thread_id TEXT,
                checkpoint_id TEXT,
                task_id TEXT,
                idx INTEGER,
                channel TEXT,
                value BLOB
            )
        """)
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
            ("wf-keep", "cp-1", b"data1")
        )
        conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
            ("wf-delete", "cp-2", b"data2")
        )
        conn.commit()
        conn.close()

        await delete_workflow_thread(temp_db_path, "wf-delete")

        # Verify wf-keep still exists
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", ("wf-keep",))
        assert cursor.fetchone()[0] == 1

        cursor = conn.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", ("wf-delete",))
        assert cursor.fetchone()[0] == 0
        conn.close()


class TestIntegrationScenarios:
    """Integration-style tests for checkpointer operations."""

    @patch("info_agent.workflow.checkpointer.SqliteSaver")
    @patch("info_agent.workflow.checkpointer.sqlite3.connect")
    def test_full_checkpointer_lifecycle(
        self, mock_connect, mock_saver_class, temp_db_path, mock_connection, mock_sqlite_saver, mock_state_graph
    ):
        """Test complete lifecycle: create, compile, use."""
        mock_connect.return_value = mock_connection
        mock_saver_class.return_value = mock_sqlite_saver
        mock_compiled = MagicMock()
        mock_state_graph.compile.return_value = mock_compiled

        # Create checkpointer
        checkpointer = create_checkpointer(temp_db_path)
        assert checkpointer == mock_sqlite_saver

        # Compile workflow
        compiled = compile_workflow_with_checkpointer(mock_state_graph, temp_db_path)
        assert compiled == mock_compiled

        # Verify compilation used checkpointer
        mock_state_graph.compile.assert_called_with(checkpointer=mock_sqlite_saver)

    @pytest.mark.asyncio
    async def test_thread_management_workflow(self, temp_db_path):
        """Test listing and deleting threads."""
        # Create database with multiple threads
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT,
                checkpoint_id TEXT,
                checkpoint BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE checkpoint_writes (
                thread_id TEXT,
                checkpoint_id TEXT,
                task_id TEXT,
                idx INTEGER,
                channel TEXT,
                value BLOB
            )
        """)

        for i in range(3):
            conn.execute(
                "INSERT INTO checkpoints (thread_id, checkpoint_id, checkpoint) VALUES (?, ?, ?)",
                (f"wf-{i}", f"cp-{i}", f"data{i}".encode())
            )
        conn.commit()
        conn.close()

        # List threads
        threads = await list_workflow_threads(temp_db_path)
        assert len(threads) == 3

        # Delete one thread
        deleted = await delete_workflow_thread(temp_db_path, "wf-1")
        assert deleted is True

        # List again
        threads = await list_workflow_threads(temp_db_path)
        assert len(threads) == 2
        assert "wf-1" not in threads
        assert "wf-0" in threads
        assert "wf-2" in threads
