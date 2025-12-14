"""
FastAPI Gateway application for Info-Agent.

This module provides the main FastAPI application that serves as the gateway
for the Info-Agent system. It integrates all components:
- REST API for workflow management
- A2A Registry for agent discovery
- Webhook endpoints for email notifications
- Health check endpoints

Usage:
    # Run with uvicorn:
    uvicorn info_agent.main:app --reload

    # Or run directly:
    python -m info_agent.main
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from info_agent.config import get_settings
from info_agent.utils.exceptions import InfoAgentError
from info_agent.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler for startup and shutdown events.

    Handles:
    - Logging setup
    - A2A Registry initialization
    - Database initialization
    - Cleanup on shutdown
    """
    logger.info("Starting Info-Agent Gateway")

    settings = get_settings()
    logger.info(
        "Configuration loaded",
        host=settings.host,
        port=settings.gateway_port,
        log_level=settings.log_level,
        debug=settings.debug,
    )

    # Initialize A2A Registry
    try:
        from info_agent.a2a.registry import init_registry

        await init_registry()
        logger.info("A2A Registry initialized")
    except Exception as e:
        logger.error("Failed to initialize A2A Registry", error=str(e))
        raise

    # Initialize workflow checkpointer database
    try:
        from info_agent.workflow.checkpointer import create_checkpointer

        await create_checkpointer(settings.checkpoint_db_path)
        logger.info(
            "Workflow checkpointer initialized",
            db_path=settings.checkpoint_db_path,
        )
    except Exception as e:
        logger.error("Failed to initialize workflow checkpointer", error=str(e))
        raise

    logger.info("Info-Agent Gateway started successfully")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down Info-Agent Gateway")

    try:
        from info_agent.a2a.registry import cleanup_registry

        await cleanup_registry()
        logger.info("A2A Registry cleanup completed")
    except Exception as e:
        logger.warning("Error during A2A Registry cleanup", error=str(e))

    logger.info("Info-Agent Gateway shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    # Setup logging
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name="info-agent-gateway",
    )

    logger.info("Creating FastAPI application")

    app = FastAPI(
        title="Info-Agent Gateway",
        description="AI-powered information retrieval system using A2A protocol",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.debug("CORS middleware configured")

    # Add exception handler for custom exceptions
    @app.exception_handler(InfoAgentError)
    async def info_agent_exception_handler(
        request: Request, exc: InfoAgentError
    ) -> JSONResponse:
        """Handle InfoAgentError exceptions."""
        logger.error(
            "InfoAgentError occurred",
            error_code=exc.code,
            error_message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=exc.to_dict(),
        )

    logger.debug("Exception handlers configured")

    # Include routers
    _include_routers(app)

    logger.info("FastAPI application created successfully")

    return app


def _include_routers(app: FastAPI) -> None:
    """
    Include all API routers in the application.

    Args:
        app: FastAPI application instance.
    """
    logger.info("Including API routers")

    # Health check endpoints (basic inline implementation)
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """Basic health check endpoint."""
        return {"status": "healthy", "service": "info-agent-gateway"}

    @app.get("/ready", tags=["health"])
    async def readiness_check() -> dict:
        """Readiness check endpoint."""
        settings = get_settings()
        return {
            "status": "ready",
            "service": "info-agent-gateway",
            "config": {
                "host": settings.host,
                "port": settings.gateway_port,
                "debug": settings.debug,
            },
        }

    logger.debug("Health check endpoints added")

    # Include A2A Registry router
    try:
        from info_agent.a2a.registry import create_a2a_router

        a2a_router = create_a2a_router()
        app.include_router(a2a_router)
        logger.info("A2A Registry router included")
    except ImportError as e:
        logger.warning("Could not import A2A router", error=str(e))
    except Exception as e:
        logger.error("Failed to include A2A router", error=str(e))

    # Include all API routes (health, webhooks, workflows)
    try:
        from info_agent.api.routes import include_all_routers

        include_all_routers(app)
        logger.info("API routes included (health, webhooks, workflows)")
    except ImportError as e:
        logger.warning("Could not import API routes", error=str(e))
    except Exception as e:
        logger.error("Failed to include API routes", error=str(e))

    logger.info("All routers included")


# Create the application instance
app = create_app()


async def main() -> None:
    """
    Main entry point for running the application.

    Runs the FastAPI server with uvicorn.
    """
    settings = get_settings()

    logger.info(
        "Starting Info-Agent Gateway server",
        host=settings.host,
        port=settings.gateway_port,
    )

    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.gateway_port,
        log_level=settings.log_level.lower(),
        reload=settings.debug,
    )

    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise
    finally:
        logger.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
