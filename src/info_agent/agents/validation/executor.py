"""
Validation Agent executor implementation.

Implements the A2A agent for document validation operations.
"""

import csv
import io
import json
from typing import Any

import structlog

from info_agent.a2a.executor import (
    BaseAgentExecutor,
    EventQueue,
    RequestContext,
)
from info_agent.a2a.models import AgentCard
from info_agent.agents.validation.models import (
    CriterionResult,
    CriterionType,
    PythonExecutionResult,
    ValidationCriterion,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)
from info_agent.agents.validation.python_executor import PythonExecutor
from info_agent.agents.validation.skills import VALIDATION_AGENT_SKILLS
from info_agent.utils.helpers import generate_uuid, get_current_timestamp

logger = structlog.get_logger(__name__)


def create_validation_agent_card(
    agent_id: str = "validation-agent",
    endpoint: str = "http://localhost:8002/a2a",
) -> AgentCard:
    """
    Create the agent card for the Validation Agent.

    Args:
        agent_id: Unique agent identifier.
        endpoint: A2A endpoint URL.

    Returns:
        Configured AgentCard.
    """
    return AgentCard(
        id=agent_id,
        name="Validation Agent",
        description="A2A agent for document validation with LLM analysis and Python execution",
        endpoint=endpoint,
        skills=VALIDATION_AGENT_SKILLS,
        capabilities=["streaming"],
        metadata={
            "version": "1.0.0",
            "author": "Info-Agent Team",
        },
    )


