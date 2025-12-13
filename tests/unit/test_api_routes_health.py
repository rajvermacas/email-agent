"""
Unit tests for health check API routes.

Tests the health check routes defined in src/info_agent/api/routes/health.py
with mocked dependencies and comprehensive coverage of all edge cases.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi import status
from fastapi.testclient import TestClient
from fastapi import FastAPI

import httpx

from info_agent.api.routes.health import create_health_router
from info_agent.api.models.responses import ComponentHealth, HealthResponse


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock()
    settings.a2a_registry_url = "http://localhost:8000/a2a"
    settings.host = "localhost"
    settings.mail_agent_port = 8001
    settings.email_server_port = 8025
    settings.checkpoint_db_path = "/tmp/test/checkpoints.db"
    settings.get_email_server_url = Mock(return_value="http://localhost:8025")
    return settings


@pytest.fixture
def app_with_health_router():
    """Create FastAPI app with health router for testing."""
    app = FastAPI()
    router = create_health_router()
    app.include_router(router)
    return app


@pytest.fixture
def client(app_with_health_router):
    """Create test client for health routes."""
    return TestClient(app_with_health_router)


class TestHealthCheckEndpoint:
    """Tests for GET /health endpoint."""

    @patch("info_agent.api.routes.health.get_settings")
    @patch("info_agent.api.routes.health._check_a2a_registry_health")
    @patch("info_agent.api.routes.health._check_mail_agent_health")
    @patch("info_agent.api.routes.health._check_email_server_health")
    @pytest.mark.asyncio
    async def test_health_check_all_healthy(
        self,
        mock_email_check,
        mock_mail_check,
        mock_a2a_check,
        mock_get_settings,
        client,
        mock_settings
    ):
        """Test health check when all components are healthy."""
        mock_get_settings.return_value = mock_settings

        # Mock all components as healthy
        mock_a2a_check.return_value = ComponentHealth(
            status="healthy",
            message="A2A registry is operational",
            latency_ms=2.1
        )
        mock_mail_check.return_value = ComponentHealth(
            status="healthy",
            message="Mail agent is registered and operational",
            latency_ms=5.2
        )
        mock_email_check.return_value = ComponentHealth(
            status="healthy",
            message="Email server is operational",
            latency_ms=3.0
        )

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "components" in data
        assert "timestamp" in data

        # Check all components
        assert data["components"]["gateway"]["status"] == "healthy"
        assert data["components"]["a2a_registry"]["status"] == "healthy"
        assert data["components"]["mail_agent"]["status"] == "healthy"
        assert data["components"]["email_server"]["status"] == "healthy"

    @patch("info_agent.api.routes.health.get_settings")
    @patch("info_agent.api.routes.health._check_a2a_registry_health")
    @patch("info_agent.api.routes.health._check_mail_agent_health")
    @patch("info_agent.api.routes.health._check_email_server_health")
    @pytest.mark.asyncio
    async def test_health_check_degraded_component(
        self,
        mock_email_check,
        mock_mail_check,
        mock_a2a_check,
        mock_get_settings,
        client,
        mock_settings
    ):
        """Test health check when one component is degraded."""
        mock_get_settings.return_value = mock_settings

        # Mock one degraded component
        mock_a2a_check.return_value = ComponentHealth(
            status="healthy",
            latency_ms=2.0
        )
        mock_mail_check.return_value = ComponentHealth(
            status="degraded",
            message="Mail agent not registered",
            latency_ms=10.0
        )
        mock_email_check.return_value = ComponentHealth(
            status="healthy",
            latency_ms=3.0
        )

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["mail_agent"]["status"] == "degraded"

    @patch("info_agent.api.routes.health.get_settings")
    @patch("info_agent.api.routes.health._check_a2a_registry_health")
    @patch("info_agent.api.routes.health._check_mail_agent_health")
    @patch("info_agent.api.routes.health._check_email_server_health")
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_component(
        self,
        mock_email_check,
        mock_mail_check,
        mock_a2a_check,
        mock_get_settings,
        client,
        mock_settings
    ):
        """Test health check when one component is unhealthy."""
        mock_get_settings.return_value = mock_settings

        # Mock one unhealthy component
        mock_a2a_check.return_value = ComponentHealth(
            status="unhealthy",
            message="Connection timeout",
            latency_ms=None
        )
        mock_mail_check.return_value = ComponentHealth(
            status="healthy",
            latency_ms=5.0
        )
        mock_email_check.return_value = ComponentHealth(
            status="healthy",
            latency_ms=3.0
        )

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["a2a_registry"]["status"] == "unhealthy"

    @patch("info_agent.api.routes.health.get_settings")
    @patch("info_agent.api.routes.health._check_a2a_registry_health")
    @patch("info_agent.api.routes.health._check_mail_agent_health")
    @patch("info_agent.api.routes.health._check_email_server_health")
    @pytest.mark.asyncio
    async def test_health_check_multiple_unhealthy(
        self,
        mock_email_check,
        mock_mail_check,
        mock_a2a_check,
        mock_get_settings,
        client,
        mock_settings
    ):
        """Test health check when multiple components are unhealthy."""
        mock_get_settings.return_value = mock_settings

        # Mock multiple unhealthy components
        mock_a2a_check.return_value = ComponentHealth(
            status="unhealthy",
            message="Connection failed"
        )
        mock_mail_check.return_value = ComponentHealth(
            status="unhealthy",
            message="Service unavailable"
        )
        mock_email_check.return_value = ComponentHealth(
            status="degraded",
            message="Slow response"
        )

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "degraded"


class TestReadinessCheckEndpoint:
    """Tests for GET /ready endpoint."""

    @patch("info_agent.api.routes.health.get_settings")
    @patch("info_agent.api.routes.health.Path")
    def test_readiness_check_success(
        self,
        mock_path,
        mock_get_settings,
        client,
        mock_settings
    ):
        """Test readiness check when service is ready."""
        mock_get_settings.return_value = mock_settings

        # Mock path existence checks
        mock_parent = Mock()
        mock_parent.exists.return_value = True
        mock_path_instance = Mock()
        mock_path_instance.parent = mock_parent
        mock_path.return_value = mock_path_instance

        response = client.get("/ready")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["ready"] is True
        assert data["version"] == "0.1.0"
        assert "timestamp" in data

    @patch("info_agent.api.routes.health.get_settings")
    @patch("info_agent.api.routes.health.Path")
    def test_readiness_check_db_directory_not_accessible(
        self,
        mock_path,
        mock_get_settings,
        client,
        mock_settings
    ):
        """Test readiness check fails when database directory is not accessible."""
        mock_get_settings.return_value = mock_settings

        # Mock path existence check to fail
        mock_parent = Mock()
        mock_parent.exists.return_value = False
        mock_path_instance = Mock()
        mock_path_instance.parent = mock_parent
        mock_path.return_value = mock_path_instance

        response = client.get("/ready")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "not accessible" in response.json()["detail"]

    @patch("info_agent.api.routes.health.get_settings")
    @patch("info_agent.api.routes.health.Path")
    def test_readiness_check_unexpected_error(
        self,
        mock_path,
        mock_get_settings,
        client,
        mock_settings
    ):
        """Test readiness check handles unexpected errors."""
        mock_get_settings.return_value = mock_settings

        # Mock path to raise unexpected error
        mock_path.side_effect = RuntimeError("Unexpected error")

        response = client.get("/ready")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Service not ready" in response.json()["detail"]


class TestA2ARegistryHealthCheck:
    """Tests for _check_a2a_registry_health function."""

    @pytest.mark.asyncio
    async def test_a2a_registry_healthy(self, mock_settings):
        """Test A2A registry health check when healthy."""
        from info_agent.api.routes.health import _check_a2a_registry_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200

            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await _check_a2a_registry_health(mock_settings)

            assert result.status == "healthy"
            assert result.message == "A2A registry is operational"
            assert result.latency_ms is not None
            assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_a2a_registry_unexpected_status(self, mock_settings):
        """Test A2A registry health check with unexpected status code."""
        from info_agent.api.routes.health import _check_a2a_registry_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 500

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await _check_a2a_registry_health(mock_settings)

            assert result.status == "degraded"
            assert "Unexpected status code: 500" in result.message

    @pytest.mark.asyncio
    async def test_a2a_registry_timeout(self, mock_settings):
        """Test A2A registry health check on timeout."""
        from info_agent.api.routes.health import _check_a2a_registry_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await _check_a2a_registry_health(mock_settings)

            assert result.status == "unhealthy"
            assert result.message == "Connection timeout"
            assert result.latency_ms is None

    @pytest.mark.asyncio
    async def test_a2a_registry_connection_error(self, mock_settings):
        """Test A2A registry health check on connection error."""
        from info_agent.api.routes.health import _check_a2a_registry_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client_class.return_value = mock_client

            result = await _check_a2a_registry_health(mock_settings)

            assert result.status == "unhealthy"
            assert "Health check failed" in result.message
            assert result.latency_ms is None


class TestMailAgentHealthCheck:
    """Tests for _check_mail_agent_health function."""

    @pytest.mark.asyncio
    async def test_mail_agent_healthy(self, mock_settings):
        """Test mail agent health check when healthy."""
        from info_agent.api.routes.health import _check_mail_agent_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await _check_mail_agent_health(mock_settings)

            assert result.status == "healthy"
            assert "Mail agent is registered" in result.message
            assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_mail_agent_not_registered(self, mock_settings):
        """Test mail agent health check when not registered."""
        from info_agent.api.routes.health import _check_mail_agent_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 404

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await _check_mail_agent_health(mock_settings)

            assert result.status == "degraded"
            assert "Mail agent not registered" in result.message

    @pytest.mark.asyncio
    async def test_mail_agent_timeout(self, mock_settings):
        """Test mail agent health check on timeout."""
        from info_agent.api.routes.health import _check_mail_agent_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await _check_mail_agent_health(mock_settings)

            assert result.status == "unhealthy"
            assert result.message == "Connection timeout"
            assert result.latency_ms is None

    @pytest.mark.asyncio
    async def test_mail_agent_error(self, mock_settings):
        """Test mail agent health check on error."""
        from info_agent.api.routes.health import _check_mail_agent_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client_class.return_value = mock_client

            result = await _check_mail_agent_health(mock_settings)

            assert result.status == "degraded"
            assert "Mail agent check failed" in result.message


class TestEmailServerHealthCheck:
    """Tests for _check_email_server_health function."""

    @pytest.mark.asyncio
    async def test_email_server_healthy(self, mock_settings):
        """Test email server health check when healthy."""
        from info_agent.api.routes.health import _check_email_server_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await _check_email_server_health(mock_settings)

            assert result.status == "healthy"
            assert "Email server is operational" in result.message
            assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_email_server_unexpected_status(self, mock_settings):
        """Test email server health check with unexpected status."""
        from info_agent.api.routes.health import _check_email_server_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 503

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await _check_email_server_health(mock_settings)

            assert result.status == "degraded"
            assert "Unexpected status code: 503" in result.message

    @pytest.mark.asyncio
    async def test_email_server_timeout(self, mock_settings):
        """Test email server health check on timeout."""
        from info_agent.api.routes.health import _check_email_server_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await _check_email_server_health(mock_settings)

            assert result.status == "unhealthy"
            assert result.message == "Connection timeout"
            assert result.latency_ms is None

    @pytest.mark.asyncio
    async def test_email_server_error(self, mock_settings):
        """Test email server health check on error."""
        from info_agent.api.routes.health import _check_email_server_health

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client_class.return_value = mock_client

            result = await _check_email_server_health(mock_settings)

            assert result.status == "degraded"
            assert "Email server check failed" in result.message


class TestDetermineOverallStatus:
    """Tests for _determine_overall_status function."""

    def test_all_healthy(self):
        """Test overall status when all components are healthy."""
        from info_agent.api.routes.health import _determine_overall_status

        components = {
            "gateway": ComponentHealth(status="healthy"),
            "database": ComponentHealth(status="healthy"),
            "cache": ComponentHealth(status="healthy")
        }

        status_result = _determine_overall_status(components)
        assert status_result == "healthy"

    def test_one_degraded(self):
        """Test overall status when one component is degraded."""
        from info_agent.api.routes.health import _determine_overall_status

        components = {
            "gateway": ComponentHealth(status="healthy"),
            "database": ComponentHealth(status="degraded"),
            "cache": ComponentHealth(status="healthy")
        }

        status_result = _determine_overall_status(components)
        assert status_result == "degraded"

    def test_one_unhealthy(self):
        """Test overall status when one component is unhealthy."""
        from info_agent.api.routes.health import _determine_overall_status

        components = {
            "gateway": ComponentHealth(status="healthy"),
            "database": ComponentHealth(status="unhealthy"),
            "cache": ComponentHealth(status="healthy")
        }

        status_result = _determine_overall_status(components)
        assert status_result == "degraded"

    def test_multiple_degraded_and_unhealthy(self):
        """Test overall status with multiple degraded and unhealthy components."""
        from info_agent.api.routes.health import _determine_overall_status

        components = {
            "gateway": ComponentHealth(status="healthy"),
            "database": ComponentHealth(status="unhealthy"),
            "cache": ComponentHealth(status="degraded")
        }

        status_result = _determine_overall_status(components)
        assert status_result == "degraded"

    def test_empty_components(self):
        """Test overall status with no components."""
        from info_agent.api.routes.health import _determine_overall_status

        components = {}

        status_result = _determine_overall_status(components)
        assert status_result == "healthy"
