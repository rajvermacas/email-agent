"""
Unit tests for custom exceptions module.

Tests the exception hierarchy, context information,
and serialization capabilities.
"""

import pytest

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


class TestInfoAgentError:
    """Tests for base InfoAgentError."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = InfoAgentError("Something went wrong")

        assert error.message == "Something went wrong"
        assert error.details == {}
        assert error.cause is None

    def test_error_with_details(self) -> None:
        """Test error with details."""
        error = InfoAgentError("Error occurred", details={"key": "value", "count": 42})

        assert error.details == {"key": "value", "count": 42}
        assert "key=value" in str(error)
        assert "count=42" in str(error)

    def test_error_with_cause(self) -> None:
        """Test error with cause."""
        cause = ValueError("Original error")
        error = InfoAgentError("Wrapped error", cause=cause)

        assert error.cause is cause
        assert "caused by: Original error" in str(error)

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        cause = ValueError("Original")
        error = InfoAgentError("Test error", details={"key": "val"}, cause=cause)

        result = error.to_dict()

        assert result["error_type"] == "InfoAgentError"
        assert result["message"] == "Test error"
        assert result["details"] == {"key": "val"}
        assert "Original" in result["cause"]

    def test_to_dict_without_cause(self) -> None:
        """Test to_dict without cause."""
        error = InfoAgentError("Test error")

        result = error.to_dict()
        assert result["cause"] is None


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_with_field_info(self) -> None:
        """Test error with field information."""
        error = ConfigurationError(
            "Invalid configuration",
            field_name="api_key",
            expected_value="non-empty string",
        )

        assert error.details["field_name"] == "api_key"
        assert error.details["expected_value"] == "non-empty string"

    def test_with_actual_value(self) -> None:
        """Test error with actual value (non-empty)."""
        error = ConfigurationError(
            "Invalid configuration",
            field_name="api_key",
            actual_value="invalid_key",
        )

        assert error.details["field_name"] == "api_key"
        assert error.details["actual_value"] == "invalid_key"

    def test_inheritance(self) -> None:
        """Test ConfigurationError inherits from InfoAgentError."""
        error = ConfigurationError("Config error")
        assert isinstance(error, InfoAgentError)


class TestLLMErrors:
    """Tests for LLM-related errors."""

    def test_llm_error_with_provider_info(self) -> None:
        """Test LLMError with provider information."""
        error = LLMError("API call failed", provider="openai", model="gpt-4")

        assert error.details["provider"] == "openai"
        assert error.details["model"] == "gpt-4"

    def test_llm_provider_not_found(self) -> None:
        """Test LLMProviderNotFoundError."""
        error = LLMProviderNotFoundError("Provider not found", provider="unknown")

        assert isinstance(error, LLMError)
        assert error.details["provider"] == "unknown"

    def test_llm_rate_limit_error(self) -> None:
        """Test LLMRateLimitError with retry info."""
        error = LLMRateLimitError(
            "Rate limited", provider="openai", retry_after_seconds=60
        )

        assert error.details["retry_after_seconds"] == 60
        assert isinstance(error, LLMError)

    def test_llm_response_error(self) -> None:
        """Test LLMResponseError with response content."""
        error = LLMResponseError(
            "Invalid response", response_content="This is an invalid response"
        )

        assert "response_content" in error.details

    def test_llm_response_error_truncation(self) -> None:
        """Test response content truncation for long responses."""
        long_response = "x" * 1000
        error = LLMResponseError("Invalid response", response_content=long_response)

        # Should be truncated to 500 chars + "..."
        assert len(error.details["response_content"]) == 503


class TestA2AErrors:
    """Tests for A2A protocol errors."""

    def test_a2a_error_with_agent_info(self) -> None:
        """Test A2AError with agent information."""
        error = A2AError(
            "Agent communication failed", agent_id="agent-001", agent_name="mail-agent"
        )

        assert error.details["agent_id"] == "agent-001"
        assert error.details["agent_name"] == "mail-agent"

    def test_a2a_registration_error(self) -> None:
        """Test A2ARegistrationError with endpoint."""
        error = A2ARegistrationError(
            "Registration failed",
            agent_id="agent-001",
            endpoint="http://localhost:8002",
        )

        assert error.details["endpoint"] == "http://localhost:8002"
        assert isinstance(error, A2AError)

    def test_a2a_task_error(self) -> None:
        """Test A2ATaskError with task details."""
        error = A2ATaskError(
            "Task execution failed",
            task_id="task-001",
            skill_id="send-email",
            task_status="failed",
        )

        assert error.details["task_id"] == "task-001"
        assert error.details["skill_id"] == "send-email"
        assert error.details["task_status"] == "failed"


class TestWorkflowErrors:
    """Tests for workflow errors."""

    def test_workflow_error_with_context(self) -> None:
        """Test WorkflowError with workflow context."""
        error = WorkflowError(
            "Workflow failed", workflow_id="wf-001", current_node="send_email"
        )

        assert error.details["workflow_id"] == "wf-001"
        assert error.details["current_node"] == "send_email"

    def test_workflow_state_error(self) -> None:
        """Test WorkflowStateError with status info."""
        error = WorkflowStateError(
            "Invalid state transition",
            workflow_id="wf-001",
            expected_status="executing",
            actual_status="completed",
        )

        assert error.details["expected_status"] == "executing"
        assert error.details["actual_status"] == "completed"
        assert isinstance(error, WorkflowError)


class TestEmailErrors:
    """Tests for email errors."""

    def test_email_server_error(self) -> None:
        """Test EmailServerError."""
        error = EmailServerError("Server error", email_address="test@example.com")

        assert error.details["email_address"] == "test@example.com"

    def test_email_delivery_error(self) -> None:
        """Test EmailDeliveryError with SMTP code."""
        error = EmailDeliveryError(
            "Delivery failed", recipient="test@example.com", smtp_code=550
        )

        assert error.details["recipient"] == "test@example.com"
        assert error.details["smtp_code"] == 550
        assert isinstance(error, EmailServerError)

    def test_email_parsing_error(self) -> None:
        """Test EmailParsingError with parsing stage."""
        error = EmailParsingError(
            "Parsing failed", message_id="msg-001", parsing_stage="headers"
        )

        assert error.details["message_id"] == "msg-001"
        assert error.details["parsing_stage"] == "headers"


class TestValidationErrors:
    """Tests for validation errors."""

    def test_validation_error(self) -> None:
        """Test ValidationError with document info."""
        error = ValidationError(
            "Validation failed",
            document_name="recipes.xlsx",
            validation_type="schema",
        )

        assert error.details["document_name"] == "recipes.xlsx"
        assert error.details["validation_type"] == "schema"

    def test_document_parsing_error(self) -> None:
        """Test DocumentParsingError with file info."""
        error = DocumentParsingError(
            "Cannot parse document", file_type="xlsx", file_size=15360
        )

        assert error.details["file_type"] == "xlsx"
        assert error.details["file_size"] == 15360
        assert isinstance(error, ValidationError)

    def test_python_execution_error(self) -> None:
        """Test PythonExecutionError."""
        error = PythonExecutionError(
            "Script failed",
            script_name="validate.py",
            exit_code=1,
            stderr="NameError: undefined variable",
        )

        assert error.details["script_name"] == "validate.py"
        assert error.details["exit_code"] == 1
        assert "NameError" in error.details["stderr"]

    def test_python_execution_error_stderr_truncation(self) -> None:
        """Test stderr truncation for long output."""
        long_stderr = "Error: " + "x" * 2000
        error = PythonExecutionError("Script failed", stderr=long_stderr)

        # Should be truncated to 1000 chars + "..."
        assert len(error.details["stderr"]) == 1003


class TestEscalationError:
    """Tests for EscalationError."""

    def test_escalation_error(self) -> None:
        """Test EscalationError with escalation details."""
        error = EscalationError(
            "Escalation failed",
            escalation_target="manager@example.com",
            escalation_reason="timeout",
        )

        assert error.details["escalation_target"] == "manager@example.com"
        assert error.details["escalation_reason"] == "timeout"


class TestTimeoutError:
    """Tests for TimeoutError."""

    def test_timeout_error(self) -> None:
        """Test TimeoutError with timeout details."""
        error = TimeoutError(
            "Operation timed out", timeout_seconds=30.0, operation="email_wait"
        )

        assert error.details["timeout_seconds"] == 30.0
        assert error.details["operation"] == "email_wait"


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_all_exceptions_inherit_from_base(self) -> None:
        """Test all custom exceptions inherit from InfoAgentError."""
        exception_classes = [
            ConfigurationError,
            LLMError,
            LLMProviderNotFoundError,
            LLMRateLimitError,
            LLMResponseError,
            A2AError,
            A2ARegistrationError,
            A2ATaskError,
            WorkflowError,
            WorkflowStateError,
            EmailServerError,
            EmailDeliveryError,
            EmailParsingError,
            ValidationError,
            DocumentParsingError,
            PythonExecutionError,
            EscalationError,
            TimeoutError,
        ]

        for cls in exception_classes:
            error = cls("Test message")
            assert isinstance(
                error, InfoAgentError
            ), f"{cls.__name__} should inherit from InfoAgentError"

    def test_all_exceptions_are_exception(self) -> None:
        """Test all custom exceptions are Python exceptions."""
        error = InfoAgentError("Test")
        assert isinstance(error, Exception)