class ValidationAgentExecutor(BaseAgentExecutor):
    """
    Validation Agent executor.

    Handles document validation tasks using criteria checking and Python execution.

    Attributes:
        _python_executor: Python code executor.
        _validation_results: Cache of validation results.
    """

    def __init__(
        self,
        python_executor: PythonExecutor | None = None,
        agent_id: str = "validation-agent",
        endpoint: str = "http://localhost:8002/a2a",
    ) -> None:
        """
        Initialize Validation Agent executor.

        Args:
            python_executor: Python executor instance.
            agent_id: Agent identifier.
            endpoint: A2A endpoint URL.
        """
        agent_card = create_validation_agent_card(agent_id, endpoint)
        super().__init__(agent_card)

        self._python_executor = python_executor or PythonExecutor()
        self._validation_results: dict[str, ValidationResult] = {}

        logger.info(
            "validation_agent_executor_initialized",
            agent_id=agent_id,
        )

    @property
    def python_executor(self) -> PythonExecutor:
        """Get Python executor."""
        return self._python_executor

    def get_validation_result(self, result_id: str) -> ValidationResult | None:
        """
        Get a cached validation result.

        Args:
            result_id: Result identifier.

        Returns:
            ValidationResult or None.
        """
        return self._validation_results.get(result_id)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute a validation agent task.

        Routes to the appropriate skill handler.

        Args:
            context: Request context.
            event_queue: Event queue for responses.
        """
        skill_id = context.task.skill_id

        logger.info(
            "executing_validation_skill",
            skill_id=skill_id,
            task_id=context.task.id,
        )

        if skill_id == "validate_document":
            await self._handle_validate_document(context, event_queue)
        elif skill_id == "execute_python":
            await self._handle_execute_python(context, event_queue)
        elif skill_id == "generate_report":
            await self._handle_generate_report(context, event_queue)
        else:
            await event_queue.send_error(f"Unknown skill: {skill_id}")

    async def _handle_validate_document(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle validate_document skill.

        Args:
            context: Request context.
            event_queue: Event queue.
        """
        # Extract input parameters
        document_id = context.get_input("document_id")
        document_name = context.get_input("document_name")
        document_content = context.get_input("document_content")
        document_type = context.get_input("document_type", "text")
        criteria_data = context.get_input("criteria", [])
        criteria_text = context.get_input("criteria_text")

        # Validate required fields
        if not document_id:
            await event_queue.send_error("document_id is required")
            return

        if not document_name:
            await event_queue.send_error("document_name is required")
            return

        if document_content is None:
            await event_queue.send_error("document_content is required")
            return

        await event_queue.send_status(f"Starting validation of {document_name}...")

        try:
            # Create validation result
            result = ValidationResult(
                document_id=document_id,
                document_name=document_name,
                status=ValidationStatus.IN_PROGRESS,
            )

            # Parse criteria
            criteria = self._parse_criteria(criteria_data, criteria_text)

            await event_queue.send_status(
                f"Checking {len(criteria)} validation criteria..."
            )

            # Parse document content based on type
            parsed_content = self._parse_document_content(
                document_content, document_type
            )

            # Validate against each criterion
            for criterion in criteria:
                criterion_result = self._check_criterion(
                    criterion, parsed_content, document_type
                )
                result.criteria_results.append(criterion_result)

                if not criterion_result.passed:
                    result.issues.append(criterion_result.message)

            # Calculate score and check pass/fail
            result.calculate_score()
            result.check_passed()

            # Update status
            result.status = (
                ValidationStatus.PASSED if result.passed else ValidationStatus.FAILED
            )
            result.validated_at = get_current_timestamp()

            # Generate recommendations if failed
            if not result.passed:
                result.recommendations = self._generate_recommendations(result)

            # Cache the result
            self._validation_results[result.id] = result

            logger.info(
                "document_validated",
                document_id=document_id,
                passed=result.passed,
                score=result.score,
                issues_count=len(result.issues),
            )

            # Return result
            await event_queue.send_data({
                "result_id": result.id,
                "document_id": result.document_id,
                "document_name": result.document_name,
                "passed": result.passed,
                "score": result.score,
                "status": result.status.value,
                "criteria_checked": len(result.criteria_results),
                "issues": result.issues,
                "recommendations": result.recommendations,
                "validated_at": result.validated_at,
            })

        except Exception as e:
            logger.error("validate_document_failed", error=str(e))
            await event_queue.send_error(f"Validation failed: {e}")

    def _parse_criteria(
        self,
        criteria_data: list[dict[str, Any]],
        criteria_text: str | None,
    ) -> list[ValidationCriterion]:
        """
        Parse validation criteria from input.

        Args:
            criteria_data: Structured criteria list.
            criteria_text: Natural language criteria.

        Returns:
            List of ValidationCriterion objects.
        """
        criteria = []

        # Parse structured criteria
        for data in criteria_data:
            try:
                criterion_type = CriterionType(data.get("type", "custom"))
            except ValueError:
                criterion_type = CriterionType.CUSTOM

            criterion = ValidationCriterion(
                type=criterion_type,
                field=data.get("field"),
                expected_value=data.get("expected_value"),
                description=data.get("description", ""),
                required=data.get("required", True),
            )
            criteria.append(criterion)

        # If no structured criteria, create basic ones from text
        if not criteria and criteria_text:
            criteria.append(
                ValidationCriterion(
                    type=CriterionType.CUSTOM,
                    description=criteria_text,
                    required=True,
                )
            )

        # Add default criterion if none specified
        if not criteria:
            criteria.append(
                ValidationCriterion(
                    type=CriterionType.NOT_EMPTY,
                    description="Document should not be empty",
                    required=True,
                )
            )

        return criteria

    def _parse_document_content(
        self,
        content: str,
        document_type: str,
    ) -> dict[str, Any]:
        """
        Parse document content based on type.

        Args:
            content: Raw document content.
            document_type: Type of document.

        Returns:
            Parsed content dictionary.
        """
        parsed: dict[str, Any] = {
            "raw": content,
            "type": document_type,
        }

        if document_type == "json":
            try:
                parsed["data"] = json.loads(content)
            except json.JSONDecodeError:
                parsed["data"] = None
                parsed["parse_error"] = "Invalid JSON"

        elif document_type == "csv":
            try:
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
                parsed["data"] = rows
                parsed["row_count"] = len(rows)
                parsed["columns"] = list(reader.fieldnames or [])
            except Exception as e:
                parsed["data"] = None
                parsed["parse_error"] = str(e)

        elif document_type == "text":
            lines = content.strip().split("\n")
            parsed["data"] = content
            parsed["line_count"] = len(lines)
            parsed["char_count"] = len(content)

        return parsed

    def _check_criterion(
        self,
        criterion: ValidationCriterion,
        content: dict[str, Any],
        document_type: str,
    ) -> CriterionResult:
        """
        Check a single validation criterion.

        Args:
            criterion: Criterion to check.
            content: Parsed document content.
            document_type: Type of document.

        Returns:
            CriterionResult.
        """
        result = CriterionResult(
            criterion_id=criterion.id,
            criterion_type=criterion.type,
            description=criterion.description,
            passed=False,
            expected_value=criterion.expected_value,
        )

        try:
            if criterion.type == CriterionType.NOT_EMPTY:
                result.passed = bool(content.get("raw", "").strip())
                result.actual_value = len(content.get("raw", ""))
                result.message = (
                    "Document is not empty"
                    if result.passed
                    else "Document is empty"
                )

            elif criterion.type == CriterionType.ROW_COUNT:
                row_count = content.get("row_count", 0)
                expected = criterion.expected_value
                result.actual_value = row_count

                if isinstance(expected, int):
                    result.passed = row_count == expected
                    result.message = (
                        f"Row count matches: {row_count}"
                        if result.passed
                        else f"Expected {expected} rows, found {row_count}"
                    )
                elif isinstance(expected, dict):
                    min_rows = expected.get("min", 0)
                    max_rows = expected.get("max", float("inf"))
                    result.passed = min_rows <= row_count <= max_rows
                    result.message = (
                        f"Row count {row_count} is within range [{min_rows}, {max_rows}]"
                        if result.passed
                        else f"Row count {row_count} is outside range [{min_rows}, {max_rows}]"
                    )
                else:
                    result.passed = row_count > 0
                    result.message = (
                        f"Found {row_count} rows"
                        if result.passed
                        else "No rows found"
                    )

            elif criterion.type == CriterionType.COLUMN_COUNT:
                columns = content.get("columns", [])
                col_count = len(columns)
                expected = criterion.expected_value
                result.actual_value = col_count

                if isinstance(expected, int):
                    result.passed = col_count == expected
                    result.message = (
                        f"Column count matches: {col_count}"
                        if result.passed
                        else f"Expected {expected} columns, found {col_count}"
                    )
                else:
                    result.passed = col_count > 0
                    result.message = f"Found {col_count} columns"

            elif criterion.type == CriterionType.REQUIRED_FIELD:
                field = criterion.field
                columns = content.get("columns", [])
                data = content.get("data")

                if field in columns:
                    result.passed = True
                    result.actual_value = field
                    result.message = f"Required field '{field}' is present"
                elif isinstance(data, dict) and field in data:
                    result.passed = True
                    result.actual_value = field
                    result.message = f"Required field '{field}' is present"
                else:
                    result.passed = False
                    result.actual_value = None
                    result.message = f"Required field '{field}' is missing"

            elif criterion.type == CriterionType.FILE_FORMAT:
                expected_format = criterion.expected_value
                actual_format = document_type
                result.actual_value = actual_format
                result.passed = actual_format == expected_format
                result.message = (
                    f"File format matches: {actual_format}"
                    if result.passed
                    else f"Expected format {expected_format}, got {actual_format}"
                )

            elif criterion.type == CriterionType.CUSTOM:
                # Custom criteria default to pass (would need LLM analysis)
                result.passed = True
                result.message = f"Custom criterion (requires manual review): {criterion.description}"

            else:
                result.message = f"Unsupported criterion type: {criterion.type}"

        except Exception as e:
            result.passed = False
            result.message = f"Error checking criterion: {e}"

        return result

    def _generate_recommendations(
        self, result: ValidationResult
    ) -> list[str]:
        """
        Generate recommendations based on validation issues.

        Args:
            result: Validation result.

        Returns:
            List of recommendations.
        """
        recommendations = []

        for criterion_result in result.criteria_results:
            if not criterion_result.passed:
                if criterion_result.criterion_type == CriterionType.ROW_COUNT:
                    recommendations.append(
                        f"Adjust the number of rows: {criterion_result.message}"
                    )
                elif criterion_result.criterion_type == CriterionType.REQUIRED_FIELD:
                    recommendations.append(
                        f"Add the missing field: {criterion_result.expected_value}"
                    )
                elif criterion_result.criterion_type == CriterionType.NOT_EMPTY:
                    recommendations.append("Ensure the document contains content")
                elif criterion_result.criterion_type == CriterionType.FILE_FORMAT:
                    recommendations.append(
                        f"Convert document to {criterion_result.expected_value} format"
                    )

        return recommendations

    async def _handle_execute_python(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle execute_python skill.

        Args:
            context: Request context.
            event_queue: Event queue.
        """
        code = context.get_input("code")
        data = context.get_input("data")
        timeout = context.get_input("timeout_seconds")

        if not code:
            await event_queue.send_error("code is required")
            return

        await event_queue.send_status("Executing Python code...")

        try:
            result = await self._python_executor.execute(
                code=code,
                data=data,
                timeout_seconds=timeout,
            )

            logger.info(
                "python_executed",
                success=result.success,
                execution_time_ms=result.execution_time_ms,
            )

            await event_queue.send_data({
                "execution_id": result.id,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
                "created_at": result.created_at,
            })

        except Exception as e:
            logger.error("execute_python_failed", error=str(e))
            await event_queue.send_error(f"Python execution failed: {e}")

    async def _handle_generate_report(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle generate_report skill.

        Args:
            context: Request context.
            event_queue: Event queue.
        """
        result_id = context.get_input("validation_result_id")
        include_recommendations = context.get_input("include_recommendations", True)
        output_format = context.get_input("format", "markdown")

        if not result_id:
            await event_queue.send_error("validation_result_id is required")
            return

        # Get cached result
        validation_result = self.get_validation_result(result_id)
        if not validation_result:
            await event_queue.send_error(f"Validation result not found: {result_id}")
            return

        await event_queue.send_status("Generating validation report...")

        try:
            # Create report
            report = ValidationReport(validation_result=validation_result)
            report.generate_summary()

            # Build details
            for criterion_result in validation_result.criteria_results:
                status = "PASS" if criterion_result.passed else "FAIL"
                report.details.append(
                    f"[{status}] {criterion_result.description}: {criterion_result.message}"
                )

            # Format output
            if output_format == "markdown":
                output = self._format_report_markdown(report, include_recommendations)
            elif output_format == "json":
                output = report.model_dump_json(indent=2)
            else:
                output = report.summary + "\n\n" + "\n".join(report.details)

            logger.info(
                "report_generated",
                result_id=result_id,
                format=output_format,
            )

            await event_queue.send_data({
                "report_id": report.id,
                "validation_result_id": result_id,
                "format": output_format,
                "content": output,
                "created_at": report.created_at,
            })

        except Exception as e:
            logger.error("generate_report_failed", error=str(e))
            await event_queue.send_error(f"Report generation failed: {e}")

    def _format_report_markdown(
        self,
        report: ValidationReport,
        include_recommendations: bool,
    ) -> str:
        """
        Format report as markdown.

        Args:
            report: Validation report.
            include_recommendations: Whether to include recommendations.

        Returns:
            Markdown string.
        """
        result = report.validation_result
        status_emoji = "check" if result.passed else "x"
        status_text = "PASSED" if result.passed else "FAILED"

        md = f"""# Validation Report

## Summary

**Document:** {result.document_name}
**Status:** {status_text}
**Score:** {result.score * 100:.1f}%
**Validated:** {result.validated_at}

## Criteria Results

| Status | Criterion | Details |
|--------|-----------|---------|
"""

        for cr in result.criteria_results:
            status = "Pass" if cr.passed else "Fail"
            md += f"| {status} | {cr.description} | {cr.message} |\n"

        if result.issues:
            md += "\n## Issues Found\n\n"
            for issue in result.issues:
                md += f"- {issue}\n"

        if include_recommendations and result.recommendations:
            md += "\n## Recommendations\n\n"
            for rec in result.recommendations:
                md += f"- {rec}\n"

        return md

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status.
        """
        base_health = await super().health_check()

        # Add validation stats
        base_health["cached_results"] = len(self._validation_results)

        return base_health
