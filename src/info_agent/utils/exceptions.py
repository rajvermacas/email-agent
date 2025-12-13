"""
Custom exception hierarchy for Info-Agent.

This module defines all custom exceptions used throughout the system.
Each exception includes context information for debugging and logging.

Exception Hierarchy:
    InfoAgentError (base)
    ├── ConfigurationError
    ├── LLMError
    │   ├── LLMProviderNotFoundError
    │   ├── LLMRateLimitError
    │   └── LLMResponseError
    ├── A2AError
    │   ├── A2ARegistrationError
    │   └── A2ATaskError
    ├── WorkflowError
    │   └── WorkflowStateError
    ├── EmailServerError
    │   ├── EmailDeliveryError
    │   └── EmailParsingError
    ├── ValidationError
    │   ├── DocumentParsingError
    │   └── PythonExecutionError
    ├── EscalationError
    └── TimeoutError
"""

from typing import Any, Optional


class InfoAgentError(Exception):
    """
    Base exception for all Info-Agent errors.

    All custom exceptions in the system inherit from this class.
    Provides consistent error formatting and context tracking.
    """

    def __init__(
        self,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """
        Initialize the exception.

        Args:
            message: Human-readable error message.
            details: Additional context as key-value pairs.
            cause: The underlying exception that caused this error.
        """
        self.message = message
        self.details = details or {}
        self.cause = cause
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation with details."""
        base = self.message
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base = f"{base} [{detail_str}]"
        if self.cause:
            base = f"{base} (caused by: {self.cause})"
        return base

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================


class ConfigurationError(InfoAgentError):
    """Raised when there is a configuration problem."""

    def __init__(
        self,
        message: str,
        *,
        field_name: Optional[str] = None,
        expected_value: Optional[str] = None,
        actual_value: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize configuration error.

        Args:
            message: Error description.
            field_name: Name of the misconfigured field.
            expected_value: What the field should be.
            actual_value: What the field actually is.
        """
        details = kwargs.pop("details", {})
        if field_name:
            details["field_name"] = field_name
        if expected_value:
            details["expected_value"] = expected_value
        if actual_value:
            details["actual_value"] = actual_value
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# LLM ERRORS
# =============================================================================


class LLMError(InfoAgentError):
    """Base exception for LLM-related errors."""

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize LLM error.

        Args:
            message: Error description.
            provider: LLM provider name.
            model: Model identifier.
        """
        details = kwargs.pop("details", {})
        if provider:
            details["provider"] = provider
        if model:
            details["model"] = model
        super().__init__(message, details=details, **kwargs)


class LLMProviderNotFoundError(LLMError):
    """Raised when the specified LLM provider is not available."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM API rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize rate limit error.

        Args:
            message: Error description.
            retry_after_seconds: Suggested wait time before retry.
        """
        details = kwargs.pop("details", {})
        if retry_after_seconds:
            details["retry_after_seconds"] = retry_after_seconds
        super().__init__(message, details=details, **kwargs)


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or unexpected."""

    def __init__(
        self,
        message: str,
        *,
        response_content: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize response error.

        Args:
            message: Error description.
            response_content: The problematic response content.
        """
        details = kwargs.pop("details", {})
        if response_content:
            # Truncate long responses
            details["response_content"] = (
                response_content[:500] + "..."
                if len(response_content) > 500
                else response_content
            )
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# A2A ERRORS
# =============================================================================


class A2AError(InfoAgentError):
    """Base exception for A2A protocol errors."""

    def __init__(
        self,
        message: str,
        *,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize A2A error.

        Args:
            message: Error description.
            agent_id: ID of the agent involved.
            agent_name: Name of the agent involved.
        """
        details = kwargs.pop("details", {})
        if agent_id:
            details["agent_id"] = agent_id
        if agent_name:
            details["agent_name"] = agent_name
        super().__init__(message, details=details, **kwargs)


class A2ARegistrationError(A2AError):
    """Raised when agent registration fails."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize registration error.

        Args:
            message: Error description.
            endpoint: The endpoint that failed to register.
        """
        details = kwargs.pop("details", {})
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(message, details=details, **kwargs)


class A2ATaskError(A2AError):
    """Raised when A2A task execution fails."""

    def __init__(
        self,
        message: str,
        *,
        task_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        task_status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize task error.

        Args:
            message: Error description.
            task_id: ID of the failed task.
            skill_id: ID of the skill being executed.
            task_status: Current status of the task.
        """
        details = kwargs.pop("details", {})
        if task_id:
            details["task_id"] = task_id
        if skill_id:
            details["skill_id"] = skill_id
        if task_status:
            details["task_status"] = task_status
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# WORKFLOW ERRORS
# =============================================================================


class WorkflowError(InfoAgentError):
    """Base exception for workflow errors."""

    def __init__(
        self,
        message: str,
        *,
        workflow_id: Optional[str] = None,
        current_node: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize workflow error.

        Args:
            message: Error description.
            workflow_id: ID of the workflow.
            current_node: Current workflow node/step.
        """
        details = kwargs.pop("details", {})
        if workflow_id:
            details["workflow_id"] = workflow_id
        if current_node:
            details["current_node"] = current_node
        super().__init__(message, details=details, **kwargs)


class WorkflowStateError(WorkflowError):
    """Raised when workflow state is invalid or corrupted."""

    def __init__(
        self,
        message: str,
        *,
        expected_status: Optional[str] = None,
        actual_status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize state error.

        Args:
            message: Error description.
            expected_status: What status was expected.
            actual_status: What status was found.
        """
        details = kwargs.pop("details", {})
        if expected_status:
            details["expected_status"] = expected_status
        if actual_status:
            details["actual_status"] = actual_status
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# EMAIL ERRORS
# =============================================================================


class EmailServerError(InfoAgentError):
    """Base exception for email server errors."""

    def __init__(
        self,
        message: str,
        *,
        email_address: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize email error.

        Args:
            message: Error description.
            email_address: Email address involved.
        """
        details = kwargs.pop("details", {})
        if email_address:
            details["email_address"] = email_address
        super().__init__(message, details=details, **kwargs)


class EmailDeliveryError(EmailServerError):
    """Raised when email delivery fails."""

    def __init__(
        self,
        message: str,
        *,
        recipient: Optional[str] = None,
        smtp_code: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize delivery error.

        Args:
            message: Error description.
            recipient: Target recipient address.
            smtp_code: SMTP error code.
        """
        details = kwargs.pop("details", {})
        if recipient:
            details["recipient"] = recipient
        if smtp_code:
            details["smtp_code"] = smtp_code
        super().__init__(message, details=details, **kwargs)


class EmailParsingError(EmailServerError):
    """Raised when email parsing fails."""

    def __init__(
        self,
        message: str,
        *,
        message_id: Optional[str] = None,
        parsing_stage: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize parsing error.

        Args:
            message: Error description.
            message_id: ID of the message being parsed.
            parsing_stage: Stage where parsing failed.
        """
        details = kwargs.pop("details", {})
        if message_id:
            details["message_id"] = message_id
        if parsing_stage:
            details["parsing_stage"] = parsing_stage
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# VALIDATION ERRORS
# =============================================================================


class ValidationError(InfoAgentError):
    """Base exception for validation errors."""

    def __init__(
        self,
        message: str,
        *,
        document_name: Optional[str] = None,
        validation_type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize validation error.

        Args:
            message: Error description.
            document_name: Name of document being validated.
            validation_type: Type of validation being performed.
        """
        details = kwargs.pop("details", {})
        if document_name:
            details["document_name"] = document_name
        if validation_type:
            details["validation_type"] = validation_type
        super().__init__(message, details=details, **kwargs)


class DocumentParsingError(ValidationError):
    """Raised when document parsing fails."""

    def __init__(
        self,
        message: str,
        *,
        file_type: Optional[str] = None,
        file_size: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize document parsing error.

        Args:
            message: Error description.
            file_type: Type of file being parsed.
            file_size: Size of the file in bytes.
        """
        details = kwargs.pop("details", {})
        if file_type:
            details["file_type"] = file_type
        if file_size:
            details["file_size"] = file_size
        super().__init__(message, details=details, **kwargs)


class PythonExecutionError(ValidationError):
    """Raised when Python code execution fails in validation agent."""

    def __init__(
        self,
        message: str,
        *,
        script_name: Optional[str] = None,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Python execution error.

        Args:
            message: Error description.
            script_name: Name of the script that failed.
            exit_code: Process exit code.
            stderr: Standard error output.
        """
        details = kwargs.pop("details", {})
        if script_name:
            details["script_name"] = script_name
        if exit_code is not None:
            details["exit_code"] = exit_code
        if stderr:
            # Truncate long stderr
            details["stderr"] = stderr[:1000] + "..." if len(stderr) > 1000 else stderr
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# ESCALATION & TIMEOUT ERRORS
# =============================================================================


class EscalationError(InfoAgentError):
    """Raised when escalation fails."""

    def __init__(
        self,
        message: str,
        *,
        escalation_target: Optional[str] = None,
        escalation_reason: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize escalation error.

        Args:
            message: Error description.
            escalation_target: Target of the escalation (email/person).
            escalation_reason: Why escalation was triggered.
        """
        details = kwargs.pop("details", {})
        if escalation_target:
            details["escalation_target"] = escalation_target
        if escalation_reason:
            details["escalation_reason"] = escalation_reason
        super().__init__(message, details=details, **kwargs)


class TimeoutError(InfoAgentError):
    """Raised when an operation times out."""

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize timeout error.

        Args:
            message: Error description.
            timeout_seconds: The timeout duration that was exceeded.
            operation: The operation that timed out.
        """
        details = kwargs.pop("details", {})
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        if operation:
            details["operation"] = operation
        super().__init__(message, details=details, **kwargs)
