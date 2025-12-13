"""Integration tests for FastAPI gateway.

These tests verify the gateway endpoints work correctly
with the supervisor agent and other components.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from info_agent.gateway.app import create_app_sync, GatewayApp, create_app
from info_agent.gateway.models import (
    WorkflowCreateRequest,
    WorkflowStatus,
)
from info_agent.supervisor.agent import SupervisorAgent


logger = logging.getLogger(__name__)


@pytest.fixture
def supervisor() -> SupervisorAgent:
    """Create supervisor agent."""
    return SupervisorAgent(
        use_llm=False,
        use_stub_delegator=True,
    )


@pytest.fixture
def app(supervisor: SupervisorAgent) -> TestClient:
    """Create test client with the gateway app."""
    fastapi_app = create_app_sync(supervisor=supervisor)
    return TestClient(fastapi_app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, app: TestClient) -> None:
        """Test basic health check endpoint."""
        response = app.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

    def test_readiness_check(self, app: TestClient) -> None:
        """Test readiness check endpoint."""
        response = app.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"

    def test_liveness_check(self, app: TestClient) -> None:
        """Test liveness check endpoint."""
        response = app.get("/health/live")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "alive"


class TestWorkflowEndpoints:
    """Tests for workflow management endpoints."""

    def test_create_workflow(self, app: TestClient) -> None:
        """Test workflow creation endpoint."""
        request_data = {
            "instructions": "Send email requesting document",
            "target_email": "user@example.com",
        }

        response = app.post("/api/workflows", json=request_data)
        assert response.status_code == 201

        data = response.json()
        assert "workflow_id" in data
        assert data["status"] in ["pending", "planning"]

    def test_create_workflow_with_options(self, app: TestClient) -> None:
        """Test workflow creation with all options."""
        request_data = {
            "instructions": "Send email requesting document",
            "target_email": "user@example.com",
            "faq": [
                {
                    "question": "What format?",
                    "answer": "Excel please",
                }
            ],
            "escalation_rules": {
                "no_response_hours": 24,
                "escalation_email": "manager@example.com",
            },
            "validation_criteria": {
                "required_format": "xlsx",
            },
        }

        response = app.post("/api/workflows", json=request_data)
        assert response.status_code == 201

        data = response.json()
        assert data["workflow_id"] is not None

    def test_list_workflows(self, app: TestClient) -> None:
        """Test workflow listing endpoint."""
        # Create a few workflows
        for i in range(3):
            app.post(
                "/api/workflows",
                json={
                    "instructions": f"Test {i}",
                    "target_email": f"user{i}@example.com",
                },
            )

        # List workflows
        response = app.get("/api/workflows")
        assert response.status_code == 200

        data = response.json()
        assert "workflows" in data
        assert len(data["workflows"]) >= 3

    def test_get_workflow(self, app: TestClient) -> None:
        """Test get single workflow endpoint."""
        # Create a workflow
        create_response = app.post(
            "/api/workflows",
            json={
                "instructions": "Test workflow",
                "target_email": "user@example.com",
            },
        )
        workflow_id = create_response.json()["workflow_id"]

        # Get the workflow
        response = app.get(f"/api/workflows/{workflow_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["workflow_id"] == workflow_id

    def test_get_nonexistent_workflow(self, app: TestClient) -> None:
        """Test getting a workflow that doesn't exist."""
        response = app.get("/api/workflows/nonexistent-id")
        assert response.status_code == 404


class TestApprovalEndpoints:
    """Tests for plan approval endpoints."""

    def test_approve_workflow(self, app: TestClient) -> None:
        """Test workflow approval endpoint."""
        # Create a workflow
        create_response = app.post(
            "/api/workflows",
            json={
                "instructions": "Test workflow",
                "target_email": "user@example.com",
            },
        )
        workflow_id = create_response.json()["workflow_id"]

        # Approve the plan
        response = app.post(
            f"/api/workflows/{workflow_id}/approve",
            json={"approved": True},
        )
        assert response.status_code == 200

    def test_reject_workflow_with_feedback(self, app: TestClient) -> None:
        """Test workflow rejection with feedback."""
        # Create a workflow
        create_response = app.post(
            "/api/workflows",
            json={
                "instructions": "Test workflow",
                "target_email": "user@example.com",
            },
        )
        workflow_id = create_response.json()["workflow_id"]

        # Reject with feedback
        response = app.post(
            f"/api/workflows/{workflow_id}/approve",
            json={
                "approved": False,
                "feedback": "Please add more detail",
            },
        )
        assert response.status_code == 200


