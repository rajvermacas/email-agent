"""
Unit tests for Validation Agent standalone runner.
"""

import signal
import sys
from unittest.mock import MagicMock, patch

import pytest

from info_agent.agents.validation.__main__ import main, run_validation_agent


class TestMainFunction:
    """Tests for main() function and argument parsing."""

    @patch("info_agent.agents.validation.__main__.run_validation_agent")
    def test_main_default_arguments(self, mock_run: MagicMock) -> None:
        """Test main() uses default arguments when none provided."""
        with patch.object(sys, "argv", ["validation"]):
            main()

        mock_run.assert_called_once_with(host="0.0.0.0", port=8003)

    @patch("info_agent.agents.validation.__main__.run_validation_agent")
    def test_main_custom_host(self, mock_run: MagicMock) -> None:
        """Test main() with custom host argument."""
        with patch.object(sys, "argv", ["validation", "--host", "127.0.0.1"]):
            main()

        mock_run.assert_called_once_with(host="127.0.0.1", port=8003)

    @patch("info_agent.agents.validation.__main__.run_validation_agent")
    def test_main_custom_port(self, mock_run: MagicMock) -> None:
        """Test main() with custom port argument."""
        with patch.object(sys, "argv", ["validation", "--port", "9000"]):
            main()

        mock_run.assert_called_once_with(host="0.0.0.0", port=9000)

    @patch("info_agent.agents.validation.__main__.run_validation_agent")
    def test_main_custom_host_and_port(self, mock_run: MagicMock) -> None:
        """Test main() with both custom host and port."""
        with patch.object(
            sys, "argv", ["validation", "--host", "192.168.1.1", "--port", "8080"]
        ):
            main()

        mock_run.assert_called_once_with(host="192.168.1.1", port=8080)


class TestRunValidationAgent:
    """Tests for run_validation_agent() function."""

    @patch("info_agent.agents.validation.__main__.AgentServer")
    @patch("info_agent.agents.validation.__main__.ValidationAgentExecutor")
    @patch("info_agent.agents.validation.__main__.PythonExecutor")
    def test_creates_python_executor(
        self,
        mock_python_executor_class: MagicMock,
        mock_executor_class: MagicMock,
        mock_server_class: MagicMock,
    ) -> None:
        """Test that PythonExecutor is created."""
        mock_python_executor = MagicMock()
        mock_python_executor_class.return_value = mock_python_executor

        mock_executor = MagicMock()
        mock_executor.agent_card.skills = []
        mock_executor_class.return_value = mock_executor

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        run_validation_agent(host="localhost", port=8003)

        mock_python_executor_class.assert_called_once()

    @patch("info_agent.agents.validation.__main__.AgentServer")
    @patch("info_agent.agents.validation.__main__.ValidationAgentExecutor")
    @patch("info_agent.agents.validation.__main__.PythonExecutor")
    def test_creates_executor_with_correct_params(
        self,
        mock_python_executor_class: MagicMock,
        mock_executor_class: MagicMock,
        mock_server_class: MagicMock,
    ) -> None:
        """Test that ValidationAgentExecutor is created with correct parameters."""
        mock_python_executor = MagicMock()
        mock_python_executor_class.return_value = mock_python_executor

        mock_executor = MagicMock()
        mock_executor.agent_card.skills = []
        mock_executor_class.return_value = mock_executor

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        run_validation_agent(host="localhost", port=8003)

        mock_executor_class.assert_called_once_with(
            python_executor=mock_python_executor,
            agent_id="validation-agent",
            endpoint="http://localhost:8003",
        )

    @patch("info_agent.agents.validation.__main__.AgentServer")
    @patch("info_agent.agents.validation.__main__.ValidationAgentExecutor")
    @patch("info_agent.agents.validation.__main__.PythonExecutor")
    def test_creates_server_with_correct_params(
        self,
        mock_python_executor_class: MagicMock,
        mock_executor_class: MagicMock,
        mock_server_class: MagicMock,
    ) -> None:
        """Test that AgentServer is created with correct parameters."""
        mock_python_executor = MagicMock()
        mock_python_executor_class.return_value = mock_python_executor

        mock_executor = MagicMock()
        mock_executor.agent_card.skills = []
        mock_executor_class.return_value = mock_executor

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        run_validation_agent(host="0.0.0.0", port=9000)

        mock_server_class.assert_called_once_with(
            executor=mock_executor,
            host="0.0.0.0",
            port=9000,
        )

    @patch("info_agent.agents.validation.__main__.AgentServer")
    @patch("info_agent.agents.validation.__main__.ValidationAgentExecutor")
    @patch("info_agent.agents.validation.__main__.PythonExecutor")
    def test_calls_server_run(
        self,
        mock_python_executor_class: MagicMock,
        mock_executor_class: MagicMock,
        mock_server_class: MagicMock,
    ) -> None:
        """Test that server.run() is called."""
        mock_python_executor = MagicMock()
        mock_python_executor_class.return_value = mock_python_executor

        mock_executor = MagicMock()
        mock_executor.agent_card.skills = []
        mock_executor_class.return_value = mock_executor

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        run_validation_agent(host="localhost", port=8003)

        mock_server.run.assert_called_once()

    @patch("info_agent.agents.validation.__main__.signal.signal")
    @patch("info_agent.agents.validation.__main__.AgentServer")
    @patch("info_agent.agents.validation.__main__.ValidationAgentExecutor")
    @patch("info_agent.agents.validation.__main__.PythonExecutor")
    def test_registers_signal_handlers(
        self,
        mock_python_executor_class: MagicMock,
        mock_executor_class: MagicMock,
        mock_server_class: MagicMock,
        mock_signal: MagicMock,
    ) -> None:
        """Test that signal handlers are registered."""
        mock_python_executor = MagicMock()
        mock_python_executor_class.return_value = mock_python_executor

        mock_executor = MagicMock()
        mock_executor.agent_card.skills = []
        mock_executor_class.return_value = mock_executor

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        run_validation_agent(host="localhost", port=8003)

        # Verify signal handlers were registered
        signal_calls = mock_signal.call_args_list
        registered_signals = [call[0][0] for call in signal_calls]

        assert signal.SIGINT in registered_signals
        assert signal.SIGTERM in registered_signals


