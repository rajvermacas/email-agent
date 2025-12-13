"""
A2A client for sending tasks to remote agents.

This module provides an async HTTP client for communicating with
A2A-compatible agents. It supports task creation, agent card retrieval,
and proper error handling.

All operations are async using httpx.
No fallback/default values - missing data raises exceptions.

Usage:
    from info_agent.a2a.client import A2AClient

    client = A2AClient("http://localhost:8001/a2a")

    # Get agent card
    card = await client.get_agent_card()

    # Send task
    result = await client.send_task(
        agent_name="currency-agent",
        skill_id="convert",
        payload={"amount": 100, "from": "USD", "to": "EUR"}
    )
"""

from typing import Any

import httpx

from info_agent.a2a.models import AgentCard
from info_agent.utils.exceptions import A2AError, AgentCommunicationError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class A2AClient:
    """
    Async HTTP client for A2A protocol communication.

    This client handles communication with remote A2A agents,
    including task submission and agent card retrieval.

    Attributes:
        base_url: Base URL of the A2A agent endpoint.
        timeout: Request timeout in seconds.
    """

    DEFAULT_TIMEOUT = 30.0
    AGENT_CARD_PATH = "/.well-known/agent.json"

    def __init__(
        self,
        base_url: str,
        timeout: float | None = None,
    ) -> None:
        """
        Initialize A2A client.

        Args:
            base_url: Base URL of the A2A agent endpoint (required).
            timeout: Optional request timeout in seconds.
                    Defaults to 30 seconds if not provided.

        Raises:
            A2AError: If base_url is invalid.
        """
        if not base_url:
            raise A2AError(
                message="base_url is required",
                details={"parameter": "base_url"},
            )

        if not base_url.startswith(("http://", "https://")):
            raise A2AError(
                message="base_url must start with http:// or https://",
                details={"base_url": base_url},
            )

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

        logger.info(
            "A2AClient initialized",
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def send_task(
        self,
        agent_name: str,
        skill_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send a task to a remote agent.

        Args:
            agent_name: Name of the target agent (required).
            skill_id: ID of the skill to execute (required).
            payload: Input data for the task (required, must not be empty).

        Returns:
            Task result as a dictionary.

        Raises:
            A2AError: If parameters are invalid.
            AgentCommunicationError: If communication fails.
        """
        logger.info(
            "Sending task to agent",
            agent_name=agent_name,
            skill_id=skill_id,
        )

        # Validate required parameters
        if not agent_name:
            raise A2AError(
                message="agent_name is required",
                details={"parameter": "agent_name"},
            )

        if not skill_id:
            raise A2AError(
                message="skill_id is required",
                agent_name=agent_name,
                details={"parameter": "skill_id"},
            )

        if not payload:
            raise A2AError(
                message="payload is required and cannot be empty",
                agent_name=agent_name,
                skill_id=skill_id,
                details={"parameter": "payload"},
            )

        # Construct task endpoint
        task_endpoint = f"{self.base_url}/tasks"

        # Prepare request payload
        request_data = {
            "skill": skill_id,
            "input": payload,
            "blocking": True,  # Wait for completion
        }

        logger.debug(
            "Sending task request",
            endpoint=task_endpoint,
            skill_id=skill_id,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    task_endpoint,
                    json=request_data,
                )

                logger.debug(
                    "Task request completed",
                    status_code=response.status_code,
                    agent_name=agent_name,
                )

                # Handle HTTP errors
                if response.status_code >= 400:
                    error_detail = response.text
                    logger.error(
                        "Task request failed with HTTP error",
                        status_code=response.status_code,
                        error=error_detail,
                        agent_name=agent_name,
                    )

                    raise AgentCommunicationError(
                        message=f"HTTP {response.status_code}: {error_detail}",
                        agent_name=agent_name,
                        endpoint=task_endpoint,
                        details={
                            "status_code": response.status_code,
                            "error": error_detail,
                        },
                    )

                # Parse response
                result = response.json()

                logger.info(
                    "Task completed successfully",
                    agent_name=agent_name,
                    skill_id=skill_id,
                )

                return result

        except httpx.TimeoutException as e:
            logger.error(
                "Task request timed out",
                agent_name=agent_name,
                timeout=self.timeout,
            )
            raise AgentCommunicationError(
                message=f"Request timed out after {self.timeout}s",
                agent_name=agent_name,
                endpoint=task_endpoint,
                details={"timeout": self.timeout, "error": str(e)},
            ) from e

        except httpx.NetworkError as e:
            logger.error(
                "Network error during task request",
                agent_name=agent_name,
                error=str(e),
            )
            raise AgentCommunicationError(
                message=f"Network error: {str(e)}",
                agent_name=agent_name,
                endpoint=task_endpoint,
                details={"error": str(e)},
            ) from e

        except httpx.HTTPError as e:
            logger.error(
                "HTTP error during task request",
                agent_name=agent_name,
                error=str(e),
            )
            raise AgentCommunicationError(
                message=f"HTTP error: {str(e)}",
                agent_name=agent_name,
                endpoint=task_endpoint,
                details={"error": str(e)},
            ) from e

        except Exception as e:
            logger.error(
                "Unexpected error during task request",
                agent_name=agent_name,
                error=str(e),
            )
            raise AgentCommunicationError(
                message=f"Unexpected error: {str(e)}",
                agent_name=agent_name,
                endpoint=task_endpoint,
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def get_agent_card(self, agent_url: str | None = None) -> AgentCard:
        """
        Retrieve agent card from a remote agent.

        The agent card is fetched from the standard A2A endpoint:
        /.well-known/agent.json

        Args:
            agent_url: Optional agent URL. If not provided, uses base_url.

        Returns:
            AgentCard instance.

        Raises:
            A2AError: If agent card retrieval fails.
            AgentCommunicationError: If communication fails.
        """
        url = (agent_url or self.base_url).rstrip("/")

        logger.info("Retrieving agent card", agent_url=url)

        # Construct agent card endpoint
        card_endpoint = f"{url}{self.AGENT_CARD_PATH}"

        logger.debug("Fetching agent card", endpoint=card_endpoint)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(card_endpoint)

                logger.debug(
                    "Agent card request completed",
                    status_code=response.status_code,
                )

                # Handle HTTP errors
                if response.status_code >= 400:
                    error_detail = response.text
                    logger.error(
                        "Agent card retrieval failed",
                        status_code=response.status_code,
                        error=error_detail,
                    )

                    raise AgentCommunicationError(
                        message=f"Failed to retrieve agent card: HTTP {response.status_code}",
                        agent_name="unknown",
                        endpoint=card_endpoint,
                        details={
                            "status_code": response.status_code,
                            "error": error_detail,
                        },
                    )

                # Parse and validate agent card
                card_data = response.json()

                # Validate required fields
                required_fields = [
                    "name",
                    "description",
                    "version",
                    "url",
                    "capabilities",
                    "skills",
                    "defaultInputModes",
                    "defaultOutputModes",
                ]

                missing_fields = [
                    field for field in required_fields if field not in card_data
                ]

                if missing_fields:
                    logger.error(
                        "Agent card missing required fields",
                        missing_fields=missing_fields,
                    )
                    raise A2AError(
                        message=f"Invalid agent card: missing fields {missing_fields}",
                        details={
                            "missing_fields": missing_fields,
                            "endpoint": card_endpoint,
                        },
                    )

                # Create and validate AgentCard
                try:
                    agent_card = AgentCard(**card_data)
                    logger.info(
                        "Agent card retrieved successfully",
                        agent_name=agent_card.name,
                        version=agent_card.version,
                        skills_count=len(agent_card.skills),
                    )
                    return agent_card

                except Exception as e:
                    logger.error(
                        "Failed to parse agent card",
                        error=str(e),
                    )
                    raise A2AError(
                        message=f"Invalid agent card format: {str(e)}",
                        details={"error": str(e), "endpoint": card_endpoint},
                    ) from e

        except httpx.TimeoutException as e:
            logger.error(
                "Agent card request timed out",
                timeout=self.timeout,
            )
            raise AgentCommunicationError(
                message=f"Request timed out after {self.timeout}s",
                agent_name="unknown",
                endpoint=card_endpoint,
                details={"timeout": self.timeout, "error": str(e)},
            ) from e

        except httpx.NetworkError as e:
            logger.error(
                "Network error during agent card retrieval",
                error=str(e),
            )
            raise AgentCommunicationError(
                message=f"Network error: {str(e)}",
                agent_name="unknown",
                endpoint=card_endpoint,
                details={"error": str(e)},
            ) from e

        except httpx.HTTPError as e:
            logger.error(
                "HTTP error during agent card retrieval",
                error=str(e),
            )
            raise AgentCommunicationError(
                message=f"HTTP error: {str(e)}",
                agent_name="unknown",
                endpoint=card_endpoint,
                details={"error": str(e)},
            ) from e

        except (A2AError, AgentCommunicationError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            logger.error(
                "Unexpected error during agent card retrieval",
                error=str(e),
            )
            raise AgentCommunicationError(
                message=f"Unexpected error: {str(e)}",
                agent_name="unknown",
                endpoint=card_endpoint,
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e
