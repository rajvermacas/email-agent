"""
SDK Client Wrapper for simplified A2A task invocation.

This module provides a wrapper around the official a2a-sdk client
to simplify task invocation with a pattern similar to the old custom client,
while maintaining full SDK compliance.

The SDK uses an async iterator pattern for streaming support, but many
use cases just need simple request-response. This wrapper handles that.
"""

import uuid
from typing import Any

import httpx

from a2a.client.client_factory import ClientConfig, ClientFactory
from a2a.types import AgentCard, DataPart, Message, Role, Task, TaskStatus

from info_agent.utils.exceptions import A2AError, AgentCommunicationError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class SDKClientWrapper:
    """
    Wrapper around a2a-sdk Client for simplified task invocation.

    This wrapper provides a simpler API for common use cases while
    maintaining full SDK compliance. It handles:
    - Agent card fetching
    - Client creation
    - Message construction
    - Async iterator handling
    - Result extraction

    Attributes:
        registry_url: URL of the A2A registry.
        client_factory: SDK ClientFactory instance.
        httpx_client: Shared HTTP client for requests.
    """

    def __init__(self, registry_url: str | None = None) -> None:
        """
        Initialize SDK client wrapper.

        Args:
            registry_url: Optional A2A registry URL for agent discovery.
        """
        self.registry_url = registry_url
        self.httpx_client = httpx.AsyncClient(timeout=30.0)

        # Create SDK client factory
        config = ClientConfig(
            httpx_client=self.httpx_client,
            supported_transports=["JSONRPC", "HTTP+JSON"],
        )
        self.client_factory = ClientFactory(config)

        logger.debug("SDK Client Wrapper initialized")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.httpx_client.aclose()
        logger.debug("SDK Client Wrapper closed")

    async def get_agent_card(
        self,
        agent_url: str,
        agent_name: str | None = None,
    ) -> AgentCard:
        """
        Fetch agent card from agent's well-known endpoint.

        Args:
            agent_url: Base URL of the agent.
            agent_name: Optional agent name for error reporting.

        Returns:
            AgentCard instance.

        Raises:
            AgentCommunicationError: If fetching agent card fails.
        """
        # Use agent name if provided, otherwise extract from URL or use "unknown"
        _agent_name = agent_name or agent_url.split("/")[-1] or "unknown"
        # SDK uses agent-card.json (with hyphen), not agent.json
        card_url = f"{agent_url}/.well-known/agent-card.json"

        logger.debug(f"Fetching agent card from {card_url}")

        try:
            response = await self.httpx_client.get(card_url)
            response.raise_for_status()

            card_data = response.json()
            agent_card = AgentCard(**card_data)

            logger.info(
                f"Fetched agent card for {agent_card.name}",
                agent_name=agent_card.name,
                skills_count=len(agent_card.skills) if agent_card.skills else 0,
            )

            return agent_card

        except httpx.HTTPError as e:
            logger.error(
                f"Failed to fetch agent card from {card_url}",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentCommunicationError(
                message=f"Failed to fetch agent card: {str(e)}",
                agent_name=_agent_name,
                endpoint=card_url,
                details={"error": str(e)},
            ) from e

        except Exception as e:
            logger.error(
                f"Unexpected error fetching agent card",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentCommunicationError(
                message=f"Unexpected error fetching agent card: {str(e)}",
                agent_name=_agent_name,
                endpoint=card_url,
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def send_task(
        self,
        agent_url: str,
        skill_id: str,
        payload: dict[str, Any],
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a task to an agent and wait for the result.

        This method handles the full SDK flow:
        1. Fetch agent card
        2. Create client from card
        3. Construct message with skill_id and payload
        4. Send message and process async iterator
        5. Extract and return result

        Args:
            agent_url: Base URL of the agent.
            skill_id: Skill ID to invoke.
            payload: Task payload data.
            agent_name: Optional agent name for logging.

        Returns:
            Task result data as dictionary.

        Raises:
            A2AError: If task fails or times out.
            AgentCommunicationError: If communication fails.
        """
        logger.info(
            f"Sending task to agent",
            agent_url=agent_url,
            skill_id=skill_id,
            agent_name=agent_name,
        )

        try:
            # Fetch agent card
            agent_card = await self.get_agent_card(agent_url, agent_name)

            # Create SDK client from agent card
            client = self.client_factory.create(agent_card)

            # Add skill_id to payload for routing
            enriched_payload = {**payload, "skill_id": skill_id}

            # Construct message
            message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.user,
                parts=[DataPart(data=enriched_payload)],
                metadata={"skill_id": skill_id},
            )

            logger.debug(
                f"Sending message to agent",
                message_id=message.message_id,
                skill_id=skill_id,
            )

            # Send message and process response
            task: Task | None = None
            async for event in client.send_message(message):
                # Event can be (Task, TaskUpdate) tuple or just Task
                if isinstance(event, tuple):
                    task, update = event
                    logger.debug(
                        f"Received task update",
                        task_id=task.id,
                        status=task.status,
                    )
                elif isinstance(event, Task):
                    task = event
                    logger.debug(
                        f"Received task",
                        task_id=task.id,
                        status=task.status,
                    )

                # Check if task is complete
                if task and task.status in [
                    TaskStatus.completed,
                    TaskStatus.failed,
                    TaskStatus.cancelled,
                    TaskStatus.rejected,
                ]:
                    logger.info(
                        f"Task reached terminal state",
                        task_id=task.id,
                        status=task.status,
                    )
                    break

            # Extract result from task
            if not task:
                logger.error("No task received from agent")
                raise A2AError(
                    message="No task received from agent",
                    agent_name=agent_name or agent_card.name,
                    skill_id=skill_id,
                )

            if task.status == TaskStatus.completed:
                # Extract result from last message in history
                result_data = self._extract_result_from_task(task)

                logger.info(
                    f"Task completed successfully",
                    task_id=task.id,
                    agent_name=agent_name or agent_card.name,
                )

                return result_data

            elif task.status == TaskStatus.failed:
                # Extract error from task
                error_msg = self._extract_error_from_task(task)

                logger.error(
                    f"Task failed",
                    task_id=task.id,
                    error=error_msg,
                )

                raise A2AError(
                    message=f"Task failed: {error_msg}",
                    agent_name=agent_name or agent_card.name,
                    task_id=task.id,
                    skill_id=skill_id,
                    details={"error": error_msg},
                )

            else:
                # Unexpected terminal state
                logger.error(
                    f"Task ended in unexpected state",
                    task_id=task.id,
                    status=task.status,
                )

                raise A2AError(
                    message=f"Task ended in unexpected state: {task.status}",
                    agent_name=agent_name or agent_card.name,
                    task_id=task.id,
                    skill_id=skill_id,
                )

        except A2AError:
            # Re-raise A2A errors as-is
            raise

        except AgentCommunicationError:
            # Re-raise communication errors as-is
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error sending task",
                agent_url=agent_url,
                skill_id=skill_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

            raise A2AError(
                message=f"Unexpected error sending task: {str(e)}",
                agent_name=agent_name,
                skill_id=skill_id,
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def list_agents(self) -> list[dict[str, Any]]:
        """
        List all agents from the A2A registry.

        This method queries the custom registry API (not part of SDK).

        Returns:
            List of agent card dictionaries.

        Raises:
            A2AError: If registry query fails.
        """
        if not self.registry_url:
            logger.error("No registry URL configured")
            raise A2AError(
                message="No registry URL configured for list_agents",
                details={"registry_url": self.registry_url},
            )

        list_url = f"{self.registry_url}/agents"

        logger.debug(f"Listing agents from registry: {list_url}")

        try:
            response = await self.httpx_client.get(list_url)
            response.raise_for_status()

            agents = response.json()

            logger.info(f"Listed {len(agents)} agents from registry")

            return agents

        except httpx.HTTPError as e:
            logger.error(
                f"Failed to list agents from registry",
                registry_url=self.registry_url,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise A2AError(
                message=f"Failed to list agents: {str(e)}",
                details={
                    "registry_url": self.registry_url,
                    "error": str(e),
                },
            ) from e

        except Exception as e:
            logger.error(
                f"Unexpected error listing agents",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise A2AError(
                message=f"Unexpected error listing agents: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    def _extract_result_from_task(self, task: Task) -> dict[str, Any]:
        """
        Extract result data from completed task.

        Args:
            task: Completed task.

        Returns:
            Result data dictionary.
        """
        if not task.history or len(task.history) == 0:
            logger.warning(f"Task {task.id} has no history")
            return {}

        # Get last message (agent's response)
        last_message = task.history[-1]

        # Extract data from DataPart
        if last_message.parts:
            for part in last_message.parts:
                if isinstance(part, DataPart) and part.data:
                    return part.data

        logger.warning(f"No data found in task {task.id} history")
        return {}

    def _extract_error_from_task(self, task: Task) -> str:
        """
        Extract error message from failed task.

        Args:
            task: Failed task.

        Returns:
            Error message string.
        """
        if not task.history or len(task.history) == 0:
            return "Unknown error (no history)"

        # Get last message (error message)
        last_message = task.history[-1]

        # Extract error from DataPart
        if last_message.parts:
            for part in last_message.parts:
                if isinstance(part, DataPart) and part.data:
                    if isinstance(part.data, dict):
                        return part.data.get("error", "Unknown error")
                    else:
                        return str(part.data)

        return "Unknown error"


# Singleton instance for convenience
_client_wrapper: SDKClientWrapper | None = None


def get_sdk_client(registry_url: str | None = None) -> SDKClientWrapper:
    """
    Get singleton SDK client wrapper instance.

    Args:
        registry_url: Optional registry URL (only used for first call).

    Returns:
        SDKClientWrapper instance.
    """
    global _client_wrapper

    if _client_wrapper is None:
        _client_wrapper = SDKClientWrapper(registry_url=registry_url)
        logger.debug("Created singleton SDK client wrapper")

    return _client_wrapper


async def cleanup_sdk_client() -> None:
    """Clean up singleton SDK client wrapper."""
    global _client_wrapper

    if _client_wrapper is not None:
        await _client_wrapper.close()
        _client_wrapper = None
        logger.debug("Cleaned up SDK client wrapper")
