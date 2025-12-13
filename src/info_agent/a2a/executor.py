"""
Base A2A Agent Executor implementation.

Provides the foundation for creating A2A-compatible agent workers.
"""

from abc import ABC, abstractmethod
from typing import Any

import structlog

from info_agent.a2a.models import (
    AgentCard,
    AgentSkill,
    Artifact,
    MessagePart,
    Task,
    TaskRequest,
    TaskState,
)
from info_agent.utils.exceptions import A2AError
from info_agent.utils.helpers import get_current_timestamp

logger = structlog.get_logger(__name__)


class EventQueue:
    """
    Queue for sending events from agent executor.

    Provides methods to send artifacts, status updates, and errors
    during task execution.
    """

    def __init__(self, task: Task) -> None:
        """
        Initialize event queue for a task.

        Args:
            task: Task being executed.
        """
        self._task = task
        self._events: list[dict[str, Any]] = []

        logger.debug("event_queue_initialized", task_id=task.id)

    @property
    def task(self) -> Task:
        """Get the associated task."""
        return self._task

    @property
    def events(self) -> list[dict[str, Any]]:
        """Get all queued events."""
        return self._events.copy()

    async def send_artifact(self, artifact: Artifact) -> None:
        """
        Send an artifact as task output.

        Args:
            artifact: Artifact to send.
        """
        self._task.add_artifact(artifact)
        self._events.append({
            "type": "artifact",
            "artifact_id": artifact.id,
            "timestamp": get_current_timestamp(),
        })

        logger.debug(
            "artifact_sent",
            task_id=self._task.id,
            artifact_id=artifact.id,
        )

    async def send_text(self, text: str) -> None:
        """
        Send a text message as artifact.

        Args:
            text: Text content to send.
        """
        artifact = Artifact(
            parts=[MessagePart(type="text", text=text)]
        )
        await self.send_artifact(artifact)

    async def send_data(self, data: dict[str, Any]) -> None:
        """
        Send structured data as artifact.

        Args:
            data: Data to send.
        """
        artifact = Artifact(
            parts=[MessagePart(type="data", data=data)]
        )
        await self.send_artifact(artifact)

    async def send_status(self, message: str) -> None:
        """
        Send a status update event.

        Args:
            message: Status message.
        """
        self._events.append({
            "type": "status",
            "message": message,
            "timestamp": get_current_timestamp(),
        })

        logger.debug(
            "status_sent",
            task_id=self._task.id,
            message=message[:50],
        )

    async def send_error(self, error: str) -> None:
        """
        Send an error and mark task as failed.

        Args:
            error: Error message.
        """
        self._task.set_error(error)
        self._events.append({
            "type": "error",
            "error": error,
            "timestamp": get_current_timestamp(),
        })

        logger.error(
            "error_sent",
            task_id=self._task.id,
            error=error,
        )

    async def request_input(self, prompt: str, fields: list[dict[str, Any]]) -> None:
        """
        Request additional input from the user.

        Args:
            prompt: Prompt explaining what input is needed.
            fields: List of field definitions for required input.
        """
        self._task.transition_to(TaskState.INPUT_REQUIRED)
        self._task.metadata["input_request"] = {
            "prompt": prompt,
            "fields": fields,
        }
        self._events.append({
            "type": "input_request",
            "prompt": prompt,
            "fields": fields,
            "timestamp": get_current_timestamp(),
        })

        logger.info(
            "input_requested",
            task_id=self._task.id,
            prompt=prompt[:50],
        )


