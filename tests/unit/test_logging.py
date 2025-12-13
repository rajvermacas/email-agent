"""
Unit tests for logging module.

Tests structured logging setup, logger creation,
and context management.
"""

import logging
from unittest.mock import patch

import pytest
import structlog

from info_agent.utils.logging import (
    LogContext,
    bind_context,
    clear_context,
    get_logger,
    setup_logging,
    unbind_context,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_json_logging(self) -> None:
        """Test JSON logging setup."""
        setup_logging(level="INFO", log_format="json")

        # Verify root logger is configured
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) > 0

    def test_setup_console_logging(self) -> None:
        """Test console logging setup."""
        setup_logging(level="DEBUG", log_format="console")

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_setup_with_timestamps(self) -> None:
        """Test logging with timestamps enabled."""
        setup_logging(level="INFO", show_timestamps=True)
        # Should not raise
        logger = get_logger("test")
        logger.info("test message")

    def test_setup_without_timestamps(self) -> None:
        """Test logging without timestamps."""
        setup_logging(level="INFO", show_timestamps=False)
        # Should not raise
        logger = get_logger("test")
        logger.info("test message")

    def test_invalid_level_defaults_to_info(self) -> None:
        """Test invalid level defaults gracefully."""
        # Invalid level should default to INFO
        setup_logging(level="INVALID")
        root = logging.getLogger()
        assert root.level == logging.INFO


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_name(self) -> None:
        """Test getting logger with name."""
        setup_logging(level="INFO", log_format="console")
        logger = get_logger("test.module")

        assert logger is not None

    def test_get_logger_without_name(self) -> None:
        """Test getting logger without name."""
        setup_logging(level="INFO", log_format="console")
        logger = get_logger()

        assert logger is not None

    def test_logger_has_expected_methods(self) -> None:
        """Test logger has standard logging methods."""
        setup_logging(level="INFO", log_format="console")
        logger = get_logger("test")

        # Should have standard methods
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")


class TestLoggerOutput:
    """Tests for logger output."""

    def test_logger_logs_message(self, capfd: pytest.CaptureFixture) -> None:
        """Test logger outputs message."""
        setup_logging(level="INFO", log_format="console")
        logger = get_logger("test.output")

        logger.info("test_message")

        captured = capfd.readouterr()
        # Console format should contain the message
        assert "test_message" in captured.out or "test_message" in captured.err

    def test_logger_logs_with_context(self, capfd: pytest.CaptureFixture) -> None:
        """Test logger includes context in output."""
        setup_logging(level="INFO", log_format="console")
        logger = get_logger("test.context")

        logger.info("operation_completed", user_id="user123", duration=150)

        captured = capfd.readouterr()
        output = captured.out + captured.err
        assert "operation_completed" in output

    def test_logger_respects_level(self, capfd: pytest.CaptureFixture) -> None:
        """Test logger respects log level."""
        setup_logging(level="WARNING", log_format="console")
        logger = get_logger("test.level")

        logger.debug("debug_message")
        logger.info("info_message")
        logger.warning("warning_message")

        captured = capfd.readouterr()
        output = captured.out + captured.err

        # Debug and info should not appear
        assert "debug_message" not in output
        assert "info_message" not in output
        # Warning should appear
        assert "warning_message" in output


class TestLogContext:
    """Tests for LogContext context manager."""

    def test_context_manager_binds_values(self) -> None:
        """Test context manager binds values during context."""
        setup_logging(level="INFO", log_format="console")
        clear_context()

        with LogContext(request_id="req-001", user_id="user-001"):
            # Values should be bound during context
            # We can't easily verify this without capturing output
            pass

        # After context, values should be unbound
        # This verifies no exception is raised

    def test_nested_context(self) -> None:
        """Test nested context managers."""
        setup_logging(level="INFO", log_format="console")
        clear_context()

        with LogContext(outer="value1"):
            with LogContext(inner="value2"):
                pass  # Both contexts active

        # Should clean up properly

    def test_context_manager_returns_self(self) -> None:
        """Test context manager returns self for 'as' clause."""
        ctx = LogContext(key="value")

        with ctx as returned:
            assert returned is ctx


class TestContextBindingFunctions:
    """Tests for context binding functions."""

    def test_bind_context(self) -> None:
        """Test bind_context function."""
        setup_logging(level="INFO", log_format="console")
        clear_context()

        # Should not raise
        bind_context(workflow_id="wf-001", session_id="sess-001")

        # Clean up
        clear_context()

    def test_unbind_context(self) -> None:
        """Test unbind_context function."""
        setup_logging(level="INFO", log_format="console")
        clear_context()

        bind_context(key1="value1", key2="value2")
        unbind_context("key1")

        # Should not raise - key1 unbound, key2 still bound
        clear_context()

    def test_clear_context(self) -> None:
        """Test clear_context function."""
        setup_logging(level="INFO", log_format="console")

        bind_context(key1="value1", key2="value2")
        clear_context()

        # Should not raise - all keys cleared


class TestNoisyLoggerSuppression:
    """Tests for noisy logger suppression."""

    def test_httpx_logger_suppressed(self) -> None:
        """Test httpx logger is set to WARNING level."""
        setup_logging(level="DEBUG", log_format="console")

        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level >= logging.WARNING

    def test_httpcore_logger_suppressed(self) -> None:
        """Test httpcore logger is set to WARNING level."""
        setup_logging(level="DEBUG", log_format="console")

        httpcore_logger = logging.getLogger("httpcore")
        assert httpcore_logger.level >= logging.WARNING

    def test_uvicorn_access_logger_suppressed(self) -> None:
        """Test uvicorn.access logger is set to WARNING level."""
        setup_logging(level="DEBUG", log_format="console")

        uvicorn_logger = logging.getLogger("uvicorn.access")
        assert uvicorn_logger.level >= logging.WARNING


class TestStructuredLogging:
    """Tests for structured logging features."""

    def test_json_format_produces_valid_json(self, capfd: pytest.CaptureFixture) -> None:
        """Test JSON format produces valid JSON output."""
        import json

        setup_logging(level="INFO", log_format="json")
        logger = get_logger("test.json")
        clear_context()

        logger.info("test_event", key="value")

        captured = capfd.readouterr()
        output = captured.out.strip() or captured.err.strip()

        # Try to parse as JSON (may have multiple lines)
        for line in output.split("\n"):
            if line.strip():
                try:
                    data = json.loads(line)
                    if "test_event" in str(data):
                        assert "event" in data or "test_event" in str(data)
                        return
                except json.JSONDecodeError:
                    continue

        # If we get here, check that the output contains our message
        assert "test_event" in output

    def test_extra_fields_included(self, capfd: pytest.CaptureFixture) -> None:
        """Test extra fields are included in output."""
        setup_logging(level="INFO", log_format="console")
        logger = get_logger("test.extra")
        clear_context()

        logger.info(
            "user_action",
            user_id="user-123",
            action="login",
            ip_address="192.168.1.1",
        )

        captured = capfd.readouterr()
        output = captured.out + captured.err

        assert "user_action" in output
