"""
Unit tests for A2A storage module.

Tests the A2AStorage class from src/info_agent/a2a/storage.py including:
- Database initialization
- Agent saving (create and update)
- Agent retrieval
- Agent listing
- Agent deletion
- Error handling

All tests use mocked aiosqlite to avoid actual database operations.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from info_agent.a2a.models import AgentCard, AgentSkill
from info_agent.a2a.storage import A2AStorage
from info_agent.utils.exceptions import AgentNotFoundError, StorageError


class AsyncContextManager:
    """Helper class that acts as both async context manager and awaitable."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def __await__(self):
        async def _async():
            return self
        return _async().__await__()


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock()
    settings.registry_db_path = "/tmp/test_registry.db"
    return settings


@pytest.fixture
def valid_skill():
    """Fixture providing a valid AgentSkill."""
    return AgentSkill(
        id="convert_currency",
        name="Convert Currency",
        description="Converts currency",
        input_schema={"type": "object", "properties": {"amount": {"type": "number"}}},
    )


@pytest.fixture
def valid_agent_card(valid_skill):
    """Fixture providing a valid AgentCard."""
    return AgentCard(
        name="currency-agent",
        description="Currency conversion agent",
        version="1.0.0",
        url="http://localhost:8001/a2a",
        capabilities={"async": True, "streaming": False},
        skills=[valid_skill],
        defaultInputModes=["text", "data"],
        defaultOutputModes=["text", "data"],
    )


class TestA2AStorageInit:
    """Tests for A2AStorage initialization."""

    @patch("info_agent.a2a.storage.get_settings")
    def test_init_with_default_db_path(self, mock_get_settings, mock_settings):
        """Test initialization with default database path from settings."""
        mock_get_settings.return_value = mock_settings

        storage = A2AStorage()

        assert storage.db_path == "/tmp/test_registry.db"
        mock_get_settings.assert_called_once()

    def test_init_with_explicit_db_path(self):
        """Test initialization with explicitly provided database path."""
        storage = A2AStorage(db_path="/custom/path/registry.db")

        assert storage.db_path == "/custom/path/registry.db"

    @patch("info_agent.a2a.storage.get_settings")
    def test_init_fails_when_no_db_path(self, mock_get_settings):
        """Test initialization fails when no db_path is provided or in settings."""
        mock_settings = Mock()
        mock_settings.registry_db_path = None
        mock_get_settings.return_value = mock_settings

        with pytest.raises(StorageError) as exc_info:
            A2AStorage()

        assert "Database path not provided" in exc_info.value.message
        assert exc_info.value.code == "STORAGE_ERROR"
        assert exc_info.value.operation == "init"

    @patch("info_agent.a2a.storage.get_settings")
    def test_init_fails_when_empty_db_path(self, mock_get_settings):
        """Test initialization fails when db_path is empty string."""
        mock_settings = Mock()
        mock_settings.registry_db_path = ""
        mock_get_settings.return_value = mock_settings

        with pytest.raises(StorageError) as exc_info:
            A2AStorage()

        assert "Database path not provided" in exc_info.value.message


