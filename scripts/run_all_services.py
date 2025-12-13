#!/usr/bin/env python
"""
Runner script to start all Info-Agent services.

This script starts:
1. Mock Email Server (SMTP + REST)
2. FastAPI Gateway

Usage:
    python scripts/run_all_services.py

    # Stop with Ctrl+C
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from info_agent.config import get_settings
from info_agent.utils.logging import get_logger, setup_logging


async def main() -> None:
    """Main entry point for running all services."""
    settings = get_settings()

    # Setup logging
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name="info-agent-all",
    )

    logger = get_logger(__name__)
    logger.info("Starting all Info-Agent services")

    # Track running tasks
    tasks: list[asyncio.Task] = []
    shutdown_event = asyncio.Event()

    def handle_shutdown(sig: signal.Signals) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig.name}, shutting down...")
        shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_shutdown, sig)

    try:
        # Import services
        from info_agent.email.server import MockEmailServer
        import uvicorn
        from info_agent.main import app

        # Start Mock Email Server
        logger.info("Starting Mock Email Server")
        email_server = MockEmailServer()

        # Create email server task (but don't await yet)
        async def run_email_server() -> None:
            try:
                await email_server.start()
            except asyncio.CancelledError:
                logger.info("Email server task cancelled")
            except Exception as e:
                logger.error("Email server error", error=str(e))

        # Create gateway server task
        async def run_gateway() -> None:
            config = uvicorn.Config(
                app,
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level.lower(),
            )
            server = uvicorn.Server(config)
            try:
                await server.serve()
            except asyncio.CancelledError:
                logger.info("Gateway server task cancelled")
            except Exception as e:
                logger.error("Gateway server error", error=str(e))

        # Start both services
        tasks.append(asyncio.create_task(run_email_server()))
        tasks.append(asyncio.create_task(run_gateway()))

        logger.info("All services started")
        logger.info(
            "Service endpoints",
            gateway=f"http://{settings.host}:{settings.port}",
            gateway_docs=f"http://{settings.host}:{settings.port}/docs",
            email_smtp=f"{settings.smtp_host}:{settings.smtp_port}",
            email_rest=f"http://{settings.host}:{settings.email_server_port}",
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

    except Exception as e:
        logger.error("Service startup error", error=str(e))
        raise
    finally:
        # Cancel all tasks
        logger.info("Cancelling all service tasks")
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("All services stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
