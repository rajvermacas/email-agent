"""
Unit tests for A2A Pydantic models.

Tests all models from src/info_agent/a2a/models.py including:
- AgentSkill model validation
- AgentCard model validation
- A2ATaskRequest model validation
- A2ATaskResponse model validation
- RegisterAgentResponse model validation

All tests use explicit test data with no fallback values.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from info_agent.a2a.models import (
    A2ATaskRequest,
    A2ATaskResponse,
    AgentCard,
    AgentSkill,
    RegisterAgentResponse,
)


class TestAgentSkill:
    """Tests for the AgentSkill model."""

    def test_valid_skill_creation(self):
        """Test creating a valid AgentSkill."""
        skill = AgentSkill(
            id="convert_currency",
            name="Convert Currency",
            description="Converts amount from one currency to another",
            input_schema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                },
                "required": ["amount", "from", "to"],
            },
        )

        assert skill.id == "convert_currency"
        assert skill.name == "Convert Currency"
        assert skill.description == "Converts amount from one currency to another"
        assert skill.input_schema["type"] == "object"
        assert skill.example_prompts is None

    def test_valid_skill_with_example_prompts(self):
        """Test creating a skill with example prompts."""
        skill = AgentSkill(
            id="convert_currency",
            name="Convert Currency",
            description="Converts amount from one currency to another",
            input_schema={"type": "object"},
            example_prompts=["Convert 100 USD to EUR", "What is 50 pounds in dollars?"],
        )

        assert skill.example_prompts == ["Convert 100 USD to EUR", "What is 50 pounds in dollars?"]

    def test_missing_id_fails(self):
        """Test that missing id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                name="Convert Currency",
                description="Converts currency",
                input_schema={"type": "object"},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)
        assert any(error["type"] == "missing" for error in errors)

    def test_empty_id_fails(self):
        """Test that empty id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="",
                name="Convert Currency",
                description="Converts currency",
                input_schema={"type": "object"},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)

    def test_missing_name_fails(self):
        """Test that missing name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="convert_currency",
                description="Converts currency",
                input_schema={"type": "object"},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_empty_name_fails(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="convert_currency",
                name="",
                description="Converts currency",
                input_schema={"type": "object"},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_missing_description_fails(self):
        """Test that missing description raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="convert_currency",
                name="Convert Currency",
                input_schema={"type": "object"},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("description",) for error in errors)

    def test_empty_description_fails(self):
        """Test that empty description raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="convert_currency",
                name="Convert Currency",
                description="",
                input_schema={"type": "object"},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("description",) for error in errors)

    def test_missing_input_schema_fails(self):
        """Test that missing input_schema raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="convert_currency",
                name="Convert Currency",
                description="Converts currency",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("input_schema",) for error in errors)

    def test_empty_input_schema_fails(self):
        """Test that empty input_schema raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="convert_currency",
                name="Convert Currency",
                description="Converts currency",
                input_schema={},
            )

        errors = exc_info.value.errors()
        assert any("cannot be empty" in str(error["ctx"]["error"]) for error in errors)

    def test_input_schema_without_type_fails(self):
        """Test that input_schema without 'type' field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSkill(
                id="convert_currency",
                name="Convert Currency",
                description="Converts currency",
                input_schema={"properties": {"amount": {"type": "number"}}},
            )

        errors = exc_info.value.errors()
        assert any("must contain 'type' field" in str(error["ctx"]["error"]) for error in errors)

    def test_skill_serialization(self):
        """Test that AgentSkill can be serialized to dict."""
        skill = AgentSkill(
            id="convert_currency",
            name="Convert Currency",
            description="Converts currency",
            input_schema={"type": "object"},
            example_prompts=["Convert 100 USD to EUR"],
        )

        data = skill.model_dump()

        assert data["id"] == "convert_currency"
        assert data["name"] == "Convert Currency"
        assert data["description"] == "Converts currency"
        assert data["input_schema"] == {"type": "object"}
        assert data["example_prompts"] == ["Convert 100 USD to EUR"]

    def test_skill_json_serialization(self):
        """Test that AgentSkill can be serialized to JSON."""
        skill = AgentSkill(
            id="convert_currency",
            name="Convert Currency",
            description="Converts currency",
            input_schema={"type": "object"},
        )

        json_str = skill.model_dump_json()
        assert "convert_currency" in json_str
        assert "Convert Currency" in json_str


class TestAgentCard:
    """Tests for the AgentCard model."""

    @pytest.fixture
    def valid_skill(self):
        """Fixture providing a valid AgentSkill."""
        return AgentSkill(
            id="convert_currency",
            name="Convert Currency",
            description="Converts currency",
            input_schema={"type": "object"},
        )

    def test_valid_agent_card_creation(self, valid_skill):
        """Test creating a valid AgentCard."""
        card = AgentCard(
            name="currency-agent",
            description="Currency conversion agent",
            version="1.0.0",
            url="http://localhost:8001/a2a",
            capabilities={"async": True, "streaming": False},
            skills=[valid_skill],
            defaultInputModes=["text", "data"],
            defaultOutputModes=["text", "data"],
        )

        assert card.name == "currency-agent"
        assert card.description == "Currency conversion agent"
        assert card.version == "1.0.0"
        assert card.url == "http://localhost:8001/a2a"
        assert card.capabilities == {"async": True, "streaming": False}
        assert len(card.skills) == 1
        assert card.skills[0].id == "convert_currency"
        assert card.defaultInputModes == ["text", "data"]
        assert card.defaultOutputModes == ["text", "data"]
        assert card.created_at is None

    def test_agent_card_with_created_at(self, valid_skill):
        """Test creating an AgentCard with created_at timestamp."""
        now = datetime.now(timezone.utc)
        card = AgentCard(
            name="currency-agent",
            description="Currency conversion agent",
            version="1.0.0",
            url="http://localhost:8001/a2a",
            capabilities={},
            skills=[valid_skill],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            created_at=now,
        )

        assert card.created_at == now

    def test_agent_card_with_https_url(self, valid_skill):
        """Test creating an AgentCard with HTTPS URL."""
        card = AgentCard(
            name="currency-agent",
            description="Currency conversion agent",
            version="1.0.0",
            url="https://api.example.com/a2a",
            capabilities={},
            skills=[valid_skill],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )

        assert card.url == "https://api.example.com/a2a"

    def test_missing_name_fails(self, valid_skill):
        """Test that missing name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_empty_name_fails(self, valid_skill):
        """Test that empty name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_missing_description_fails(self, valid_skill):
        """Test that missing description raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("description",) for error in errors)

    def test_missing_version_fails(self, valid_skill):
        """Test that missing version raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("version",) for error in errors)

    def test_missing_url_fails(self, valid_skill):
        """Test that missing url raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("url",) for error in errors)

    def test_invalid_url_fails(self, valid_skill):
        """Test that URL without http/https prefix raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any("must start with http:// or https://" in str(error["ctx"]["error"]) for error in errors)

    def test_missing_capabilities_fails(self, valid_skill):
        """Test that missing capabilities raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("capabilities",) for error in errors)

    def test_missing_skills_fails(self):
        """Test that missing skills raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("skills",) for error in errors)

    def test_empty_skills_fails(self):
        """Test that empty skills list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        # Check for either custom validator or pydantic's min_length validation
        assert any(
            error["loc"] == ("skills",) and
            (error["type"] == "too_short" or "must have at least one skill" in str(error.get("ctx", {}).get("error", "")))
            for error in errors
        )

    def test_duplicate_skill_ids_fails(self):
        """Test that duplicate skill IDs raise validation error."""
        skill1 = AgentSkill(
            id="convert",
            name="Convert Currency",
            description="Converts currency",
            input_schema={"type": "object"},
        )
        skill2 = AgentSkill(
            id="convert",
            name="Convert Again",
            description="Another converter",
            input_schema={"type": "object"},
        )

        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[skill1, skill2],
                defaultInputModes=["text"],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any("Skill IDs must be unique" in str(error["ctx"]["error"]) for error in errors)

    def test_multiple_unique_skills(self):
        """Test that multiple skills with unique IDs work correctly."""
        skill1 = AgentSkill(
            id="convert_currency",
            name="Convert Currency",
            description="Converts currency",
            input_schema={"type": "object"},
        )
        skill2 = AgentSkill(
            id="get_rate",
            name="Get Exchange Rate",
            description="Gets current exchange rate",
            input_schema={"type": "object"},
        )

        card = AgentCard(
            name="currency-agent",
            description="Currency conversion agent",
            version="1.0.0",
            url="http://localhost:8001/a2a",
            capabilities={},
            skills=[skill1, skill2],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )

        assert len(card.skills) == 2
        assert card.skills[0].id == "convert_currency"
        assert card.skills[1].id == "get_rate"

    def test_missing_default_input_modes_fails(self, valid_skill):
        """Test that missing defaultInputModes raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("defaultInputModes",) for error in errors)

    def test_empty_default_input_modes_fails(self, valid_skill):
        """Test that empty defaultInputModes raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=[],
                defaultOutputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("defaultInputModes",) for error in errors)

    def test_missing_default_output_modes_fails(self, valid_skill):
        """Test that missing defaultOutputModes raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("defaultOutputModes",) for error in errors)

    def test_empty_default_output_modes_fails(self, valid_skill):
        """Test that empty defaultOutputModes raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCard(
                name="currency-agent",
                description="Currency conversion agent",
                version="1.0.0",
                url="http://localhost:8001/a2a",
                capabilities={},
                skills=[valid_skill],
                defaultInputModes=["text"],
                defaultOutputModes=[],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("defaultOutputModes",) for error in errors)

    def test_agent_card_serialization(self, valid_skill):
        """Test that AgentCard can be serialized to dict."""
        card = AgentCard(
            name="currency-agent",
            description="Currency conversion agent",
            version="1.0.0",
            url="http://localhost:8001/a2a",
            capabilities={"async": True},
            skills=[valid_skill],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )

        data = card.model_dump()

        assert data["name"] == "currency-agent"
        assert data["description"] == "Currency conversion agent"
        assert data["version"] == "1.0.0"
        assert data["url"] == "http://localhost:8001/a2a"
        assert data["capabilities"] == {"async": True}
        assert len(data["skills"]) == 1
        assert data["defaultInputModes"] == ["text"]
        assert data["defaultOutputModes"] == ["text"]


