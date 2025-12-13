"""
Unit tests for A2A registry FastAPI routes.

Tests the FastAPI router from src/info_agent/a2a/registry.py including:
- Registry initialization and cleanup
- POST /a2a/agents/register endpoint
- GET /a2a/agents endpoint
- GET /a2a/agents/{agent_name} endpoint
- DELETE /a2a/agents/{agent_name} endpoint
- Error handling and HTTP status codes

All tests use mocked storage to avoid actual database operations.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from info_agent.a2a.models import AgentCard, AgentSkill
from info_agent.a2a.registry import (
    cleanup_registry,
    create_a2a_router,
    get_storage,
    init_registry,
)
from info_agent.utils.exceptions import AgentNotFoundError, StorageError


def create_test_app(router):
    """Create a test FastAPI app with the router included."""
    app = FastAPI()
    app.include_router(router)
    return app


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


@pytest.fixture
def valid_agent_card_dict(valid_skill):
    """Fixture providing a valid AgentCard as dict for API requests."""
    return {
        "name": "currency-agent",
        "description": "Currency conversion agent",
        "version": "1.0.0",
        "url": "http://localhost:8001/a2a",
        "capabilities": {"async": True, "streaming": False},
        "skills": [valid_skill.model_dump()],
        "defaultInputModes": ["text", "data"],
        "defaultOutputModes": ["text", "data"],
    }


@pytest.fixture
def mock_storage():
    """Create a mock A2AStorage instance."""
    storage = Mock()
    storage.init_db = AsyncMock()
    storage.save_agent = AsyncMock()
    storage.get_agent = AsyncMock()
    storage.list_agents = AsyncMock()
    storage.delete_agent = AsyncMock()
    return storage


@pytest.fixture(autouse=True)
async def reset_registry():
    """Reset registry before and after each test."""
    await cleanup_registry()
    yield
    await cleanup_registry()


class TestRegistryInitialization:
    """Tests for registry initialization and cleanup."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_init_registry_success(self, mock_storage_class):
        """Test successful registry initialization."""
        mock_storage = Mock()
        mock_storage.init_db = AsyncMock()
        mock_storage_class.return_value = mock_storage

        await init_registry()

        mock_storage_class.assert_called_once()
        mock_storage.init_db.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_init_registry_fails_on_storage_error(self, mock_storage_class):
        """Test that init_registry raises StorageError on initialization failure."""
        mock_storage_class.side_effect = Exception("Storage initialization failed")

        with pytest.raises(StorageError) as exc_info:
            await init_registry()

        assert "Registry initialization failed" in exc_info.value.message
        assert exc_info.value.code == "STORAGE_ERROR"
        assert exc_info.value.operation == "init"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_cleanup_registry(self, mock_storage_class):
        """Test registry cleanup."""
        mock_storage = Mock()
        mock_storage.init_db = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize first
        await init_registry()

        # Then cleanup
        await cleanup_registry()

        # Storage should be cleared
        # (This is verified by next test that checks get_storage fails)

    @pytest.mark.asyncio
    async def test_get_storage_fails_when_not_initialized(self):
        """Test that get_storage raises HTTPException when not initialized."""
        from fastapi import HTTPException

        await cleanup_registry()

        with pytest.raises(HTTPException) as exc_info:
            get_storage()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "not initialized" in exc_info.value.detail


