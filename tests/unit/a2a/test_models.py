"""
Unit tests for A2A models.
"""

import pytest

from info_agent.a2a.models import (
    AgentCard,
    AgentEvent,
    AgentSkill,
    Artifact,
    MessagePart,
    SkillInputSchema,
    SkillOutputSchema,
    Task,
    TaskRequest,
    TaskResponse,
    TaskState,
)


class TestTaskState:
    """Tests for TaskState enum."""

    def test_all_states_exist(self) -> None:
        """Test all expected states exist."""
        assert TaskState.SUBMITTED.value == "submitted"
        assert TaskState.WORKING.value == "working"
        assert TaskState.INPUT_REQUIRED.value == "input_required"
        assert TaskState.COMPLETED.value == "completed"
        assert TaskState.FAILED.value == "failed"
        assert TaskState.CANCELLED.value == "cancelled"


class TestSkillInputSchema:
    """Tests for SkillInputSchema model."""

    def test_default_schema(self) -> None:
        """Test default input schema."""
        schema = SkillInputSchema()
        assert schema.type == "object"
        assert schema.properties == {}
        assert schema.required == []

    def test_schema_with_properties(self) -> None:
        """Test schema with properties."""
        schema = SkillInputSchema(
            properties={
                "amount": {"type": "number"},
                "currency": {"type": "string"},
            },
            required=["amount"],
        )
        assert "amount" in schema.properties
        assert "amount" in schema.required


class TestAgentSkill:
    """Tests for AgentSkill model."""

    def test_skill_creation(self) -> None:
        """Test creating a skill."""
        skill = AgentSkill(
            id="convert-currency",
            name="Convert Currency",
            description="Converts amounts between currencies",
        )
        assert skill.id == "convert-currency"
        assert skill.name == "Convert Currency"

    def test_skill_with_schema(self) -> None:
        """Test skill with input schema."""
        skill = AgentSkill(
            id="test-skill",
            name="Test",
            description="Test skill",
            input_schema=SkillInputSchema(
                properties={"value": {"type": "string"}},
            ),
        )
        assert skill.input_schema is not None
        assert "value" in skill.input_schema.properties

    def test_skill_with_tags(self) -> None:
        """Test skill with tags."""
        skill = AgentSkill(
            id="test-skill",
            name="Test",
            description="Test skill",
            tags=["conversion", "finance"],
        )
        assert "conversion" in skill.tags
        assert len(skill.tags) == 2


class TestAgentCard:
    """Tests for AgentCard model."""

    def test_agent_card_creation(self) -> None:
        """Test creating an agent card."""
        card = AgentCard(
            name="Test Agent",
            description="A test agent",
            endpoint="http://localhost:8000/a2a",
        )
        assert card.name == "Test Agent"
        assert card.endpoint == "http://localhost:8000/a2a"

    def test_agent_card_has_id(self) -> None:
        """Test agent card has auto-generated ID."""
        card = AgentCard(
            name="Test Agent",
            description="Test",
            endpoint="http://localhost:8000",
        )
        assert card.id is not None
        assert len(card.id) > 0

    def test_agent_card_default_protocol_version(self) -> None:
        """Test default protocol version."""
        card = AgentCard(
            name="Test",
            description="Test",
            endpoint="http://localhost:8000",
        )
        assert card.protocol_version == "1.0"

    def test_has_skill(self) -> None:
        """Test checking for skill."""
        skill = AgentSkill(
            id="test-skill",
            name="Test",
            description="Test",
        )
        card = AgentCard(
            name="Test",
            description="Test",
            endpoint="http://localhost:8000",
            skills=[skill],
        )
        assert card.has_skill("test-skill") is True
        assert card.has_skill("nonexistent") is False

    def test_get_skill(self) -> None:
        """Test getting a skill by ID."""
        skill = AgentSkill(
            id="test-skill",
            name="Test",
            description="Test",
        )
        card = AgentCard(
            name="Test",
            description="Test",
            endpoint="http://localhost:8000",
            skills=[skill],
        )
        found = card.get_skill("test-skill")
        assert found is not None
        assert found.id == "test-skill"

        not_found = card.get_skill("nonexistent")
        assert not_found is None

    def test_has_capability(self) -> None:
        """Test checking for capability."""
        card = AgentCard(
            name="Test",
            description="Test",
            endpoint="http://localhost:8000",
            capabilities=["streaming", "push_notifications"],
        )
        assert card.has_capability("streaming") is True
        assert card.has_capability("unknown") is False


