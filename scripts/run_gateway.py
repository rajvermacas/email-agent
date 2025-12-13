#!/usr/bin/env python
"""
Runner script for the Info-Agent FastAPI Gateway.

This script starts the main FastAPI gateway server with proper
configuration and logging.

Usage:
    python scripts/run_gateway.py

    # With custom port:
    PORT=8080 python scripts/run_gateway.py

    # With debug mode:
    DEBUG=true python scripts/run_gateway.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from info_agent.config import get_settings
from info_agent.utils.logging import get_logger, setup_logging


def main() -> None:
    """Main entry point for running the gateway."""
    settings = get_settings()

    # Setup logging
    setup_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name="info-agent-gateway",
    )

    logger = get_logger(__name__)
    logger.info("Starting Info-Agent Gateway runner script")
    logger.info(
        "Configuration",
        host=settings.host,
        port=settings.gateway_port,
        debug=settings.debug,
        log_level=settings.log_level,
    )

    # Import and run the main module
    from info_agent.main import main as run_main

    try:
        asyncio.run(run_main())
    except KeyboardInterrupt:
        logger.info("Gateway stopped by user")
    except Exception as e:
        logger.error("Gateway error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
