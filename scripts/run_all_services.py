#!/usr/bin/env python
"""
Runner script to start all Info-Agent services.

This script starts:
1. Mock Email Server (SMTP + REST)
2. FastAPI Gateway (includes Supervisor Agent)
3. Mail Agent (A2A worker)

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

    # Create logs directory if it doesn't exist
    from pathlib import Path
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Setup main logging to console
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name="info-agent-orchestrator",
    )

    logger = get_logger(__name__)
    logger.info("Starting all Info-Agent services")
    logger.info(f"Log files will be written to: {logs_dir.absolute()}")

    # Track running tasks and server instances for cleanup
    tasks: list[asyncio.Task] = []
    shutdown_event = asyncio.Event()

    # Store server instances at module scope for cleanup
    email_server = None
    gateway_server = None
    mail_agent_server = None
    mail_agent = None

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
        from info_agent.agents.mail.agent import MailAgent
        import uvicorn
        from info_agent.main import app

        # Start Mock Email Server
        logger.info("Starting Mock Email Server")
        email_server = MockEmailServer()

        # Create email server task (but don't await yet)
        async def run_email_server() -> None:
            nonlocal email_server
            import logging

            # Add file handler for email server logs
            email_log_file = logs_dir / "email_server.log"
            file_handler = logging.FileHandler(email_log_file, mode='a')
            file_handler.setLevel(logging.DEBUG)

            # Get email server related loggers
            email_loggers = [
                logging.getLogger("info_agent.email"),
                logging.getLogger("aiosmtpd"),
            ]
            for log in email_loggers:
                log.addHandler(file_handler)

            logger.info(f"Email Server logs → {email_log_file}")

            try:
                await email_server.start()
            except asyncio.CancelledError:
                logger.info("Email server task cancelled, shutting down gracefully...")
                if email_server is not None:
                    await email_server.stop()
                logger.info("Email server stopped")
                # Clean up file handler
                for log in email_loggers:
                    log.removeHandler(file_handler)
                file_handler.close()
                raise
            except Exception as e:
                logger.error("Email server error", error=str(e))
                if email_server is not None:
                    await email_server.stop()
                # Clean up file handler
                for log in email_loggers:
                    log.removeHandler(file_handler)
                file_handler.close()
                raise

        # Create gateway server task
        async def run_gateway() -> None:
            nonlocal gateway_server
            import logging

            # Add file handler for gateway logs
            gateway_log_file = logs_dir / "gateway.log"
            file_handler = logging.FileHandler(gateway_log_file, mode='a')
            file_handler.setLevel(logging.DEBUG)

            # Get gateway related loggers
            gateway_loggers = [
                logging.getLogger("info_agent.main"),
                logging.getLogger("info_agent.api"),
                logging.getLogger("info_agent.agents.supervisor"),
                logging.getLogger("info_agent.workflow"),
                logging.getLogger("info_agent.a2a"),
                logging.getLogger("uvicorn"),
                logging.getLogger("uvicorn.error"),
            ]
            for log in gateway_loggers:
                log.addHandler(file_handler)

            logger.info(f"Gateway Server logs → {gateway_log_file}")

            config = uvicorn.Config(
                app,
                host=settings.host,
                port=settings.gateway_port,
                log_level=settings.log_level.lower(),
            )
            gateway_server = uvicorn.Server(config)
            try:
                await gateway_server.serve()
            except asyncio.CancelledError:
                logger.info("Gateway server task cancelled, shutting down gracefully...")
                if gateway_server is not None:
                    gateway_server.should_exit = True
                logger.info("Gateway server stopped")
                # Clean up file handler
                for log in gateway_loggers:
                    log.removeHandler(file_handler)
                file_handler.close()
                raise
            except Exception as e:
                logger.error("Gateway server error", error=str(e))
                if gateway_server is not None:
                    gateway_server.should_exit = True
                # Clean up file handler
                for log in gateway_loggers:
                    log.removeHandler(file_handler)
                file_handler.close()
                raise

        # Create Mail Agent task
        async def run_mail_agent() -> None:
            nonlocal mail_agent, mail_agent_server
            import logging

            # Add file handler for mail agent logs
            mail_agent_log_file = logs_dir / "mail_agent.log"
            file_handler = logging.FileHandler(mail_agent_log_file, mode='a')
            file_handler.setLevel(logging.DEBUG)

            # Get mail agent related loggers
            mail_agent_loggers = [
                logging.getLogger("info_agent.agents.mail"),
                logging.getLogger("aiosmtplib"),
            ]
            for log in mail_agent_loggers:
                log.addHandler(file_handler)

            logger.info(f"Mail Agent logs → {mail_agent_log_file}")

            try:
                # Wait for Gateway and Email Server to be ready
                logger.info("Waiting for Gateway and SMTP server to be ready...")
                await asyncio.sleep(3)

                logger.info("Creating Mail Agent instance")
                mail_agent = MailAgent(settings)

                logger.info("Starting Mail Agent and registering with A2A registry")
                await mail_agent.start()

                logger.info("Starting Mail Agent A2A server")
                config = uvicorn.Config(
                    mail_agent.app,
                    host=settings.host,
                    port=settings.mail_agent_port,
                    log_level=settings.log_level.lower(),
                )
                mail_agent_server = uvicorn.Server(config)
                await mail_agent_server.serve()
            except asyncio.CancelledError:
                logger.info("Mail Agent task cancelled, shutting down gracefully...")
                if mail_agent is not None:
                    await mail_agent.shutdown()
                if mail_agent_server is not None:
                    mail_agent_server.should_exit = True
                logger.info("Mail Agent stopped")
                # Clean up file handler
                for log in mail_agent_loggers:
                    log.removeHandler(file_handler)
                file_handler.close()
                raise
            except Exception as e:
                logger.error("Mail Agent error", error=str(e))
                if mail_agent is not None:
                    await mail_agent.shutdown()
                if mail_agent_server is not None:
                    mail_agent_server.should_exit = True
                # Clean up file handler
                for log in mail_agent_loggers:
                    log.removeHandler(file_handler)
                file_handler.close()
                raise

        # Start all services
        tasks.append(asyncio.create_task(run_email_server()))
        tasks.append(asyncio.create_task(run_gateway()))
        tasks.append(asyncio.create_task(run_mail_agent()))

        logger.info("All services started")
        logger.info(
            "Service endpoints",
            gateway=f"http://{settings.host}:{settings.gateway_port}",
            gateway_docs=f"http://{settings.host}:{settings.gateway_port}/docs",
            mail_agent=f"http://{settings.host}:{settings.mail_agent_port}",
            mail_agent_health=f"http://{settings.host}:{settings.mail_agent_port}/health",
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

        # Wait for tasks to complete with timeout
        if tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some tasks did not complete within timeout")

        # Ensure all servers are stopped (backup cleanup)
        logger.info("Performing final cleanup...")
        if email_server is not None:
            try:
                await email_server.stop()
                logger.info("Email server final cleanup complete")
            except Exception as e:
                logger.warning("Error during email server cleanup", error=str(e))

        if gateway_server is not None:
            try:
                gateway_server.should_exit = True
                logger.info("Gateway server final cleanup complete")
            except Exception as e:
                logger.warning("Error during gateway server cleanup", error=str(e))

        if mail_agent is not None:
            try:
                await mail_agent.shutdown()
                logger.info("Mail agent final cleanup complete")
            except Exception as e:
                logger.warning("Error during mail agent cleanup", error=str(e))

        if mail_agent_server is not None:
            try:
                mail_agent_server.should_exit = True
                logger.info("Mail agent server final cleanup complete")
            except Exception as e:
                logger.warning("Error during mail agent server cleanup", error=str(e))

        logger.info("All services stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
