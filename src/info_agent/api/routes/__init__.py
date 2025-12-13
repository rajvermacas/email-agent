"""
API routes module for Info-Agent Gateway.

This module exports all API routers and provides a convenience function
to combine them into a single application.

Available routers:
- Health: Health check and readiness endpoints
- Webhooks: Webhook endpoints for external notifications
- Workflows: Workflow management endpoints

Usage:
    from fastapi import FastAPI
    from info_agent.api.routes import (
        create_health_router,
        create_webhook_router,
        create_workflow_router,
        include_all_routers,
    )

    app = FastAPI()

    # Option 1: Include all routers at once
    include_all_routers(app)

    # Option 2: Include routers individually
    app.include_router(create_health_router())
    app.include_router(create_webhook_router())
    app.include_router(create_workflow_router())
"""

from fastapi import FastAPI

from info_agent.api.routes.health import create_health_router
from info_agent.api.routes.webhooks import create_webhook_router
from info_agent.api.routes.workflows import create_workflow_router
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Export router factory functions
__all__ = [
    "create_health_router",
    "create_webhook_router",
    "create_workflow_router",
    "include_all_routers",
]


def include_all_routers(app: FastAPI) -> None:
    """
    Include all API routers in the FastAPI application.

    This is a convenience function that adds all available routers
    to the application with their appropriate prefixes and tags.

    Args:
        app: FastAPI application instance.

    Example:
        >>> from fastapi import FastAPI
        >>> from info_agent.api.routes import include_all_routers
        >>>
        >>> app = FastAPI()
        >>> include_all_routers(app)
    """
    logger.info("Including all API routers")

    # Create routers
    logger.debug("Creating health router")
    health_router = create_health_router()

    logger.debug("Creating webhook router")
    webhook_router = create_webhook_router()

    logger.debug("Creating workflow router")
    workflow_router = create_workflow_router()

    # Include routers in app
    logger.debug("Including health router")
    app.include_router(health_router)

    logger.debug("Including webhook router")
    app.include_router(webhook_router)

    logger.debug("Including workflow router")
    app.include_router(workflow_router)

    logger.info(
        "All API routers included successfully",
        router_count=3,
        routers=["health", "webhooks", "workflows"],
    )
