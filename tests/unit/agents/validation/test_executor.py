"""
Unit tests for Validation Agent executor.
"""

import pytest

from info_agent.a2a.models import TaskRequest, TaskState
from info_agent.agents.validation.executor import (
    ValidationAgentExecutor,
    create_validation_agent_card,
)
from info_agent.agents.validation.models import CriterionType
from info_agent.agents.validation.python_executor import PythonExecutor
from info_agent.agents.validation.skills import VALIDATION_AGENT_SKILLS


class TestCreateValidationAgentCard:
    """Tests for create_validation_agent_card function."""

    def test_default_values(self) -> None:
        """Test default agent card values."""
        card = create_validation_agent_card()

        assert card.id == "validation-agent"
        assert card.endpoint == "http://localhost:8002/a2a"

    def test_custom_agent_id(self) -> None:
        """Test custom agent ID."""
        card = create_validation_agent_card(agent_id="custom-validation")

        assert card.id == "custom-validation"

    def test_custom_endpoint(self) -> None:
        """Test custom endpoint."""
        card = create_validation_agent_card(endpoint="http://custom:9000/a2a")

        assert card.endpoint == "http://custom:9000/a2a"

    def test_agent_name(self) -> None:
        """Test agent name."""
        card = create_validation_agent_card()

        assert card.name == "Validation Agent"

    def test_skills_included(self) -> None:
        """Test skills are included."""
        card = create_validation_agent_card()

        assert card.skills == VALIDATION_AGENT_SKILLS
        assert len(card.skills) == 3

    def test_capabilities(self) -> None:
        """Test capabilities are set."""
        card = create_validation_agent_card()

        assert "streaming" in card.capabilities


class TestValidationAgentExecutorInit:
    """Tests for ValidationAgentExecutor initialization."""

    def test_basic_initialization(self) -> None:
        """Test basic initialization."""
        executor = ValidationAgentExecutor()

        assert executor.agent_card.id == "validation-agent"
        assert executor.python_executor is not None

    def test_custom_python_executor(self) -> None:
        """Test custom Python executor."""
        custom_executor = PythonExecutor(timeout_seconds=10)
        executor = ValidationAgentExecutor(python_executor=custom_executor)

        assert executor.python_executor is custom_executor
        assert executor.python_executor.timeout_seconds == 10


