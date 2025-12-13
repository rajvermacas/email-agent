"""
Pydantic models for A2A (Agent-to-Agent) protocol.

This module defines the data models used in the A2A protocol for agent
communication, task management, and capability discovery.

All models use Pydantic v2 for validation and serialization.
No fallback/default values are used for required fields.

Usage:
    from info_agent.a2a.models import AgentCard, AgentSkill

    skill = AgentSkill(
        id="convert_currency",
        name="Convert Currency",
        description="Converts between currencies",
        input_schema={
            "type": "object",
            "properties": {"amount": {"type": "number"}}
        }
    )

    card = AgentCard(
        name="currency-agent",
        description="Currency conversion agent",
        version="1.0",
        url="http://localhost:8001/a2a",
        capabilities={},
        skills=[skill],
        defaultInputModes=["text"],
        defaultOutputModes=["text"]
    )
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class AgentSkill(BaseModel):
    """
    Represents a skill that an agent can perform.

    A skill defines a specific capability with its input requirements
    and optional example prompts.

    Attributes:
        id: Unique identifier for the skill (required).
        name: Human-readable name of the skill (required).
        description: Detailed description of what the skill does (required).
        input_schema: JSON schema defining the input structure (required).
        example_prompts: List of example user prompts (optional).
    """

    id: str = Field(
        ...,
        description="Unique identifier for the skill",
        min_length=1,
    )
    name: str = Field(
        ...,
        description="Human-readable name of the skill",
        min_length=1,
    )
    description: str = Field(
        ...,
        description="Detailed description of what the skill does",
        min_length=1,
    )
    input_schema: dict[str, Any] = Field(
        ...,
        description="JSON schema defining the input structure",
    )
    example_prompts: list[str] | None = Field(
        default=None,
        description="List of example user prompts",
    )

    @field_validator("input_schema")
    @classmethod
    def validate_input_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that input_schema is a non-empty dictionary."""
        logger.debug("Validating input_schema", schema_keys=list(v.keys()))
        if not v:
            raise ValueError("input_schema cannot be empty")
        if "type" not in v:
            raise ValueError("input_schema must contain 'type' field")
        logger.debug("input_schema validation passed")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "convert_currency",
                "name": "Convert Currency",
                "description": "Converts amount from one currency to another",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number"},
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                    },
                    "required": ["amount", "from", "to"],
                },
                "example_prompts": [
                    "Convert 100 USD to EUR",
                    "What is 50 pounds in dollars?",
                ],
            }
        }
    }


