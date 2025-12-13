"""
Unit tests for gateway app factory.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi import FastAPI

from info_agent.gateway.app import create_app, create_app_sync, GatewayApp
from info_agent.config import Settings
from info_agent.supervisor.agent import SupervisorAgent


class TestGatewayApp:
    """Tests for GatewayApp container."""

    def test_init(self) -> None:
        """Test GatewayApp initialization."""
        mock_app = MagicMock(spec=FastAPI)
        mock_supervisor = MagicMock(spec=SupervisorAgent)
        mock_settings = MagicMock(spec=Settings)

        gateway_app = GatewayApp(
            app=mock_app,
            supervisor=mock_supervisor,
            settings=mock_settings,
        )

        assert gateway_app.app is mock_app
        assert gateway_app.supervisor is mock_supervisor
        assert gateway_app.settings is mock_settings

    def test_properties(self) -> None:
        """Test GatewayApp properties."""
        mock_app = MagicMock(spec=FastAPI)
        mock_supervisor = MagicMock(spec=SupervisorAgent)
        mock_settings = MagicMock(spec=Settings)

        gateway_app = GatewayApp(
            app=mock_app,
            supervisor=mock_supervisor,
            settings=mock_settings,
        )

        # Access properties multiple times to ensure consistency
        assert gateway_app.app is gateway_app.app
        assert gateway_app.supervisor is gateway_app.supervisor
        assert gateway_app.settings is gateway_app.settings


class TestCreateAppSync:
    """Tests for synchronous app creation."""

    def test_create_app_sync_default(self) -> None:
        """Test creating app with defaults."""
        app = create_app_sync()

        assert isinstance(app, FastAPI)
        assert app.title == "Info-Agent Gateway"
        assert app.version == "1.0.0"

    def test_create_app_sync_with_settings(self) -> None:
        """Test creating app with custom settings."""
        settings = Settings()

        app = create_app_sync(settings=settings)

        assert app.state.settings is settings

    def test_create_app_sync_with_supervisor(self) -> None:
        """Test creating app with custom supervisor."""
        supervisor = SupervisorAgent(use_llm=False, use_stub_delegator=True)

        app = create_app_sync(supervisor=supervisor)

        assert app.state.supervisor is supervisor

    def test_create_app_sync_has_routes(self) -> None:
        """Test created app has expected routes."""
        app = create_app_sync()

        # Get all route paths
        routes = [route.path for route in app.routes]

        # Check health routes
        assert "/health" in routes
        assert "/health/live" in routes
        assert "/health/ready" in routes

        # Check workflow routes
        assert "/api/workflows" in routes
        assert "/api/workflows/{workflow_id}" in routes
        assert "/api/workflows/{workflow_id}/approve" in routes
        assert "/api/workflows/{workflow_id}/cancel" in routes

        # Check webhook routes
        assert "/webhooks/email" in routes
        assert "/webhooks/agent" in routes

    def test_create_app_sync_has_cors(self) -> None:
        """Test created app has CORS middleware."""
        app = create_app_sync()

        # Check that CORS middleware is added
        # FastAPI adds middleware in a stack, we check it exists
        middleware_classes = [m.cls for m in app.user_middleware]
        from starlette.middleware.cors import CORSMiddleware

        assert CORSMiddleware in middleware_classes


class TestCreateAppAsync:
    """Tests for async app creation."""

    @pytest.mark.asyncio
    async def test_create_app_default(self) -> None:
        """Test creating app with defaults."""
        gateway_app = await create_app()

        assert isinstance(gateway_app, GatewayApp)
        assert isinstance(gateway_app.app, FastAPI)
        assert gateway_app.supervisor is not None

        # Cleanup
        await gateway_app.supervisor.close()

    @pytest.mark.asyncio
    async def test_create_app_with_settings(self) -> None:
        """Test creating app with custom settings."""
        settings = Settings()

        gateway_app = await create_app(settings=settings)

        assert gateway_app.settings is settings

        # Cleanup
        await gateway_app.supervisor.close()

    @pytest.mark.asyncio
    async def test_create_app_with_checkpoint_path(self) -> None:
        """Test creating app with checkpoint path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "checkpoints.db"

            gateway_app = await create_app(checkpoint_db_path=db_path)

            assert gateway_app.supervisor.workflow.checkpointer is not None

            # Cleanup
            await gateway_app.supervisor.close()

    @pytest.mark.asyncio
    async def test_create_app_supervisor_initialized(self) -> None:
        """Test supervisor is properly initialized."""
        gateway_app = await create_app()

        # Supervisor should have workflow
        assert gateway_app.supervisor.workflow is not None

        # Supervisor should be accessible from app state
        assert gateway_app.app.state.supervisor is gateway_app.supervisor

        # Cleanup
        await gateway_app.supervisor.close()


