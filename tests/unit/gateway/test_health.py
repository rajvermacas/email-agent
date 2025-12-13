"""
Unit tests for health routes.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from info_agent.gateway.app import create_app_sync
from info_agent.supervisor.agent import SupervisorAgent


class TestHealthCheck:
    """Tests for health check endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.workflow.checkpointer = None
        supervisor.close = AsyncMock()
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_health_check_healthy(self, client: TestClient) -> None:
        """Test health check returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
        assert "components" in data

    def test_health_check_includes_supervisor(self, client: TestClient) -> None:
        """Test health check includes supervisor component."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "supervisor" in data["components"]
        assert data["components"]["supervisor"]["status"] == "ok"

    def test_health_check_includes_database(self, client: TestClient) -> None:
        """Test health check includes database component."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "database" in data["components"]

    def test_health_check_degraded_without_supervisor(self) -> None:
        """Test health check returns degraded when supervisor missing."""
        app = create_app_sync()
        app.state.supervisor = None
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["supervisor"]["status"] == "down"

    def test_health_check_degraded_without_workflow(
        self, mock_supervisor: MagicMock
    ) -> None:
        """Test health check returns degraded when workflow missing."""
        mock_supervisor.workflow = None
        app = create_app_sync(supervisor=mock_supervisor)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["components"]["supervisor"]["status"] == "degraded"


class TestLivenessProbe:
    """Tests for liveness probe endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        app = create_app_sync()
        return TestClient(app)

    def test_liveness_probe_ok(self, client: TestClient) -> None:
        """Test liveness probe returns ok."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestReadinessProbe:
    """Tests for readiness probe endpoint."""

    @pytest.fixture
    def mock_supervisor(self) -> MagicMock:
        """Create a mock supervisor."""
        supervisor = MagicMock(spec=SupervisorAgent)
        supervisor.workflow = MagicMock()
        supervisor.close = AsyncMock()
        return supervisor

    @pytest.fixture
    def client(self, mock_supervisor: MagicMock) -> TestClient:
        """Create a test client."""
        app = create_app_sync(supervisor=mock_supervisor)
        return TestClient(app)

    def test_readiness_probe_ok(self, client: TestClient) -> None:
        """Test readiness probe returns ok when ready."""
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_readiness_probe_not_ready(self) -> None:
        """Test readiness probe returns 503 when not ready."""
        app = create_app_sync()
        app.state.supervisor = None
        client = TestClient(app)

        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert "not ready" in data["detail"].lower()
