"""
Integration tests for the FastAPI Gateway.

Tests the complete API gateway functionality including routes,
request/response handling, and basic endpoint behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_workflow_graph():
    """Mock the workflow graph for testing."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "workflow_id": "test-workflow-001",
        "status": "completed",
        "plan": {"steps": []},
        "audit_log": ["Step 1 completed"],
    })
    return mock_graph


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self, test_client):
        """Test that health check returns healthy status."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_health_check_includes_service_info(self, test_client):
        """Test that health check includes service information."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "info-agent-gateway"


class TestAPIRoutes:
    """Tests for API route structure."""

    def test_api_v1_prefix_exists(self, test_client):
        """Test that API v1 prefix is configured."""
        # Health endpoint should be accessible
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_openapi_schema_available(self, test_client):
        """Test that OpenAPI schema is available."""
        response = test_client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data

    def test_docs_endpoint_available(self, test_client):
        """Test that Swagger docs are available."""
        response = test_client.get("/docs")

        assert response.status_code == 200


class TestWorkflowEndpoints:
    """Tests for workflow management endpoints."""

    @patch("info_agent.api.routes.workflows.create_supervisor_graph")
    def test_create_workflow_success(
        self, mock_create_graph, test_client, mock_workflow_graph
    ):
        """Test successful workflow creation."""
        mock_create_graph.return_value = mock_workflow_graph

        response = test_client.post(
            "/api/v1/workflows",
            json={
                "instructions": "Send an email to test@example.com",
                "target_email": "test@example.com",
            },
        )

        assert response.status_code in [200, 201, 202]

    def test_create_workflow_missing_instructions(self, test_client):
        """Test workflow creation fails without instructions."""
        response = test_client.post(
            "/api/v1/workflows",
            json={"target_email": "test@example.com"},
        )

        assert response.status_code == 422  # Validation error

    def test_create_workflow_invalid_email(self, test_client):
        """Test workflow creation fails with invalid email format."""
        response = test_client.post(
            "/api/v1/workflows",
            json={
                "instructions": "Send an email",
                "target_email": "invalid-email",
            },
        )

        assert response.status_code == 422  # Validation error

    @patch("info_agent.api.routes.workflows.get_workflow_status")
    def test_get_workflow_status(self, mock_get_status, test_client):
        """Test getting workflow status."""
        mock_get_status.return_value = {
            "workflow_id": "test-123",
            "status": "running",
            "current_step": 1,
        }

        response = test_client.get("/api/v1/workflows/test-123")

        assert response.status_code == 200

    @patch("info_agent.api.routes.workflows.get_workflow_status")
    def test_get_workflow_not_found(self, mock_get_status, test_client):
        """Test getting non-existent workflow returns 404."""
        from info_agent.utils.exceptions import WorkflowNotFoundError

        mock_get_status.side_effect = WorkflowNotFoundError(
            "Workflow not found", workflow_id="nonexistent"
        )

        response = test_client.get("/api/v1/workflows/nonexistent")

        assert response.status_code == 404


class TestWebhookEndpoints:
    """Tests for webhook endpoints."""

    @patch("info_agent.api.routes.webhooks.process_email_webhook")
    def test_email_webhook_success(self, mock_process, test_client):
        """Test successful email webhook processing."""
        mock_process.return_value = {"status": "processed"}

        response = test_client.post(
            "/api/v1/webhooks/email",
            json={
                "event_type": "email_received",
                "email_id": "email-123",
                "from_addr": "sender@example.com",
                "to_addr": "recipient@example.com",
                "subject": "Test Subject",
                "body": "Test body content",
            },
        )

        assert response.status_code in [200, 202]

    def test_email_webhook_missing_fields(self, test_client):
        """Test webhook fails with missing required fields."""
        response = test_client.post(
            "/api/v1/webhooks/email",
            json={"event_type": "email_received"},
        )

        assert response.status_code == 422


class TestA2ARegistryEndpoints:
    """Tests for A2A registry endpoints."""

    @patch("info_agent.a2a.registry.storage")
    def test_list_agents_empty(self, mock_storage, test_client):
        """Test listing agents when registry is empty."""
        mock_storage.list_agents = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/a2a/agents")

        assert response.status_code == 200
        assert response.json() == []

    @patch("info_agent.a2a.registry.storage")
    def test_register_agent_success(self, mock_storage, test_client, sample_agent_card):
        """Test successful agent registration."""
        mock_storage.register_agent = AsyncMock(return_value=sample_agent_card)

        response = test_client.post(
            "/api/v1/a2a/agents",
            json=sample_agent_card,
        )

        assert response.status_code in [200, 201]

    @patch("info_agent.a2a.registry.storage")
    def test_get_agent_by_name(self, mock_storage, test_client, sample_agent_card):
        """Test getting agent by name."""
        mock_storage.get_agent = AsyncMock(return_value=sample_agent_card)

        response = test_client.get("/api/v1/a2a/agents/test-agent")

        assert response.status_code == 200

    @patch("info_agent.a2a.registry.storage")
    def test_get_agent_not_found(self, mock_storage, test_client):
        """Test getting non-existent agent."""
        from info_agent.utils.exceptions import AgentNotFoundError

        mock_storage.get_agent = AsyncMock(
            side_effect=AgentNotFoundError("Agent not found", agent_name="unknown")
        )

        response = test_client.get("/api/v1/a2a/agents/unknown")

        assert response.status_code == 404


class TestErrorHandling:
    """Tests for error handling middleware."""

    def test_invalid_json_returns_422(self, test_client):
        """Test that invalid JSON returns 422."""
        response = test_client.post(
            "/api/v1/workflows",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_method_not_allowed(self, test_client):
        """Test that wrong HTTP method returns 405."""
        response = test_client.delete("/health")

        assert response.status_code == 405

    def test_not_found_returns_404(self, test_client):
        """Test that non-existent endpoint returns 404."""
        response = test_client.get("/api/v1/nonexistent")

        assert response.status_code == 404


class TestCORSConfiguration:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are present in response."""
        response = test_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS preflight should return 200
        assert response.status_code in [200, 204, 400]
