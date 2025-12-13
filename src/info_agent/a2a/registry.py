"""
FastAPI router for A2A agent registry.

This module provides REST API endpoints for agent registration,
discovery, and management in the A2A protocol.

All endpoints use async operations and proper error handling.
No fallback/default values - missing data raises HTTP exceptions.

Usage:
    from fastapi import FastAPI
    from info_agent.a2a.registry import get_a2a_router

    app = FastAPI()
    router = await get_a2a_router()
    app.include_router(router, prefix="/a2a")

    # Endpoints:
    # POST /a2a/agents/register - Register agent
    # GET /a2a/agents - List agents
    # GET /a2a/agents/{agent_name} - Get agent
    # DELETE /a2a/agents/{agent_name} - Delete agent
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status

from info_agent.a2a.models import AgentCard, RegisterAgentResponse
from info_agent.a2a.storage import A2AStorage
from info_agent.utils.exceptions import AgentNotFoundError, StorageError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Global storage instance
_storage: A2AStorage | None = None


def get_storage() -> A2AStorage:
    """
    Get the A2A storage instance.

    Returns:
        A2AStorage instance.

    Raises:
        HTTPException: If storage is not initialized.
    """
    if _storage is None:
        logger.error("A2A storage not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A2A storage not initialized. Call init_registry() first.",
        )
    return _storage


async def init_registry() -> None:
    """
    Initialize the A2A registry storage.

    This should be called on application startup.

    Raises:
        StorageError: If initialization fails.
    """
    global _storage

    logger.info("Initializing A2A registry")

    try:
        _storage = A2AStorage()
        await _storage.init_db()
        logger.info("A2A registry initialized successfully")

    except Exception as e:
        logger.error("Failed to initialize A2A registry", error=str(e))
        raise StorageError(
            message=f"Registry initialization failed: {e}",
            operation="init",
            entity_type="a2a_registry",
            details={"error": str(e)},
        ) from e


async def cleanup_registry() -> None:
    """
    Cleanup the A2A registry resources.

    This should be called on application shutdown.
    """
    global _storage

    logger.info("Cleaning up A2A registry")
    _storage = None
    logger.info("A2A registry cleanup completed")


def create_a2a_router() -> APIRouter:
    """
    Create the A2A registry FastAPI router.

    Returns:
        APIRouter instance with all A2A endpoints.
    """
    logger.info("Creating A2A registry router")

    router = APIRouter(
        prefix="/a2a",
        tags=["A2A Registry"],
        responses={
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "Internal server error"
            },
        },
    )

    @router.post(
        "/agents/register",
        response_model=RegisterAgentResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Register an agent",
        description="Register a new agent or update an existing agent in the registry",
    )
    async def register_agent(agent_card: AgentCard) -> RegisterAgentResponse:
        """
        Register or update an agent in the registry.

        Args:
            agent_card: Agent card containing agent information and capabilities.

        Returns:
            RegisterAgentResponse with registration status.

        Raises:
            HTTPException: If registration fails.
        """
        logger.info("Registering agent", agent_name=agent_card.name)

        if not agent_card.name:
            logger.warning("Agent registration failed: missing name")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent name is required",
            )

        try:
            storage = get_storage()

            # Check if agent already exists
            try:
                existing_agent = await storage.get_agent(agent_card.name)
                is_update = True
                logger.info(
                    "Agent exists, will update",
                    agent_name=agent_card.name,
                    old_version=existing_agent.version,
                    new_version=agent_card.version,
                )
            except AgentNotFoundError:
                is_update = False
                logger.info("New agent registration", agent_name=agent_card.name)

            # Save the agent
            await storage.save_agent(agent_card)

            response = RegisterAgentResponse(
                status="updated" if is_update else "registered",
                agent_name=agent_card.name,
                message=(
                    f"Agent '{agent_card.name}' updated successfully"
                    if is_update
                    else f"Agent '{agent_card.name}' registered successfully"
                ),
            )

            logger.info(
                "Agent registration completed",
                agent_name=agent_card.name,
                status=response.status,
            )
            return response

        except StorageError as e:
            logger.error(
                "Agent registration failed",
                agent_name=agent_card.name,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to register agent: {e.message}",
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error during agent registration",
                agent_name=agent_card.name,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            ) from e

    @router.get(
        "/agents",
        response_model=list[AgentCard],
        summary="List all agents",
        description="Retrieve a list of all registered agents",
    )
    async def list_agents() -> list[AgentCard]:
        """
        List all registered agents.

        Returns:
            List of AgentCard instances.

        Raises:
            HTTPException: If listing fails.
        """
        logger.info("Listing all agents")

        try:
            storage = get_storage()
            agents = await storage.list_agents()

            logger.info("Agents listed successfully", agent_count=len(agents))
            return agents

        except StorageError as e:
            logger.error("Failed to list agents", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list agents: {e.message}",
            ) from e
        except Exception as e:
            logger.error("Unexpected error while listing agents", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            ) from e

    @router.get(
        "/agents/{agent_name}",
        response_model=AgentCard,
        summary="Get agent by name",
        description="Retrieve a specific agent's card by name",
    )
    async def get_agent(agent_name: str) -> AgentCard:
        """
        Get an agent by name.

        Args:
            agent_name: Name of the agent to retrieve.

        Returns:
            AgentCard instance.

        Raises:
            HTTPException: If agent not found or retrieval fails.
        """
        logger.info("Getting agent", agent_name=agent_name)

        if not agent_name:
            logger.warning("Get agent failed: missing name")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent name is required",
            )

        try:
            storage = get_storage()
            agent = await storage.get_agent(agent_name)

            logger.info("Agent retrieved successfully", agent_name=agent_name)
            return agent

        except AgentNotFoundError as e:
            logger.warning("Agent not found", agent_name=agent_name)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent not found: {agent_name}",
            ) from e
        except StorageError as e:
            logger.error(
                "Failed to retrieve agent",
                agent_name=agent_name,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve agent: {e.message}",
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error while getting agent",
                agent_name=agent_name,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            ) from e

    @router.delete(
        "/agents/{agent_name}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Deregister an agent",
        description="Remove an agent from the registry",
    )
    async def deregister_agent(agent_name: str) -> None:
        """
        Deregister an agent from the registry.

        Args:
            agent_name: Name of the agent to deregister.

        Raises:
            HTTPException: If agent not found or deletion fails.
        """
        logger.info("Deregistering agent", agent_name=agent_name)

        if not agent_name:
            logger.warning("Deregister agent failed: missing name")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent name is required",
            )

        try:
            storage = get_storage()
            await storage.delete_agent(agent_name)

            logger.info("Agent deregistered successfully", agent_name=agent_name)

        except AgentNotFoundError as e:
            logger.warning("Agent not found for deletion", agent_name=agent_name)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent not found: {agent_name}",
            ) from e
        except StorageError as e:
            logger.error(
                "Failed to deregister agent",
                agent_name=agent_name,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to deregister agent: {e.message}",
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error while deregistering agent",
                agent_name=agent_name,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            ) from e

    logger.info("A2A registry router created successfully")
    return router


@asynccontextmanager
async def get_a2a_router() -> AsyncGenerator[APIRouter, None]:
    """
    Get A2A router with automatic initialization and cleanup.

    This is an async context manager that initializes the registry
    on entry and cleans up on exit.

    Yields:
        APIRouter instance.

    Example:
        async with get_a2a_router() as router:
            app.include_router(router)
    """
    logger.info("Initializing A2A router with context manager")

    await init_registry()
    router = create_a2a_router()

    try:
        yield router
    finally:
        await cleanup_registry()
        logger.info("A2A router context manager completed")