class TestA2AStorageInitDB:
    """Tests for database initialization."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    @patch("info_agent.a2a.storage.Path")
    async def test_init_db_creates_schema(self, mock_path_class, mock_connect):
        """Test that init_db creates the database schema."""
        # Mock Path behavior
        mock_path_instance = Mock()
        mock_path_instance.parent = Mock()
        mock_path_instance.parent.mkdir = Mock()
        mock_path_class.return_value = mock_path_instance

        # Mock database connection
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        await storage.init_db()

        # Verify directory creation
        mock_path_instance.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify database operations
        mock_connect.assert_called_once_with("/tmp/test.db")
        assert mock_db.execute.call_count == 3  # CREATE TABLE + 2 CREATE INDEX
        mock_db.commit.assert_called_once()

        # Verify table creation SQL
        create_table_call = mock_db.execute.call_args_list[0]
        sql = create_table_call[0][0]
        assert "CREATE TABLE IF NOT EXISTS agents" in sql
        assert "name TEXT PRIMARY KEY" in sql

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    @patch("info_agent.a2a.storage.Path")
    async def test_init_db_creates_indexes(self, mock_path_class, mock_connect):
        """Test that init_db creates proper indexes."""
        mock_path_instance = Mock()
        mock_path_instance.parent = Mock()
        mock_path_instance.parent.mkdir = Mock()
        mock_path_class.return_value = mock_path_instance

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        await storage.init_db()

        # Verify index creation
        assert mock_db.execute.call_count == 3
        index_calls = [call[0][0] for call in mock_db.execute.call_args_list[1:]]
        assert any("idx_agents_created_at" in sql for sql in index_calls)
        assert any("idx_agents_updated_at" in sql for sql in index_calls)

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    @patch("info_agent.a2a.storage.Path")
    async def test_init_db_fails_on_database_error(self, mock_path_class, mock_connect):
        """Test that init_db raises StorageError on database errors."""
        mock_path_instance = Mock()
        mock_path_instance.parent = Mock()
        mock_path_instance.parent.mkdir = Mock()
        mock_path_class.return_value = mock_path_instance

        mock_connect.side_effect = Exception("Database connection failed")

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.init_db()

        assert "Database initialization failed" in exc_info.value.message
        assert exc_info.value.code == "STORAGE_ERROR"
        assert exc_info.value.operation == "init_db"
        assert "Database connection failed" in str(exc_info.value.details)


class TestA2AStorageSaveAgent:
    """Tests for saving agents."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_save_new_agent(self, mock_connect, valid_agent_card):
        """Test saving a new agent to the database."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        await storage.save_agent(valid_agent_card)

        # Verify database operations
        mock_connect.assert_called_once_with("/tmp/test.db")
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify SQL contains INSERT and ON CONFLICT
        sql = mock_db.execute.call_args[0][0]
        assert "INSERT INTO agents" in sql
        assert "ON CONFLICT(name) DO UPDATE SET" in sql

        # Verify data passed to execute
        data = mock_db.execute.call_args[0][1]
        assert data[0] == "currency-agent"  # name
        assert data[1] == "Currency conversion agent"  # description
        assert data[2] == "1.0.0"  # version
        assert data[3] == "http://localhost:8001/a2a"  # url

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_save_agent_with_created_at(self, mock_connect, valid_agent_card):
        """Test saving an agent with existing created_at timestamp."""
        created_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        valid_agent_card.created_at = created_time

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        await storage.save_agent(valid_agent_card)

        # Verify created_at is preserved
        data = mock_db.execute.call_args[0][1]
        assert data[8] == created_time.isoformat()  # created_at

    @pytest.mark.asyncio
    async def test_save_agent_fails_with_empty_name(self, valid_agent_card):
        """Test that saving agent with empty name raises StorageError."""
        valid_agent_card.name = ""

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.save_agent(valid_agent_card)

        assert "Agent name is required" in exc_info.value.message
        assert exc_info.value.operation == "save"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_save_agent_fails_on_database_error(self, mock_connect, valid_agent_card):
        """Test that save_agent raises StorageError on database errors."""
        mock_connect.side_effect = Exception("Database write failed")

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.save_agent(valid_agent_card)

        assert "Failed to save agent" in exc_info.value.message
        assert exc_info.value.operation == "save"
        assert exc_info.value.entity_id == "currency-agent"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_save_agent_serializes_skills(self, mock_connect, valid_agent_card):
        """Test that save_agent properly serializes skills to JSON."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        await storage.save_agent(valid_agent_card)

        # Verify skills are serialized
        data = mock_db.execute.call_args[0][1]
        skills_json = data[5]  # skills field
        assert "convert_currency" in skills_json
        assert "Convert Currency" in skills_json