class TestMessagePart:
    """Tests for MessagePart model."""

    def test_text_part(self) -> None:
        """Test text message part."""
        part = MessagePart(type="text", text="Hello world")
        assert part.type == "text"
        assert part.text == "Hello world"

    def test_data_part(self) -> None:
        """Test data message part."""
        part = MessagePart(type="data", data={"key": "value"})
        assert part.type == "data"
        assert part.data["key"] == "value"

    def test_file_part(self) -> None:
        """Test file message part."""
        part = MessagePart(
            type="file",
            file={"path": "s3://bucket/file", "mime_type": "text/plain"},
        )
        assert part.type == "file"
        assert part.file["path"] == "s3://bucket/file"


class TestArtifact:
    """Tests for Artifact model."""

    def test_artifact_creation(self) -> None:
        """Test creating an artifact."""
        artifact = Artifact(
            parts=[MessagePart(type="text", text="Result")]
        )
        assert len(artifact.parts) == 1

    def test_artifact_has_id(self) -> None:
        """Test artifact has auto-generated ID."""
        artifact = Artifact()
        assert artifact.id is not None

    def test_artifact_has_timestamp(self) -> None:
        """Test artifact has creation timestamp."""
        artifact = Artifact()
        assert artifact.created_at is not None


class TestTask:
    """Tests for Task model."""

    def test_task_creation(self) -> None:
        """Test creating a task."""
        task = Task(
            skill_id="test-skill",
            input={"param": "value"},
        )
        assert task.skill_id == "test-skill"
        assert task.input["param"] == "value"

    def test_task_default_state(self) -> None:
        """Test task default state."""
        task = Task(skill_id="test")
        assert task.state == TaskState.SUBMITTED

    def test_task_transition(self) -> None:
        """Test task state transition."""
        task = Task(skill_id="test")
        task.transition_to(TaskState.WORKING)
        assert task.state == TaskState.WORKING

    def test_task_add_artifact(self) -> None:
        """Test adding artifact to task."""
        task = Task(skill_id="test")
        artifact = Artifact(parts=[MessagePart(type="text", text="Result")])
        task.add_artifact(artifact)
        assert len(task.artifacts) == 1

    def test_task_set_error(self) -> None:
        """Test setting task error."""
        task = Task(skill_id="test")
        task.set_error("Something went wrong")
        assert task.state == TaskState.FAILED
        assert task.error == "Something went wrong"


class TestTaskRequest:
    """Tests for TaskRequest model."""

    def test_task_request(self) -> None:
        """Test creating a task request."""
        request = TaskRequest(
            skill_id="convert",
            input={"amount": 100},
        )
        assert request.skill_id == "convert"
        assert request.input["amount"] == 100

    def test_to_task(self) -> None:
        """Test converting request to task."""
        request = TaskRequest(
            skill_id="convert",
            input={"amount": 100},
            metadata={"source": "test"},
        )
        task = request.to_task()
        assert task.skill_id == "convert"
        assert task.input["amount"] == 100
        assert task.metadata["source"] == "test"


class TestTaskResponse:
    """Tests for TaskResponse model."""

    def test_task_response(self) -> None:
        """Test task response."""
        response = TaskResponse(
            task_id="task-123",
            state=TaskState.COMPLETED,
        )
        assert response.task_id == "task-123"
        assert response.state == TaskState.COMPLETED


class TestAgentEvent:
    """Tests for AgentEvent model."""

    def test_agent_event(self) -> None:
        """Test creating an agent event."""
        event = AgentEvent(
            type="status_update",
            task_id="task-123",
            data={"status": "processing"},
        )
        assert event.type == "status_update"
        assert event.task_id == "task-123"

    def test_event_has_id(self) -> None:
        """Test event has auto-generated ID."""
        event = AgentEvent(type="test", task_id="task-123")
        assert event.id is not None

    def test_event_has_timestamp(self) -> None:
        """Test event has timestamp."""
        event = AgentEvent(type="test", task_id="task-123")
        assert event.timestamp is not None
