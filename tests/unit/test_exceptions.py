"""
Unit tests for custom exceptions.

Tests all custom exception classes to ensure proper initialization,
error code assignment, message formatting, and logging behavior.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

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
    ValidationError,
    StorageError,
)


class TestInfoAgentError:
    """Tests for the base InfoAgentError class."""

    def test_init_with_message_and_code(self):
        """Test initialization with message and code."""
        with patch("info_agent.utils.exceptions.logger") as mock_logger:
            error = InfoAgentError(
                message="Test error message",
                code="TEST_ERROR",
            )

        assert error.message == "Test error message"
        assert error.code == "TEST_ERROR"
        assert error.details == {}

        # Verify logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "[TEST_ERROR] Test error message" in call_args[0][0]
        assert call_args[1]["extra"]["error_code"] == "TEST_ERROR"
        assert call_args[1]["extra"]["error_details"] == {}

    def test_init_with_details(self):
        """Test initialization with details dictionary."""
        details = {"key1": "value1", "key2": 42}

        with patch("info_agent.utils.exceptions.logger"):
            error = InfoAgentError(
                message="Test error",
                code="TEST_ERROR",
                details=details,
            )

        assert error.details == details
        assert error.details["key1"] == "value1"
        assert error.details["key2"] == 42

    def test_init_with_none_details(self):
        """Test initialization with None details defaults to empty dict."""
        with patch("info_agent.utils.exceptions.logger"):
            error = InfoAgentError(
                message="Test error",
                code="TEST_ERROR",
                details=None,
            )

        assert error.details == {}

    def test_str_without_details(self):
        """Test string representation without details."""
        with patch("info_agent.utils.exceptions.logger"):
            error = InfoAgentError(
                message="Test error",
                code="TEST_ERROR",
            )

        assert str(error) == "[TEST_ERROR] Test error"

    def test_str_with_details(self):
        """Test string representation with details."""
        with patch("info_agent.utils.exceptions.logger"):
            error = InfoAgentError(
                message="Test error",
                code="TEST_ERROR",
                details={"context": "testing"},
            )

        result = str(error)
        assert "[TEST_ERROR] Test error" in result
        assert "Details:" in result
        assert "context" in result
        assert "testing" in result

    def test_repr(self):
        """Test repr representation."""
        with patch("info_agent.utils.exceptions.logger"):
            error = InfoAgentError(
                message="Test error",
                code="TEST_ERROR",
                details={"key": "value"},
            )

        result = repr(error)
        assert "InfoAgentError(" in result
        assert "message='Test error'" in result
        assert "code='TEST_ERROR'" in result
        assert "details={'key': 'value'}" in result

    def test_to_dict(self):
        """Test conversion to dictionary."""
        with patch("info_agent.utils.exceptions.logger"):
            error = InfoAgentError(
                message="Test error",
                code="TEST_ERROR",
                details={"context": "testing"},
            )

        result = error.to_dict()

        assert result == {
            "error": {
                "code": "TEST_ERROR",
                "message": "Test error",
                "details": {"context": "testing"},
            }
        }

    def test_inherits_from_exception(self):
        """Test that InfoAgentError inherits from Exception."""
        with patch("info_agent.utils.exceptions.logger"):
            error = InfoAgentError(message="Test", code="TEST")

        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test that error can be raised and caught."""
        with patch("info_agent.utils.exceptions.logger"):
            with pytest.raises(InfoAgentError) as exc_info:
                raise InfoAgentError(message="Test", code="TEST")

            assert exc_info.value.message == "Test"
            assert exc_info.value.code == "TEST"


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_init_with_message_only(self):
        """Test initialization with message only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ConfigurationError(message="Configuration is invalid")

        assert error.message == "Configuration is invalid"
        assert error.code == "CONFIG_ERROR"
        assert error.config_key is None
        assert error.details == {}

    def test_init_with_config_key(self):
        """Test initialization with config key."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ConfigurationError(
                message="Missing required configuration",
                config_key="database_url",
            )

        assert error.message == "Missing required configuration"
        assert error.code == "CONFIG_ERROR"
        assert error.config_key == "database_url"
        assert error.details["config_key"] == "database_url"

    def test_init_with_config_key_and_details(self):
        """Test initialization with both config_key and details."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ConfigurationError(
                message="Invalid configuration",
                config_key="api_key",
                details={"expected_format": "string", "got_type": "int"},
            )

        assert error.config_key == "api_key"
        assert error.details["config_key"] == "api_key"
        assert error.details["expected_format"] == "string"
        assert error.details["got_type"] == "int"

    def test_inherits_from_info_agent_error(self):
        """Test that ConfigurationError inherits from InfoAgentError."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ConfigurationError(message="Test")

        assert isinstance(error, InfoAgentError)


