"""
Unit tests for A2A Client.
"""

import pytest
import httpx
import respx

from info_agent.a2a.client import A2AClient
from info_agent.a2a.models import Task, TaskRequest, TaskState
from info_agent.utils.exceptions import A2AError


class TestA2AClientInit:
    """Tests for client initialization."""

    def test_default_initialization(self) -> None:
        """Test client initializes with defaults."""
        client = A2AClient()
        assert client._timeout == 30.0
        assert client._max_retries == 3

    def test_custom_initialization(self) -> None:
        """Test client with custom settings."""
        client = A2AClient(timeout=60.0, max_retries=5)
        assert client._timeout == 60.0
        assert client._max_retries == 5


class TestA2AClientDiscover:
    """Tests for agent discovery."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_discover_agent_success(self) -> None:
        """Test successful agent discovery."""
        client = A2AClient()

        mock_card = {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "A test agent",
            "endpoint": "http://localhost:8000/a2a",
            "protocol_version": "1.0",
            "skills": [],
        }

        respx.get("http://localhost:8000/.well-known/agent.json").mock(
            return_value=httpx.Response(200, json=mock_card)
        )

        result = await client.discover_agent("http://localhost:8000")

        assert result.id == "test-agent"
        assert result.name == "Test Agent"

    @pytest.mark.asyncio
    @respx.mock
    async def test_discover_agent_not_found(self) -> None:
        """Test agent discovery when not found."""
        client = A2AClient()

        respx.get("http://localhost:8000/.well-known/agent.json").mock(
            return_value=httpx.Response(404)
        )
        respx.get("http://localhost:8000/agent.json").mock(
            return_value=httpx.Response(404)
        )

        with pytest.raises(A2AError) as exc_info:
            await client.discover_agent("http://localhost:8000")

        assert "failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_discover_agent_timeout(self) -> None:
        """Test agent discovery timeout."""
        client = A2AClient()

        respx.get("http://localhost:8000/.well-known/agent.json").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(A2AError) as exc_info:
            await client.discover_agent("http://localhost:8000")

        assert "timed out" in str(exc_info.value).lower()


class TestA2AClientSubmitTask:
    """Tests for task submission."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_task_success(self) -> None:
        """Test successful task submission."""
        client = A2AClient()
        request = TaskRequest(skill_id="test-skill", input={"value": "test"})

        mock_task = {
            "id": "task-123",
            "skill_id": "test-skill",
            "input": {"value": "test"},
            "state": "submitted",
            "artifacts": [],
        }

        respx.post("http://localhost:8000/a2a/tasks").mock(
            return_value=httpx.Response(201, json=mock_task)
        )

        result = await client.submit_task("http://localhost:8000/a2a", request)

        assert result.id == "task-123"
        assert result.state == TaskState.SUBMITTED

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_task_failure(self) -> None:
        """Test task submission failure."""
        client = A2AClient()
        request = TaskRequest(skill_id="test-skill", input={})

        respx.post("http://localhost:8000/a2a/tasks").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(A2AError) as exc_info:
            await client.submit_task("http://localhost:8000/a2a", request)

        assert "failed" in str(exc_info.value).lower()


class TestA2AClientGetTask:
    """Tests for getting task status."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_task_success(self) -> None:
        """Test getting task successfully."""
        client = A2AClient()

        mock_task = {
            "id": "task-123",
            "skill_id": "test-skill",
            "input": {},
            "state": "working",
            "artifacts": [],
        }

        respx.get("http://localhost:8000/a2a/tasks/task-123").mock(
            return_value=httpx.Response(200, json=mock_task)
        )

        result = await client.get_task("http://localhost:8000/a2a", "task-123")

        assert result.id == "task-123"
        assert result.state == TaskState.WORKING

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_task_not_found(self) -> None:
        """Test getting nonexistent task."""
        client = A2AClient()

        respx.get("http://localhost:8000/a2a/tasks/nonexistent").mock(
            return_value=httpx.Response(404)
        )

        with pytest.raises(A2AError) as exc_info:
            await client.get_task("http://localhost:8000/a2a", "nonexistent")

        assert "not found" in str(exc_info.value).lower()


class TestA2AClientCancelTask:
    """Tests for task cancellation."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_cancel_task_success(self) -> None:
        """Test cancelling a task."""
        client = A2AClient()

        mock_task = {
            "id": "task-123",
            "skill_id": "test-skill",
            "input": {},
            "state": "cancelled",
            "artifacts": [],
        }

        respx.post("http://localhost:8000/a2a/tasks/task-123/cancel").mock(
            return_value=httpx.Response(200, json=mock_task)
        )

        result = await client.cancel_task("http://localhost:8000/a2a", "task-123")

        assert result.state == TaskState.CANCELLED


