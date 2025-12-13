"""
Utility modules for Info-Agent.

This package provides shared utilities including:
- Logging: Structured logging configuration
- Exceptions: Custom exception classes with error codes
"""

from info_agent.utils.exceptions import (
    InfoAgentError,
    ConfigurationError,
    WorkflowNotFoundError,
    WorkflowError,
    AgentNotFoundError,
    AgentCommunicationError,
    LLMError,
    A2AError,
    EmailError,
    ValidationError as InfoAgentValidationError,
    StorageError,
)
from info_agent.utils.logging import setup_logging, get_logger

__all__ = [
    # Exceptions
    "InfoAgentError",
    "ConfigurationError",
    "WorkflowNotFoundError",
    "WorkflowError",
    "AgentNotFoundError",
    "AgentCommunicationError",
    "LLMError",
    "A2AError",
    "EmailError",
    "InfoAgentValidationError",
    "StorageError",
    # Logging
    "setup_logging",
    "get_logger",
]
