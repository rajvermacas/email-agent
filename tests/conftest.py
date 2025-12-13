"""
Shared pytest fixtures for Info-Agent tests.

This module provides common fixtures used across unit and integration tests.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set test environment before importing any info_agent modules
os.environ.setdefault("GOOGLE_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("ENV", "test")


# =============================================================================
# Event Loop Fixture
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db_path(temp_dir: Path) -> Path:
    """Create a temporary database path."""
    return temp_dir / "test.db"


@pytest.fixture
def temp_checkpoint_path(temp_dir: Path) -> Path:
    """Create a temporary checkpoint database path."""
    return temp_dir / "checkpoints.db"


# =============================================================================
# Mock Settings Fixture
# =============================================================================

@pytest.fixture
def mock_settings() -> Mock:
    """Create mock settings for testing."""
    from info_agent.config import Settings

    settings = Mock(spec=Settings)
    settings.google_api_key = "test-api-key-123456789"
    settings.llm_model = "gemini-2.5-flash"
    settings.llm_temperature = 0.7
    settings.llm_max_tokens = 4096
    settings.env = "test"
    settings.debug = True
    settings.log_level = "DEBUG"
    settings.log_format = "console"
    settings.gateway_host = "127.0.0.1"
    settings.gateway_port = 8000
    settings.email_server_host = "127.0.0.1"
    settings.email_smtp_port = 1025
    settings.email_rest_port = 8025
    settings.webhook_url = "http://localhost:8000/api/v1/webhooks/email"
    settings.a2a_registry_url = "http://localhost:8000/api/v1/a2a"
    settings.checkpoint_db_path = ":memory:"
    settings.a2a_db_path = ":memory:"
    settings.email_db_path = ":memory:"
    return settings


@pytest.fixture
def mock_settings_context(mock_settings: Mock):
    """Context manager to patch get_settings globally."""
    with patch("info_agent.config.get_settings", return_value=mock_settings):
        yield mock_settings


# =============================================================================
# Mock LLM Fixtures
# =============================================================================

@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM instance."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test LLM response"))
    llm.invoke = MagicMock(return_value=MagicMock(content="Test LLM response"))
    return llm


@pytest.fixture
def mock_llm_factory(mock_llm: MagicMock):
    """Patch the LLM factory to return mock LLM."""
    with patch("info_agent.llm.get_gemini_llm", return_value=mock_llm):
        with patch("info_agent.llm.factory.get_gemini_llm", return_value=mock_llm):
            yield mock_llm


# =============================================================================
# Mock HTTP Client Fixtures
# =============================================================================

@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Create a mock httpx AsyncClient."""
    client = MagicMock()
    client.post = AsyncMock()
    client.get = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# =============================================================================
# Mock Email Fixtures
# =============================================================================

@pytest.fixture
def sample_email_data() -> dict:
    """Sample email data for testing."""
    return {
        "id": "test-email-001",
        "from_addr": "sender@example.com",
        "to_addr": "recipient@example.com",
        "subject": "Test Subject",
        "body": "This is a test email body.",
        "timestamp": "2024-01-15T10:30:00Z",
        "status": "received",
    }


@pytest.fixture
def sample_email_list(sample_email_data: dict) -> list:
    """Sample list of emails for testing."""
    return [
        sample_email_data,
        {
            **sample_email_data,
            "id": "test-email-002",
            "subject": "Another Test Subject",
        },
        {
            **sample_email_data,
            "id": "test-email-003",
            "subject": "Third Test Subject",
        },
    ]


# =============================================================================
# Mock A2A Fixtures
# =============================================================================

@pytest.fixture
def sample_agent_card() -> dict:
    """Sample A2A agent card for testing."""
    return {
        "name": "test-agent",
        "description": "A test agent for unit testing",
        "url": "http://localhost:9000",
        "version": "1.0.0",
        "skills": [
            {
                "name": "test-skill",
                "description": "A test skill",
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {"type": "object", "properties": {}},
            }
        ],
        "metadata": {"category": "test"},
    }


@pytest.fixture
def sample_agent_cards(sample_agent_card: dict) -> list:
    """Sample list of agent cards for testing."""
    return [
        sample_agent_card,
        {
            **sample_agent_card,
            "name": "mail-agent",
            "description": "Email handling agent",
            "url": "http://localhost:9001",
        },
        {
            **sample_agent_card,
            "name": "search-agent",
            "description": "Search and retrieval agent",
            "url": "http://localhost:9002",
        },
    ]


# =============================================================================
# Mock Workflow Fixtures
# =============================================================================

@pytest.fixture
def sample_workflow_state() -> dict:
    """Sample workflow state for testing."""
    return {
        "workflow_id": "test-workflow-001",
        "instructions": "Process this test request",
        "target_email": "target@example.com",
        "plan": None,
        "status": "pending",
        "audit_log": [],
        "current_step": 0,
        "step_results": [],
    }


@pytest.fixture
def sample_execution_plan() -> dict:
    """Sample execution plan for testing."""
    return {
        "workflow_id": "test-workflow-001",
        "steps": [
            {
                "step_id": 1,
                "agent": "mail-agent",
                "action": "send_email",
                "parameters": {
                    "to": "target@example.com",
                    "subject": "Test",
                    "body": "Test body",
                },
            },
            {
                "step_id": 2,
                "agent": "mail-agent",
                "action": "wait_for_response",
                "parameters": {"timeout": 300},
            },
        ],
        "estimated_steps": 2,
    }


# =============================================================================
# FastAPI Test Client Fixtures
# =============================================================================

@pytest.fixture
def test_app(mock_settings_context) -> FastAPI:
    """Create a test FastAPI application."""
    from info_agent.main import create_app

    app = create_app()
    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(test_app)


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
async def a2a_storage(temp_db_path: Path):
    """Create A2A storage instance for testing."""
    from info_agent.a2a.storage import A2AStorage

    storage = A2AStorage(str(temp_db_path))
    await storage.initialize()
    yield storage
    await storage.close()


@pytest.fixture
async def email_storage(temp_db_path: Path):
    """Create email storage instance for testing."""
    from info_agent.email.storage import EmailStorage

    storage = EmailStorage(str(temp_db_path))
    await storage.initialize()
    yield storage
    await storage.close()


# =============================================================================
# Utility Functions
# =============================================================================

def create_mock_response(status_code: int = 200, json_data: dict = None) -> MagicMock:
    """Create a mock HTTP response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        response.raise_for_status.side_effect = HTTPStatusError(
            "Error", request=MagicMock(), response=response
        )
    return response


def create_mock_async_response(
    status_code: int = 200, json_data: dict = None
) -> AsyncMock:
    """Create a mock async HTTP response."""
    response = AsyncMock()
    response.status_code = status_code
    response.json = AsyncMock(return_value=json_data or {})
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        response.raise_for_status.side_effect = HTTPStatusError(
            "Error", request=MagicMock(), response=response
        )
    return response