class TestA2AClientWaitForCompletion:
    """Tests for waiting for task completion."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_wait_completed_immediately(self) -> None:
        """Test waiting when task is already completed."""
        client = A2AClient()

        mock_task = {
            "id": "task-123",
            "skill_id": "test-skill",
            "input": {},
            "state": "completed",
            "artifacts": [],
        }

        respx.get("http://localhost:8000/a2a/tasks/task-123").mock(
            return_value=httpx.Response(200, json=mock_task)
        )

        result = await client.wait_for_completion(
            "http://localhost:8000/a2a",
            "task-123",
            poll_interval=0.1,
            max_wait=1.0,
        )

        assert result.state == TaskState.COMPLETED

    @pytest.mark.asyncio
    @respx.mock
    async def test_wait_returns_on_input_required(self) -> None:
        """Test waiting returns when input is required."""
        client = A2AClient()

        mock_task = {
            "id": "task-123",
            "skill_id": "test-skill",
            "input": {},
            "state": "input_required",
            "artifacts": [],
        }

        respx.get("http://localhost:8000/a2a/tasks/task-123").mock(
            return_value=httpx.Response(200, json=mock_task)
        )

        result = await client.wait_for_completion(
            "http://localhost:8000/a2a",
            "task-123",
            poll_interval=0.1,
            max_wait=1.0,
        )

        assert result.state == TaskState.INPUT_REQUIRED


class TestA2AClientExecuteSkill:
    """Tests for skill execution."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_skill_success(self) -> None:
        """Test executing a skill successfully."""
        client = A2AClient()

        submitted_task = {
            "id": "task-123",
            "skill_id": "test-skill",
            "input": {"value": "test"},
            "state": "submitted",
            "artifacts": [],
        }

        completed_task = {
            "id": "task-123",
            "skill_id": "test-skill",
            "input": {"value": "test"},
            "state": "completed",
            "artifacts": [
                {"id": "artifact-1", "parts": [{"type": "text", "text": "Result"}]}
            ],
        }

        respx.post("http://localhost:8000/a2a/tasks").mock(
            return_value=httpx.Response(201, json=submitted_task)
        )

        respx.get("http://localhost:8000/a2a/tasks/task-123").mock(
            return_value=httpx.Response(200, json=completed_task)
        )

        result = await client.execute_skill(
            "http://localhost:8000/a2a",
            "test-skill",
            {"value": "test"},
            wait=True,
            poll_interval=0.1,
            max_wait=1.0,
        )

        assert result.state == TaskState.COMPLETED
        assert len(result.artifacts) == 1


class TestA2AClientHealthCheck:
    """Tests for health check."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        client = A2AClient()

        respx.get("http://localhost:8000/health").mock(
            return_value=httpx.Response(200)
        )

        result = await client.health_check("http://localhost:8000")

        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_failure(self) -> None:
        """Test failed health check."""
        client = A2AClient()

        respx.get("http://localhost:8000/health").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await client.health_check("http://localhost:8000")

        assert result is False

    @respx.mock
    def test_health_check_sync(self) -> None:
        """Test synchronous health check wrapper."""
        client = A2AClient()

        respx.get("http://localhost:8000/health").mock(
            return_value=httpx.Response(200)
        )

        result = client.health_check_sync("http://localhost:8000")

        assert result is True