class TestValidateDocument:
    """Tests for validate_document skill."""

    @pytest.fixture
    def executor(self) -> ValidationAgentExecutor:
        """Create test executor."""
        return ValidationAgentExecutor()

    @pytest.mark.asyncio
    async def test_validate_non_empty_text(self, executor: ValidationAgentExecutor) -> None:
        """Test validation of non-empty text."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-123",
                "document_name": "test.txt",
                "document_content": "Hello, this is test content.",
                "document_type": "text",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is True
        assert artifact.data["document_id"] == "doc-123"

    @pytest.mark.asyncio
    async def test_validate_empty_document(self, executor: ValidationAgentExecutor) -> None:
        """Test validation of empty document."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-empty",
                "document_name": "empty.txt",
                "document_content": "",
                "document_type": "text",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is False
        assert len(artifact.data["issues"]) > 0

    @pytest.mark.asyncio
    async def test_validate_csv_row_count(self, executor: ValidationAgentExecutor) -> None:
        """Test CSV validation with row count criterion."""
        csv_content = """Name,Age,City
John,25,NYC
Jane,30,LA
Bob,35,Chicago"""

        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-csv",
                "document_name": "data.csv",
                "document_content": csv_content,
                "document_type": "csv",
                "criteria": [
                    {
                        "type": "row_count",
                        "expected_value": 3,
                        "description": "Should have 3 rows",
                    },
                ],
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is True

    @pytest.mark.asyncio
    async def test_validate_csv_wrong_row_count(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test CSV validation failing row count criterion."""
        csv_content = """Name,Age
John,25
Jane,30"""

        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-csv-fail",
                "document_name": "data.csv",
                "document_content": csv_content,
                "document_type": "csv",
                "criteria": [
                    {
                        "type": "row_count",
                        "expected_value": 5,
                        "description": "Should have 5 rows",
                    },
                ],
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is False
        assert "row" in artifact.data["issues"][0].lower()

    @pytest.mark.asyncio
    async def test_validate_required_field(self, executor: ValidationAgentExecutor) -> None:
        """Test validation with required field criterion."""
        csv_content = """Name,Age,Email
John,25,john@example.com"""

        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-fields",
                "document_name": "users.csv",
                "document_content": csv_content,
                "document_type": "csv",
                "criteria": [
                    {
                        "type": "required_field",
                        "field": "Name",
                        "description": "Name field is required",
                    },
                    {
                        "type": "required_field",
                        "field": "Email",
                        "description": "Email field is required",
                    },
                ],
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is True

    @pytest.mark.asyncio
    async def test_validate_missing_required_field(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test validation failing for missing required field."""
        csv_content = """Name,Age
John,25"""

        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-missing",
                "document_name": "users.csv",
                "document_content": csv_content,
                "document_type": "csv",
                "criteria": [
                    {
                        "type": "required_field",
                        "field": "Email",
                        "description": "Email field is required",
                    },
                ],
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is False
        assert "Email" in str(artifact.data["issues"])

    @pytest.mark.asyncio
    async def test_validate_json_document(self, executor: ValidationAgentExecutor) -> None:
        """Test validation of JSON document."""
        json_content = '{"name": "Test", "count": 42}'

        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-json",
                "document_name": "data.json",
                "document_content": json_content,
                "document_type": "json",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is True

    @pytest.mark.asyncio
    async def test_validate_file_format(self, executor: ValidationAgentExecutor) -> None:
        """Test file format validation."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-format",
                "document_name": "data.csv",
                "document_content": "a,b\n1,2",
                "document_type": "csv",
                "criteria": [
                    {
                        "type": "file_format",
                        "expected_value": "csv",
                        "description": "Must be CSV format",
                    },
                ],
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is True

    @pytest.mark.asyncio
    async def test_validate_with_criteria_text(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test validation with natural language criteria."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-text-criteria",
                "document_name": "report.txt",
                "document_content": "This is a detailed report.",
                "document_type": "text",
                "criteria_text": "Document should contain a report summary",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        # Custom criteria pass by default (need LLM for real analysis)
        artifact = result.artifacts[0]
        assert artifact.data["passed"] is True

    @pytest.mark.asyncio
    async def test_validate_missing_document_id(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test error when document_id is missing."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_name": "test.txt",
                "document_content": "content",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert "document_id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validate_missing_document_name(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test error when document_name is missing."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-123",
                "document_content": "content",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert "document_name" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validate_missing_content(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test error when document_content is missing."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-123",
                "document_name": "test.txt",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert "document_content" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validation_result_cached(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test that validation results are cached."""
        request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-cache",
                "document_name": "test.txt",
                "document_content": "content",
            },
        )

        result = await executor.handle_task(request)
        artifact = result.artifacts[0]
        result_id = artifact.data["result_id"]

        # Verify cached
        cached = executor.get_validation_result(result_id)
        assert cached is not None
        assert cached.document_id == "doc-cache"


