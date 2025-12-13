"""
Unit tests for the logging module.

Tests the logging setup, configuration, and utility functions
with extensive mocking to avoid side effects during testing.
"""

import logging
import sys
from unittest.mock import MagicMock, Mock, patch, call

import pytest
import structlog

from info_agent.utils.logging import (
    setup_logging,
    get_logger,
    bind_context,
    unbind_context,
    clear_context,
    _add_service_name,
)


@pytest.fixture(autouse=True)
def reset_logging_state():
    """Reset logging state before and after each test."""
    # Reset the global flag
    import info_agent.utils.logging as logging_module
    logging_module._logging_configured = False

    yield

    # Reset after test
    logging_module._logging_configured = False
    structlog.reset_defaults()


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_with_defaults(self):
        """Test setup_logging with default parameters."""
        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            setup_logging()

            # Verify structlog.configure was called
            mock_structlog.configure.assert_called_once()

            # Check the call includes processors
            call_kwargs = mock_structlog.configure.call_args[1]
            assert "processors" in call_kwargs
            assert "logger_factory" in call_kwargs
            assert "wrapper_class" in call_kwargs

    def test_setup_with_info_level(self):
        """Test setup_logging with INFO level."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging(level="INFO")

            mock_basicConfig.assert_called_once()
            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["level"] == logging.INFO

    def test_setup_with_debug_level(self):
        """Test setup_logging with DEBUG level."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging(level="DEBUG")

            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["level"] == logging.DEBUG

    def test_setup_with_warning_level(self):
        """Test setup_logging with WARNING level."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging(level="WARNING")

            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["level"] == logging.WARNING

    def test_setup_with_error_level(self):
        """Test setup_logging with ERROR level."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging(level="ERROR")

            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["level"] == logging.ERROR

    def test_setup_with_critical_level(self):
        """Test setup_logging with CRITICAL level."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging(level="CRITICAL")

            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["level"] == logging.CRITICAL

    def test_setup_with_lowercase_level(self):
        """Test that level is case-insensitive."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging(level="info")

            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["level"] == logging.INFO

    def test_setup_with_invalid_level_raises_error(self):
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            setup_logging(level="INVALID")

        assert "Invalid log level: INVALID" in str(exc_info.value)
        assert "DEBUG" in str(exc_info.value)
        assert "INFO" in str(exc_info.value)

    def test_setup_with_json_format(self):
        """Test setup_logging with JSON format."""
        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            setup_logging(log_format="json")

            # Verify that JSONRenderer is used
            # This is complex to verify directly, but we can check the call was made
            mock_structlog.configure.assert_called_once()

    def test_setup_with_console_format(self):
        """Test setup_logging with console format."""
        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            setup_logging(log_format="console")

            # Verify that ConsoleRenderer is used
            mock_structlog.configure.assert_called_once()

    def test_setup_with_invalid_format_raises_error(self):
        """Test that invalid log format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            setup_logging(log_format="xml")

        assert "Invalid log format: xml" in str(exc_info.value)
        assert "json" in str(exc_info.value)
        assert "console" in str(exc_info.value)

    def test_setup_with_custom_service_name(self):
        """Test setup_logging with custom service name."""
        with patch("info_agent.utils.logging.structlog"):
            setup_logging(service_name="test-service")

            # Service name is embedded in processor, tested separately
            # Just verify no errors occur
            pass

    def test_setup_configures_stdlib_logging(self):
        """Test that setup_logging configures standard library logging."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging()

            mock_basicConfig.assert_called_once()
            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["format"] == "%(message)s"
            assert call_kwargs["stream"] == sys.stdout
            assert call_kwargs["force"] is True

    def test_setup_reduces_third_party_noise(self):
        """Test that setup_logging reduces logging from third-party libraries."""
        with patch("logging.getLogger") as mock_getLogger:
            mock_httpx_logger = Mock()
            mock_httpcore_logger = Mock()
            mock_uvicorn_logger = Mock()
            mock_aiosmtpd_logger = Mock()
            mock_root_logger = Mock()
            mock_root_logger.handlers = []

            def getLogger_side_effect(name=None):
                if name == "httpx":
                    return mock_httpx_logger
                elif name == "httpcore":
                    return mock_httpcore_logger
                elif name == "uvicorn.access":
                    return mock_uvicorn_logger
                elif name == "aiosmtpd":
                    return mock_aiosmtpd_logger
                elif name is None or name == "root":
                    return mock_root_logger
                else:
                    return Mock()

            mock_getLogger.side_effect = getLogger_side_effect

            setup_logging()

            mock_httpx_logger.setLevel.assert_called_once_with(logging.WARNING)
            mock_httpcore_logger.setLevel.assert_called_once_with(logging.WARNING)
            mock_uvicorn_logger.setLevel.assert_called_once_with(logging.WARNING)
            mock_aiosmtpd_logger.setLevel.assert_called_once_with(logging.WARNING)

    def test_setup_sets_global_flag(self):
        """Test that setup_logging sets the global configured flag."""
        import info_agent.utils.logging as logging_module

        assert logging_module._logging_configured is False

        with patch("info_agent.utils.logging.structlog"):
            setup_logging()

        assert logging_module._logging_configured is True

    def test_setup_applies_formatter_to_handlers(self):
        """Test that setup_logging applies formatter to root logger handlers."""
        mock_handler1 = Mock()
        mock_handler2 = Mock()
        mock_root_logger = Mock()
        mock_root_logger.handlers = [mock_handler1, mock_handler2]

        with patch("logging.getLogger", return_value=mock_root_logger):
            with patch("info_agent.utils.logging.structlog"):
                setup_logging()

        mock_handler1.setFormatter.assert_called_once()
        mock_handler2.setFormatter.assert_called_once()

    def test_setup_logs_startup_message(self):
        """Test that setup_logging logs a startup message."""
        with patch("info_agent.utils.logging.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            with patch("info_agent.utils.logging.structlog"):
                setup_logging(level="DEBUG", log_format="json", service_name="test-service")

            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args[1]
            assert call_kwargs["level"] == "DEBUG"
            assert call_kwargs["format"] == "json"
            assert call_kwargs["service"] == "test-service"


class TestAddServiceName:
    """Tests for _add_service_name processor."""

    def test_processor_adds_service_name(self):
        """Test that processor adds service name to event_dict."""
        processor = _add_service_name("test-service")

        event_dict = {"event": "test event", "level": "info"}
        mock_logger = Mock()

        result = processor(mock_logger, "info", event_dict)

        assert result["service"] == "test-service"
        assert result["event"] == "test event"
        assert result["level"] == "info"

    def test_processor_with_empty_event_dict(self):
        """Test processor with empty event_dict."""
        processor = _add_service_name("my-service")

        event_dict = {}
        result = processor(Mock(), "debug", event_dict)

        assert result["service"] == "my-service"

    def test_processor_preserves_existing_fields(self):
        """Test that processor preserves existing fields in event_dict."""
        processor = _add_service_name("service-name")

        event_dict = {
            "event": "test",
            "workflow_id": "wf-123",
            "user": "admin",
        }

        result = processor(Mock(), "info", event_dict)

        assert result["service"] == "service-name"
        assert result["event"] == "test"
        assert result["workflow_id"] == "wf-123"
        assert result["user"] == "admin"


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_name(self):
        """Test get_logger returns logger with specified name."""
        import info_agent.utils.logging as logging_module
        logging_module._logging_configured = True  # Prevent auto-setup

        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            mock_logger = Mock()
            mock_structlog.get_logger.return_value = mock_logger

            logger = get_logger("test.module")

            mock_structlog.get_logger.assert_called_once_with("test.module")
            assert logger == mock_logger

    def test_get_logger_without_name(self):
        """Test get_logger with None name."""
        import info_agent.utils.logging as logging_module
        logging_module._logging_configured = True  # Prevent auto-setup

        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            mock_logger = Mock()
            mock_structlog.get_logger.return_value = mock_logger

            logger = get_logger(None)

            mock_structlog.get_logger.assert_called_once_with(None)
            assert logger == mock_logger

    def test_get_logger_configures_logging_if_needed(self):
        """Test get_logger auto-configures logging if not already done."""
        import info_agent.utils.logging as logging_module
        logging_module._logging_configured = False

        with patch("info_agent.utils.logging.setup_logging") as mock_setup:
            with patch("info_agent.utils.logging.structlog"):
                get_logger("test")

                mock_setup.assert_called_once()

    def test_get_logger_does_not_reconfigure(self):
        """Test get_logger doesn't reconfigure if already configured."""
        import info_agent.utils.logging as logging_module
        logging_module._logging_configured = True

        with patch("info_agent.utils.logging.setup_logging") as mock_setup:
            with patch("info_agent.utils.logging.structlog"):
                get_logger("test")

                mock_setup.assert_not_called()

    def test_get_logger_returns_bound_logger(self):
        """Test get_logger returns BoundLogger instance."""
        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            mock_bound_logger = Mock(spec=structlog.stdlib.BoundLogger)
            mock_structlog.get_logger.return_value = mock_bound_logger

            logger = get_logger("test.module")

            assert logger == mock_bound_logger


class TestBindContext:
    """Tests for bind_context function."""

    def test_bind_context_with_single_kwarg(self):
        """Test bind_context with single keyword argument."""
        with patch("info_agent.utils.logging.structlog.contextvars.bind_contextvars") as mock_bind:
            bind_context(workflow_id="wf-123")

            mock_bind.assert_called_once_with(workflow_id="wf-123")

    def test_bind_context_with_multiple_kwargs(self):
        """Test bind_context with multiple keyword arguments."""
        with patch("info_agent.utils.logging.structlog.contextvars.bind_contextvars") as mock_bind:
            bind_context(workflow_id="wf-123", user="admin", request_id="req-456")

            mock_bind.assert_called_once_with(
                workflow_id="wf-123",
                user="admin",
                request_id="req-456",
            )

    def test_bind_context_with_no_kwargs(self):
        """Test bind_context with no arguments."""
        with patch("info_agent.utils.logging.structlog.contextvars.bind_contextvars") as mock_bind:
            bind_context()

            mock_bind.assert_called_once_with()

    def test_bind_context_with_various_types(self):
        """Test bind_context with various data types."""
        with patch("info_agent.utils.logging.structlog.contextvars.bind_contextvars") as mock_bind:
            bind_context(
                string_val="test",
                int_val=42,
                float_val=3.14,
                bool_val=True,
                none_val=None,
            )

            mock_bind.assert_called_once_with(
                string_val="test",
                int_val=42,
                float_val=3.14,
                bool_val=True,
                none_val=None,
            )


class TestUnbindContext:
    """Tests for unbind_context function."""

    def test_unbind_context_with_single_key(self):
        """Test unbind_context with single key."""
        with patch("info_agent.utils.logging.structlog.contextvars.unbind_contextvars") as mock_unbind:
            unbind_context("workflow_id")

            mock_unbind.assert_called_once_with("workflow_id")

    def test_unbind_context_with_multiple_keys(self):
        """Test unbind_context with multiple keys."""
        with patch("info_agent.utils.logging.structlog.contextvars.unbind_contextvars") as mock_unbind:
            unbind_context("workflow_id", "user", "request_id")

            mock_unbind.assert_called_once_with("workflow_id", "user", "request_id")

    def test_unbind_context_with_no_keys(self):
        """Test unbind_context with no arguments."""
        with patch("info_agent.utils.logging.structlog.contextvars.unbind_contextvars") as mock_unbind:
            unbind_context()

            mock_unbind.assert_called_once_with()


class TestClearContext:
    """Tests for clear_context function."""

    def test_clear_context_clears_all_context(self):
        """Test clear_context clears all context variables."""
        with patch("info_agent.utils.logging.structlog.contextvars.clear_contextvars") as mock_clear:
            clear_context()

            mock_clear.assert_called_once()

    def test_clear_context_can_be_called_multiple_times(self):
        """Test clear_context can be called multiple times."""
        with patch("info_agent.utils.logging.structlog.contextvars.clear_contextvars") as mock_clear:
            clear_context()
            clear_context()
            clear_context()

            assert mock_clear.call_count == 3


class TestLoggingIntegration:
    """Integration-style tests for common logging scenarios."""

    def test_typical_logging_flow(self):
        """Test typical flow of setting up logging and getting a logger."""
        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            mock_logger = Mock()
            mock_structlog.get_logger.return_value = mock_logger

            # Setup logging
            setup_logging(level="INFO", log_format="console", service_name="test-app")

            # Get logger
            logger = get_logger(__name__)

            assert logger == mock_logger
            mock_structlog.configure.assert_called_once()
            # get_logger is called twice: once in setup_logging, once explicitly
            assert mock_structlog.get_logger.call_count == 2

    def test_context_binding_flow(self):
        """Test flow of binding and unbinding context."""
        with patch("info_agent.utils.logging.structlog.contextvars") as mock_contextvars:
            # Bind context
            bind_context(workflow_id="wf-123", user="admin")
            mock_contextvars.bind_contextvars.assert_called_once_with(
                workflow_id="wf-123",
                user="admin",
            )

            # Unbind specific key
            unbind_context("user")
            mock_contextvars.unbind_contextvars.assert_called_once_with("user")

            # Clear all context
            clear_context()
            mock_contextvars.clear_contextvars.assert_called_once()

    def test_get_logger_without_explicit_setup(self):
        """Test that get_logger works even without explicit setup_logging call."""
        import info_agent.utils.logging as logging_module
        logging_module._logging_configured = False

        with patch("info_agent.utils.logging.setup_logging") as mock_setup:
            with patch("info_agent.utils.logging.structlog") as mock_structlog:
                mock_logger = Mock()
                mock_structlog.get_logger.return_value = mock_logger

                logger = get_logger("test")

                # Should auto-configure
                mock_setup.assert_called_once()
                assert logger == mock_logger

    def test_multiple_loggers_share_configuration(self):
        """Test that multiple loggers share the same configuration."""
        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            # Need 4 mocks: 1 for setup_logging + 3 explicit calls
            mock_structlog.get_logger.side_effect = [Mock(), Mock(), Mock(), Mock()]

            # Setup once
            setup_logging()

            # Get multiple loggers
            logger1 = get_logger("module1")
            logger2 = get_logger("module2")
            logger3 = get_logger("module3")

            # Configure should only be called once (during setup)
            assert mock_structlog.configure.call_count == 1

            # But get_logger should be called for each logger
            assert mock_structlog.get_logger.call_count == 4  # 1 in setup + 3 explicit


class TestLoggingEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_setup_logging_with_mixed_case_level(self):
        """Test setup_logging handles mixed case log levels."""
        with patch("logging.basicConfig") as mock_basicConfig:
            setup_logging(level="InFo")

            call_kwargs = mock_basicConfig.call_args[1]
            assert call_kwargs["level"] == logging.INFO

    def test_setup_logging_with_mixed_case_format(self):
        """Test setup_logging handles mixed case formats."""
        with patch("info_agent.utils.logging.structlog"):
            # Should not raise error
            setup_logging(log_format="JsOn")
            setup_logging(log_format="CoNsOlE")

    def test_bind_context_overwrites_existing_values(self):
        """Test that bind_context can overwrite existing context values."""
        with patch("info_agent.utils.logging.structlog.contextvars.bind_contextvars") as mock_bind:
            bind_context(workflow_id="wf-123")
            bind_context(workflow_id="wf-456")

            # Should be called twice with different values
            assert mock_bind.call_count == 2
            assert mock_bind.call_args_list[0] == call(workflow_id="wf-123")
            assert mock_bind.call_args_list[1] == call(workflow_id="wf-456")

    def test_unbind_nonexistent_key(self):
        """Test unbinding a key that doesn't exist (should not error)."""
        with patch("info_agent.utils.logging.structlog.contextvars.unbind_contextvars") as mock_unbind:
            # Should not raise error
            unbind_context("nonexistent_key")

            mock_unbind.assert_called_once_with("nonexistent_key")

    def test_setup_logging_twice(self):
        """Test calling setup_logging multiple times."""
        import info_agent.utils.logging as logging_module

        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            setup_logging()
            assert logging_module._logging_configured is True

            setup_logging()  # Call again

            # Should be called twice
            assert mock_structlog.configure.call_count == 2

    def test_get_logger_with_empty_string_name(self):
        """Test get_logger with empty string name."""
        import info_agent.utils.logging as logging_module
        logging_module._logging_configured = True  # Prevent auto-setup

        with patch("info_agent.utils.logging.structlog") as mock_structlog:
            mock_logger = Mock()
            mock_structlog.get_logger.return_value = mock_logger

            logger = get_logger("")

            mock_structlog.get_logger.assert_called_once_with("")
            assert logger == mock_logger
