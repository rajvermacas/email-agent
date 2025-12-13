"""
Task delegation for the Supervisor Agent.

This module provides the A2A protocol client for invoking worker agents
and delegating tasks from the Supervisor.
"""

import logging
from typing import Any

from info_agent.a2a.client import A2AClient
from info_agent.a2a.models import Artifact, MessagePart, Task, TaskState

logger = logging.getLogger(__name__)


class TaskDelegator:
    """
    A2A protocol client for delegating tasks to worker agents.

    The TaskDelegator handles communication with worker agents
    using the A2A protocol.
    """

    def __init__(
        self,
        a2a_client: A2AClient | None = None,
    ) -> None:
        """
        Initialize the task delegator.

        Args:
            a2a_client: Optional pre-configured A2A client.
                If not provided, creates a new client.
        """
        logger.info("Initializing TaskDelegator")

        if a2a_client is not None:
            self._client = a2a_client
        else:
            self._client = A2AClient()

        logger.info("TaskDelegator initialized")

    async def delegate_task(
        self,
        agent_endpoint: str,
        skill_id: str,
        parameters: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Task:
        """
        Delegate a task to a worker agent.

        Args:
            agent_endpoint: The agent's A2A endpoint URL.
            skill_id: The skill ID to invoke.
            parameters: Parameters for the skill.
            context: Optional context for the task.

        Returns:
            The Task object with result.

        Raises:
            A2AError: If the task fails.
        """
        logger.info(
            "Delegating task to %s, skill=%s",
            agent_endpoint,
            skill_id,
        )

        task = await self._client.send_task(
            endpoint=agent_endpoint,
            skill_id=skill_id,
            parameters=parameters,
            context=context,
        )

        logger.info(
            "Task delegated: task_id=%s, state=%s",
            task.id,
            task.state,
        )

        return task

    async def delegate_task_streaming(
        self,
        agent_endpoint: str,
        skill_id: str,
        parameters: dict[str, Any],
        context: dict[str, Any] | None = None,
    ):
        """
        Delegate a task to a worker agent with streaming.

        Args:
            agent_endpoint: The agent's A2A endpoint URL.
            skill_id: The skill ID to invoke.
            parameters: Parameters for the skill.
            context: Optional context for the task.

        Yields:
            Task updates as they occur.

        Raises:
            A2AError: If the task fails.
        """
        logger.info(
            "Delegating streaming task to %s, skill=%s",
            agent_endpoint,
            skill_id,
        )

        async for update in self._client.stream_task(
            endpoint=agent_endpoint,
            skill_id=skill_id,
            parameters=parameters,
            context=context,
        ):
            logger.debug("Task update: %s", update)
            yield update

    async def get_task_status(
        self,
        agent_endpoint: str,
        task_id: str,
    ) -> Task:
        """
        Get the status of a delegated task.

        Args:
            agent_endpoint: The agent's A2A endpoint URL.
            task_id: The task ID to check.

        Returns:
            The Task object with current state.

        Raises:
            A2AError: If the request fails.
        """
        logger.debug("Getting task status: task_id=%s", task_id)

        task = await self._client.get_task(
            endpoint=agent_endpoint,
            task_id=task_id,
        )

        logger.debug("Task status: %s", task.state)
        return task

    async def cancel_task(
        self,
        agent_endpoint: str,
        task_id: str,
    ) -> Task:
        """
        Cancel a delegated task.

        Args:
            agent_endpoint: The agent's A2A endpoint URL.
            task_id: The task ID to cancel.

        Returns:
            The Task object with updated state.

        Raises:
            A2AError: If the cancellation fails.
        """
        logger.info("Cancelling task: task_id=%s", task_id)

        task = await self._client.cancel_task(
            endpoint=agent_endpoint,
            task_id=task_id,
        )

        logger.info("Task cancelled: state=%s", task.state)
        return task

    async def wait_for_completion(
        self,
        agent_endpoint: str,
        task_id: str,
        timeout_seconds: float = 300.0,
        poll_interval: float = 1.0,
    ) -> Task:
        """
        Wait for a task to complete.

        Args:
            agent_endpoint: The agent's A2A endpoint URL.
            task_id: The task ID to wait for.
            timeout_seconds: Maximum wait time in seconds.
            poll_interval: Time between status checks.

        Returns:
            The completed Task object.

        Raises:
            TimeoutError: If task doesn't complete within timeout.
            A2AError: If the task fails.
        """
        import asyncio

        logger.info(
            "Waiting for task completion: task_id=%s, timeout=%ss",
            task_id,
            timeout_seconds,
        )

        elapsed = 0.0

        while elapsed < timeout_seconds:
            task = await self.get_task_status(agent_endpoint, task_id)

            if task.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
                logger.info(
                    "Task finished: task_id=%s, state=%s",
                    task_id,
                    task.state,
                )
                return task

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(
            f"Task {task_id} did not complete within {timeout_seconds}s"
        )


class StubTaskDelegator:
    """
    Stub task delegator for testing without actual A2A communication.

    Returns simulated responses instead of making actual A2A calls.
    """

    def __init__(self) -> None:
        """Initialize the stub delegator."""
        logger.info("Initializing StubTaskDelegator")

    async def delegate_task(
        self,
        agent_endpoint: str,
        skill_id: str,
        parameters: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Task:
        """
        Simulate delegating a task.

        Args:
            agent_endpoint: The agent's A2A endpoint URL.
            skill_id: The skill ID to invoke.
            parameters: Parameters for the skill.
            context: Optional context for the task.

        Returns:
            A simulated Task object.
        """
        import uuid

        logger.info(
            "Stub: Delegating task to %s, skill=%s",
            agent_endpoint,
            skill_id,
        )

        # Create a stub successful task
        result_data = self._generate_stub_result(skill_id, parameters)
        artifact = Artifact(
            parts=[MessagePart(type="data", data=result_data)]
        )

        task = Task(
            id=str(uuid.uuid4()),
            state=TaskState.COMPLETED,
            skill_id=skill_id,
            input=parameters,
            artifacts=[artifact],
        )

        return task

    def _generate_stub_result(
        self,
        skill_id: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate stub result based on skill."""
        if skill_id == "send_email":
            return {
                "success": True,
                "message_id": "stub-message-id",
                "thread_id": "stub-thread-id",
            }
        elif skill_id == "validate_document":
            return {
                "passed": True,
                "score": 1.0,
                "issues": [],
                "recommendations": [],
            }
        elif skill_id == "execute_python":
            return {
                "success": True,
                "output": "Stub execution output",
                "exit_code": 0,
            }
        else:
            return {
                "success": True,
            }