class TestWebhookEndpoints:
    """Tests for webhook endpoints."""

    def test_email_received_webhook(self, app: TestClient) -> None:
        """Test email received webhook."""
        # Create a workflow first
        create_response = app.post(
            "/api/workflows",
            json={
                "instructions": "Test workflow",
                "target_email": "user@example.com",
            },
        )
        workflow_id = create_response.json()["workflow_id"]

        # Send email received webhook
        response = app.post(
            "/webhooks/email/received",
            json={
                "workflow_id": workflow_id,
                "from_address": "user@example.com",
                "to_address": "agent@example.com",
                "subject": "Re: Document Request",
                "body": "Here is the document.",
            },
        )
        assert response.status_code in [200, 202]

    def test_validation_complete_webhook(self, app: TestClient) -> None:
        """Test validation complete webhook."""
        # Create a workflow first
        create_response = app.post(
            "/api/workflows",
            json={
                "instructions": "Test workflow",
                "target_email": "user@example.com",
            },
        )
        workflow_id = create_response.json()["workflow_id"]

        # Send validation complete webhook
        response = app.post(
            "/webhooks/validation/complete",
            json={
                "workflow_id": workflow_id,
                "passed": True,
                "score": 0.95,
                "issues": [],
            },
        )
        assert response.status_code in [200, 202]


class TestSSEEndpoint:
    """Tests for Server-Sent Events endpoint."""

    def test_sse_endpoint_exists(self, app: TestClient) -> None:
        """Test that SSE endpoint exists."""
        # Create a workflow
        create_response = app.post(
            "/api/workflows",
            json={
                "instructions": "Test workflow",
                "target_email": "user@example.com",
            },
        )
        workflow_id = create_response.json()["workflow_id"]

        # Check SSE endpoint - just verify it returns streaming response
        with app.stream("POST", f"/api/workflows/{workflow_id}/stream") as response:
            # SSE streams should be text/event-stream
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type


class TestPagination:
    """Tests for pagination in list endpoints."""

    def test_list_workflows_with_limit(self, app: TestClient) -> None:
        """Test workflow listing with limit."""
        # Create multiple workflows
        for i in range(10):
            app.post(
                "/api/workflows",
                json={
                    "instructions": f"Test {i}",
                    "target_email": f"user{i}@example.com",
                },
            )

        # List with limit
        response = app.get("/api/workflows?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert len(data["workflows"]) <= 5

    def test_list_workflows_with_offset(self, app: TestClient) -> None:
        """Test workflow listing with offset."""
        # Create multiple workflows
        for i in range(10):
            app.post(
                "/api/workflows",
                json={
                    "instructions": f"Test {i}",
                    "target_email": f"user{i}@example.com",
                },
            )

        # List with offset
        response = app.get("/api/workflows?offset=5")
        assert response.status_code == 200


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_json(self, app: TestClient) -> None:
        """Test handling of invalid JSON."""
        response = app.post(
            "/api/workflows",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_required_field(self, app: TestClient) -> None:
        """Test handling of missing required field."""
        response = app.post(
            "/api/workflows",
            json={
                "target_email": "user@example.com",
                # Missing 'instructions'
            },
        )
        assert response.status_code == 422

    def test_invalid_email_format(self, app: TestClient) -> None:
        """Test handling of invalid email format."""
        response = app.post(
            "/api/workflows",
            json={
                "instructions": "Test",
                "target_email": "not-an-email",
            },
        )
        # Might be 422 or 400 depending on validation
        assert response.status_code in [400, 422]


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, app: TestClient) -> None:
        """Test that CORS headers are present."""
        response = app.options(
            "/api/workflows",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # CORS preflight should return 200
        assert response.status_code == 200


class TestContentTypes:
    """Tests for content type handling."""

    def test_json_response(self, app: TestClient) -> None:
        """Test that API returns JSON content type."""
        response = app.get("/health")
        assert "application/json" in response.headers["content-type"]

    def test_html_response_for_frontend(self, app: TestClient) -> None:
        """Test that frontend returns HTML content type."""
        response = app.get("/")
        assert "text/html" in response.headers["content-type"]