class TestA2ATaskRequest:
    """Tests for the A2ATaskRequest model."""

    def test_valid_task_request_creation(self):
        """Test creating a valid A2ATaskRequest."""
        request = A2ATaskRequest(
            task_id="task-123",
            skill_id="convert_currency",
            payload={
                "amount": 100,
                "from": "USD",
                "to": "EUR",
            },
        )

        assert request.task_id == "task-123"
        assert request.skill_id == "convert_currency"
        assert request.payload["amount"] == 100
        assert request.payload["from"] == "USD"
        assert request.payload["to"] == "EUR"

    def test_missing_task_id_fails(self):
        """Test that missing task_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskRequest(
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("task_id",) for error in errors)

    def test_empty_task_id_fails(self):
        """Test that empty task_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskRequest(
                task_id="",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("task_id",) for error in errors)

    def test_missing_skill_id_fails(self):
        """Test that missing skill_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskRequest(
                task_id="task-123",
                payload={"amount": 100},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("skill_id",) for error in errors)

    def test_empty_skill_id_fails(self):
        """Test that empty skill_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskRequest(
                task_id="task-123",
                skill_id="",
                payload={"amount": 100},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("skill_id",) for error in errors)

    def test_missing_payload_fails(self):
        """Test that missing payload raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskRequest(
                task_id="task-123",
                skill_id="convert_currency",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("payload",) for error in errors)

    def test_empty_payload_fails(self):
        """Test that empty payload raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskRequest(
                task_id="task-123",
                skill_id="convert_currency",
                payload={},
            )

        errors = exc_info.value.errors()
        assert any("cannot be empty" in str(error["ctx"]["error"]) for error in errors)

    def test_task_request_serialization(self):
        """Test that A2ATaskRequest can be serialized to dict."""
        request = A2ATaskRequest(
            task_id="task-123",
            skill_id="convert_currency",
            payload={"amount": 100, "from": "USD", "to": "EUR"},
        )

        data = request.model_dump()

        assert data["task_id"] == "task-123"
        assert data["skill_id"] == "convert_currency"
        assert data["payload"] == {"amount": 100, "from": "USD", "to": "EUR"}


