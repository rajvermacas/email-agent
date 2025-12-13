"""
Utility modules for Info-Agent.

This package provides common utilities including:
- Structured logging with structlog
- Custom exception hierarchy
- Helper functions for common operations
"""

from info_agent.utils.exceptions import (
    A2AError,
    A2ARegistrationError,
    A2ATaskError,
    ConfigurationError,
    DocumentParsingError,
    EmailDeliveryError,
    EmailParsingError,
    EmailServerError,
    EscalationError,
    InfoAgentError,
    LLMError,
    LLMProviderNotFoundError,
    LLMRateLimitError,
    LLMResponseError,
    PythonExecutionError,
    TimeoutError,
    ValidationError,
    WorkflowError,
    WorkflowStateError,
)
from info_agent.utils.helpers import (
    generate_uuid,
    get_current_timestamp,
    get_current_timestamp_iso,
    safe_json_loads,
    truncate_string,
)
from info_agent.utils.logging import get_logger, setup_logging

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "InfoAgentError",
    "ConfigurationError",
    "LLMError",
    "LLMProviderNotFoundError",
    "LLMRateLimitError",
    "LLMResponseError",
    "A2AError",
    "A2ARegistrationError",
    "A2ATaskError",
    "WorkflowError",
    "WorkflowStateError",
    "EmailServerError",
    "EmailDeliveryError",
    "EmailParsingError",
    "ValidationError",
    "DocumentParsingError",
    "PythonExecutionError",
    "EscalationError",
    "TimeoutError",
    # Helpers
    "generate_uuid",
    "get_current_timestamp",
    "get_current_timestamp_iso",
    "truncate_string",
    "safe_json_loads",
]
