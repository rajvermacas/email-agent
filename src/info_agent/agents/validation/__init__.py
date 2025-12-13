"""
Validation Agent package.

Provides an A2A worker agent for document validation including:
- Validating received documents against specified criteria
- LLM analysis of document content
- Python code execution for complex validation logic
- Generating detailed validation reports
"""

from info_agent.agents.validation.executor import (
    ValidationAgentExecutor,
    create_validation_agent_card,
)
from info_agent.agents.validation.models import (
    ValidationCriterion,
    ValidationResult,
    ValidationReport,
)
from info_agent.agents.validation.skills import (
    EXECUTE_PYTHON_SKILL,
    GENERATE_REPORT_SKILL,
    VALIDATE_DOCUMENT_SKILL,
    VALIDATION_AGENT_SKILLS,
)

__all__ = [
    "ValidationAgentExecutor",
    "create_validation_agent_card",
    "ValidationCriterion",
    "ValidationResult",
    "ValidationReport",
    "VALIDATE_DOCUMENT_SKILL",
    "EXECUTE_PYTHON_SKILL",
    "GENERATE_REPORT_SKILL",
    "VALIDATION_AGENT_SKILLS",
]