class TestA2ATaskResponse:
    """Tests for the A2ATaskResponse model."""

    def test_valid_completed_response(self):
        """Test creating a valid completed task response."""
        response = A2ATaskResponse(
            task_id="task-123",
            status="completed",
            result={
                "converted_amount": 92.0,
                "rate": 0.92,
            },
        )

        assert response.task_id == "task-123"
        assert response.status == "completed"
        assert response.result["converted_amount"] == 92.0
        assert response.result["rate"] == 0.92
        assert response.error is None

    def test_valid_failed_response(self):
        """Test creating a valid failed task response."""
        response = A2ATaskResponse(
            task_id="task-123",
            status="failed",
            error="Currency not supported",
        )

        assert response.task_id == "task-123"
        assert response.status == "failed"
        assert response.error == "Currency not supported"
        assert response.result is None

    def test_valid_submitted_response(self):
        """Test creating a valid submitted task response."""
        response = A2ATaskResponse(
            task_id="task-123",
            status="submitted",
        )

        assert response.task_id == "task-123"
        assert response.status == "submitted"
        assert response.result is None
        assert response.error is None

    def test_valid_working_response(self):
        """Test creating a valid working task response."""
        response = A2ATaskResponse(
            task_id="task-123",
            status="working",
        )

        assert response.task_id == "task-123"
        assert response.status == "working"
        assert response.result is None
        assert response.error is None

    def test_valid_cancelled_response(self):
        """Test creating a valid cancelled task response."""
        response = A2ATaskResponse(
            task_id="task-123",
            status="cancelled",
        )

        assert response.task_id == "task-123"
        assert response.status == "cancelled"
        assert response.result is None
        assert response.error is None

    def test_missing_task_id_fails(self):
        """Test that missing task_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskResponse(
                status="completed",
                result={"amount": 92.0},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("task_id",) for error in errors)

    def test_empty_task_id_fails(self):
        """Test that empty task_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskResponse(
                task_id="",
                status="completed",
                result={"amount": 92.0},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("task_id",) for error in errors)

    def test_missing_status_fails(self):
        """Test that missing status raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskResponse(
                task_id="task-123",
                result={"amount": 92.0},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

    def test_invalid_status_fails(self):
        """Test that invalid status value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskResponse(
                task_id="task-123",
                status="invalid_status",
                result={"amount": 92.0},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

    def test_completed_without_result_fails(self):
        """Test that completed status without result raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskResponse(
                task_id="task-123",
                status="completed",
                result=None,  # Explicitly set to None to trigger validation
            )

        errors = exc_info.value.errors()
        assert any("result is required when status is 'completed'" in str(error["ctx"]["error"]) for error in errors)

    def test_completed_with_empty_result_fails(self):
        """Test that completed status with empty result raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskResponse(
                task_id="task-123",
                status="completed",
                result={},
            )

        errors = exc_info.value.errors()
        assert any("result is required when status is 'completed'" in str(error["ctx"]["error"]) for error in errors)

    def test_failed_with_result_fails(self):
        """Test that failed status with result raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            A2ATaskResponse(
                task_id="task-123",
                status="failed",
                result={"amount": 92.0},
                error="Some error",
            )

        errors = exc_info.value.errors()
        assert any("result should not be present when status is 'failed'" in str(error["ctx"]["error"]) for error in errors)

    def test_task_response_serialization(self):
        """Test that A2ATaskResponse can be serialized to dict."""
        response = A2ATaskResponse(
            task_id="task-123",
            status="completed",
            result={"converted_amount": 92.0},
        )

        data = response.model_dump()

        assert data["task_id"] == "task-123"
        assert data["status"] == "completed"
        assert data["result"] == {"converted_amount": 92.0}
        assert data["error"] is None


class TestRegisterAgentResponse:
    """Tests for the RegisterAgentResponse model."""

    def test_valid_registered_response(self):
        """Test creating a valid registered response."""
        response = RegisterAgentResponse(
            status="registered",
            agent_name="currency-agent",
            message="Agent successfully registered",
        )

        assert response.status == "registered"
        assert response.agent_name == "currency-agent"
        assert response.message == "Agent successfully registered"

    def test_valid_updated_response(self):
        """Test creating a valid updated response."""
        response = RegisterAgentResponse(
            status="updated",
            agent_name="currency-agent",
            message="Agent successfully updated",
        )

        assert response.status == "updated"
        assert response.agent_name == "currency-agent"
        assert response.message == "Agent successfully updated"

    def test_valid_failed_response(self):
        """Test creating a valid failed response."""
        response = RegisterAgentResponse(
            status="failed",
            agent_name="currency-agent",
            message="Agent registration failed",
        )

        assert response.status == "failed"
        assert response.agent_name == "currency-agent"
        assert response.message == "Agent registration failed"

    def test_response_without_message(self):
        """Test creating a response without optional message."""
        response = RegisterAgentResponse(
            status="registered",
            agent_name="currency-agent",
        )

        assert response.status == "registered"
        assert response.agent_name == "currency-agent"
        assert response.message is None

    def test_missing_status_fails(self):
        """Test that missing status raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterAgentResponse(
                agent_name="currency-agent",
                message="Agent registered",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

    def test_invalid_status_fails(self):
        """Test that invalid status value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterAgentResponse(
                status="invalid_status",
                agent_name="currency-agent",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

    def test_missing_agent_name_fails(self):
        """Test that missing agent_name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterAgentResponse(
                status="registered",
                message="Agent registered",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("agent_name",) for error in errors)

    def test_empty_agent_name_fails(self):
        """Test that empty agent_name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterAgentResponse(
                status="registered",
                agent_name="",
                message="Agent registered",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("agent_name",) for error in errors)

    def test_response_serialization(self):
        """Test that RegisterAgentResponse can be serialized to dict."""
        response = RegisterAgentResponse(
            status="registered",
            agent_name="currency-agent",
            message="Agent successfully registered",
        )

        data = response.model_dump()

        assert data["status"] == "registered"
        assert data["agent_name"] == "currency-agent"
        assert data["message"] == "Agent successfully registered"
