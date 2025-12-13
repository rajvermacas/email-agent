"""
Validation Agent data models.

Defines the data structures for validation operations.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from info_agent.utils.helpers import generate_uuid, get_current_timestamp


class ValidationStatus(str, Enum):
    """Validation status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class CriterionType(str, Enum):
    """Type of validation criterion."""

    REQUIRED_FIELD = "required_field"
    ROW_COUNT = "row_count"
    COLUMN_COUNT = "column_count"
    DATA_TYPE = "data_type"
    VALUE_RANGE = "value_range"
    VALUE_IN_SET = "value_in_set"
    REGEX_MATCH = "regex_match"
    NOT_EMPTY = "not_empty"
    FILE_FORMAT = "file_format"
    CUSTOM = "custom"


class ValidationCriterion(BaseModel):
    """
    A single validation criterion.

    Attributes:
        id: Unique criterion identifier.
        type: Type of validation check.
        field: Field or column to validate (if applicable).
        expected_value: Expected value or pattern.
        description: Human-readable description.
        required: Whether this criterion must pass.
    """

    id: str = Field(default_factory=generate_uuid)
    type: CriterionType
    field: str | None = None
    expected_value: Any = None
    description: str
    required: bool = True


class CriterionResult(BaseModel):
    """
    Result of checking a single criterion.

    Attributes:
        criterion_id: ID of the criterion checked.
        criterion_type: Type of criterion.
        description: Description of what was checked.
        passed: Whether the criterion passed.
        actual_value: The actual value found.
        expected_value: The expected value.
        message: Detailed message about the result.
    """

    criterion_id: str
    criterion_type: CriterionType
    description: str
    passed: bool
    actual_value: Any = None
    expected_value: Any = None
    message: str = ""


class ValidationResult(BaseModel):
    """
    Overall validation result.

    Attributes:
        id: Unique result identifier.
        document_id: ID of the validated document.
        document_name: Name of the validated document.
        status: Overall validation status.
        passed: Whether all required criteria passed.
        score: Validation score (0.0 to 1.0).
        criteria_results: Results for each criterion.
        issues: List of issues found.
        recommendations: Suggestions for fixing issues.
        validated_at: Timestamp of validation.
    """

    id: str = Field(default_factory=generate_uuid)
    document_id: str
    document_name: str
    status: ValidationStatus = ValidationStatus.PENDING
    passed: bool = False
    score: float = 0.0
    criteria_results: list[CriterionResult] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    validated_at: str = Field(default_factory=get_current_timestamp)

    def calculate_score(self) -> float:
        """
        Calculate validation score based on criteria results.

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.criteria_results:
            return 0.0

        passed_count = sum(1 for r in self.criteria_results if r.passed)
        self.score = passed_count / len(self.criteria_results)
        return self.score

    def check_passed(self) -> bool:
        """
        Check if validation passed (all required criteria met).

        Returns:
            True if all required criteria passed.
        """
        for result in self.criteria_results:
            # Find the original criterion to check if it's required
            # For simplicity, we mark as passed only if all criteria passed
            if not result.passed:
                self.passed = False
                return False

        self.passed = True
        return True


class PythonExecutionResult(BaseModel):
    """
    Result of Python code execution.

    Attributes:
        id: Unique result identifier.
        code: The Python code executed.
        output: Standard output from execution.
        error: Error message if execution failed.
        success: Whether execution succeeded.
        execution_time_ms: Time taken in milliseconds.
        created_at: Timestamp of execution.
    """

    id: str = Field(default_factory=generate_uuid)
    code: str
    output: str = ""
    error: str | None = None
    success: bool = False
    execution_time_ms: float = 0.0
    created_at: str = Field(default_factory=get_current_timestamp)


class ValidationReport(BaseModel):
    """
    Complete validation report.

    Attributes:
        id: Unique report identifier.
        validation_result: The validation result.
        summary: Executive summary.
        details: Detailed findings.
        python_analysis: Results from Python analysis (if any).
        created_at: Timestamp of report creation.
    """

    id: str = Field(default_factory=generate_uuid)
    validation_result: ValidationResult
    summary: str = ""
    details: list[str] = Field(default_factory=list)
    python_analysis: PythonExecutionResult | None = None
    created_at: str = Field(default_factory=get_current_timestamp)

    def generate_summary(self) -> str:
        """
        Generate executive summary.

        Returns:
            Summary string.
        """
        result = self.validation_result
        status = "PASSED" if result.passed else "FAILED"
        score_pct = result.score * 100

        passed_count = sum(1 for r in result.criteria_results if r.passed)
        total_count = len(result.criteria_results)

        self.summary = (
            f"Validation {status}: {result.document_name}\n"
            f"Score: {score_pct:.1f}% ({passed_count}/{total_count} criteria passed)\n"
            f"Issues found: {len(result.issues)}"
        )

        if result.issues:
            self.summary += "\n\nKey Issues:\n"
            for issue in result.issues[:3]:  # Show top 3 issues
                self.summary += f"  - {issue}\n"

        return self.summary