class AgentCard(BaseModel):
    """
    Agent Card describes an agent's identity and capabilities.

    This is the primary way agents advertise their capabilities to other agents.
    It follows the A2A protocol specification.

    Attributes:
        name: Unique name of the agent (required).
        description: Human-readable description of the agent (required).
        version: Agent version string (required).
        url: Base URL where the agent can be reached (required).
        capabilities: Dictionary of agent capabilities (required).
        skills: List of skills the agent provides (required).
        defaultInputModes: Default input modes supported (required).
        defaultOutputModes: Default output modes supported (required).
        created_at: Timestamp when agent was registered (auto-set).
    """

    name: str = Field(
        ...,
        description="Unique name of the agent",
        min_length=1,
    )
    description: str = Field(
        ...,
        description="Human-readable description of the agent",
        min_length=1,
    )
    version: str = Field(
        ...,
        description="Agent version string",
        min_length=1,
    )
    url: str = Field(
        ...,
        description="Base URL where the agent can be reached",
        min_length=1,
    )
    capabilities: dict[str, Any] = Field(
        ...,
        description="Dictionary of agent capabilities",
    )
    skills: list[AgentSkill] = Field(
        ...,
        description="List of skills the agent provides",
        min_length=1,
    )
    defaultInputModes: list[str] = Field(
        ...,
        description="Default input modes supported",
        min_length=1,
    )
    defaultOutputModes: list[str] = Field(
        ...,
        description="Default output modes supported",
        min_length=1,
    )
    created_at: datetime | None = Field(
        default=None,
        description="Timestamp when agent was registered",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URL is properly formatted."""
        logger.debug("Validating agent URL", url=v)
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        logger.debug("Agent URL validation passed")
        return v

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: list[AgentSkill]) -> list[AgentSkill]:
        """Validate that skills list is not empty and has unique IDs."""
        logger.debug("Validating skills list", skill_count=len(v))
        if not v:
            raise ValueError("Agent must have at least one skill")

        skill_ids = [skill.id for skill in v]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Skill IDs must be unique")

        logger.debug("Skills validation passed", skill_ids=skill_ids)
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "currency-agent",
                "description": "Currency conversion agent",
                "version": "1.0.0",
                "url": "http://localhost:8001/a2a",
                "capabilities": {"async": True, "streaming": False},
                "skills": [
                    {
                        "id": "convert",
                        "name": "Convert Currency",
                        "description": "Convert between currencies",
                        "input_schema": {
                            "type": "object",
                            "properties": {"amount": {"type": "number"}},
                        },
                    }
                ],
                "defaultInputModes": ["text", "data"],
                "defaultOutputModes": ["text", "data"],
            }
        }
    }


class A2ATaskRequest(BaseModel):
    """
    Request to execute a task on an agent.

    This represents a task request sent to an agent to execute
    one of its advertised skills.

    Attributes:
        task_id: Unique identifier for the task (required).
        skill_id: ID of the skill to execute (required).
        payload: Input data for the task (required).
    """

    task_id: str = Field(
        ...,
        description="Unique identifier for the task",
        min_length=1,
    )
    skill_id: str = Field(
        ...,
        description="ID of the skill to execute",
        min_length=1,
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Input data for the task",
    )

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that payload is not empty."""
        logger.debug("Validating task payload", payload_keys=list(v.keys()))
        if not v:
            raise ValueError("payload cannot be empty")
        logger.debug("Payload validation passed")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-123",
                "skill_id": "convert_currency",
                "payload": {
                    "amount": 100,
                    "from": "USD",
                    "to": "EUR",
                },
            }
        }
    }


class A2ATaskResponse(BaseModel):
    """
    Response from a task execution.

    This represents the result of executing a task on an agent.

    Attributes:
        task_id: Unique identifier for the task (required).
        status: Current status of the task (required).
        result: Output data from the task (required if status is completed).
        error: Error message if task failed (optional).
    """

    task_id: str = Field(
        ...,
        description="Unique identifier for the task",
        min_length=1,
    )
    status: Literal["submitted", "working", "completed", "failed", "cancelled"] = Field(
        ...,
        description="Current status of the task",
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="Output data from the task",
    )
    error: str | None = Field(
        default=None,
        description="Error message if task failed",
    )

    @field_validator("result")
    @classmethod
    def validate_result(cls, v: dict[str, Any] | None, info: Any) -> dict[str, Any] | None:
        """Validate that result is present when status is completed."""
        status = info.data.get("status")
        logger.debug("Validating task result", status=status, has_result=v is not None)

        if status == "completed" and not v:
            raise ValueError("result is required when status is 'completed'")

        if status == "failed" and v:
            raise ValueError("result should not be present when status is 'failed'")

        logger.debug("Result validation passed")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-123",
                "status": "completed",
                "result": {
                    "converted_amount": 92.0,
                    "rate": 0.92,
                },
            }
        }
    }


class RegisterAgentResponse(BaseModel):
    """
    Response from registering an agent.

    Attributes:
        status: Status of the registration (required).
        agent_name: Name of the registered agent (required).
        message: Additional information about the registration (optional).
    """

    status: Literal["registered", "updated", "failed"] = Field(
        ...,
        description="Status of the registration",
    )
    agent_name: str = Field(
        ...,
        description="Name of the registered agent",
        min_length=1,
    )
    message: str | None = Field(
        default=None,
        description="Additional information about the registration",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "registered",
                "agent_name": "currency-agent",
                "message": "Agent successfully registered",
            }
        }
    }
