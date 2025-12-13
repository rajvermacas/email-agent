"""
Structured logging configuration for Info-Agent.

This module provides centralized logging setup using structlog for
structured logging with JSON or console output formats.

Usage:
    from info_agent.utils.logging import setup_logging, get_logger

    # Setup at application startup
    setup_logging()

    # Get logger for module
    logger = get_logger(__name__)
    logger.info("Starting workflow", workflow_id="wf-123")
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import Processor

# Global flag to track if logging has been configured
_logging_configured = False


def setup_logging(
    level: str = "INFO",
    log_format: str = "console",
    service_name: str = "info-agent",
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format - "json" for production, "console" for development.
        service_name: Name of the service for log context.

    Raises:
        ValueError: If level or log_format is invalid.
    """
    global _logging_configured

    # Validate inputs
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if level.upper() not in valid_levels:
        raise ValueError(f"Invalid log level: {level}. Must be one of {valid_levels}")

    valid_formats = {"json", "console"}
    if log_format.lower() not in valid_formats:
        raise ValueError(f"Invalid log format: {log_format}. Must be one of {valid_formats}")

    log_level = getattr(logging, level.upper())

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout,
        force=True,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosmtpd").setLevel(logging.WARNING)

    # Build processor chain
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _add_service_name(service_name),
    ]

    # Choose renderer based on format
    if log_format.lower() == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure formatter for stdlib logging
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Apply formatter to root handler
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)

    _logging_configured = True

    # Log startup
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        level=level,
        format=log_format,
        service=service_name,
    )


def _add_service_name(service_name: str) -> Processor:
    """
    Create a processor that adds service name to log entries.

    Args:
        service_name: Name of the service.

    Returns:
        Processor function.
    """
    def processor(
        logger: logging.Logger,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict["service"] = service_name
        return event_dict

    return processor


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    If logging hasn't been configured yet, this will configure it with defaults.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Bound structlog logger.
    """
    global _logging_configured

    if not _logging_configured:
        # Configure with defaults if not already done
        setup_logging()

    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables that will be included in all subsequent log entries.

    This is useful for adding request-scoped context like workflow_id or
    request_id that should appear in all logs within a request.

    Args:
        **kwargs: Key-value pairs to bind to the logging context.

    Example:
        bind_context(workflow_id="wf-123", user="admin")
        logger.info("Processing")  # Will include workflow_id and user
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """
    Remove context variables from the logging context.

    Args:
        *keys: Keys to remove from the context.
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all context variables from the logging context."""
    structlog.contextvars.clear_contextvars()
