"""
Validation Agent skill definitions.

Defines the A2A skills that the Validation Agent provides.
"""

from info_agent.a2a.models import AgentSkill, SkillInputSchema


VALIDATE_DOCUMENT_SKILL = AgentSkill(
    id="validate_document",
    name="Validate Document",
    description="Validates a document against specified criteria using LLM analysis",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "document_id": {
                "type": "string",
                "description": "Unique identifier for the document",
            },
            "document_name": {
                "type": "string",
                "description": "Name of the document being validated",
            },
            "document_content": {
                "type": "string",
                "description": "The content of the document to validate (text or base64)",
            },
            "document_type": {
                "type": "string",
                "enum": ["text", "csv", "json", "xlsx"],
                "description": "Type/format of the document",
            },
            "criteria": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Type of criterion",
                        },
                        "field": {
                            "type": "string",
                            "description": "Field to validate",
                        },
                        "expected_value": {
                            "description": "Expected value or pattern",
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable description",
                        },
                        "required": {
                            "type": "boolean",
                            "description": "Whether criterion is required",
                        },
                    },
                },
                "description": "List of validation criteria",
            },
            "criteria_text": {
                "type": "string",
                "description": "Natural language description of validation criteria",
            },
        },
        required=["document_id", "document_name", "document_content"],
    ),
    tags=["validation", "document", "analysis"],
)


EXECUTE_PYTHON_SKILL = AgentSkill(
    id="execute_python",
    name="Execute Python",
    description="Executes Python code for complex validation logic",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "code": {
                "type": "string",
                "description": "Python code to execute",
            },
            "data": {
                "type": "object",
                "description": "Data to make available to the code (as 'data' variable)",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds (default: 30)",
            },
        },
        required=["code"],
    ),
    tags=["validation", "python", "execution"],
)


GENERATE_REPORT_SKILL = AgentSkill(
    id="generate_report",
    name="Generate Report",
    description="Generates a detailed validation report",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "validation_result_id": {
                "type": "string",
                "description": "ID of the validation result to report on",
            },
            "include_recommendations": {
                "type": "boolean",
                "description": "Whether to include recommendations (default: true)",
            },
            "format": {
                "type": "string",
                "enum": ["text", "json", "markdown"],
                "description": "Output format for the report (default: markdown)",
            },
        },
        required=["validation_result_id"],
    ),
    tags=["validation", "report", "summary"],
)


VALIDATION_AGENT_SKILLS = [
    VALIDATE_DOCUMENT_SKILL,
    EXECUTE_PYTHON_SKILL,
    GENERATE_REPORT_SKILL,
]