class TestAppState:
    """Tests for app state management."""

    def test_app_state_has_supervisor(self) -> None:
        """Test app state has supervisor."""
        app = create_app_sync()

        assert hasattr(app.state, "supervisor")
        assert app.state.supervisor is not None

    def test_app_state_has_settings(self) -> None:
        """Test app state has settings."""
        app = create_app_sync()

        assert hasattr(app.state, "settings")
        assert app.state.settings is not None

    def test_app_state_supervisor_type(self) -> None:
        """Test supervisor in app state is correct type."""
        supervisor = SupervisorAgent(use_llm=False, use_stub_delegator=True)
        app = create_app_sync(supervisor=supervisor)

        assert isinstance(app.state.supervisor, SupervisorAgent)


class TestAppRoutes:
    """Tests for app route registration."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test app."""
        return create_app_sync()

    def test_health_routes_registered(self, app: FastAPI) -> None:
        """Test health routes are registered."""
        routes = {route.path for route in app.routes}

        assert "/health" in routes
        assert "/health/live" in routes
        assert "/health/ready" in routes

    def test_workflow_routes_registered(self, app: FastAPI) -> None:
        """Test workflow routes are registered."""
        routes = {route.path for route in app.routes}

        assert "/api/workflows" in routes
        assert "/api/workflows/{workflow_id}" in routes
        assert "/api/workflows/{workflow_id}/approve" in routes
        assert "/api/workflows/{workflow_id}/cancel" in routes
        assert "/api/workflows/{workflow_id}/status" in routes
        assert "/api/workflows/{workflow_id}/audit" in routes
        assert "/api/workflows/{workflow_id}/emails" in routes
        assert "/api/workflows/{workflow_id}/stream" in routes

    def test_webhook_routes_registered(self, app: FastAPI) -> None:
        """Test webhook routes are registered."""
        routes = {route.path for route in app.routes}

        assert "/webhooks/email" in routes
        assert "/webhooks/agent" in routes

    def test_routes_have_correct_methods(self, app: FastAPI) -> None:
        """Test routes have correct HTTP methods."""
        # Collect all methods per path (FastAPI can have multiple routes per path)
        route_methods: dict[str, set[str]] = {}
        for route in app.routes:
            if hasattr(route, "methods"):
                path = route.path
                if path not in route_methods:
                    route_methods[path] = set()
                route_methods[path].update(route.methods)

        # Health routes
        assert "GET" in route_methods.get("/health", set())
        assert "GET" in route_methods.get("/health/live", set())
        assert "GET" in route_methods.get("/health/ready", set())

        # Workflow routes - POST and GET are separate routes for /api/workflows
        workflows_methods = route_methods.get("/api/workflows", set())
        assert "POST" in workflows_methods or "GET" in workflows_methods
        assert "GET" in route_methods.get("/api/workflows/{workflow_id}", set())
        assert "POST" in route_methods.get(
            "/api/workflows/{workflow_id}/approve", set()
        )
        assert "POST" in route_methods.get(
            "/api/workflows/{workflow_id}/cancel", set()
        )

        # Webhook routes
        assert "POST" in route_methods.get("/webhooks/email", set())
        assert "POST" in route_methods.get("/webhooks/agent", set())


class TestAppMiddleware:
    """Tests for app middleware configuration."""

    def test_cors_middleware_added(self) -> None:
        """Test CORS middleware is added."""
        app = create_app_sync()

        from starlette.middleware.cors import CORSMiddleware

        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_cors_allows_all_origins(self) -> None:
        """Test CORS allows all origins (for development)."""
        app = create_app_sync()

        # Find CORS middleware
        for middleware in app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                assert "*" in middleware.kwargs.get("allow_origins", [])
                break


class TestAppMetadata:
    """Tests for app metadata."""

    def test_app_title(self) -> None:
        """Test app title."""
        app = create_app_sync()

        assert app.title == "Info-Agent Gateway"

    def test_app_description(self) -> None:
        """Test app description."""
        app = create_app_sync()

        assert "multi-agent" in app.description.lower()

    def test_app_version(self) -> None:
        """Test app version."""
        app = create_app_sync()

        assert app.version == "1.0.0"
