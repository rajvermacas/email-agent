"""
Unit tests for Validation Agent models.
"""

import pytest

from info_agent.agents.validation.models import (
    CriterionResult,
    CriterionType,
    PythonExecutionResult,
    ValidationCriterion,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)


class TestValidationStatus:
    """Tests for ValidationStatus enum."""

    def test_pending_value(self) -> None:
        """Test PENDING status value."""
        assert ValidationStatus.PENDING.value == "pending"

    def test_passed_value(self) -> None:
        """Test PASSED status value."""
        assert ValidationStatus.PASSED.value == "passed"

    def test_failed_value(self) -> None:
        """Test FAILED status value."""
        assert ValidationStatus.FAILED.value == "failed"


class TestCriterionType:
    """Tests for CriterionType enum."""

    def test_all_types_exist(self) -> None:
        """Test all criterion types are defined."""
        expected_types = [
            "required_field",
            "row_count",
            "column_count",
            "data_type",
            "value_range",
            "value_in_set",
            "regex_match",
            "not_empty",
            "file_format",
            "custom",
        ]
        actual_types = [t.value for t in CriterionType]
        for expected in expected_types:
            assert expected in actual_types


class TestValidationCriterion:
    """Tests for ValidationCriterion model."""

    def test_create_basic_criterion(self) -> None:
        """Test creating a basic criterion."""
        criterion = ValidationCriterion(
            type=CriterionType.NOT_EMPTY,
            description="Document should not be empty",
        )

        assert criterion.type == CriterionType.NOT_EMPTY
        assert criterion.description == "Document should not be empty"
        assert criterion.required is True
        assert criterion.id is not None

    def test_create_criterion_with_field(self) -> None:
        """Test creating criterion with field."""
        criterion = ValidationCriterion(
            type=CriterionType.REQUIRED_FIELD,
            field="Name",
            description="Name field is required",
        )

        assert criterion.field == "Name"

    def test_create_criterion_with_expected_value(self) -> None:
        """Test creating criterion with expected value."""
        criterion = ValidationCriterion(
            type=CriterionType.ROW_COUNT,
            expected_value=10,
            description="Should have 10 rows",
        )

        assert criterion.expected_value == 10

    def test_create_optional_criterion(self) -> None:
        """Test creating optional criterion."""
        criterion = ValidationCriterion(
            type=CriterionType.CUSTOM,
            description="Optional check",
            required=False,
        )

        assert criterion.required is False


class TestCriterionResult:
    """Tests for CriterionResult model."""

    def test_create_passed_result(self) -> None:
        """Test creating passed result."""
        result = CriterionResult(
            criterion_id="test-id",
            criterion_type=CriterionType.NOT_EMPTY,
            description="Document not empty",
            passed=True,
            actual_value=1000,
            message="Document has 1000 characters",
        )

        assert result.passed is True
        assert result.actual_value == 1000

    def test_create_failed_result(self) -> None:
        """Test creating failed result."""
        result = CriterionResult(
            criterion_id="test-id",
            criterion_type=CriterionType.ROW_COUNT,
            description="Should have 10 rows",
            passed=False,
            actual_value=5,
            expected_value=10,
            message="Expected 10 rows, found 5",
        )

        assert result.passed is False
        assert result.expected_value == 10
        assert result.actual_value == 5


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_create_result(self) -> None:
        """Test creating validation result."""
        result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
        )

        assert result.document_id == "doc-123"
        assert result.document_name == "test.csv"
        assert result.status == ValidationStatus.PENDING
        assert result.passed is False
        assert result.score == 0.0
        assert result.id is not None

    def test_calculate_score_all_passed(self) -> None:
        """Test score calculation with all passed."""
        result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
            criteria_results=[
                CriterionResult(
                    criterion_id="1",
                    criterion_type=CriterionType.NOT_EMPTY,
                    description="Check 1",
                    passed=True,
                ),
                CriterionResult(
                    criterion_id="2",
                    criterion_type=CriterionType.ROW_COUNT,
                    description="Check 2",
                    passed=True,
                ),
            ],
        )

        score = result.calculate_score()

        assert score == 1.0
        assert result.score == 1.0

    def test_calculate_score_partial_pass(self) -> None:
        """Test score calculation with partial pass."""
        result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
            criteria_results=[
                CriterionResult(
                    criterion_id="1",
                    criterion_type=CriterionType.NOT_EMPTY,
                    description="Check 1",
                    passed=True,
                ),
                CriterionResult(
                    criterion_id="2",
                    criterion_type=CriterionType.ROW_COUNT,
                    description="Check 2",
                    passed=False,
                ),
            ],
        )

        score = result.calculate_score()

        assert score == 0.5

    def test_calculate_score_empty(self) -> None:
        """Test score calculation with no criteria."""
        result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
        )

        score = result.calculate_score()

        assert score == 0.0

    def test_check_passed_all_pass(self) -> None:
        """Test pass check when all criteria pass."""
        result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
            criteria_results=[
                CriterionResult(
                    criterion_id="1",
                    criterion_type=CriterionType.NOT_EMPTY,
                    description="Check 1",
                    passed=True,
                ),
                CriterionResult(
                    criterion_id="2",
                    criterion_type=CriterionType.ROW_COUNT,
                    description="Check 2",
                    passed=True,
                ),
            ],
        )

        passed = result.check_passed()

        assert passed is True
        assert result.passed is True

    def test_check_passed_with_failure(self) -> None:
        """Test pass check with a failure."""
        result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
            criteria_results=[
                CriterionResult(
                    criterion_id="1",
                    criterion_type=CriterionType.NOT_EMPTY,
                    description="Check 1",
                    passed=True,
                ),
                CriterionResult(
                    criterion_id="2",
                    criterion_type=CriterionType.ROW_COUNT,
                    description="Check 2",
                    passed=False,
                ),
            ],
        )

        passed = result.check_passed()

        assert passed is False
        assert result.passed is False