class TestWorkflowNotFoundError:
    """Tests for WorkflowNotFoundError."""

    def test_init_with_workflow_id(self):
        """Test initialization with workflow_id."""
        with patch("info_agent.utils.exceptions.logger"):
            error = WorkflowNotFoundError(workflow_id="wf-12345")

        assert error.message == "Workflow not found: wf-12345"
        assert error.code == "WORKFLOW_NOT_FOUND"
        assert error.workflow_id == "wf-12345"
        assert error.details["workflow_id"] == "wf-12345"

    def test_init_with_additional_details(self):
        """Test initialization with additional details."""
        with patch("info_agent.utils.exceptions.logger"):
            error = WorkflowNotFoundError(
                workflow_id="wf-67890",
                details={"searched_in": "active_workflows", "total_workflows": 42},
            )

        assert error.workflow_id == "wf-67890"
        assert error.details["workflow_id"] == "wf-67890"
        assert error.details["searched_in"] == "active_workflows"
        assert error.details["total_workflows"] == 42

    def test_inherits_from_info_agent_error(self):
        """Test that WorkflowNotFoundError inherits from InfoAgentError."""
        with patch("info_agent.utils.exceptions.logger"):
            error = WorkflowNotFoundError(workflow_id="wf-123")

        assert isinstance(error, InfoAgentError)


class TestWorkflowError:
    """Tests for WorkflowError."""

    def test_init_with_message_only(self):
        """Test initialization with message only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = WorkflowError(message="Workflow execution failed")

        assert error.message == "Workflow execution failed"
        assert error.code == "WORKFLOW_ERROR"
        assert error.workflow_id is None
        assert error.step is None
        assert error.details == {}

    def test_init_with_workflow_id(self):
        """Test initialization with workflow_id."""
        with patch("info_agent.utils.exceptions.logger"):
            error = WorkflowError(
                message="Step execution failed",
                workflow_id="wf-12345",
            )

        assert error.workflow_id == "wf-12345"
        assert error.details["workflow_id"] == "wf-12345"

    def test_init_with_step(self):
        """Test initialization with step."""
        with patch("info_agent.utils.exceptions.logger"):
            error = WorkflowError(
                message="Step failed",
                step="send_email",
            )

        assert error.step == "send_email"
        assert error.details["step"] == "send_email"

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        with patch("info_agent.utils.exceptions.logger"):
            error = WorkflowError(
                message="Timeout waiting for response",
                workflow_id="wf-12345",
                step="wait_for_reply",
                details={"timeout_seconds": 300, "retry_count": 3},
            )

        assert error.message == "Timeout waiting for response"
        assert error.workflow_id == "wf-12345"
        assert error.step == "wait_for_reply"
        assert error.details["workflow_id"] == "wf-12345"
        assert error.details["step"] == "wait_for_reply"
        assert error.details["timeout_seconds"] == 300
        assert error.details["retry_count"] == 3


class TestAgentNotFoundError:
    """Tests for AgentNotFoundError."""

    def test_init_with_agent_name(self):
        """Test initialization with agent_name."""
        with patch("info_agent.utils.exceptions.logger"):
            error = AgentNotFoundError(agent_name="mail-agent")

        assert error.message == "Agent not found in registry: mail-agent"
        assert error.code == "AGENT_NOT_FOUND"
        assert error.agent_name == "mail-agent"
        assert error.details["agent_name"] == "mail-agent"

    def test_init_with_additional_details(self):
        """Test initialization with additional details."""
        with patch("info_agent.utils.exceptions.logger"):
            error = AgentNotFoundError(
                agent_name="unknown-agent",
                details={"registry_size": 5, "available_agents": ["agent1", "agent2"]},
            )

        assert error.agent_name == "unknown-agent"
        assert error.details["agent_name"] == "unknown-agent"
        assert error.details["registry_size"] == 5
        assert len(error.details["available_agents"]) == 2


class TestAgentCommunicationError:
    """Tests for AgentCommunicationError."""

    def test_init_with_agent_name_only(self):
        """Test initialization with agent_name only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = AgentCommunicationError(
                message="Connection timeout",
                agent_name="mail-agent",
            )

        assert error.message == "Agent communication failed (mail-agent): Connection timeout"
        assert error.code == "AGENT_COMMUNICATION_ERROR"
        assert error.agent_name == "mail-agent"
        assert error.endpoint is None
        assert error.details["agent_name"] == "mail-agent"

    def test_init_with_endpoint(self):
        """Test initialization with endpoint."""
        with patch("info_agent.utils.exceptions.logger"):
            error = AgentCommunicationError(
                message="HTTP 500 error",
                agent_name="mail-agent",
                endpoint="http://localhost:8001/a2a",
            )

        assert error.endpoint == "http://localhost:8001/a2a"
        assert error.details["endpoint"] == "http://localhost:8001/a2a"

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        with patch("info_agent.utils.exceptions.logger"):
            error = AgentCommunicationError(
                message="Request failed",
                agent_name="mail-agent",
                endpoint="http://localhost:8001/a2a",
                details={"status_code": 500, "retry_attempt": 3},
            )

        assert error.agent_name == "mail-agent"
        assert error.endpoint == "http://localhost:8001/a2a"
        assert error.details["agent_name"] == "mail-agent"
        assert error.details["endpoint"] == "http://localhost:8001/a2a"
        assert error.details["status_code"] == 500
        assert error.details["retry_attempt"] == 3


