"""
Unit tests for A2A Agent Server.
"""

import pytest
from fastapi.testclient import TestClient

from info_agent.a2a.executor import (
    BaseAgentExecutor,
    EventQueue,
    RequestContext,
)
from info_agent.a2a.models import (
    AgentCard,
    AgentSkill,
    Task,
    TaskRequest,
    TaskState,
)
from info_agent.a2a.server import (
    AgentServer,
    TaskStore,
    create_agent_app,
    create_agent_router,
)


@pytest.fixture
def sample_skill() -> AgentSkill:
    """Create a sample skill."""
    return AgentSkill(
        id="echo",
        name="Echo",
        description="Echoes back the input message",
    )


@pytest.fixture
def sample_agent_card(sample_skill: AgentSkill) -> AgentCard:
    """Create a sample agent card."""
    return AgentCard(
        id="echo-agent",
        name="Echo Agent",
        description="An agent that echoes messages",
        endpoint="http://localhost:8000",
        skills=[sample_skill],
    )


class EchoExecutor(BaseAgentExecutor):
    """Simple echo executor for testing."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Echo back the message."""
        message = context.get_input("message", "No message")
        await event_queue.send_text(f"Echo: {message}")


@pytest.fixture
def executor(sample_agent_card: AgentCard) -> EchoExecutor:
    """Create test executor."""
    return EchoExecutor(sample_agent_card)


@pytest.fixture
def task_store() -> TaskStore:
    """Create test task store."""
    return TaskStore()


@pytest.fixture
def client(executor: EchoExecutor, task_store: TaskStore) -> TestClient:
    """Create test client."""
    app = create_agent_app(executor, task_store)
    return TestClient(app)


class TestTaskStore:
    """Tests for TaskStore."""

    def test_store_and_get(self) -> None:
        """Test storing and retrieving a task."""
        store = TaskStore()
        task = Task(skill_id="test", input={"key": "value"})

        store.store(task)
        result = store.get(task.id)

        assert result is not None
        assert result.id == task.id

    def test_get_nonexistent(self) -> None:
        """Test getting nonexistent task."""
        store = TaskStore()

        result = store.get("nonexistent")

        assert result is None

    def test_delete(self) -> None:
        """Test deleting a task."""
        store = TaskStore()
        task = Task(skill_id="test", input={})
        store.store(task)

        result = store.delete(task.id)

        assert result is True
        assert store.get(task.id) is None

    def test_delete_nonexistent(self) -> None:
        """Test deleting nonexistent task."""
        store = TaskStore()

        result = store.delete("nonexistent")

        assert result is False

    def test_list_all(self) -> None:
        """Test listing all tasks."""
        store = TaskStore()
        for i in range(3):
            store.store(Task(skill_id=f"skill-{i}", input={}))

        tasks = store.list_all()

        assert len(tasks) == 3

    def test_count(self) -> None:
        """Test counting tasks."""
        store = TaskStore()
        for i in range(5):
            store.store(Task(skill_id=f"skill-{i}", input={}))

        assert store.count() == 5

    def test_clear(self) -> None:
        """Test clearing all tasks."""
        store = TaskStore()
        for i in range(5):
            store.store(Task(skill_id=f"skill-{i}", input={}))

        count = store.clear()

        assert count == 5
        assert store.count() == 0


class TestAgentCardEndpoint:
    """Tests for agent card endpoints."""

    def test_get_agent_card_well_known(self, client: TestClient) -> None:
        """Test getting agent card from well-known path."""
        response = client.get("/.well-known/agent.json")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "echo-agent"
        assert data["name"] == "Echo Agent"

    def test_get_agent_card_alt(self, client: TestClient) -> None:
        """Test getting agent card from alternative path."""
        response = client.get("/agent.json")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "echo-agent"


class TestTaskEndpoints:
    """Tests for task endpoints."""

    def test_create_task(self, client: TestClient) -> None:
        """Test creating a task."""
        response = client.post(
            "/tasks",
            json={
                "skill_id": "echo",
                "input": {"message": "Hello World"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["skill_id"] == "echo"
        assert data["state"] == "completed"
        assert len(data["artifacts"]) == 1

    def test_get_task(self, client: TestClient) -> None:
        """Test getting a task."""
        # First create a task
        create_response = client.post(
            "/tasks",
            json={"skill_id": "echo", "input": {"message": "Test"}},
        )
        task_id = create_response.json()["id"]

        # Then get it
        response = client.get(f"/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id

    def test_get_nonexistent_task(self, client: TestClient) -> None:
        """Test getting nonexistent task."""
        response = client.get("/tasks/nonexistent")

        assert response.status_code == 404

    def test_list_tasks(self, client: TestClient) -> None:
        """Test listing tasks."""
        # Create a few tasks
        for i in range(3):
            client.post(
                "/tasks",
                json={"skill_id": "echo", "input": {"message": f"Test {i}"}},
            )

        response = client.get("/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_tasks_filter_by_state(self, client: TestClient) -> None:
        """Test listing tasks filtered by state."""
        # Create a task
        client.post(
            "/tasks",
            json={"skill_id": "echo", "input": {"message": "Test"}},
        )

        response = client.get("/tasks?state=completed")

        assert response.status_code == 200
        data = response.json()
        assert all(t["state"] == "completed" for t in data)


class TestCancelEndpoint:
    """Tests for cancel endpoint."""

    def test_cancel_task(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        """Test cancelling a task."""
        # Create a working task manually
        task = Task(skill_id="echo", input={})
        task.transition_to(TaskState.WORKING)
        task_store.store(task)

        response = client.post(f"/tasks/{task.id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "cancelled"

    def test_cancel_nonexistent_task(self, client: TestClient) -> None:
        """Test cancelling nonexistent task."""
        response = client.post("/tasks/nonexistent/cancel")

        assert response.status_code == 404

    def test_cancel_completed_task(self, client: TestClient) -> None:
        """Test cancelling already completed task."""
        # Create a completed task
        create_response = client.post(
            "/tasks",
            json={"skill_id": "echo", "input": {"message": "Test"}},
        )
        task_id = create_response.json()["id"]

        response = client.post(f"/tasks/{task_id}/cancel")

        assert response.status_code == 400


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent_id"] == "echo-agent"


class TestStatsEndpoint:
    """Tests for stats endpoint."""

    def test_get_stats(self, client: TestClient) -> None:
        """Test getting stats."""
        # Create a task
        client.post(
            "/tasks",
            json={"skill_id": "echo", "input": {"message": "Test"}},
        )

        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "echo-agent"
        assert data["total_tasks"] == 1


class TestAgentServer:
    """Tests for AgentServer class."""

    def test_initialization(
        self, sample_agent_card: AgentCard
    ) -> None:
        """Test server initialization."""
        executor = EchoExecutor(sample_agent_card)
        server = AgentServer(executor, host="0.0.0.0", port=9000)

        assert server.host == "0.0.0.0"
        assert server.port == 9000
        assert server.executor == executor

    def test_app_property(
        self, sample_agent_card: AgentCard
    ) -> None:
        """Test app property creates app on first access."""
        executor = EchoExecutor(sample_agent_card)
        server = AgentServer(executor)

        app = server.app

        assert app is not None
        # Second access returns same app
        assert server.app is app