class TestA2AStorageGetAgent:
    """Tests for retrieving agents."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_get_existing_agent(self, mock_connect):
        """Test retrieving an existing agent from the database."""
        # Mock database row
        mock_row = {
            "name": "currency-agent",
            "description": "Currency conversion agent",
            "version": "1.0.0",
            "url": "http://localhost:8001/a2a",
            "capabilities": '{"async": true}',
            "skills": '[{"id": "convert", "name": "Convert", "description": "Convert currency", "input_schema": {"type": "object"}}]',
            "default_input_modes": '["text"]',
            "default_output_modes": '["text"]',
            "created_at": "2024-01-15T10:30:00+00:00",
        }

        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)

        mock_db = AsyncMock()
        mock_db.row_factory = None
        mock_db.execute = Mock(return_value=AsyncContextManager(mock_cursor))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        agent = await storage.get_agent("currency-agent")

        assert agent.name == "currency-agent"
        assert agent.description == "Currency conversion agent"
        assert agent.version == "1.0.0"
        assert agent.url == "http://localhost:8001/a2a"
        assert agent.capabilities == {"async": True}
        assert len(agent.skills) == 1
        assert agent.skills[0].id == "convert"
        assert agent.defaultInputModes == ["text"]
        assert agent.defaultOutputModes == ["text"]
        assert isinstance(agent.created_at, datetime)

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_get_agent_not_found(self, mock_connect):
        """Test that get_agent raises AgentNotFoundError when agent doesn't exist."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.row_factory = None
        mock_db.execute = Mock(return_value=AsyncContextManager(mock_cursor))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(AgentNotFoundError) as exc_info:
            await storage.get_agent("nonexistent-agent")

        assert exc_info.value.agent_name == "nonexistent-agent"
        assert exc_info.value.code == "AGENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_agent_fails_with_empty_name(self):
        """Test that get_agent raises StorageError with empty name."""
        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.get_agent("")

        assert "Agent name is required" in exc_info.value.message
        assert exc_info.value.operation == "get"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_get_agent_fails_on_database_error(self, mock_connect):
        """Test that get_agent raises StorageError on database errors."""
        mock_connect.side_effect = Exception("Database read failed")

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.get_agent("currency-agent")

        assert "Failed to retrieve agent" in exc_info.value.message
        assert exc_info.value.operation == "get"
        assert exc_info.value.entity_id == "currency-agent"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_get_agent_uses_correct_query(self, mock_connect):
        """Test that get_agent uses the correct SQL query."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.row_factory = None
        mock_db.execute = Mock(return_value=AsyncContextManager(mock_cursor))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")

        try:
            await storage.get_agent("test-agent")
        except AgentNotFoundError:
            pass

        # Verify SQL query
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        sql = call_args[0]
        assert "SELECT name, description, version, url" in sql
        assert "FROM agents" in sql
        assert "WHERE name = ?" in sql

        # Verify parameter
        params = call_args[1]
        assert params == ("test-agent",)


class TestA2AStorageListAgents:
    """Tests for listing agents."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_list_agents_returns_all(self, mock_connect):
        """Test listing all agents from the database."""
        mock_rows = [
            {
                "name": "agent-1",
                "description": "First agent",
                "version": "1.0.0",
                "url": "http://localhost:8001/a2a",
                "capabilities": "{}",
                "skills": '[{"id": "skill1", "name": "Skill 1", "description": "Test", "input_schema": {"type": "object"}}]',
                "default_input_modes": '["text"]',
                "default_output_modes": '["text"]',
                "created_at": "2024-01-15T10:00:00+00:00",
            },
            {
                "name": "agent-2",
                "description": "Second agent",
                "version": "2.0.0",
                "url": "http://localhost:8002/a2a",
                "capabilities": "{}",
                "skills": '[{"id": "skill2", "name": "Skill 2", "description": "Test", "input_schema": {"type": "object"}}]',
                "default_input_modes": '["text"]',
                "default_output_modes": '["text"]',
                "created_at": "2024-01-15T11:00:00+00:00",
            },
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)

        mock_db = AsyncMock()
        mock_db.row_factory = None
        mock_db.execute = Mock(return_value=AsyncContextManager(mock_cursor))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        agents = await storage.list_agents()

        assert len(agents) == 2
        assert agents[0].name == "agent-1"
        assert agents[0].version == "1.0.0"
        assert agents[1].name == "agent-2"
        assert agents[1].version == "2.0.0"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_list_agents_returns_empty_list(self, mock_connect):
        """Test listing agents when database is empty."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_db = AsyncMock()
        mock_db.row_factory = None
        mock_db.execute = Mock(return_value=AsyncContextManager(mock_cursor))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        agents = await storage.list_agents()

        assert agents == []

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_list_agents_orders_by_created_at(self, mock_connect):
        """Test that list_agents orders results by created_at DESC."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_db = AsyncMock()
        mock_db.row_factory = None
        mock_db.execute = Mock(return_value=AsyncContextManager(mock_cursor))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        await storage.list_agents()

        # Verify SQL query contains ORDER BY
        mock_db.execute.assert_called_once()
        sql = mock_db.execute.call_args[0][0]
        assert "ORDER BY created_at DESC" in sql

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_list_agents_fails_on_database_error(self, mock_connect):
        """Test that list_agents raises StorageError on database errors."""
        mock_connect.side_effect = Exception("Database read failed")

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.list_agents()

        assert "Failed to list agents" in exc_info.value.message
        assert exc_info.value.operation == "list"


class TestA2AStorageDeleteAgent:
    """Tests for deleting agents."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_delete_existing_agent(self, mock_connect):
        """Test deleting an existing agent from the database."""
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")
        await storage.delete_agent("currency-agent")

        # Verify database operations
        mock_connect.assert_called_once_with("/tmp/test.db")
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify SQL
        sql = mock_db.execute.call_args[0][0]
        assert "DELETE FROM agents WHERE name = ?" in sql

        # Verify parameter
        params = mock_db.execute.call_args[0][1]
        assert params == ("currency-agent",)

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_delete_nonexistent_agent(self, mock_connect):
        """Test that deleting nonexistent agent raises AgentNotFoundError."""
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_connect.return_value = mock_db

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(AgentNotFoundError) as exc_info:
            await storage.delete_agent("nonexistent-agent")

        assert exc_info.value.agent_name == "nonexistent-agent"
        assert exc_info.value.code == "AGENT_NOT_FOUND"
        assert "delete" in str(exc_info.value.details)

    @pytest.mark.asyncio
    async def test_delete_agent_fails_with_empty_name(self):
        """Test that delete_agent raises StorageError with empty name."""
        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.delete_agent("")

        assert "Agent name is required" in exc_info.value.message
        assert exc_info.value.operation == "delete"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.storage.aiosqlite.connect")
    async def test_delete_agent_fails_on_database_error(self, mock_connect):
        """Test that delete_agent raises StorageError on database errors."""
        mock_connect.side_effect = Exception("Database delete failed")

        storage = A2AStorage(db_path="/tmp/test.db")

        with pytest.raises(StorageError) as exc_info:
            await storage.delete_agent("currency-agent")

        assert "Failed to delete agent" in exc_info.value.message
        assert exc_info.value.operation == "delete"
        assert exc_info.value.entity_id == "currency-agent"
