"""
Custom exceptions for Info-Agent.

This module provides a hierarchy of custom exceptions with:
- Unique error codes for each exception type
- Detailed error information via the `details` dict
- Consistent error message formatting

All exceptions inherit from InfoAgentError which provides the base structure.

Usage:
    from info_agent.utils.exceptions import WorkflowNotFoundError

    raise WorkflowNotFoundError(
        workflow_id="wf-123",
        details={"searched_in": "active_workflows"}
    )
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InfoAgentError(Exception):
    """
    Base exception for all Info-Agent errors.

    Attributes:
        message: Human-readable error message.
        code: Unique error code string (e.g., "WORKFLOW_NOT_FOUND").
        details: Additional error context as a dictionary.
    """

    def __init__(
        self,
        message: str,
        code: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the exception.

        Args:
            message: Human-readable error message.
            code: Unique error code string.
            details: Additional error context.
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

        logger.error(
            f"[{self.code}] {self.message}",
            extra={"error_code": self.code, "error_details": self.details},
        )

    def __str__(self) -> str:
        """Return formatted error string."""
        if self.details:
            return f"[{self.code}] {self.message} - Details: {self.details}"
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        """Return repr string."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"details={self.details!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to dictionary for API responses.

        Returns:
            Dictionary with error information.
        """
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ConfigurationError(InfoAgentError):
    """
    Raised when configuration is invalid or missing.

    Error codes:
    - CONFIG_MISSING: Required configuration value not provided
    - CONFIG_INVALID: Configuration value is invalid
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize configuration error.

        Args:
            message: Error description.
            config_key: Name of the problematic configuration key.
            details: Additional context.
        """
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        super().__init__(
            message=message,
            code="CONFIG_ERROR",
            details=error_details,
        )
        self.config_key = config_key


class WorkflowNotFoundError(InfoAgentError):
    """Raised when a workflow cannot be found."""

    def __init__(
        self,
        workflow_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize workflow not found error.

        Args:
            workflow_id: ID of the workflow that was not found.
            details: Additional context.
        """
        error_details = details or {}
        error_details["workflow_id"] = workflow_id

        super().__init__(
            message=f"Workflow not found: {workflow_id}",
            code="WORKFLOW_NOT_FOUND",
            details=error_details,
        )
        self.workflow_id = workflow_id


class WorkflowError(InfoAgentError):
    """Raised when a workflow operation fails."""

    def __init__(
        self,
        message: str,
        workflow_id: str | None = None,
        step: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize workflow error.

        Args:
            message: Error description.
            workflow_id: ID of the affected workflow.
            step: Current workflow step where error occurred.
            details: Additional context.
        """
        error_details = details or {}
        if workflow_id:
            error_details["workflow_id"] = workflow_id
        if step:
            error_details["step"] = step

        super().__init__(
            message=message,
            code="WORKFLOW_ERROR",
            details=error_details,
        )
        self.workflow_id = workflow_id
        self.step = step


class AgentNotFoundError(InfoAgentError):
    """Raised when an agent cannot be found in the registry."""

    def __init__(
        self,
        agent_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize agent not found error.

        Args:
            agent_name: Name of the agent that was not found.
            details: Additional context.
        """
        error_details = details or {}
        error_details["agent_name"] = agent_name

        super().__init__(
            message=f"Agent not found in registry: {agent_name}",
            code="AGENT_NOT_FOUND",
            details=error_details,
        )
        self.agent_name = agent_name


class AgentCommunicationError(InfoAgentError):
    """Raised when communication with an agent fails."""

    def __init__(
        self,
        message: str,
        agent_name: str,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize agent communication error.

        Args:
            message: Error description.
            agent_name: Name of the agent.
            endpoint: Agent endpoint URL.
            details: Additional context.
        """
        error_details = details or {}
        error_details["agent_name"] = agent_name
        if endpoint:
            error_details["endpoint"] = endpoint

        super().__init__(
            message=f"Agent communication failed ({agent_name}): {message}",
            code="AGENT_COMMUNICATION_ERROR",
            details=error_details,
        )
        self.agent_name = agent_name
        self.endpoint = endpoint


class LLMError(InfoAgentError):
    """Raised when an LLM operation fails."""

    def __init__(
        self,
        message: str,
        model: str | None = None,
        original_error: Exception | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize LLM error.

        Args:
            message: Error description.
            model: LLM model name.
            original_error: Original exception if any.
            details: Additional context.
        """
        error_details = details or {}
        if model:
            error_details["model"] = model
        if original_error:
            error_details["original_error"] = str(original_error)
            error_details["original_error_type"] = type(original_error).__name__

        super().__init__(
            message=f"LLM error: {message}",
            code="LLM_ERROR",
            details=error_details,
        )
        self.model = model
        self.original_error = original_error


class A2AError(InfoAgentError):
    """Raised when an A2A protocol operation fails."""

    def __init__(
        self,
        message: str,
        agent_name: str | None = None,
        task_id: str | None = None,
        skill_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize A2A error.

        Args:
            message: Error description.
            agent_name: Name of the agent involved.
            task_id: A2A task ID if applicable.
            skill_id: A2A skill ID if applicable.
            details: Additional context.
        """
        error_details = details or {}
        if agent_name:
            error_details["agent_name"] = agent_name
        if task_id:
            error_details["task_id"] = task_id
        if skill_id:
            error_details["skill_id"] = skill_id

        super().__init__(
            message=f"A2A error: {message}",
            code="A2A_ERROR",
            details=error_details,
        )
        self.agent_name = agent_name
        self.task_id = task_id
        self.skill_id = skill_id


class EmailError(InfoAgentError):
    """Raised when an email operation fails."""

    def __init__(
        self,
        message: str,
        email_id: str | None = None,
        thread_id: str | None = None,
        recipient: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize email error.

        Args:
            message: Error description.
            email_id: Email message ID.
            thread_id: Email thread ID.
            recipient: Recipient email address.
            details: Additional context.
        """
        error_details = details or {}
        if email_id:
            error_details["email_id"] = email_id
        if thread_id:
            error_details["thread_id"] = thread_id
        if recipient:
            error_details["recipient"] = recipient

        super().__init__(
            message=f"Email error: {message}",
            code="EMAIL_ERROR",
            details=error_details,
        )
        self.email_id = email_id
        self.thread_id = thread_id
        self.recipient = recipient


class ValidationError(InfoAgentError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize validation error.

        Args:
            message: Error description.
            field: Name of the invalid field.
            value: The invalid value (be careful with sensitive data).
            details: Additional context.
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            # Only include value if it's not potentially sensitive
            error_details["value"] = str(value)[:100]  # Truncate long values

        super().__init__(
            message=f"Validation error: {message}",
            code="VALIDATION_ERROR",
            details=error_details,
        )
        self.field = field
        self.value = value


class StorageError(InfoAgentError):
    """Raised when a storage operation fails."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize storage error.

        Args:
            message: Error description.
            operation: Storage operation (e.g., "save", "load", "delete").
            entity_type: Type of entity (e.g., "workflow", "email").
            entity_id: Entity ID.
            details: Additional context.
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if entity_type:
            error_details["entity_type"] = entity_type
        if entity_id:
            error_details["entity_id"] = entity_id

        super().__init__(
            message=f"Storage error: {message}",
            code="STORAGE_ERROR",
            details=error_details,
        )
        self.operation = operation
        self.entity_type = entity_type
        self.entity_id = entity_id
