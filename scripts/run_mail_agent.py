#!/usr/bin/env python
"""
Runner script for the Mail Agent.

This script starts the Mail Agent as an A2A worker server.
The agent registers with the A2A registry on startup and handles
email-related tasks delegated by the Supervisor Agent.

Usage:
    python scripts/run_mail_agent.py

    # With custom port:
    MAIL_AGENT_PORT=8002 python scripts/run_mail_agent.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from info_agent.agents.mail.agent import MailAgent
from info_agent.config import get_settings
from info_agent.utils.logging import get_logger, setup_logging


async def main() -> None:
    """Main entry point for running the Mail Agent."""
    settings = get_settings()

    # Setup logging
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name="mail-agent",
    )

    logger = get_logger(__name__)
    logger.info("Starting Mail Agent runner script")
    logger.info(
        "Configuration",
        host=settings.host,
        port=settings.mail_agent_port,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        registry_url=settings.a2a_registry_url,
    )

    # Create Mail Agent
    logger.info("Creating Mail Agent instance")
    agent = MailAgent(settings)

    # Start the agent (registers with A2A registry)
    logger.info("Starting Mail Agent and registering with A2A registry")
    await agent.start()

    # Run the FastAPI app
    logger.info("Starting Mail Agent A2A server")
    import uvicorn

    config = uvicorn.Config(
        agent.app,
        host=settings.host,
        port=settings.mail_agent_port,
        log_level=settings.log_level.lower(),
    )

    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Mail Agent stopped by user")
    except Exception as e:
        logger.error("Mail Agent error", error=str(e))
        sys.exit(1)
    finally:
        logger.info("Shutting down Mail Agent")
        await agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