class TestLLMError:
    """Tests for LLMError."""

    def test_init_with_message_only(self):
        """Test initialization with message only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = LLMError(message="API request failed")

        assert error.message == "LLM error: API request failed"
        assert error.code == "LLM_ERROR"
        assert error.model is None
        assert error.original_error is None
        assert error.details == {}

    def test_init_with_model(self):
        """Test initialization with model."""
        with patch("info_agent.utils.exceptions.logger"):
            error = LLMError(
                message="Generation failed",
                model="gemini-2.5-flash",
            )

        assert error.model == "gemini-2.5-flash"
        assert error.details["model"] == "gemini-2.5-flash"

    def test_init_with_original_error(self):
        """Test initialization with original error."""
        original = ValueError("Invalid input")

        with patch("info_agent.utils.exceptions.logger"):
            error = LLMError(
                message="Request failed",
                original_error=original,
            )

        assert error.original_error is original
        assert error.details["original_error"] == "Invalid input"
        assert error.details["original_error_type"] == "ValueError"

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        original = RuntimeError("Connection lost")

        with patch("info_agent.utils.exceptions.logger"):
            error = LLMError(
                message="Failed to generate response",
                model="gemini-2.5-flash",
                original_error=original,
                details={"tokens_used": 1500, "request_id": "req-123"},
            )

        assert error.message == "LLM error: Failed to generate response"
        assert error.model == "gemini-2.5-flash"
        assert error.original_error is original
        assert error.details["model"] == "gemini-2.5-flash"
        assert error.details["original_error"] == "Connection lost"
        assert error.details["original_error_type"] == "RuntimeError"
        assert error.details["tokens_used"] == 1500
        assert error.details["request_id"] == "req-123"


class TestA2AError:
    """Tests for A2AError."""

    def test_init_with_message_only(self):
        """Test initialization with message only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = A2AError(message="Protocol violation")

        assert error.message == "A2A error: Protocol violation"
        assert error.code == "A2A_ERROR"
        assert error.agent_name is None
        assert error.task_id is None
        assert error.skill_id is None
        assert error.details == {}

    def test_init_with_agent_name(self):
        """Test initialization with agent_name."""
        with patch("info_agent.utils.exceptions.logger"):
            error = A2AError(
                message="Task creation failed",
                agent_name="mail-agent",
            )

        assert error.agent_name == "mail-agent"
        assert error.details["agent_name"] == "mail-agent"

    def test_init_with_task_id(self):
        """Test initialization with task_id."""
        with patch("info_agent.utils.exceptions.logger"):
            error = A2AError(
                message="Task not found",
                task_id="task-12345",
            )

        assert error.task_id == "task-12345"
        assert error.details["task_id"] == "task-12345"

    def test_init_with_skill_id(self):
        """Test initialization with skill_id."""
        with patch("info_agent.utils.exceptions.logger"):
            error = A2AError(
                message="Skill not supported",
                skill_id="send_email",
            )

        assert error.skill_id == "send_email"
        assert error.details["skill_id"] == "send_email"

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        with patch("info_agent.utils.exceptions.logger"):
            error = A2AError(
                message="Execution timeout",
                agent_name="mail-agent",
                task_id="task-67890",
                skill_id="send_email",
                details={"timeout_seconds": 60, "status": "pending"},
            )

        assert error.agent_name == "mail-agent"
        assert error.task_id == "task-67890"
        assert error.skill_id == "send_email"
        assert error.details["agent_name"] == "mail-agent"
        assert error.details["task_id"] == "task-67890"
        assert error.details["skill_id"] == "send_email"
        assert error.details["timeout_seconds"] == 60
        assert error.details["status"] == "pending"


