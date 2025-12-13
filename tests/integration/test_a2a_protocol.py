"""
Integration tests for A2A protocol functionality.

Tests agent registration, discovery, task dispatch,
and inter-agent communication.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestA2AStorage:
    """Tests for A2A agent storage."""

    @pytest.fixture
    async def storage(self, temp_db_path):
        """Create A2A storage for testing."""
        from info_agent.a2a.storage import A2AStorage

        storage = A2AStorage(str(temp_db_path))
        await storage.initialize()
        yield storage
        await storage.close()

    async def test_register_agent(self, storage, sample_agent_card):
        """Test agent registration."""
        result = await storage.register_agent(sample_agent_card)

        assert result["name"] == sample_agent_card["name"]

    async def test_get_agent(self, storage, sample_agent_card):
        """Test getting registered agent."""
        await storage.register_agent(sample_agent_card)

        result = await storage.get_agent(sample_agent_card["name"])

        assert result is not None
        assert result["name"] == sample_agent_card["name"]

    async def test_list_agents(self, storage, sample_agent_cards):
        """Test listing all agents."""
        for card in sample_agent_cards:
            await storage.register_agent(card)

        result = await storage.list_agents()

        assert len(result) >= len(sample_agent_cards)

    async def test_delete_agent(self, storage, sample_agent_card):
        """Test agent deletion."""
        await storage.register_agent(sample_agent_card)

        await storage.delete_agent(sample_agent_card["name"])
        result = await storage.get_agent(sample_agent_card["name"])

        assert result is None

    async def test_update_agent(self, storage, sample_agent_card):
        """Test agent update."""
        await storage.register_agent(sample_agent_card)

        updated_card = {
            **sample_agent_card,
            "description": "Updated description",
        }
        await storage.update_agent(sample_agent_card["name"], updated_card)

        result = await storage.get_agent(sample_agent_card["name"])

        assert result["description"] == "Updated description"


class TestA2ARegistry:
    """Tests for A2A registry API."""

    @pytest.fixture
    def registry_app(self):
        """Create registry API test app."""
        from fastapi import FastAPI
        from info_agent.a2a.registry import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/a2a")
        return app

    @pytest.fixture
    def registry_client(self, registry_app):
        """Create test client for registry API."""
        from fastapi.testclient import TestClient

        return TestClient(registry_app)

    @patch("info_agent.a2a.registry.storage")
    def test_register_agent_endpoint(
        self, mock_storage, registry_client, sample_agent_card
    ):
        """Test agent registration endpoint."""
        mock_storage.register_agent = AsyncMock(return_value=sample_agent_card)

        response = registry_client.post(
            "/api/v1/a2a/agents",
            json=sample_agent_card,
        )

        assert response.status_code in [200, 201]

    @patch("info_agent.a2a.registry.storage")
    def test_list_agents_endpoint(self, mock_storage, registry_client):
        """Test list agents endpoint."""
        mock_storage.list_agents = AsyncMock(return_value=[])

        response = registry_client.get("/api/v1/a2a/agents")

        assert response.status_code == 200
        assert response.json() == []

    @patch("info_agent.a2a.registry.storage")
    def test_get_agent_endpoint(
        self, mock_storage, registry_client, sample_agent_card
    ):
        """Test get agent endpoint."""
        mock_storage.get_agent = AsyncMock(return_value=sample_agent_card)

        response = registry_client.get(
            f"/api/v1/a2a/agents/{sample_agent_card['name']}"
        )

        assert response.status_code == 200

    @patch("info_agent.a2a.registry.storage")
    def test_delete_agent_endpoint(self, mock_storage, registry_client):
        """Test delete agent endpoint."""
        mock_storage.delete_agent = AsyncMock(return_value=None)

        response = registry_client.delete("/api/v1/a2a/agents/test-agent")

        assert response.status_code in [200, 204]

    @patch("info_agent.a2a.registry.storage")
    def test_get_agent_not_found(self, mock_storage, registry_client):
        """Test getting non-existent agent."""
        from info_agent.utils.exceptions import AgentNotFoundError

        mock_storage.get_agent = AsyncMock(
            side_effect=AgentNotFoundError("Not found", agent_name="unknown")
        )

        response = registry_client.get("/api/v1/a2a/agents/unknown")

        assert response.status_code == 404


class TestA2AClient:
    """Tests for A2A client functionality."""

    @pytest.fixture
    def a2a_client(self):
        """Create A2A client for testing."""
        from info_agent.a2a.client import A2AClient

        return A2AClient()

    @patch("httpx.AsyncClient.post")
    async def test_send_task_success(self, mock_post, a2a_client):
        """Test successful task dispatch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "task-001",
            "status": "completed",
            "result": {"message": "Task completed"},
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await a2a_client.send_task(
            agent_url="http://localhost:9000",
            skill="send_email",
            payload={"to": "test@example.com", "body": "Hello"},
        )

        assert result["status"] == "completed"

    @patch("httpx.AsyncClient.post")
    async def test_send_task_agent_error(self, mock_post, a2a_client):
        """Test handling agent error response."""
        from httpx import HTTPStatusError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(HTTPStatusError):
            await a2a_client.send_task(
                agent_url="http://localhost:9000",
                skill="send_email",
                payload={},
            )

    @patch("httpx.AsyncClient.post")
    async def test_send_task_timeout(self, mock_post, a2a_client):
        """Test handling timeout."""
        from httpx import TimeoutException

        mock_post.side_effect = TimeoutException("Connection timed out")

        with pytest.raises(TimeoutException):
            await a2a_client.send_task(
                agent_url="http://localhost:9000",
                skill="send_email",
                payload={},
            )


