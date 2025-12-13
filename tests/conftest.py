"""
Pytest configuration and fixtures for Info-Agent tests.

This module provides shared fixtures for all tests including:
- Mock LLM responses
- Test settings/configuration
- Mock A2A clients
- Test data fixtures
- Database fixtures
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test environment before importing settings
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("LLM_MODEL", "gpt-4-turbo")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("LOG_FORMAT", "console")


# =============================================================================
# CONFIGURATION FIXTURES
# =============================================================================


@pytest.fixture
def test_env_vars() -> dict[str, str]:
    """Return test environment variables."""
    return {
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "gpt-4-turbo",
        "OPENAI_API_KEY": "test-openai-key",
        "GATEWAY_HOST": "127.0.0.1",
        "GATEWAY_PORT": "8000",
        "MAIL_AGENT_PORT": "8002",
        "VALIDATION_AGENT_PORT": "8003",
        "EMAIL_SERVER_PORT": "8080",
        "SMTP_PORT": "1025",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "LOG_FORMAT": "console",
    }


@pytest.fixture
def azure_env_vars() -> dict[str, str]:
    """Return Azure OpenAI environment variables."""
    return {
        "LLM_PROVIDER": "azure_openai",
        "LLM_MODEL": "gpt-4",
        "AZURE_OPENAI_API_KEY": "test-azure-key",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4-deployment",
        "AZURE_OPENAI_API_VERSION": "2024-02-01",
    }


@pytest.fixture
def gemini_env_vars() -> dict[str, str]:
    """Return Gemini environment variables."""
    return {
        "LLM_PROVIDER": "gemini",
        "LLM_MODEL": "gemini-pro",
        "GOOGLE_API_KEY": "test-google-key",
    }


@pytest.fixture
def openrouter_env_vars() -> dict[str, str]:
    """Return OpenRouter environment variables."""
    return {
        "LLM_PROVIDER": "openrouter",
        "LLM_MODEL": "anthropic/claude-3-opus",
        "OPENROUTER_API_KEY": "test-openrouter-key",
    }


@pytest.fixture
def clean_settings_cache() -> Generator[None, None, None]:
    """Clear settings cache before and after test."""
    from info_agent.config import clear_settings_cache

    clear_settings_cache()
    yield
    clear_settings_cache()


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)

    yield path

    # Cleanup
    if path.exists():
        path.unlink()


@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# MOCK LLM FIXTURES
# =============================================================================


@pytest.fixture
def mock_llm_response() -> dict[str, Any]:
    """Return a mock LLM response."""
    return {
        "content": "This is a mock LLM response for testing purposes.",
        "role": "assistant",
        "model": "gpt-4-turbo",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


@pytest.fixture
def mock_chat_model() -> MagicMock:
    """Create a mock chat model."""
    mock = MagicMock()
    mock.invoke = MagicMock(return_value=MagicMock(content="Mock response"))
    mock.ainvoke = AsyncMock(return_value=MagicMock(content="Mock async response"))
    return mock


# =============================================================================
# A2A FIXTURES
# =============================================================================


@pytest.fixture
def mock_agent_card() -> dict[str, Any]:
    """Return a mock A2A agent card."""
    return {
        "id": "test-agent-001",
        "name": "Test Agent",
        "description": "A test agent for unit testing",
        "protocol_version": "1.0",
        "endpoint": "http://localhost:8002/a2a",
        "skills": [
            {
                "id": "test-skill",
                "name": "Test Skill",
                "description": "A skill for testing",
                "input_schema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            }
        ],
    }


@pytest.fixture
def mock_a2a_task() -> dict[str, Any]:
    """Return a mock A2A task."""
    return {
        "id": "task-001",
        "skill_id": "test-skill",
        "status": "completed",
        "input": {"message": "Test input"},
        "artifacts": [
            {
                "parts": [
                    {"type": "text", "text": "Test output"},
                    {"type": "data", "data": {"result": "success"}},
                ]
            }
        ],
    }


@pytest.fixture
def mock_a2a_client() -> MagicMock:
    """Create a mock A2A client."""
    mock = MagicMock()
    mock.create_task = AsyncMock(
        return_value=MagicMock(id="task-001", status="completed", artifacts=[])
    )
    mock.get_task = AsyncMock(
        return_value=MagicMock(id="task-001", status="completed", artifacts=[])
    )
    mock.cancel_task = AsyncMock(return_value=True)
    return mock


# =============================================================================
# EMAIL FIXTURES
# =============================================================================


@pytest.fixture
def sample_email() -> dict[str, Any]:
    """Return a sample email message."""
    return {
        "id": "email-001",
        "thread_id": "thread-001",
        "from_address": "sender@example.com",
        "to_address": "recipient@example.com",
        "subject": "Test Email",
        "body": "This is a test email body.",
        "html_body": "<p>This is a test email body.</p>",
        "attachments": [],
        "sent_at": "2024-01-15T10:30:00Z",
        "received_at": None,
        "is_reply": False,
        "in_reply_to": None,
    }


@pytest.fixture
def sample_email_with_attachment() -> dict[str, Any]:
    """Return a sample email with attachment."""
    return {
        "id": "email-002",
        "thread_id": "thread-001",
        "from_address": "sender@example.com",
        "to_address": "recipient@example.com",
        "subject": "Re: Test Email",
        "body": "Please find the attached document.",
        "attachments": [
            {
                "id": "attach-001",
                "filename": "recipes.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size": 15360,
            }
        ],
        "is_reply": True,
        "in_reply_to": "email-001",
    }


# =============================================================================
# WORKFLOW FIXTURES
# =============================================================================


@pytest.fixture
def sample_workflow_input() -> dict[str, Any]:
    """Return sample workflow input data."""
    return {
        "instructions": "Send mail to raj@gmail.com asking for 10 food recipes.",
        "faq": "Q: What format? A: Excel file with Recipe Name, Ingredients columns.",
        "escalation_rules": "If no reply in 48 hours, contact vishal@gmail.com.",
        "validation_criteria": "Excel with exactly 10 rows, all cells filled.",
        "target_email": "raj@gmail.com",
        "target_name": "Raj",
        "requester_email": "mrinal@gmail.com",
    }


@pytest.fixture
def sample_workflow_state() -> dict[str, Any]:
    """Return a sample workflow state."""
    return {
        "workflow_id": "wf-001",
        "status": "planning",
        "instructions": "Send email requesting recipes",
        "target_email": "raj@gmail.com",
        "target_name": "Raj",
        "timeout_hours": 48,
        "retry_count": 0,
        "max_retries": 3,
        "plan": [],
        "current_step": 0,
        "email_threads": [],
        "clarification_history": [],
        "received_documents": [],
        "validation_result": None,
        "audit_log": [],
    }


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
def test_data_dir() -> Path:
    """Return path to test_data directory."""
    return Path(__file__).parent.parent / "test_data"


@pytest.fixture
def sample_instructions_content() -> str:
    """Return sample instructions file content."""
    return """Send mail to raj@gmail.com asking for an Excel sheet containing 10 rows of food recipes.
