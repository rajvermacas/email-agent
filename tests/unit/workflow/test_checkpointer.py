"""
Unit tests for workflow checkpointer.
"""

import tempfile
from pathlib import Path

import pytest

from langgraph.checkpoint.sqlite import SqliteSaver

from info_agent.workflow.checkpointer import (
    CheckpointStorage,
    create_checkpointer,
)


class TestCheckpointStorage:
    """Tests for CheckpointStorage."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_checkpoints.db"

    @pytest.fixture
    def storage(self, temp_db: Path) -> CheckpointStorage:
        """Create storage instance."""
        return CheckpointStorage(temp_db)

    def test_init_creates_db(self, temp_db: Path) -> None:
        """Test initialization creates database."""
        storage = CheckpointStorage(temp_db)

        assert temp_db.exists()

    def test_init_empty_path_raises(self) -> None:
        """Test empty path raises error."""
        with pytest.raises(ValueError, match="db_path is required"):
            CheckpointStorage("")

    def test_save_checkpoint(self, storage: CheckpointStorage) -> None:
        """Test saving checkpoint."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"test": "data"}',
        )

        result = storage.load_checkpoint("thread-1")
        assert result is not None
        assert result[0] == b'{"test": "data"}'

    def test_save_checkpoint_with_metadata(self, storage: CheckpointStorage) -> None:
        """Test saving checkpoint with metadata."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"test": "data"}',
            metadata=b'{"version": 1}',
        )

        result = storage.load_checkpoint("thread-1")
        assert result is not None
        assert result[1] == b'{"version": 1}'

    def test_save_checkpoint_with_parent(self, storage: CheckpointStorage) -> None:
        """Test saving checkpoint with parent."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-2",
            checkpoint_data=b'{"test": "data"}',
            parent_checkpoint_id="cp-1",
        )

        result = storage.load_checkpoint("thread-1")
        assert result is not None
        assert result[2] == "cp-1"

    def test_load_specific_checkpoint(self, storage: CheckpointStorage) -> None:
        """Test loading specific checkpoint by ID."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"version": 1}',
        )
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-2",
            checkpoint_data=b'{"version": 2}',
        )

        result = storage.load_checkpoint("thread-1", "", "cp-1")
        assert result is not None
        assert result[0] == b'{"version": 1}'

    def test_load_latest_checkpoint(self, storage: CheckpointStorage) -> None:
        """Test loading latest checkpoint."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"version": 1}',
        )
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-2",
            checkpoint_data=b'{"version": 2}',
        )

        result = storage.load_checkpoint("thread-1")
        assert result is not None
        # Should get latest (cp-2)
        assert result[0] == b'{"version": 2}'

    def test_load_nonexistent_checkpoint(self, storage: CheckpointStorage) -> None:
        """Test loading nonexistent checkpoint."""
        result = storage.load_checkpoint("nonexistent")
        assert result is None

    def test_list_checkpoints(self, storage: CheckpointStorage) -> None:
        """Test listing checkpoints."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"version": 1}',
        )
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-2",
            checkpoint_data=b'{"version": 2}',
        )

        checkpoints = storage.list_checkpoints("thread-1")

        assert len(checkpoints) == 2

    def test_list_checkpoints_with_limit(self, storage: CheckpointStorage) -> None:
        """Test listing checkpoints with limit."""
        for i in range(5):
            storage.save_checkpoint(
                thread_id="thread-1",
                checkpoint_ns="",
                checkpoint_id=f"cp-{i}",
                checkpoint_data=b'{"test": "data"}',
            )

        checkpoints = storage.list_checkpoints("thread-1", limit=3)

        assert len(checkpoints) == 3

    def test_delete_checkpoints(self, storage: CheckpointStorage) -> None:
        """Test deleting checkpoints."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"test": "data"}',
        )

        count = storage.delete_checkpoints("thread-1")

        assert count == 1
        assert storage.load_checkpoint("thread-1") is None

    def test_save_writes(self, storage: CheckpointStorage) -> None:
        """Test saving writes."""
        writes = [
            ("task-1", "channel-1", "type-1", b'{"data": 1}'),
            ("task-1", "channel-2", "type-2", b'{"data": 2}'),
        ]

        storage.save_writes("thread-1", "", "cp-1", writes)

        loaded = storage.load_writes("thread-1", "", "cp-1")
        assert len(loaded) == 2

    def test_load_empty_writes(self, storage: CheckpointStorage) -> None:
        """Test loading writes when none exist."""
        loaded = storage.load_writes("thread-1", "", "cp-1")
        assert loaded == []

    def test_checkpoint_namespaces(self, storage: CheckpointStorage) -> None:
        """Test checkpoints with different namespaces."""
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="ns-1",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"ns": "1"}',
        )
        storage.save_checkpoint(
            thread_id="thread-1",
            checkpoint_ns="ns-2",
            checkpoint_id="cp-1",
            checkpoint_data=b'{"ns": "2"}',
        )

        result1 = storage.load_checkpoint("thread-1", "ns-1")
        result2 = storage.load_checkpoint("thread-1", "ns-2")

        assert result1 is not None
        assert result2 is not None
        assert result1[0] == b'{"ns": "1"}'
        assert result2[0] == b'{"ns": "2"}'


class TestCreateCheckpointer:
    """Tests for create_checkpointer function."""

    def test_create_with_path(self) -> None:
        """Test creating checkpointer with path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            checkpointer = create_checkpointer(db_path)

            assert isinstance(checkpointer, SqliteSaver)
            assert db_path.exists()

    def test_create_with_string_path(self) -> None:
        """Test creating checkpointer with string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"

            checkpointer = create_checkpointer(db_path)

            assert isinstance(checkpointer, SqliteSaver)

    def test_creates_parent_directories(self) -> None:
        """Test that parent directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "dirs" / "test.db"

            checkpointer = create_checkpointer(db_path)

            assert db_path.parent.exists()
