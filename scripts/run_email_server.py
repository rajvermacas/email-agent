#!/usr/bin/env python
"""
Runner script for the Mock Email Server.

This script starts the mock email server with SMTP and REST API
endpoints for development and testing.

Usage:
    python scripts/run_email_server.py

    # With custom ports:
    SMTP_PORT=2525 EMAIL_SERVER_PORT=8026 python scripts/run_email_server.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from info_agent.config import get_settings
from info_agent.utils.logging import get_logger, setup_logging


async def main() -> None:
    """Main entry point for running the email server."""
    settings = get_settings()

    # Setup logging
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name="mock-email-server",
    )

    logger = get_logger(__name__)
    logger.info("Starting Mock Email Server runner script")
    logger.info(
        "Configuration",
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        rest_port=settings.email_server_port,
        db_path=settings.email_db_path,
        webhook_url=settings.email_webhook_url,
    )

    # Import and create the email server
    from info_agent.email.server import MockEmailServer

    server = MockEmailServer()

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Email server stopped by user")
    except Exception as e:
        logger.error("Email server error", error=str(e))
        raise
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
