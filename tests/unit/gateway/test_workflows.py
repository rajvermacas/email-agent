"""
Unit tests for workflow routes.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from info_agent.gateway.app import create_app_sync
from info_agent.gateway.routes.workflows import clear_workflows
from info_agent.supervisor.agent import SupervisorAgent
from info_agent.workflow import WorkflowStatus as WFStatus


class TestCreateWorkflow:
    """Tests for workflow creation endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.workflow.checkpointer = None
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={
                "workflow_id": "wf-test",
                "status": "awaiting_approval",
                "plan": [
                    {
                        "step_number": 1,
                        "action": "send_email",
                        "agent": "mail-agent",
                        "skill": "send_email",
                        "description": "Send email",
                        "parameters": {},
                        "status": "pending",
                    }
                ],
            }
        )
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_create_workflow(self, client: TestClient) -> None:
        """Test creating a workflow."""
        payload = {
            "instructions": "Send email to test@example.com",
            "faq": "Q: Format? A: Excel",
            "escalation_rules": "Escalate after 48 hours",
            "validation_criteria": "Must have 10 rows",
        }

        response = client.post("/api/workflows", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "workflow_id" in data
        assert data["status"] in ["planning", "awaiting_approval"]
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_workflow_with_custom_id(self, client: TestClient) -> None:
        """Test creating workflow with custom ID."""
        payload = {
            "instructions": "Send email",
            "workflow_id": "custom-wf-123",
        }

        response = client.post("/api/workflows", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "custom-wf-123"

    def test_create_workflow_minimal(self, client: TestClient) -> None:
        """Test creating workflow with minimal input."""
        payload = {
            "instructions": "Send email",
        }

        response = client.post("/api/workflows", json=payload)

        assert response.status_code == 200

    def test_create_workflow_empty_instructions(self, client: TestClient) -> None:
        """Test creating workflow with empty instructions fails."""
        payload = {
            "instructions": "",
        }

        response = client.post("/api/workflows", json=payload)

        assert response.status_code == 422  # Validation error

    def test_create_workflow_no_supervisor(self) -> None:
        """Test creating workflow when supervisor not available."""
        clear_workflows()
        app = create_app_sync()
        app.state.supervisor = None
        client = TestClient(app)

        payload = {
            "instructions": "Send email",
        }

        response = client.post("/api/workflows", json=payload)

        assert response.status_code == 503

    def test_create_workflow_includes_plan(
        self,
        client: TestClient,
        mock_supervisor: MagicMock,
    ) -> None:
        """Test created workflow includes plan."""
        payload = {
            "instructions": "Send email to test@example.com",
        }

        response = client.post("/api/workflows", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] is not None
        assert len(data["plan"]) > 0


class TestListWorkflows:
    """Tests for listing workflows endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={"workflow_id": "wf-test", "status": "completed"}
        )
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_list_workflows_empty(self, client: TestClient) -> None:
        """Test listing workflows when empty."""
        response = client.get("/api/workflows")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["workflows"]) == 0

    def test_list_workflows_with_data(self, client: TestClient) -> None:
        """Test listing workflows with data."""
        # Create some workflows
        for i in range(3):
            client.post(
                "/api/workflows",
                json={"instructions": f"Workflow {i}", "workflow_id": f"wf-{i}"},
            )

        response = client.get("/api/workflows")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["workflows"]) == 3

    def test_list_workflows_pagination(self, client: TestClient) -> None:
        """Test listing workflows with pagination."""
        # Create 5 workflows
        for i in range(5):
            client.post(
                "/api/workflows",
                json={"instructions": f"Workflow {i}", "workflow_id": f"wf-{i}"},
            )

        # Get first page
        response = client.get("/api/workflows?offset=0&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["workflows"]) == 2
        assert data["offset"] == 0
        assert data["limit"] == 2

        # Get second page
        response = client.get("/api/workflows?offset=2&limit=2")

        data = response.json()
        assert len(data["workflows"]) == 2
        assert data["offset"] == 2


class TestGetWorkflow:
    """Tests for getting workflow details endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={"workflow_id": "wf-test", "status": "completed"}
        )
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_get_workflow(self, client: TestClient) -> None:
        """Test getting workflow details."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.get("/api/workflows/wf-123")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "wf-123"

    def test_get_workflow_not_found(self, client: TestClient) -> None:
        """Test getting non-existent workflow."""
        response = client.get("/api/workflows/nonexistent")

        assert response.status_code == 404

    def test_get_workflow_status(self, client: TestClient) -> None:
        """Test getting workflow status."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.get("/api/workflows/wf-123/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestApproveWorkflow:
    """Tests for approving workflow endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={"workflow_id": "wf-test", "status": "awaiting_approval"}
        )
        supervisor.approve_plan = AsyncMock(return_value=None)
        supervisor.reject_plan = AsyncMock(return_value=None)
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_approve_workflow(
        self,
        client: TestClient,
        mock_supervisor: MagicMock,
    ) -> None:
        """Test approving workflow."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.post(
            "/api/workflows/wf-123/approve",
            json={"approved": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "executing"
        mock_supervisor.approve_plan.assert_called_once_with("wf-123")

    def test_reject_workflow(
        self,
        client: TestClient,
        mock_supervisor: MagicMock,
    ) -> None:
        """Test rejecting workflow."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.post(
            "/api/workflows/wf-123/approve",
            json={"approved": False, "feedback": "Need more details"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "planning"
        mock_supervisor.reject_plan.assert_called_once_with(
            "wf-123", "Need more details"
        )

    def test_approve_workflow_not_found(self, client: TestClient) -> None:
        """Test approving non-existent workflow."""
        response = client.post(
            "/api/workflows/nonexistent/approve",
            json={"approved": True},
        )

        assert response.status_code == 404


class TestCancelWorkflow:
    """Tests for cancelling workflow endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={"workflow_id": "wf-test", "status": "executing"}
        )
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_cancel_workflow(self, client: TestClient) -> None:
        """Test cancelling workflow."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.post(
            "/api/workflows/wf-123/cancel",
            json={"reason": "No longer needed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_workflow_without_reason(self, client: TestClient) -> None:
        """Test cancelling workflow without reason."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.post(
            "/api/workflows/wf-123/cancel",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_workflow_not_found(self, client: TestClient) -> None:
        """Test cancelling non-existent workflow."""
        response = client.post(
            "/api/workflows/nonexistent/cancel",
            json={},
        )

        assert response.status_code == 404


class TestWorkflowAudit:
    """Tests for workflow audit endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={"workflow_id": "wf-test", "status": "completed"}
        )
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_get_audit_log(self, client: TestClient) -> None:
        """Test getting workflow audit log."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.get("/api/workflows/wf-123/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "wf-123"
        assert "entries" in data
        assert len(data["entries"]) > 0  # Should have creation entry

    def test_get_audit_log_not_found(self, client: TestClient) -> None:
        """Test getting audit log for non-existent workflow."""
        response = client.get("/api/workflows/nonexistent/audit")

        assert response.status_code == 404


class TestWorkflowEmails:
    """Tests for workflow emails endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={"workflow_id": "wf-test", "status": "completed"}
        )
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_get_emails(self, client: TestClient) -> None:
        """Test getting workflow emails."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.get("/api/workflows/wf-123/emails")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "wf-123"
        assert "threads" in data
        assert "messages" in data

    def test_get_emails_not_found(self, client: TestClient) -> None:
        """Test getting emails for non-existent workflow."""
        response = client.get("/api/workflows/nonexistent/emails")

        assert response.status_code == 404


class TestWorkflowStream:
    """Tests for workflow streaming endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        supervisor.start_workflow = AsyncMock(
            return_value={"workflow_id": "wf-test", "status": "executing"}
        )

        # Mock stream_workflow to yield events
        async def mock_stream(*args, **kwargs):
            yield ("parse_inputs", {"status": "executing"})
            yield ("generate_plan", {"status": "executing"})

        supervisor.stream_workflow = mock_stream
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        clear_workflows()
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_stream_workflow(self, client: TestClient) -> None:
        """Test streaming workflow events."""
        # Create workflow
        client.post(
            "/api/workflows",
            json={"instructions": "Test", "workflow_id": "wf-123"},
        )

        response = client.get("/api/workflows/wf-123/stream")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read SSE events
        content = response.text
        assert "event:" in content
        assert "data:" in content
        assert "RUN_STARTED" in content

    def test_stream_workflow_not_found(self, client: TestClient) -> None:
        """Test streaming non-existent workflow."""
        response = client.get("/api/workflows/nonexistent/stream")

        assert response.status_code == 404