class RequestContext:
    """
    Context for an agent request.

    Provides access to the task, skill, and execution context.
    """

    def __init__(
        self,
        task: Task,
        skill: AgentSkill | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize request context.

        Args:
            task: Task being executed.
            skill: Skill being invoked.
            metadata: Additional context metadata.
        """
        self._task = task
        self._skill = skill
        self._metadata = metadata or {}

    @property
    def task(self) -> Task:
        """Get the task."""
        return self._task

    @property
    def skill(self) -> AgentSkill | None:
        """Get the skill being invoked."""
        return self._skill

    @property
    def input(self) -> dict[str, Any]:
        """Get task input parameters."""
        return self._task.input

    @property
    def metadata(self) -> dict[str, Any]:
        """Get context metadata."""
        return self._metadata

    def get_input(self, key: str, default: Any = None) -> Any:
        """
        Get an input parameter by key.

        Args:
            key: Parameter key.
            default: Default value if not found.

        Returns:
            Parameter value or default.
        """
        return self._task.input.get(key, default)


class BaseAgentExecutor(ABC):
    """
    Abstract base class for A2A agent executors.

    Subclasses implement execute() to handle task execution.
    """

    def __init__(self, agent_card: AgentCard) -> None:
        """
        Initialize agent executor.

        Args:
            agent_card: Card describing this agent.
        """
        self._agent_card = agent_card
        logger.info(
            "agent_executor_initialized",
            agent_id=agent_card.id,
            agent_name=agent_card.name,
        )

    @property
    def agent_card(self) -> AgentCard:
        """Get the agent card."""
        return self._agent_card

    def get_skill(self, skill_id: str) -> AgentSkill | None:
        """
        Get a skill by ID.

        Args:
            skill_id: Skill identifier.

        Returns:
            AgentSkill if found, None otherwise.
        """
        return self._agent_card.get_skill(skill_id)

    def has_skill(self, skill_id: str) -> bool:
        """
        Check if agent has a skill.

        Args:
            skill_id: Skill identifier.

        Returns:
            True if skill exists.
        """
        return self._agent_card.has_skill(skill_id)

    async def handle_task(self, request: TaskRequest) -> Task:
        """
        Handle an incoming task request.

        Args:
            request: Task request to handle.

        Returns:
            Completed or in-progress task.

        Raises:
            A2AError: If task handling fails.
        """
        # Create task from request
        task = request.to_task()

        logger.info(
            "handling_task",
            task_id=task.id,
            skill_id=task.skill_id,
        )

        # Validate skill exists
        skill = self.get_skill(task.skill_id)
        if not skill:
            task.set_error(f"Unknown skill: {task.skill_id}")
            logger.error("unknown_skill", task_id=task.id, skill_id=task.skill_id)
            return task

        # Create context and event queue
        context = RequestContext(task=task, skill=skill)
        event_queue = EventQueue(task)

        # Transition to working state
        task.transition_to(TaskState.WORKING)

        try:
            # Execute the task
            await self.execute(context, event_queue)

            # Mark as completed if not already in a terminal state
            if task.state == TaskState.WORKING:
                task.transition_to(TaskState.COMPLETED)

            logger.info(
                "task_completed",
                task_id=task.id,
                state=task.state.value,
            )

        except Exception as e:
            task.set_error(str(e))
            logger.error(
                "task_execution_failed",
                task_id=task.id,
                error=str(e),
            )

        return task

    @abstractmethod
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute a task.

        Subclasses must implement this method to handle task execution.

        Args:
            context: Request context with task and skill info.
            event_queue: Queue for sending events and artifacts.
        """
        pass

    async def on_cancel(self, task: Task) -> Task:
        """
        Handle task cancellation.

        Override to implement custom cancellation logic.

        Args:
            task: Task being cancelled.

        Returns:
            Cancelled task.
        """
        task.transition_to(TaskState.CANCELLED)
        logger.info("task_cancelled", task_id=task.id)
        return task

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check.

        Override to add custom health checks.

        Returns:
            Health status dictionary.
        """
        return {
            "status": "healthy",
            "agent_id": self._agent_card.id,
            "agent_name": self._agent_card.name,
            "skills": [s.id for s in self._agent_card.skills],
            "timestamp": get_current_timestamp(),
        }