class TestEmailError:
    """Tests for EmailError."""

    def test_init_with_message_only(self):
        """Test initialization with message only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = EmailError(message="Failed to send email")

        assert error.message == "Email error: Failed to send email"
        assert error.code == "EMAIL_ERROR"
        assert error.email_id is None
        assert error.thread_id is None
        assert error.recipient is None
        assert error.details == {}

    def test_init_with_email_id(self):
        """Test initialization with email_id."""
        with patch("info_agent.utils.exceptions.logger"):
            error = EmailError(
                message="Email not found",
                email_id="email-12345",
            )

        assert error.email_id == "email-12345"
        assert error.details["email_id"] == "email-12345"

    def test_init_with_thread_id(self):
        """Test initialization with thread_id."""
        with patch("info_agent.utils.exceptions.logger"):
            error = EmailError(
                message="Thread processing failed",
                thread_id="thread-67890",
            )

        assert error.thread_id == "thread-67890"
        assert error.details["thread_id"] == "thread-67890"

    def test_init_with_recipient(self):
        """Test initialization with recipient."""
        with patch("info_agent.utils.exceptions.logger"):
            error = EmailError(
                message="Delivery failed",
                recipient="user@example.com",
            )

        assert error.recipient == "user@example.com"
        assert error.details["recipient"] == "user@example.com"

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        with patch("info_agent.utils.exceptions.logger"):
            error = EmailError(
                message="SMTP error",
                email_id="email-12345",
                thread_id="thread-67890",
                recipient="user@example.com",
                details={"smtp_code": 550, "error_message": "Mailbox unavailable"},
            )

        assert error.email_id == "email-12345"
        assert error.thread_id == "thread-67890"
        assert error.recipient == "user@example.com"
        assert error.details["email_id"] == "email-12345"
        assert error.details["thread_id"] == "thread-67890"
        assert error.details["recipient"] == "user@example.com"
        assert error.details["smtp_code"] == 550
        assert error.details["error_message"] == "Mailbox unavailable"


class TestValidationError:
    """Tests for ValidationError."""

    def test_init_with_message_only(self):
        """Test initialization with message only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ValidationError(message="Invalid input")

        assert error.message == "Validation error: Invalid input"
        assert error.code == "VALIDATION_ERROR"
        assert error.field is None
        assert error.value is None
        assert error.details == {}

    def test_init_with_field(self):
        """Test initialization with field."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ValidationError(
                message="Field is required",
                field="email_address",
            )

        assert error.field == "email_address"
        assert error.details["field"] == "email_address"

    def test_init_with_value(self):
        """Test initialization with value."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ValidationError(
                message="Invalid format",
                field="age",
                value=150,
            )

        assert error.value == 150
        assert error.details["value"] == "150"

    def test_init_with_long_value_truncation(self):
        """Test that long values are truncated to 100 characters."""
        long_value = "x" * 200

        with patch("info_agent.utils.exceptions.logger"):
            error = ValidationError(
                message="Value too long",
                value=long_value,
            )

        assert error.value == long_value
        assert len(error.details["value"]) == 100
        assert error.details["value"] == "x" * 100

    def test_init_with_none_value_not_included(self):
        """Test that None value is not included in details."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ValidationError(
                message="Missing value",
                field="name",
                value=None,
            )

        assert error.value is None
        assert "value" not in error.details

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        with patch("info_agent.utils.exceptions.logger"):
            error = ValidationError(
                message="Email format invalid",
                field="email",
                value="not-an-email",
                details={"expected_pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$"},
            )

        assert error.field == "email"
        assert error.value == "not-an-email"
        assert error.details["field"] == "email"
        assert error.details["value"] == "not-an-email"
        assert error.details["expected_pattern"] == r"^[\w\.-]+@[\w\.-]+\.\w+$"


class TestStorageError:
    """Tests for StorageError."""

    def test_init_with_message_only(self):
        """Test initialization with message only."""
        with patch("info_agent.utils.exceptions.logger"):
            error = StorageError(message="Database connection failed")

        assert error.message == "Storage error: Database connection failed"
        assert error.code == "STORAGE_ERROR"
        assert error.operation is None
        assert error.entity_type is None
        assert error.entity_id is None
        assert error.details == {}

    def test_init_with_operation(self):
        """Test initialization with operation."""
        with patch("info_agent.utils.exceptions.logger"):
            error = StorageError(
                message="Save failed",
                operation="save",
            )

        assert error.operation == "save"
        assert error.details["operation"] == "save"

    def test_init_with_entity_type(self):
        """Test initialization with entity_type."""
        with patch("info_agent.utils.exceptions.logger"):
            error = StorageError(
                message="Entity not found",
                entity_type="workflow",
            )

        assert error.entity_type == "workflow"
        assert error.details["entity_type"] == "workflow"

    def test_init_with_entity_id(self):
        """Test initialization with entity_id."""
        with patch("info_agent.utils.exceptions.logger"):
            error = StorageError(
                message="Delete failed",
                entity_id="wf-12345",
            )

        assert error.entity_id == "wf-12345"
        assert error.details["entity_id"] == "wf-12345"

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        with patch("info_agent.utils.exceptions.logger"):
            error = StorageError(
                message="Foreign key constraint violation",
                operation="delete",
                entity_type="workflow",
                entity_id="wf-12345",
                details={
                    "constraint": "fk_workflow_checkpoint",
                    "related_entity": "checkpoint",
                },
            )

        assert error.operation == "delete"
        assert error.entity_type == "workflow"
        assert error.entity_id == "wf-12345"
        assert error.details["operation"] == "delete"
        assert error.details["entity_type"] == "workflow"
        assert error.details["entity_id"] == "wf-12345"
        assert error.details["constraint"] == "fk_workflow_checkpoint"
        assert error.details["related_entity"] == "checkpoint"


class TestExceptionLogging:
    """Tests for exception logging behavior."""

    def test_logging_called_on_init(self):
        """Test that logger.error is called when exception is initialized."""
        with patch("info_agent.utils.exceptions.logger") as mock_logger:
            InfoAgentError(message="Test", code="TEST")

            mock_logger.error.assert_called_once()

    def test_logging_includes_error_code(self):
        """Test that logging includes error code in extra."""
        with patch("info_agent.utils.exceptions.logger") as mock_logger:
            InfoAgentError(message="Test", code="TEST_CODE")

            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs["extra"]["error_code"] == "TEST_CODE"

    def test_logging_includes_error_details(self):
        """Test that logging includes error details in extra."""
        details = {"key1": "value1", "key2": 42}

        with patch("info_agent.utils.exceptions.logger") as mock_logger:
            InfoAgentError(message="Test", code="TEST", details=details)

            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs["extra"]["error_details"] == details

    def test_all_exception_types_log(self):
        """Test that all exception types properly log."""
        exception_classes = [
            (ConfigurationError, {"message": "Test"}),
            (WorkflowNotFoundError, {"workflow_id": "wf-123"}),
            (WorkflowError, {"message": "Test"}),
            (AgentNotFoundError, {"agent_name": "test-agent"}),
            (AgentCommunicationError, {"message": "Test", "agent_name": "test-agent"}),
            (LLMError, {"message": "Test"}),
            (A2AError, {"message": "Test"}),
            (EmailError, {"message": "Test"}),
            (ValidationError, {"message": "Test"}),
            (StorageError, {"message": "Test"}),
        ]

        for exception_class, kwargs in exception_classes:
            with patch("info_agent.utils.exceptions.logger") as mock_logger:
                exception_class(**kwargs)

                mock_logger.error.assert_called_once()
