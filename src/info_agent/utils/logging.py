"""
Structured logging configuration for Info-Agent.

This module provides centralized logging setup using structlog.
Supports both JSON (production) and console (development) formats.

Usage:
    from info_agent.utils.logging import setup_logging, get_logger

    # Setup once at application startup
    setup_logging(level="INFO", format="json")

    # Get logger in any module
    logger = get_logger(__name__)
    logger.info("operation_started", workflow_id="123", user="alice")
"""

import logging
import sys
from typing import Any, Optional

import structlog
from structlog.types import Processor


def add_log_level(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add log level to event dict."""
    event_dict["level"] = method_name.upper()
    return event_dict


def add_logger_name(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add logger name to event dict."""
    record = event_dict.get("_record")
    if record:
        event_dict["logger"] = record.name
    elif hasattr(logger, "name"):
        event_dict["logger"] = logger.name
    return event_dict


def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
    show_timestamps: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format ('json' or 'console').
        show_timestamps: Whether to include timestamps in output.

    Example:
        >>> setup_logging(level="DEBUG", log_format="console")
    """
    # Convert level string to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Common processors for all formats
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if show_timestamps:
        shared_processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))

    # Format-specific processors
    if log_format.lower() == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Setup handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    # Log setup completion
    logger = get_logger(__name__)
    logger.info(
        "logging_configured",
        level=level,
        format=log_format,
        show_timestamps=show_timestamps,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        BoundLogger: Structlog bound logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_logged_in", user_id="123", ip="192.168.1.1")
    """
    return structlog.get_logger(name)


class LogContext:
    """
    Context manager for adding temporary context to log entries.

    Usage:
        with LogContext(request_id="abc123", user_id="user1"):
            logger.info("processing_request")  # Will include request_id and user_id
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize log context.

        Args:
            **kwargs: Key-value pairs to add to log context.
        """
        self.context = kwargs
        self._token: Optional[object] = None

    def __enter__(self) -> "LogContext":
        """Enter context and bind values."""
        self._token = structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and unbind values."""
        structlog.contextvars.unbind_contextvars(*self.context.keys())


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables that will be included in all subsequent log entries.

    Args:
        **kwargs: Key-value pairs to bind.

    Example:
        >>> bind_context(workflow_id="wf-123", session_id="sess-456")
        >>> logger.info("step_completed")  # Will include workflow_id and session_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """
    Unbind context variables.

    Args:
        *keys: Names of context variables to unbind.

    Example:
        >>> unbind_context("workflow_id", "session_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
