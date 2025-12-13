"""
Unit tests for A2A Agent Executor.
"""

import pytest

from info_agent.a2a.executor import (
    BaseAgentExecutor,
    EventQueue,
    RequestContext,
)
from info_agent.a2a.models import (
    AgentCard,
    AgentSkill,
    Artifact,
    MessagePart,
    Task,
    TaskRequest,
    TaskState,
)


@pytest.fixture
def sample_skill() -> AgentSkill:
    """Create a sample skill."""
    return AgentSkill(
        id="greet",
        name="Greet User",
        description="Greets a user by name",
        tags=["greeting"],
    )


@pytest.fixture
def sample_agent_card(sample_skill: AgentSkill) -> AgentCard:
    """Create a sample agent card."""
    return AgentCard(
        id="greeter-agent",
        name="Greeter Agent",
        description="An agent that greets users",
        endpoint="http://localhost:8000/a2a",
        skills=[sample_skill],
    )


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task."""
    return Task(
        skill_id="greet",
        input={"name": "World"},
    )


class TestEventQueue:
    """Tests for EventQueue."""

    def test_initialization(self, sample_task: Task) -> None:
        """Test event queue initialization."""
        queue = EventQueue(sample_task)

        assert queue.task == sample_task
        assert queue.events == []

    @pytest.mark.asyncio
    async def test_send_artifact(self, sample_task: Task) -> None:
        """Test sending an artifact."""
        queue = EventQueue(sample_task)
        artifact = Artifact(parts=[MessagePart(type="text", text="Hello")])

        await queue.send_artifact(artifact)

        assert len(sample_task.artifacts) == 1
        assert len(queue.events) == 1
        assert queue.events[0]["type"] == "artifact"

    @pytest.mark.asyncio
    async def test_send_text(self, sample_task: Task) -> None:
        """Test sending text message."""
        queue = EventQueue(sample_task)

        await queue.send_text("Hello World")

        assert len(sample_task.artifacts) == 1
        assert sample_task.artifacts[0].parts[0].text == "Hello World"

    @pytest.mark.asyncio
    async def test_send_data(self, sample_task: Task) -> None:
        """Test sending structured data."""
        queue = EventQueue(sample_task)

        await queue.send_data({"key": "value"})

        assert len(sample_task.artifacts) == 1
        assert sample_task.artifacts[0].parts[0].data["key"] == "value"

    @pytest.mark.asyncio
    async def test_send_status(self, sample_task: Task) -> None:
        """Test sending status update."""
        queue = EventQueue(sample_task)

        await queue.send_status("Processing...")

        assert len(queue.events) == 1
        assert queue.events[0]["type"] == "status"
        assert queue.events[0]["message"] == "Processing..."

    @pytest.mark.asyncio
    async def test_send_error(self, sample_task: Task) -> None:
        """Test sending error."""
        queue = EventQueue(sample_task)

        await queue.send_error("Something went wrong")

        assert sample_task.state == TaskState.FAILED
        assert sample_task.error == "Something went wrong"
        assert queue.events[0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_request_input(self, sample_task: Task) -> None:
        """Test requesting input."""
        queue = EventQueue(sample_task)
        fields = [{"name": "email", "type": "string"}]

        await queue.request_input("Please provide email", fields)

        assert sample_task.state == TaskState.INPUT_REQUIRED
        assert sample_task.metadata["input_request"]["prompt"] == "Please provide email"


class TestRequestContext:
    """Tests for RequestContext."""

    def test_initialization(
        self, sample_task: Task, sample_skill: AgentSkill
    ) -> None:
        """Test context initialization."""
        context = RequestContext(
            task=sample_task,
            skill=sample_skill,
            metadata={"source": "test"},
        )

        assert context.task == sample_task
        assert context.skill == sample_skill
        assert context.metadata["source"] == "test"

    def test_input_property(self, sample_task: Task) -> None:
        """Test input property."""
        context = RequestContext(task=sample_task)

        assert context.input == {"name": "World"}

    def test_get_input(self, sample_task: Task) -> None:
        """Test getting input by key."""
        context = RequestContext(task=sample_task)

        assert context.get_input("name") == "World"
        assert context.get_input("missing", "default") == "default"


class SimpleGreeterExecutor(BaseAgentExecutor):
    """Simple test executor that greets users."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute greeting task."""
        name = context.get_input("name", "Anonymous")
        await event_queue.send_text(f"Hello, {name}!")


class ErrorExecutor(BaseAgentExecutor):
    """Test executor that raises an error."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute and raise error."""
        raise ValueError("Test error")


class TestBaseAgentExecutor:
    """Tests for BaseAgentExecutor."""

    def test_initialization(self, sample_agent_card: AgentCard) -> None:
        """Test executor initialization."""
        executor = SimpleGreeterExecutor(sample_agent_card)

        assert executor.agent_card == sample_agent_card

    def test_get_skill(self, sample_agent_card: AgentCard) -> None:
        """Test getting skill by ID."""
        executor = SimpleGreeterExecutor(sample_agent_card)

        skill = executor.get_skill("greet")

        assert skill is not None
        assert skill.id == "greet"

    def test_get_skill_not_found(self, sample_agent_card: AgentCard) -> None:
        """Test getting nonexistent skill."""
        executor = SimpleGreeterExecutor(sample_agent_card)

        skill = executor.get_skill("nonexistent")

        assert skill is None

    def test_has_skill(self, sample_agent_card: AgentCard) -> None:
        """Test has_skill method."""
        executor = SimpleGreeterExecutor(sample_agent_card)

        assert executor.has_skill("greet") is True
        assert executor.has_skill("nonexistent") is False

    @pytest.mark.asyncio
    async def test_handle_task_success(
        self, sample_agent_card: AgentCard
    ) -> None:
        """Test successful task handling."""
        executor = SimpleGreeterExecutor(sample_agent_card)
        request = TaskRequest(skill_id="greet", input={"name": "Alice"})

        task = await executor.handle_task(request)

        assert task.state == TaskState.COMPLETED
        assert len(task.artifacts) == 1
        assert "Hello, Alice!" in task.artifacts[0].parts[0].text

    @pytest.mark.asyncio
    async def test_handle_task_unknown_skill(
        self, sample_agent_card: AgentCard
    ) -> None:
        """Test handling task with unknown skill."""
        executor = SimpleGreeterExecutor(sample_agent_card)
        request = TaskRequest(skill_id="unknown", input={})

        task = await executor.handle_task(request)

        assert task.state == TaskState.FAILED
        assert "Unknown skill" in task.error

    @pytest.mark.asyncio
    async def test_handle_task_execution_error(
        self, sample_agent_card: AgentCard
    ) -> None:
        """Test handling task that throws error."""
        executor = ErrorExecutor(sample_agent_card)
        request = TaskRequest(skill_id="greet", input={})

        task = await executor.handle_task(request)

        assert task.state == TaskState.FAILED
        assert "Test error" in task.error

    @pytest.mark.asyncio
    async def test_on_cancel(self, sample_agent_card: AgentCard) -> None:
        """Test task cancellation."""
        executor = SimpleGreeterExecutor(sample_agent_card)
        task = Task(skill_id="greet", input={"name": "Test"})

        result = await executor.on_cancel(task)

        assert result.state == TaskState.CANCELLED

    @pytest.mark.asyncio
    async def test_health_check(self, sample_agent_card: AgentCard) -> None:
        """Test health check."""
        executor = SimpleGreeterExecutor(sample_agent_card)

        health = await executor.health_check()

        assert health["status"] == "healthy"
        assert health["agent_id"] == "greeter-agent"
        assert "greet" in health["skills"]