class TestExecutePython:
    """Tests for execute_python skill."""

    @pytest.fixture
    def executor(self) -> ValidationAgentExecutor:
        """Create test executor."""
        return ValidationAgentExecutor(
            python_executor=PythonExecutor(timeout_seconds=5)
        )

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, executor: ValidationAgentExecutor) -> None:
        """Test executing simple Python code."""
        request = TaskRequest(
            skill_id="execute_python",
            input={
                "code": "print('hello from python')",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["success"] is True
        assert "hello from python" in artifact.data["output"]

    @pytest.mark.asyncio
    async def test_execute_with_data(self, executor: ValidationAgentExecutor) -> None:
        """Test executing code with data."""
        request = TaskRequest(
            skill_id="execute_python",
            input={
                "code": "total = sum(data['numbers'])\nprint(f'Total: {total}')",
                "data": {"numbers": [1, 2, 3, 4, 5]},
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["success"] is True
        assert "15" in artifact.data["output"]

    @pytest.mark.asyncio
    async def test_execute_disallowed_import(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test blocking disallowed imports."""
        request = TaskRequest(
            skill_id="execute_python",
            input={
                "code": "import os\nprint(os.getcwd())",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["success"] is False
        assert "Disallowed" in artifact.data["error"]

    @pytest.mark.asyncio
    async def test_execute_missing_code(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test error when code is missing."""
        request = TaskRequest(
            skill_id="execute_python",
            input={},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert "code" in result.error.lower()


class TestGenerateReport:
    """Tests for generate_report skill."""

    @pytest.fixture
    def executor(self) -> ValidationAgentExecutor:
        """Create test executor with a cached validation result."""
        exec = ValidationAgentExecutor()
        return exec

    @pytest.mark.asyncio
    async def test_generate_report_markdown(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test generating markdown report."""
        # First validate a document to create a cached result
        validate_request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-report",
                "document_name": "data.csv",
                "document_content": "a,b\n1,2\n3,4",
                "document_type": "csv",
            },
        )
        validate_result = await executor.handle_task(validate_request)
        result_id = validate_result.artifacts[0].data["result_id"]

        # Generate report
        report_request = TaskRequest(
            skill_id="generate_report",
            input={
                "validation_result_id": result_id,
                "format": "markdown",
            },
        )
        report_result = await executor.handle_task(report_request)

        assert report_result.state == TaskState.COMPLETED
        artifact = report_result.artifacts[0]
        assert artifact.data["format"] == "markdown"
        assert "# Validation Report" in artifact.data["content"]
        assert "data.csv" in artifact.data["content"]

    @pytest.mark.asyncio
    async def test_generate_report_json(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test generating JSON report."""
        # First validate a document
        validate_request = TaskRequest(
            skill_id="validate_document",
            input={
                "document_id": "doc-json-report",
                "document_name": "test.txt",
                "document_content": "test content",
                "document_type": "text",
            },
        )
        validate_result = await executor.handle_task(validate_request)
        result_id = validate_result.artifacts[0].data["result_id"]

        # Generate JSON report
        report_request = TaskRequest(
            skill_id="generate_report",
            input={
                "validation_result_id": result_id,
                "format": "json",
            },
        )
        report_result = await executor.handle_task(report_request)

        assert report_result.state == TaskState.COMPLETED
        artifact = report_result.artifacts[0]
        assert artifact.data["format"] == "json"
        # Should be valid JSON
        import json
        parsed = json.loads(artifact.data["content"])
        assert "validation_result" in parsed

    @pytest.mark.asyncio
    async def test_generate_report_not_found(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test error when validation result not found."""
        request = TaskRequest(
            skill_id="generate_report",
            input={
                "validation_result_id": "nonexistent-id",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_generate_report_missing_id(
        self, executor: ValidationAgentExecutor
    ) -> None:
        """Test error when result ID is missing."""
        request = TaskRequest(
            skill_id="generate_report",
            input={},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert "validation_result_id" in result.error.lower()


class TestUnknownSkill:
    """Tests for unknown skill handling."""

    @pytest.fixture
    def executor(self) -> ValidationAgentExecutor:
        """Create test executor."""
        return ValidationAgentExecutor()

    @pytest.mark.asyncio
    async def test_unknown_skill(self, executor: ValidationAgentExecutor) -> None:
        """Test handling of unknown skill."""
        request = TaskRequest(
            skill_id="unknown_skill",
            input={},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert "unknown" in result.error.lower()


class TestHealthCheck:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test health check."""
        executor = ValidationAgentExecutor()

        health = await executor.health_check()

        assert health["status"] == "healthy"
        assert health["agent_id"] == "validation-agent"
        assert "cached_results" in health