class TestPythonExecutionResult:
    """Tests for PythonExecutionResult model."""

    def test_create_successful_result(self) -> None:
        """Test creating successful execution result."""
        result = PythonExecutionResult(
            code="print('hello')",
            output="hello\n",
            success=True,
            execution_time_ms=50.5,
        )

        assert result.success is True
        assert result.output == "hello\n"
        assert result.error is None

    def test_create_failed_result(self) -> None:
        """Test creating failed execution result."""
        result = PythonExecutionResult(
            code="import os",
            output="",
            error="Disallowed import: os",
            success=False,
        )

        assert result.success is False
        assert result.error == "Disallowed import: os"


class TestValidationReport:
    """Tests for ValidationReport model."""

    def test_create_report(self) -> None:
        """Test creating validation report."""
        validation_result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
            passed=True,
            score=1.0,
            criteria_results=[
                CriterionResult(
                    criterion_id="1",
                    criterion_type=CriterionType.NOT_EMPTY,
                    description="Check 1",
                    passed=True,
                ),
            ],
        )

        report = ValidationReport(validation_result=validation_result)

        assert report.validation_result == validation_result
        assert report.id is not None

    def test_generate_summary_passed(self) -> None:
        """Test summary generation for passed validation."""
        validation_result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
            passed=True,
            score=1.0,
            criteria_results=[
                CriterionResult(
                    criterion_id="1",
                    criterion_type=CriterionType.NOT_EMPTY,
                    description="Check 1",
                    passed=True,
                ),
            ],
        )

        report = ValidationReport(validation_result=validation_result)
        summary = report.generate_summary()

        assert "PASSED" in summary
        assert "test.csv" in summary
        assert "100.0%" in summary

    def test_generate_summary_failed_with_issues(self) -> None:
        """Test summary generation for failed validation."""
        validation_result = ValidationResult(
            document_id="doc-123",
            document_name="test.csv",
            passed=False,
            score=0.5,
            criteria_results=[
                CriterionResult(
                    criterion_id="1",
                    criterion_type=CriterionType.NOT_EMPTY,
                    description="Check 1",
                    passed=True,
                ),
                CriterionResult(
                    criterion_id="2",
                    criterion_type=CriterionType.ROW_COUNT,
                    description="Check 2",
                    passed=False,
                ),
            ],
            issues=["Expected 10 rows, found 5"],
        )

        report = ValidationReport(validation_result=validation_result)
        summary = report.generate_summary()

        assert "FAILED" in summary
        assert "50.0%" in summary
        assert "Issues found: 1" in summary
        assert "Expected 10 rows" in summary