class TestEndpointConstruction:
    """Tests for endpoint URL construction."""

    @patch("info_agent.agents.validation.__main__.AgentServer")
    @patch("info_agent.agents.validation.__main__.ValidationAgentExecutor")
    @patch("info_agent.agents.validation.__main__.PythonExecutor")
    def test_endpoint_with_localhost(
        self,
        mock_python_executor_class: MagicMock,
        mock_executor_class: MagicMock,
        mock_server_class: MagicMock,
    ) -> None:
        """Test endpoint construction with localhost."""
        mock_python_executor = MagicMock()
        mock_python_executor_class.return_value = mock_python_executor

        mock_executor = MagicMock()
        mock_executor.agent_card.skills = []
        mock_executor_class.return_value = mock_executor

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        run_validation_agent(host="localhost", port=8003)

        call_args = mock_executor_class.call_args
        assert call_args[1]["endpoint"] == "http://localhost:8003"

    @patch("info_agent.agents.validation.__main__.AgentServer")
    @patch("info_agent.agents.validation.__main__.ValidationAgentExecutor")
    @patch("info_agent.agents.validation.__main__.PythonExecutor")
    def test_endpoint_with_ip_address(
        self,
        mock_python_executor_class: MagicMock,
        mock_executor_class: MagicMock,
        mock_server_class: MagicMock,
    ) -> None:
        """Test endpoint construction with IP address."""
        mock_python_executor = MagicMock()
        mock_python_executor_class.return_value = mock_python_executor

        mock_executor = MagicMock()
        mock_executor.agent_card.skills = []
        mock_executor_class.return_value = mock_executor

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        run_validation_agent(host="192.168.1.100", port=9999)

        call_args = mock_executor_class.call_args
        assert call_args[1]["endpoint"] == "http://192.168.1.100:9999"
