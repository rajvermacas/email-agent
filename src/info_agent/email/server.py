"""
Combined SMTP + REST server for mock email system.

This module provides a unified server that runs both:
1. SMTP server for receiving emails
2. FastAPI REST server for email management

Usage:
    from info_agent.email.server import MockEmailServer

    server = MockEmailServer()
    await server.start()
    # ... server runs ...
    await server.stop()

Or run standalone:
    python -m info_agent.email.server
"""

import asyncio

import uvicorn
from fastapi import FastAPI

from info_agent.config import get_settings
from info_agent.email.api import create_email_router
from info_agent.email.smtp import start_smtp_server
from info_agent.email.storage import EmailStorage
from info_agent.email.webhook import WebhookNotifier
from info_agent.utils.exceptions import EmailError
from info_agent.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


class MockEmailServer:
    """
    Combined SMTP + REST server for mock email system.

    Manages both the SMTP server (for receiving emails) and the REST API
    (for email management and queries). Provides graceful startup and shutdown.
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        rest_host: str | None = None,
        rest_port: int | None = None,
        db_path: str | None = None,
        webhook_url: str | None = None,
    ) -> None:
        """
        Initialize mock email server.

        Args:
            smtp_host: SMTP server host. If None, uses config.
            smtp_port: SMTP server port. If None, uses config.
            rest_host: REST API host. If None, uses config.
            rest_port: REST API port. If None, uses config.
            db_path: Database path. If None, uses config.
            webhook_url: Webhook URL. If None, uses config.

        Raises:
            EmailError: If configuration is invalid.
        """
        settings = get_settings()

        self.smtp_host = smtp_host or settings.smtp_host
        self.smtp_port = smtp_port or settings.smtp_port
        self.rest_host = rest_host or settings.host
        self.rest_port = rest_port or settings.email_server_port
        self.db_path = db_path or settings.email_db_path
        self.webhook_url = webhook_url or settings.email_webhook_url

        # Validate configuration
        if not self.smtp_host:
            raise EmailError(
                message="SMTP host is required",
                details={"smtp_host": self.smtp_host},
            )

        if not self.smtp_port or self.smtp_port < 1 or self.smtp_port > 65535:
            raise EmailError(
                message="Valid SMTP port is required (1-65535)",
                details={"smtp_port": self.smtp_port},
            )

        if not self.rest_host:
            raise EmailError(
                message="REST host is required",
                details={"rest_host": self.rest_host},
            )

        if not self.rest_port or self.rest_port < 1 or self.rest_port > 65535:
            raise EmailError(
                message="Valid REST port is required (1-65535)",
                details={"rest_port": self.rest_port},
            )

        if not self.db_path:
            raise EmailError(
                message="Database path is required",
                details={"db_path": self.db_path},
            )

        logger.info(
            "MockEmailServer initialized",
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            rest_host=self.rest_host,
            rest_port=self.rest_port,
            db_path=self.db_path,
            webhook_url=self.webhook_url,
        )

        # Initialize components
        self.storage = EmailStorage(db_path=self.db_path)
        self.webhook_notifier = WebhookNotifier(webhook_url=self.webhook_url)
        self.smtp_controller = None
        self.rest_server = None

        logger.info("Components initialized", has_webhook=True)

    async def start(self) -> None:
        """
        Start both SMTP and REST servers.

        Initializes the database, starts the SMTP server, and starts the
        FastAPI REST server.

        Raises:
            EmailError: If server startup fails.
        """
        logger.info("Starting MockEmailServer")

        try:
            # Initialize database
            logger.info("Initializing email database")
            await self.storage.init_db()
            logger.info("Email database initialized")

            # Start SMTP server
            logger.info(
                "Starting SMTP server", host=self.smtp_host, port=self.smtp_port
            )
            self.smtp_controller = await start_smtp_server(
                host=self.smtp_host,
                port=self.smtp_port,
                storage=self.storage,
                webhook_notifier=self.webhook_notifier,
            )
            logger.info("SMTP server started successfully")

            # Create FastAPI app
            logger.info("Creating FastAPI application")
            app = FastAPI(
                title="Mock Email Server",
                description="Mock email server with SMTP and REST API",
                version="1.0.0",
            )

            # Add email router
            email_router = create_email_router(
                storage=self.storage, webhook_notifier=self.webhook_notifier
            )
            app.include_router(email_router)
            logger.info("Email router added to FastAPI app")

            # Add health check endpoint
            @app.get("/health", tags=["health"])
            async def health_check() -> dict:
                """Health check endpoint."""
                return {
                    "status": "healthy",
                    "smtp": {
                        "host": self.smtp_host,
                        "port": self.smtp_port,
                        "running": self.smtp_controller is not None,
                    },
                    "rest": {
                        "host": self.rest_host,
                        "port": self.rest_port,
                    },
                }

            logger.info("Health check endpoint added")

            # Start REST server in background
            logger.info("Starting REST server", host=self.rest_host, port=self.rest_port)
            config = uvicorn.Config(
                app,
                host=self.rest_host,
                port=self.rest_port,
                log_level="info",
            )
            self.rest_server = uvicorn.Server(config)

            logger.info("MockEmailServer started successfully")
            logger.info(
                "Server endpoints",
                smtp=f"{self.smtp_host}:{self.smtp_port}",
                rest=f"http://{self.rest_host}:{self.rest_port}",
                health=f"http://{self.rest_host}:{self.rest_port}/health",
                docs=f"http://{self.rest_host}:{self.rest_port}/docs",
            )

            # Run REST server
            await self.rest_server.serve()

        except Exception as e:
            logger.error(
                "Failed to start MockEmailServer",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Failed to start MockEmailServer: {e}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def stop(self) -> None:
        """
        Stop both SMTP and REST servers gracefully.

        Raises:
            EmailError: If server shutdown fails.
        """
        logger.info("Stopping MockEmailServer")

        try:
            # Stop SMTP server
            if self.smtp_controller:
                logger.info("Stopping SMTP server")
                self.smtp_controller.stop()
                self.smtp_controller = None
                logger.info("SMTP server stopped")

            # Stop REST server
            if self.rest_server:
                logger.info("Stopping REST server")
                self.rest_server.should_exit = True
                self.rest_server = None
                logger.info("REST server stopped")

            logger.info("MockEmailServer stopped successfully")

        except Exception as e:
            logger.error(
                "Error during server shutdown",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Error during server shutdown: {e}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e


async def main() -> None:
    """
    Main entry point for running the server standalone.

    Initializes logging, creates the server, and runs until interrupted.
    """
    # Setup logging
    settings = get_settings()
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name="mock-email-server",
    )

    logger.info("Starting Mock Email Server")

    # Create and start server
    server = MockEmailServer()

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(
            "Server error", error=str(e), error_type=type(e).__name__
        )
        raise
    finally:
        await server.stop()
        logger.info("Mock Email Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
