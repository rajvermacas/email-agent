"""
A2A Protocol data models.

Defines the core data structures for A2A agent communication.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from info_agent.utils.helpers import generate_uuid, get_current_timestamp


class TaskState(str, Enum):
    """
    State of an A2A task.

    States follow the A2A protocol task lifecycle:
    submitted -> working -> input_required/completed/failed/cancelled
    """

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCapability(str, Enum):
    """Standard A2A agent capabilities."""

    STREAMING = "streaming"
    PUSH_NOTIFICATIONS = "push_notifications"
    STATE_MANAGEMENT = "state_management"


class SkillInputSchema(BaseModel):
    """
    JSON Schema for skill input parameters.

    Attributes:
        type: Schema type (usually "object").
        properties: Dictionary of property definitions.
        required: List of required property names.
    """

    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class SkillOutputSchema(BaseModel):
    """
    JSON Schema for skill output.

    Attributes:
        type: Schema type.
        properties: Dictionary of property definitions.
    """

    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)


class AgentSkill(BaseModel):
    """
    An agent skill/capability definition.

    Skills define what operations an agent can perform.

    Attributes:
        id: Unique identifier for the skill.
        name: Human-readable name.
        description: Detailed description of what the skill does.
        input_schema: JSON schema for input parameters.
        output_schema: JSON schema for output.
        tags: List of tags for categorization.
    """

    id: str
    name: str
    description: str
    input_schema: SkillInputSchema | None = None
    output_schema: SkillOutputSchema | None = None
    tags: list[str] = Field(default_factory=list)


class AgentCard(BaseModel):
    """
    Agent Card - describes an agent's identity and capabilities.

    The agent card is the primary discovery mechanism in A2A.
    It's typically served at /.well-known/agent.json.

    Attributes:
        id: Unique agent identifier.
        name: Human-readable agent name.
        description: What the agent does.
        endpoint: URL for A2A communication.
        protocol_version: A2A protocol version supported.
        skills: List of skills the agent provides.
        capabilities: List of supported capabilities.
        authentication: Authentication configuration.
        metadata: Additional agent metadata.
        created_at: When the agent was registered.
        updated_at: When the agent was last updated.
        status: Agent operational status.
    """

    id: str = Field(default_factory=generate_uuid)
    name: str
    description: str
    endpoint: str
    protocol_version: str = "1.0"
    skills: list[AgentSkill] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    authentication: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=get_current_timestamp)
    updated_at: str = Field(default_factory=get_current_timestamp)
    status: str = "active"

    def has_skill(self, skill_id: str) -> bool:
        """
        Check if agent has a specific skill.

        Args:
            skill_id: Skill identifier to check.

        Returns:
            True if agent has the skill.
        """
        return any(skill.id == skill_id for skill in self.skills)

    def get_skill(self, skill_id: str) -> AgentSkill | None:
        """
        Get a specific skill by ID.

        Args:
            skill_id: Skill identifier.

        Returns:
            AgentSkill if found, None otherwise.
        """
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None

    def has_capability(self, capability: str) -> bool:
        """
        Check if agent has a specific capability.

        Args:
            capability: Capability to check.

        Returns:
            True if agent has the capability.
        """
        return capability in self.capabilities


class MessagePart(BaseModel):
    """
    A part of an A2A message.

    Messages can contain multiple parts of different types.

    Attributes:
        type: Part type (text, data, file).
        text: Text content (for text type).
        data: Structured data (for data type).
        file: File reference (for file type).
        metadata: Additional part metadata.
    """

    type: str = "text"
    text: str | None = None
    data: dict[str, Any] | None = None
    file: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    """
    An artifact produced by a task.

    Artifacts contain the results of task execution.

    Attributes:
        id: Unique artifact identifier.
        parts: List of message parts in the artifact.
        created_at: When the artifact was created.
    """

    id: str = Field(default_factory=generate_uuid)
    parts: list[MessagePart] = Field(default_factory=list)
    created_at: str = Field(default_factory=get_current_timestamp)

    @property
    def type(self) -> str:
        """Get the type of the first part."""
        if self.parts:
            return "application/json" if self.parts[0].data else "text/plain"
        return "text/plain"

    @property
    def data(self) -> dict[str, Any] | None:
        """Get data from the first part (convenience accessor)."""
        if self.parts and self.parts[0].data:
            return self.parts[0].data
        return None

    @property
    def text(self) -> str | None:
        """Get text from the first part (convenience accessor)."""
        if self.parts and self.parts[0].text:
            return self.parts[0].text
        return None


class Task(BaseModel):
    """
    An A2A task request.

    Tasks represent units of work sent to agents.

    Attributes:
        id: Unique task identifier.
        skill_id: ID of the skill to invoke.
        input: Input parameters for the skill.
        state: Current task state.
        artifacts: Produced artifacts.
        error: Error message if failed.
        created_at: When the task was created.
        updated_at: When the task was last updated.
        metadata: Additional task metadata.
    """

    id: str = Field(default_factory=generate_uuid)
    skill_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    state: TaskState = TaskState.SUBMITTED
    artifacts: list[Artifact] = Field(default_factory=list)
    error: str | None = None
    created_at: str = Field(default_factory=get_current_timestamp)
    updated_at: str = Field(default_factory=get_current_timestamp)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def transition_to(self, new_state: TaskState) -> None:
        """
        Transition task to a new state.

        Args:
            new_state: Target state.
        """
        self.state = new_state
        self.updated_at = get_current_timestamp()

    def add_artifact(self, artifact: Artifact) -> None:
        """
        Add an artifact to the task.

        Args:
            artifact: Artifact to add.
        """
        self.artifacts.append(artifact)
        self.updated_at = get_current_timestamp()

    def set_error(self, error: str) -> None:
        """
        Set task error and transition to failed state.

        Args:
            error: Error message.
        """
        self.error = error
        self.transition_to(TaskState.FAILED)


class TaskRequest(BaseModel):
    """
    Request to create a new task.

    Attributes:
        skill_id: ID of the skill to invoke.
        input: Input parameters.
        metadata: Additional request metadata.
    """

    skill_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_task(self) -> Task:
        """
        Convert request to a Task.

        Returns:
            New Task instance.
        """
        return Task(
            skill_id=self.skill_id,
            input=self.input,
            metadata=self.metadata,
        )


class TaskResponse(BaseModel):
    """
    Response containing task information.

    Attributes:
        task_id: ID of the task.
        state: Current task state.
        artifacts: Task artifacts.
        error: Error message if any.
    """

    task_id: str
    state: TaskState
    artifacts: list[Artifact] = Field(default_factory=list)
    error: str | None = None


class AgentEvent(BaseModel):
    """
    Event from an agent during task execution.

    Attributes:
        id: Event identifier.
        type: Event type.
        task_id: Associated task ID.
        data: Event data.
        timestamp: When the event occurred.
    """

    id: str = Field(default_factory=generate_uuid)
    type: str
    task_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=get_current_timestamp)