The Excel should have columns: Recipe Name, Ingredients, Cooking Time, Difficulty Level.
"""


@pytest.fixture
def sample_faq_content() -> str:
    """Return sample FAQ file content."""
    return """Q: What format should the recipes be in?
A: Please provide an Excel file (.xlsx) with columns for Recipe Name, Ingredients, Cooking Time, and Difficulty Level.

Q: How many recipes are needed?
A: We need exactly 10 recipes.

Q: What difficulty levels should be used?
A: Use Easy, Medium, or Hard for difficulty levels.
"""


@pytest.fixture
def sample_escalation_content() -> str:
    """Return sample escalation file content."""
    return """If raj@gmail.com is not available, out of office, or doesn't reply within 48 hours, reach out to vishal@gmail.com.

If the requested user has clarifying questions not covered in the FAQ, first email mrinal@gmail.com to get answers, then share with raj@gmail.com.
"""


@pytest.fixture
def sample_validation_content() -> str:
    """Return sample validation file content."""
    return """The reply should have an attachment with:
1. An Excel file (.xlsx format)
2. Exactly 10 rows of food recipes
3. Columns: Recipe Name, Ingredients, Cooking Time, Difficulty Level
4. All cells should be filled (no empty values)
5. Difficulty Level should be one of: Easy, Medium, Hard
"""


# =============================================================================
# UTILITY FIXTURES
# =============================================================================


@pytest.fixture
def mock_httpx_client() -> Generator[MagicMock, None, None]:
    """Mock httpx.AsyncClient for HTTP tests."""
    with patch("httpx.AsyncClient") as mock:
        client_instance = MagicMock()
        client_instance.post = AsyncMock()
        client_instance.get = AsyncMock()
        client_instance.aclose = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        mock.return_value.__aexit__ = AsyncMock(return_value=None)
        yield client_instance


@pytest.fixture
def capture_logs(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture log output for assertions."""
    import logging

    caplog.set_level(logging.DEBUG)
    return caplog