class TestRegisterAgentEndpoint:
    """Tests for POST /a2a/agents/register endpoint."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_register_new_agent(self, mock_storage_class, mock_storage, valid_agent_card_dict):
        """Test registering a new agent."""
        mock_storage.get_agent = AsyncMock(side_effect=AgentNotFoundError(agent_name="currency-agent"))
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.post("/a2a/agents/register", json=valid_agent_card_dict)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "registered"
        assert data["agent_name"] == "currency-agent"
        assert "registered successfully" in data["message"]

        mock_storage.save_agent.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_update_existing_agent(self, mock_storage_class, mock_storage, valid_agent_card, valid_agent_card_dict):
        """Test updating an existing agent."""
        mock_storage.get_agent = AsyncMock(return_value=valid_agent_card)
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        # Update with new version
        updated_card = valid_agent_card_dict.copy()
        updated_card["version"] = "2.0.0"

        response = client.post("/a2a/agents/register", json=updated_card)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "updated"
        assert data["agent_name"] == "currency-agent"
        assert "updated successfully" in data["message"]

        mock_storage.save_agent.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_register_agent_with_missing_name(self, mock_storage_class, mock_storage, valid_agent_card_dict):
        """Test that registering agent with missing name fails."""
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        invalid_card = valid_agent_card_dict.copy()
        del invalid_card["name"]

        response = client.post("/a2a/agents/register", json=invalid_card)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_register_agent_with_invalid_url(self, mock_storage_class, mock_storage, valid_agent_card_dict):
        """Test that registering agent with invalid URL fails."""
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        invalid_card = valid_agent_card_dict.copy()
        invalid_card["url"] = "invalid-url"

        response = client.post("/a2a/agents/register", json=invalid_card)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_register_agent_storage_error(self, mock_storage_class, mock_storage, valid_agent_card_dict):
        """Test that storage errors are handled properly."""
        mock_storage.get_agent = AsyncMock(side_effect=AgentNotFoundError(agent_name="currency-agent"))
        mock_storage.save_agent = AsyncMock(
            side_effect=StorageError(
                message="Database write failed",
                operation="save",
                entity_type="agent",
            )
        )
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.post("/a2a/agents/register", json=valid_agent_card_dict)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to register agent" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_register_agent_unexpected_error(self, mock_storage_class, mock_storage, valid_agent_card_dict):
        """Test that unexpected errors are handled properly."""
        mock_storage.get_agent = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.post("/a2a/agents/register", json=valid_agent_card_dict)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Unexpected error" in response.json()["detail"]


class TestListAgentsEndpoint:
    """Tests for GET /a2a/agents endpoint."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_list_agents_success(self, mock_storage_class, mock_storage, valid_agent_card):
        """Test listing all agents successfully."""
        mock_storage.list_agents = AsyncMock(return_value=[valid_agent_card])
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "currency-agent"
        assert data[0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_list_agents_empty(self, mock_storage_class, mock_storage):
        """Test listing agents when registry is empty."""
        mock_storage.list_agents = AsyncMock(return_value=[])
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_list_agents_multiple(self, mock_storage_class, mock_storage, valid_skill):
        """Test listing multiple agents."""
        agent1 = AgentCard(
            name="agent-1",
            description="First agent",
            version="1.0.0",
            url="http://localhost:8001/a2a",
            capabilities={},
            skills=[valid_skill],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )
        agent2 = AgentCard(
            name="agent-2",
            description="Second agent",
            version="2.0.0",
            url="http://localhost:8002/a2a",
            capabilities={},
            skills=[valid_skill],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )

        mock_storage.list_agents = AsyncMock(return_value=[agent1, agent2])
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "agent-1"
        assert data[1]["name"] == "agent-2"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_list_agents_storage_error(self, mock_storage_class, mock_storage):
        """Test that storage errors are handled properly."""
        mock_storage.list_agents = AsyncMock(
            side_effect=StorageError(
                message="Database read failed",
                operation="list",
                entity_type="agent",
            )
        )
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to list agents" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_list_agents_unexpected_error(self, mock_storage_class, mock_storage):
        """Test that unexpected errors are handled properly."""
        mock_storage.list_agents = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Unexpected error" in response.json()["detail"]


class TestGetAgentEndpoint:
    """Tests for GET /a2a/agents/{agent_name} endpoint."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_get_agent_success(self, mock_storage_class, mock_storage, valid_agent_card):
        """Test getting an agent successfully."""
        mock_storage.get_agent = AsyncMock(return_value=valid_agent_card)
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents/currency-agent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "currency-agent"
        assert data["version"] == "1.0.0"
        assert data["url"] == "http://localhost:8001/a2a"

        mock_storage.get_agent.assert_called_once_with("currency-agent")

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_get_agent_not_found(self, mock_storage_class, mock_storage):
        """Test getting a nonexistent agent."""
        mock_storage.get_agent = AsyncMock(
            side_effect=AgentNotFoundError(agent_name="nonexistent-agent")
        )
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents/nonexistent-agent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_get_agent_storage_error(self, mock_storage_class, mock_storage):
        """Test that storage errors are handled properly."""
        mock_storage.get_agent = AsyncMock(
            side_effect=StorageError(
                message="Database read failed",
                operation="get",
                entity_type="agent",
            )
        )
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents/currency-agent")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to retrieve agent" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_get_agent_unexpected_error(self, mock_storage_class, mock_storage):
        """Test that unexpected errors are handled properly."""
        mock_storage.get_agent = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.get("/a2a/agents/currency-agent")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Unexpected error" in response.json()["detail"]


class TestDeregisterAgentEndpoint:
    """Tests for DELETE /a2a/agents/{agent_name} endpoint."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_deregister_agent_success(self, mock_storage_class, mock_storage):
        """Test deregistering an agent successfully."""
        mock_storage.delete_agent = AsyncMock()
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.delete("/a2a/agents/currency-agent")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        mock_storage.delete_agent.assert_called_once_with("currency-agent")

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_deregister_agent_not_found(self, mock_storage_class, mock_storage):
        """Test deregistering a nonexistent agent."""
        mock_storage.delete_agent = AsyncMock(
            side_effect=AgentNotFoundError(agent_name="nonexistent-agent")
        )
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.delete("/a2a/agents/nonexistent-agent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_deregister_agent_storage_error(self, mock_storage_class, mock_storage):
        """Test that storage errors are handled properly."""
        mock_storage.delete_agent = AsyncMock(
            side_effect=StorageError(
                message="Database delete failed",
                operation="delete",
                entity_type="agent",
            )
        )
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.delete("/a2a/agents/currency-agent")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to deregister agent" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_deregister_agent_unexpected_error(self, mock_storage_class, mock_storage):
        """Test that unexpected errors are handled properly."""
        mock_storage.delete_agent = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()
        app = create_test_app(router)
        client = TestClient(app)

        response = client.delete("/a2a/agents/currency-agent")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Unexpected error" in response.json()["detail"]


class TestRouterConfiguration:
    """Tests for router configuration and metadata."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_router_prefix(self, mock_storage_class, mock_storage):
        """Test that router has correct prefix."""
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()

        assert router.prefix == "/a2a"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.registry.A2AStorage")
    async def test_router_tags(self, mock_storage_class, mock_storage):
        """Test that router has correct tags."""
        mock_storage_class.return_value = mock_storage

        await init_registry()
        router = create_a2a_router()

        assert "A2A Registry" in router.tags
