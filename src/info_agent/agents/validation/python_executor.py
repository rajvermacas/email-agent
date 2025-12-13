"""
Secure Python code executor for validation.

Provides sandboxed execution of Python code with restricted imports.
"""

import asyncio
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import structlog

from info_agent.agents.validation.models import PythonExecutionResult
from info_agent.utils.exceptions import ValidationError

logger = structlog.get_logger(__name__)

# Allowed imports for sandboxed execution
ALLOWED_IMPORTS = frozenset([
    "pandas",
    "numpy",
    "json",
    "csv",
    "openpyxl",
    "re",
    "datetime",
    "math",
    "statistics",
    "collections",
    "itertools",
])

# Default timeout in seconds
DEFAULT_TIMEOUT = 30


class PythonExecutor:
    """
    Secure Python code executor.

    Executes Python code in a subprocess with timeout and import restrictions.

    Attributes:
        timeout_seconds: Maximum execution time.
        allowed_imports: Set of allowed import modules.
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        allowed_imports: frozenset[str] | None = None,
    ) -> None:
        """
        Initialize Python executor.

        Args:
            timeout_seconds: Maximum execution time.
            allowed_imports: Allowed import modules (defaults to ALLOWED_IMPORTS).
        """
        self.timeout_seconds = timeout_seconds
        self.allowed_imports = allowed_imports or ALLOWED_IMPORTS

        logger.info(
            "python_executor_initialized",
            timeout=timeout_seconds,
            allowed_imports=list(self.allowed_imports),
        )

    def _validate_code(self, code: str) -> list[str]:
        """
        Validate code for disallowed imports.

        Args:
            code: Python code to validate.

        Returns:
            List of disallowed imports found.
        """
        import ast

        disallowed = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        if module not in self.allowed_imports:
                            disallowed.append(module)

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split(".")[0]
                        if module not in self.allowed_imports:
                            disallowed.append(module)

        except SyntaxError as e:
            logger.warning("code_syntax_error", error=str(e))
            # Syntax errors will be caught during execution
            pass

        return disallowed

    def _create_wrapper_code(self, code: str, data: dict[str, Any] | None) -> str:
        """
        Create wrapper code that includes data and captures output.

        Args:
            code: User code to execute.
            data: Data to make available.

        Returns:
            Wrapped code string.
        """
        data_json = json.dumps(data) if data else "{}"

        wrapper = f'''
import sys
import json

# Make data available
data = json.loads('{data_json}')

# Capture result
_result = None

# User code
{code}

# Output result if set
if _result is not None:
    print("__RESULT__")
    print(json.dumps(_result, default=str))
'''
        return wrapper

    async def execute(
        self,
        code: str,
        data: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> PythonExecutionResult:
        """
        Execute Python code securely.

        Args:
            code: Python code to execute.
            data: Data to make available as 'data' variable.
            timeout_seconds: Override timeout.

        Returns:
            Execution result.

        Raises:
            ValidationError: If code contains disallowed imports.
        """
        timeout = timeout_seconds or self.timeout_seconds

        logger.info(
            "executing_python_code",
            code_length=len(code),
            has_data=data is not None,
            timeout=timeout,
        )

        # Validate imports
        disallowed = self._validate_code(code)
        if disallowed:
            error_msg = f"Disallowed imports: {', '.join(disallowed)}"
            logger.warning("disallowed_imports", imports=disallowed)

            return PythonExecutionResult(
                code=code,
                output="",
                error=error_msg,
                success=False,
            )

        # Create temporary file for execution
        start_time = time.time()

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
            ) as f:
                wrapper_code = self._create_wrapper_code(code, data)
                f.write(wrapper_code)
                temp_path = Path(f.name)

            # Execute in subprocess
            try:
                process = await asyncio.create_subprocess_exec(
                    "python",
                    str(temp_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                    execution_time = (time.time() - start_time) * 1000

                    logger.warning(
                        "python_execution_timeout",
                        timeout=timeout,
                    )

                    return PythonExecutionResult(
                        code=code,
                        output="",
                        error=f"Execution timed out after {timeout} seconds",
                        success=False,
                        execution_time_ms=execution_time,
                    )

                execution_time = (time.time() - start_time) * 1000

                stdout_str = stdout.decode("utf-8", errors="replace")
                stderr_str = stderr.decode("utf-8", errors="replace")

                if process.returncode != 0:
                    logger.warning(
                        "python_execution_failed",
                        return_code=process.returncode,
                        stderr=stderr_str[:500],
                    )

                    return PythonExecutionResult(
                        code=code,
                        output=stdout_str,
                        error=stderr_str,
                        success=False,
                        execution_time_ms=execution_time,
                    )

                logger.info(
                    "python_execution_success",
                    execution_time_ms=execution_time,
                    output_length=len(stdout_str),
                )

                return PythonExecutionResult(
                    code=code,
                    output=stdout_str,
                    error=None,
                    success=True,
                    execution_time_ms=execution_time,
                )

            finally:
                # Clean up temp file
                try:
                    temp_path.unlink()
                except Exception:
                    pass

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000

            logger.error(
                "python_execution_error",
                error=str(e),
            )

            return PythonExecutionResult(
                code=code,
                output="",
                error=str(e),
                success=False,
                execution_time_ms=execution_time,
            )

    def execute_sync(
        self,
        code: str,
        data: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> PythonExecutionResult:
        """
        Execute Python code synchronously.

        Args:
            code: Python code to execute.
            data: Data to make available.
            timeout_seconds: Override timeout.

        Returns:
            Execution result.
        """
        return asyncio.run(self.execute(code, data, timeout_seconds))