class TestA2ADiscovery:
    """Tests for agent discovery functionality."""

    @patch("info_agent.a2a.registry.storage")
    async def test_discover_agents_by_skill(self, mock_storage):
        """Test discovering agents by skill."""
        from info_agent.a2a.registry import discover_agents_by_skill

        mock_storage.list_agents = AsyncMock(return_value=[
            {
                "name": "mail-agent",
                "skills": [
                    {"name": "send_email"},
                    {"name": "receive_email"},
                ],
            },
            {
                "name": "search-agent",
                "skills": [
                    {"name": "web_search"},
                ],
            },
        ])

        result = await discover_agents_by_skill("send_email")

        assert len(result) == 1
        assert result[0]["name"] == "mail-agent"

    @patch("info_agent.a2a.registry.storage")
    async def test_discover_agents_no_match(self, mock_storage):
        """Test discovery returns empty when no agents match."""
        from info_agent.a2a.registry import discover_agents_by_skill

        mock_storage.list_agents = AsyncMock(return_value=[
            {"name": "agent1", "skills": [{"name": "skill1"}]},
        ])

        result = await discover_agents_by_skill("nonexistent_skill")

        assert result == []


class TestA2ATaskExecution:
    """Tests for A2A task execution flow."""

    @patch("info_agent.a2a.client.A2AClient.send_task")
    async def test_execute_task_on_remote_agent(self, mock_send_task):
        """Test executing a task on a remote agent."""
        from info_agent.a2a.client import execute_task

        mock_send_task.return_value = {
            "task_id": "remote-task-001",
            "status": "completed",
            "result": {"data": "processed"},
        }

        result = await execute_task(
            agent_url="http://remote-agent:9000",
            skill="process_data",
            input_data={"input": "raw data"},
        )

        assert result["status"] == "completed"

    @patch("info_agent.a2a.client.A2AClient.send_task")
    async def test_execute_task_handles_failure(self, mock_send_task):
        """Test handling task execution failure."""
        from info_agent.utils.exceptions import A2AError

        mock_send_task.side_effect = Exception("Remote agent unavailable")

        with pytest.raises(Exception):
            from info_agent.a2a.client import execute_task

            await execute_task(
                agent_url="http://unavailable-agent:9000",
                skill="some_skill",
                input_data={},
            )


class TestA2AProtocolCompliance:
    """Tests for A2A protocol compliance."""

    def test_agent_card_schema(self, sample_agent_card):
        """Test agent card conforms to A2A schema."""
        from info_agent.a2a.models import AgentCard

        # Should not raise validation error
        card = AgentCard(**sample_agent_card)

        assert card.name == sample_agent_card["name"]
        assert card.url == sample_agent_card["url"]

    def test_task_request_schema(self):
        """Test task request conforms to A2A schema."""
        from info_agent.a2a.models import A2ATaskRequest

        request = A2ATaskRequest(
            task_id="task-001",
            skill="send_email",
            input_data={"to": "test@example.com"},
        )

        assert request.task_id == "task-001"
        assert request.skill == "send_email"

    def test_task_response_schema(self):
        """Test task response conforms to A2A schema."""
        from info_agent.a2a.models import A2ATaskResponse

        response = A2ATaskResponse(
            task_id="task-001",
            status="completed",
            result={"message": "Email sent"},
        )

        assert response.task_id == "task-001"
        assert response.status == "completed"
