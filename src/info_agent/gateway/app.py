"""
FastAPI application factory for Info-Agent Gateway.

This module provides the main FastAPI application factory that creates
and configures the gateway with all routes, middleware, and dependencies.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from info_agent.config import Settings, get_settings
from info_agent.supervisor.agent import SupervisorAgent

logger = logging.getLogger(__name__)


class GatewayApp:
    """
    Gateway application container.

    Holds the FastAPI app instance and shared resources like
    the SupervisorAgent instance.
    """

    def __init__(
        self,
        app: FastAPI,
        supervisor: SupervisorAgent,
        settings: Settings,
    ) -> None:
        """
        Initialize the gateway app container.

        Args:
            app: FastAPI application instance.
            supervisor: Supervisor agent instance.
            settings: Application settings.
        """
        logger.info("Initializing GatewayApp")
        self._app = app
        self._supervisor = supervisor
        self._settings = settings
        logger.info("GatewayApp initialized")

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self._app

    @property
    def supervisor(self) -> SupervisorAgent:
        """Get the supervisor agent."""
        return self._supervisor

    @property
    def settings(self) -> Settings:
        """Get the application settings."""
        return self._settings


async def create_app(
    settings: Settings | None = None,
    checkpoint_db_path: Path | None = None,
) -> GatewayApp:
    """
    Create and configure the FastAPI gateway application.

    Args:
        settings: Optional settings instance. If not provided,
            settings are loaded from environment.
        checkpoint_db_path: Optional path for checkpoint database.
            If not provided, uses settings or memory.

    Returns:
        GatewayApp container with configured application.

    Raises:
        RuntimeError: If application creation fails.
    """
    logger.info("Creating FastAPI gateway application")

    if settings is None:
        settings = get_settings()
        logger.info("Loaded settings from environment")

    # Determine checkpoint path
    if checkpoint_db_path is None and settings.checkpoint_db_path:
        checkpoint_db_path = Path(settings.checkpoint_db_path)
        logger.info("Using checkpoint path from settings: %s", checkpoint_db_path)

    # Create supervisor agent
    logger.info("Creating SupervisorAgent")
    supervisor = await SupervisorAgent.create(
        checkpoint_db_path=checkpoint_db_path,
        use_llm=False,  # Use stub mode by default
        use_stub_delegator=True,  # Use stub delegator for testing
    )
    logger.info("SupervisorAgent created")

    # Create lifespan context manager
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan handler."""
        logger.info("Gateway application starting up")
        yield
        logger.info("Gateway application shutting down")
        await supervisor.close()
        logger.info("SupervisorAgent closed")

    # Create FastAPI app
    app = FastAPI(
        title="Info-Agent Gateway",
        description="Multi-agent information retrieval and validation system",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store references in app state
    app.state.supervisor = supervisor
    app.state.settings = settings

    # Register routes
    _register_routes(app)

    logger.info("FastAPI gateway application created")

    return GatewayApp(
        app=app,
        supervisor=supervisor,
        settings=settings,
    )


def create_app_sync(
    settings: Settings | None = None,
    supervisor: SupervisorAgent | None = None,
) -> FastAPI:
    """
    Create FastAPI app synchronously (for testing).

    This version creates the app without async initialization,
    useful for test fixtures.

    Args:
        settings: Optional settings instance.
        supervisor: Optional pre-created supervisor agent.

    Returns:
        FastAPI application instance.
    """
    logger.info("Creating FastAPI gateway application (sync)")

    if settings is None:
        settings = get_settings()

    if supervisor is None:
        supervisor = SupervisorAgent(
            use_llm=False,
            use_stub_delegator=True,
        )

    # Create lifespan context manager
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan handler."""
        logger.info("Gateway application starting up")
        yield
        logger.info("Gateway application shutting down")
        await supervisor.close()
        logger.info("SupervisorAgent closed")

    # Create FastAPI app
    app = FastAPI(
        title="Info-Agent Gateway",
        description="Multi-agent information retrieval and validation system",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store references in app state
    app.state.supervisor = supervisor
    app.state.settings = settings

    # Register routes
    _register_routes(app)

    logger.info("FastAPI gateway application created (sync)")

    return app


def _register_routes(app: FastAPI) -> None:
    """
    Register all routes with the FastAPI application.

    Args:
        app: FastAPI application instance.
    """
    from info_agent.gateway.routes.frontend import router as frontend_router
    from info_agent.gateway.routes.health import router as health_router
    from info_agent.gateway.routes.webhooks import router as webhooks_router
    from info_agent.gateway.routes.workflows import router as workflows_router

    logger.info("Registering routes")

    # Health routes (no prefix for /health)
    app.include_router(health_router, tags=["Health"])

    # Workflow routes
    app.include_router(
        workflows_router,
        prefix="/api/workflows",
        tags=["Workflows"],
    )

    # Webhook routes
    app.include_router(
        webhooks_router,
        prefix="/webhooks",
        tags=["Webhooks"],
    )

    # Frontend routes (no prefix)
    app.include_router(frontend_router, tags=["Frontend"])

    # Mount static files if available
    _mount_static_files(app)

    logger.info("Routes registered")


def _mount_static_files(app: FastAPI) -> None:
    """
    Mount static files directory if available.

    Args:
        app: FastAPI application instance.
    """
    static_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "static"

    if static_dir.exists():
        logger.info("Mounting static files from: %s", static_dir)
        app.mount(
            "/static",
            StaticFiles(directory=str(static_dir)),
            name="static",
        )
    else:
        logger.warning("Static files directory not found: %s", static_dir)


logger.info("Gateway app module initialized")
