"""
Unit tests for Validation Agent skill definitions.
"""

import pytest

from info_agent.a2a.models import AgentSkill, SkillInputSchema
from info_agent.agents.validation.skills import (
    EXECUTE_PYTHON_SKILL,
    GENERATE_REPORT_SKILL,
    VALIDATE_DOCUMENT_SKILL,
    VALIDATION_AGENT_SKILLS,
)


class TestValidateDocumentSkill:
    """Tests for validate_document skill definition."""

    def test_skill_id(self) -> None:
        """Test skill ID."""
        assert VALIDATE_DOCUMENT_SKILL.id == "validate_document"

    def test_skill_name(self) -> None:
        """Test skill name."""
        assert VALIDATE_DOCUMENT_SKILL.name == "Validate Document"

    def test_skill_description(self) -> None:
        """Test skill has description."""
        assert VALIDATE_DOCUMENT_SKILL.description is not None
        assert "valid" in VALIDATE_DOCUMENT_SKILL.description.lower()

    def test_skill_input_schema(self) -> None:
        """Test skill has input schema."""
        assert VALIDATE_DOCUMENT_SKILL.input_schema is not None
        assert isinstance(VALIDATE_DOCUMENT_SKILL.input_schema, SkillInputSchema)

    def test_required_fields(self) -> None:
        """Test required fields are defined."""
        schema = VALIDATE_DOCUMENT_SKILL.input_schema
        assert schema is not None
        assert "document_id" in schema.required
        assert "document_name" in schema.required
        assert "document_content" in schema.required

    def test_optional_fields(self) -> None:
        """Test optional fields are defined."""
        schema = VALIDATE_DOCUMENT_SKILL.input_schema
        assert schema is not None
        properties = schema.properties
        assert "document_type" in properties
        assert "criteria" in properties
        assert "criteria_text" in properties

    def test_skill_tags(self) -> None:
        """Test skill has tags."""
        assert VALIDATE_DOCUMENT_SKILL.tags is not None
        assert "validation" in VALIDATE_DOCUMENT_SKILL.tags
        assert "document" in VALIDATE_DOCUMENT_SKILL.tags


class TestExecutePythonSkill:
    """Tests for execute_python skill definition."""

    def test_skill_id(self) -> None:
        """Test skill ID."""
        assert EXECUTE_PYTHON_SKILL.id == "execute_python"

    def test_skill_name(self) -> None:
        """Test skill name."""
        assert EXECUTE_PYTHON_SKILL.name == "Execute Python"

    def test_skill_description(self) -> None:
        """Test skill has description."""
        assert EXECUTE_PYTHON_SKILL.description is not None
        assert "python" in EXECUTE_PYTHON_SKILL.description.lower()

    def test_required_fields(self) -> None:
        """Test required fields."""
        schema = EXECUTE_PYTHON_SKILL.input_schema
        assert schema is not None
        assert "code" in schema.required

    def test_optional_fields(self) -> None:
        """Test optional fields."""
        schema = EXECUTE_PYTHON_SKILL.input_schema
        assert schema is not None
        properties = schema.properties
        assert "data" in properties
        assert "timeout_seconds" in properties

    def test_skill_tags(self) -> None:
        """Test skill has tags."""
        assert EXECUTE_PYTHON_SKILL.tags is not None
        assert "validation" in EXECUTE_PYTHON_SKILL.tags
        assert "python" in EXECUTE_PYTHON_SKILL.tags


class TestGenerateReportSkill:
    """Tests for generate_report skill definition."""

    def test_skill_id(self) -> None:
        """Test skill ID."""
        assert GENERATE_REPORT_SKILL.id == "generate_report"

    def test_skill_name(self) -> None:
        """Test skill name."""
        assert GENERATE_REPORT_SKILL.name == "Generate Report"

    def test_skill_description(self) -> None:
        """Test skill has description."""
        assert GENERATE_REPORT_SKILL.description is not None
        assert "report" in GENERATE_REPORT_SKILL.description.lower()

    def test_required_fields(self) -> None:
        """Test required fields."""
        schema = GENERATE_REPORT_SKILL.input_schema
        assert schema is not None
        assert "validation_result_id" in schema.required

    def test_optional_fields(self) -> None:
        """Test optional fields."""
        schema = GENERATE_REPORT_SKILL.input_schema
        assert schema is not None
        properties = schema.properties
        assert "include_recommendations" in properties
        assert "format" in properties

    def test_skill_tags(self) -> None:
        """Test skill has tags."""
        assert GENERATE_REPORT_SKILL.tags is not None
        assert "validation" in GENERATE_REPORT_SKILL.tags
        assert "report" in GENERATE_REPORT_SKILL.tags


class TestValidationAgentSkillsList:
    """Tests for the aggregated skills list."""

    def test_contains_all_skills(self) -> None:
        """Test list contains all skills."""
        assert len(VALIDATION_AGENT_SKILLS) == 3
        assert VALIDATE_DOCUMENT_SKILL in VALIDATION_AGENT_SKILLS
        assert EXECUTE_PYTHON_SKILL in VALIDATION_AGENT_SKILLS
        assert GENERATE_REPORT_SKILL in VALIDATION_AGENT_SKILLS

    def test_all_are_agent_skills(self) -> None:
        """Test all items are AgentSkill instances."""
        for skill in VALIDATION_AGENT_SKILLS:
            assert isinstance(skill, AgentSkill)

    def test_unique_skill_ids(self) -> None:
        """Test all skill IDs are unique."""
        skill_ids = [skill.id for skill in VALIDATION_AGENT_SKILLS]
        assert len(skill_ids) == len(set(skill_ids))
