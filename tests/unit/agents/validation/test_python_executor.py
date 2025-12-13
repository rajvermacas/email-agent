"""
Unit tests for Python executor.
"""

import pytest

from info_agent.agents.validation.python_executor import (
    ALLOWED_IMPORTS,
    DEFAULT_TIMEOUT,
    PythonExecutor,
)


class TestPythonExecutorInit:
    """Tests for PythonExecutor initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        executor = PythonExecutor()

        assert executor.timeout_seconds == DEFAULT_TIMEOUT
        assert executor.allowed_imports == ALLOWED_IMPORTS

    def test_custom_timeout(self) -> None:
        """Test custom timeout."""
        executor = PythonExecutor(timeout_seconds=10)

        assert executor.timeout_seconds == 10

    def test_custom_allowed_imports(self) -> None:
        """Test custom allowed imports."""
        custom_imports = frozenset(["json", "csv"])
        executor = PythonExecutor(allowed_imports=custom_imports)

        assert executor.allowed_imports == custom_imports


class TestCodeValidation:
    """Tests for code validation."""

    @pytest.fixture
    def executor(self) -> PythonExecutor:
        """Create test executor."""
        return PythonExecutor()

    def test_validate_allowed_import(self, executor: PythonExecutor) -> None:
        """Test validation of allowed import."""
        code = "import json"
        disallowed = executor._validate_code(code)

        assert len(disallowed) == 0

    def test_validate_disallowed_import(self, executor: PythonExecutor) -> None:
        """Test validation of disallowed import."""
        code = "import os"
        disallowed = executor._validate_code(code)

        assert "os" in disallowed

    def test_validate_from_import_disallowed(self, executor: PythonExecutor) -> None:
        """Test validation of from import disallowed."""
        code = "from subprocess import run"
        disallowed = executor._validate_code(code)

        assert "subprocess" in disallowed

    def test_validate_multiple_imports(self, executor: PythonExecutor) -> None:
        """Test validation with multiple imports."""
        code = """
import json
import pandas
import os
import subprocess
"""
        disallowed = executor._validate_code(code)

        assert "os" in disallowed
        assert "subprocess" in disallowed
        assert "json" not in disallowed
        assert "pandas" not in disallowed

    def test_validate_syntax_error_passes(self, executor: PythonExecutor) -> None:
        """Test that syntax errors don't crash validation."""
        code = "import ("  # Syntax error
        # Should not raise, syntax errors caught at execution
        disallowed = executor._validate_code(code)
        # May or may not find imports due to parse failure
        assert isinstance(disallowed, list)


class TestCodeExecution:
    """Tests for code execution."""

    @pytest.fixture
    def executor(self) -> PythonExecutor:
        """Create test executor."""
        return PythonExecutor(timeout_seconds=5)

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, executor: PythonExecutor) -> None:
        """Test executing simple code."""
        code = "print('hello world')"
        result = await executor.execute(code)

        assert result.success is True
        assert "hello world" in result.output
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_with_data(self, executor: PythonExecutor) -> None:
        """Test executing code with data."""
        code = "print(data['name'])"
        data = {"name": "Test User"}
        result = await executor.execute(code, data=data)

        assert result.success is True
        assert "Test User" in result.output

    @pytest.mark.asyncio
    async def test_execute_disallowed_import(self, executor: PythonExecutor) -> None:
        """Test execution blocked for disallowed import."""
        code = "import os\nprint(os.getcwd())"
        result = await executor.execute(code)

        assert result.success is False
        assert "Disallowed imports" in result.error

    @pytest.mark.asyncio
    async def test_execute_allowed_imports(self, executor: PythonExecutor) -> None:
        """Test execution with allowed imports."""
        code = """
import json
data_str = json.dumps({"key": "value"})
print(data_str)
"""
        result = await executor.execute(code)

        assert result.success is True
        assert "key" in result.output

    @pytest.mark.asyncio
    async def test_execute_syntax_error(self, executor: PythonExecutor) -> None:
        """Test execution with syntax error."""
        code = "print('hello"  # Missing closing quote
        result = await executor.execute(code)

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_execute_runtime_error(self, executor: PythonExecutor) -> None:
        """Test execution with runtime error."""
        code = "x = 1 / 0"  # ZeroDivisionError
        result = await executor.execute(code)

        assert result.success is False
        assert "ZeroDivisionError" in result.error or "division" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execution_time_recorded(self, executor: PythonExecutor) -> None:
        """Test that execution time is recorded."""
        code = "print('quick')"
        result = await executor.execute(code)

        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_execute_with_result_variable(self, executor: PythonExecutor) -> None:
        """Test execution with _result variable."""
        code = "_result = {'status': 'ok', 'count': 42}"
        result = await executor.execute(code)

        assert result.success is True
        # The result should be printed as JSON
        assert "__RESULT__" in result.output
        assert "status" in result.output

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test that timeout is enforced."""
        # time is not in allowed imports, so we use a while loop to test timeout
        # Add time to allowed imports just for this test
        executor = PythonExecutor(
            timeout_seconds=1,
            allowed_imports=frozenset(["time", "json"]),
        )
        code = """
import time
time.sleep(10)
print('done')
"""
        result = await executor.execute(code)

        assert result.success is False
        assert "timed out" in result.error.lower()


class TestSyncExecution:
    """Tests for synchronous execution."""

    def test_execute_sync(self) -> None:
        """Test synchronous execution."""
        executor = PythonExecutor(timeout_seconds=5)
        code = "print('sync test')"

        result = executor.execute_sync(code)

        assert result.success is True
        assert "sync test" in result.output
