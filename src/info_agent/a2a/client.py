"""
A2A Client implementation.

Provides HTTP client for communicating with A2A agents.
"""

import asyncio
from typing import Any, AsyncIterator

import httpx
import structlog

from info_agent.a2a.models import (
    AgentCard,
    Artifact,
    Task,
    TaskRequest,
    TaskResponse,
    TaskState,
)
from info_agent.utils.exceptions import A2AError
from info_agent.utils.helpers import safe_json_loads

logger = structlog.get_logger(__name__)


class A2AClient:
    """
    HTTP client for A2A agent communication.

    Provides methods to discover agents, submit tasks,
    and retrieve results.

    Attributes:
        _base_timeout: Default request timeout in seconds.
        _max_retries: Maximum number of retries for failed requests.
    """

    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        """
        Initialize A2A client.

        Args:
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts.
        """
        self._timeout = timeout
        self._max_retries = max_retries

        logger.info(
            "a2a_client_initialized",
            timeout=timeout,
            max_retries=max_retries,
        )

    async def discover_agent(self, base_url: str) -> AgentCard:
        """
        Discover an agent by fetching its agent card.

        Args:
            base_url: Base URL of the agent.

        Returns:
            AgentCard describing the agent.

        Raises:
            A2AError: If discovery fails.
        """
        # Try standard well-known path first
        card_url = f"{base_url.rstrip('/')}/.well-known/agent.json"

        logger.debug("discovering_agent", url=card_url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    card_url,
                    timeout=self._timeout,
                )

                if response.status_code == 404:
                    # Try alternative path
                    card_url = f"{base_url.rstrip('/')}/agent.json"
                    response = await client.get(
                        card_url,
                        timeout=self._timeout,
                    )

                if response.status_code != 200:
                    raise A2AError(
                        message=f"Agent discovery failed with status {response.status_code}",
                        details={
                            "url": card_url,
                            "status_code": response.status_code,
                        },
                    )

                card_data = response.json()
                agent_card = AgentCard(**card_data)

                logger.info(
                    "agent_discovered",
                    agent_id=agent_card.id,
                    agent_name=agent_card.name,
                    skills_count=len(agent_card.skills),
                )

                return agent_card

        except httpx.TimeoutException as e:
            logger.error("agent_discovery_timeout", url=card_url)
            raise A2AError(
                message="Agent discovery timed out",
                details={"url": card_url},
            ) from e

        except Exception as e:
            logger.error("agent_discovery_failed", url=card_url, error=str(e))
            raise A2AError(
                message=f"Agent discovery failed: {e}",
                details={"url": card_url, "error": str(e)},
            ) from e

    async def submit_task(
        self,
        agent_endpoint: str,
        request: TaskRequest,
    ) -> Task:
        """
        Submit a task to an agent.

        Args:
            agent_endpoint: Agent's A2A endpoint URL.
            request: Task request to submit.

        Returns:
            Created task.

        Raises:
            A2AError: If task submission fails.
        """
        task_url = f"{agent_endpoint.rstrip('/')}/tasks"

        logger.info(
            "submitting_task",
            endpoint=task_url,
            skill_id=request.skill_id,
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    task_url,
                    json=request.model_dump(),
                    timeout=self._timeout,
                )

                if response.status_code not in [200, 201, 202]:
                    error_detail = response.text[:500] if response.text else "No details"
                    raise A2AError(
                        message=f"Task submission failed with status {response.status_code}",
                        details={
                            "endpoint": task_url,
                            "status_code": response.status_code,
                            "error": error_detail,
                        },
                    )

                task_data = response.json()
                task = Task(**task_data)

                logger.info(
                    "task_submitted",
                    task_id=task.id,
                    state=task.state.value,
                )

                return task

        except httpx.TimeoutException as e:
            logger.error("task_submission_timeout", endpoint=task_url)
            raise A2AError(
                message="Task submission timed out",
                details={"endpoint": task_url},
            ) from e

        except A2AError:
            raise

        except Exception as e:
            logger.error("task_submission_failed", endpoint=task_url, error=str(e))
            raise A2AError(
                message=f"Task submission failed: {e}",
                details={"endpoint": task_url, "error": str(e)},
            ) from e

    async def get_task(
        self,
        agent_endpoint: str,
        task_id: str,
    ) -> Task:
        """
        Get task status and results.

        Args:
            agent_endpoint: Agent's A2A endpoint URL.
            task_id: ID of the task.

        Returns:
            Task with current state and results.

        Raises:
            A2AError: If retrieval fails.
        """
        task_url = f"{agent_endpoint.rstrip('/')}/tasks/{task_id}"

        logger.debug("getting_task", endpoint=task_url, task_id=task_id)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    task_url,
                    timeout=self._timeout,
                )

                if response.status_code == 404:
                    raise A2AError(
                        message=f"Task not found: {task_id}",
                        details={"task_id": task_id, "endpoint": task_url},
                    )

                if response.status_code != 200:
                    raise A2AError(
                        message=f"Failed to get task with status {response.status_code}",
                        details={
                            "task_id": task_id,
                            "status_code": response.status_code,
                        },
                    )

                task_data = response.json()
                task = Task(**task_data)

                logger.debug(
                    "task_retrieved",
                    task_id=task.id,
                    state=task.state.value,
                )

                return task

        except A2AError:
            raise

        except Exception as e:
            logger.error("get_task_failed", task_id=task_id, error=str(e))
            raise A2AError(
                message=f"Failed to get task: {e}",
                details={"task_id": task_id, "error": str(e)},
            ) from e

    async def cancel_task(
        self,
        agent_endpoint: str,
        task_id: str,
    ) -> Task:
        """
        Cancel a running task.

        Args:
            agent_endpoint: Agent's A2A endpoint URL.
            task_id: ID of the task to cancel.

        Returns:
            Cancelled task.

        Raises:
            A2AError: If cancellation fails.
        """
        task_url = f"{agent_endpoint.rstrip('/')}/tasks/{task_id}/cancel"

        logger.info("cancelling_task", task_id=task_id)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    task_url,
                    timeout=self._timeout,
                )

                if response.status_code not in [200, 202]:
                    raise A2AError(
                        message=f"Task cancellation failed with status {response.status_code}",
                        details={
                            "task_id": task_id,
                            "status_code": response.status_code,
                        },
                    )

                task_data = response.json()
                task = Task(**task_data)

                logger.info(
                    "task_cancelled",
                    task_id=task.id,
                    state=task.state.value,
                )

                return task

        except A2AError:
            raise

        except Exception as e:
            logger.error("cancel_task_failed", task_id=task_id, error=str(e))
            raise A2AError(
                message=f"Failed to cancel task: {e}",
                details={"task_id": task_id, "error": str(e)},
            ) from e

    async def wait_for_completion(
        self,
        agent_endpoint: str,
        task_id: str,
        poll_interval: float = 1.0,
        max_wait: float = 300.0,
    ) -> Task:
        """
        Wait for a task to complete by polling.

        Args:
            agent_endpoint: Agent's A2A endpoint URL.
            task_id: ID of the task.
            poll_interval: Seconds between polls.
            max_wait: Maximum wait time in seconds.

        Returns:
            Completed task.

        Raises:
            A2AError: If task fails, times out, or retrieval fails.
        """
        logger.info(
            "waiting_for_task",
            task_id=task_id,
            max_wait=max_wait,
        )

        elapsed = 0.0
        terminal_states = {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }

        while elapsed < max_wait:
            task = await self.get_task(agent_endpoint, task_id)

            if task.state in terminal_states:
                logger.info(
                    "task_finished",
                    task_id=task_id,
                    state=task.state.value,
                    elapsed=elapsed,
                )
                return task

            if task.state == TaskState.INPUT_REQUIRED:
                logger.warning(
                    "task_requires_input",
                    task_id=task_id,
                )
                return task

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise A2AError(
            message=f"Task timed out after {max_wait} seconds",
            details={"task_id": task_id, "elapsed": elapsed},
        )

    async def execute_skill(
        self,
        agent_endpoint: str,
        skill_id: str,
        input_data: dict[str, Any],
        wait: bool = True,
        poll_interval: float = 1.0,
        max_wait: float = 300.0,
    ) -> Task:
        """
        Execute a skill on an agent and optionally wait for completion.

        This is a convenience method that combines task submission
        and waiting for results.

        Args:
            agent_endpoint: Agent's A2A endpoint URL.
            skill_id: Skill to execute.
            input_data: Input parameters for the skill.
            wait: Whether to wait for completion.
            poll_interval: Seconds between polls when waiting.
            max_wait: Maximum wait time when waiting.

        Returns:
            Task with results.

        Raises:
            A2AError: If execution fails.
        """
        request = TaskRequest(skill_id=skill_id, input=input_data)
        task = await self.submit_task(agent_endpoint, request)

        if wait:
            task = await self.wait_for_completion(
                agent_endpoint,
                task.id,
                poll_interval=poll_interval,
                max_wait=max_wait,
            )

        return task

    async def health_check(self, agent_endpoint: str) -> bool:
        """
        Check if an agent is healthy.

        Args:
            agent_endpoint: Agent's endpoint URL.

        Returns:
            True if agent is healthy.
        """
        health_url = f"{agent_endpoint.rstrip('/')}/health"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    health_url,
                    timeout=5.0,
                )
                return response.status_code == 200

        except Exception:
            return False

    def health_check_sync(self, agent_endpoint: str) -> bool:
        """
        Synchronous wrapper for health check.

        Args:
            agent_endpoint: Agent's endpoint URL.

        Returns:
            True if agent is healthy.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.health_check(agent_endpoint))
