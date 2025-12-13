"""Tests for frontend routes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from info_agent.gateway.routes.frontend import (
    router,
    get_templates,
    reset_templates,
    TEMPLATES_DIR,
)


@pytest.fixture(autouse=True)
def reset_templates_fixture() -> None:
    """Reset templates before and after each test."""
    reset_templates()
    yield
    reset_templates()


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app with frontend routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestGetTemplates:
    """Tests for get_templates function."""

    def test_get_templates_returns_jinja2_templates(self) -> None:
        """Test that get_templates returns a Jinja2Templates instance."""
        from fastapi.templating import Jinja2Templates

        templates = get_templates()
        assert isinstance(templates, Jinja2Templates)

    def test_get_templates_caches_instance(self) -> None:
        """Test that get_templates caches and returns same instance."""
        templates1 = get_templates()
        templates2 = get_templates()
        assert templates1 is templates2

    def test_get_templates_raises_if_directory_not_found(self) -> None:
        """Test that get_templates raises if templates directory missing."""
        with patch(
            "info_agent.gateway.routes.frontend.TEMPLATES_DIR"
        ) as mock_path:
            mock_path.exists.return_value = False
            reset_templates()

            # Import fresh to use the patched constant
            with pytest.raises(RuntimeError, match="Templates directory not found"):
                get_templates()


class TestResetTemplates:
    """Tests for reset_templates function."""

    def test_reset_templates_clears_cache(self) -> None:
        """Test that reset_templates clears the cached instance."""
        templates1 = get_templates()
        reset_templates()
        templates2 = get_templates()

        # Should be new instances after reset
        assert templates1 is not templates2


class TestDashboardRoute:
    """Tests for dashboard route."""

    def test_dashboard_returns_html(self, client: TestClient) -> None:
        """Test that dashboard returns HTML response."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_contains_expected_content(self, client: TestClient) -> None:
        """Test that dashboard contains expected HTML elements."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Check for key dashboard elements
        assert "Info-Agent" in html
        assert "Dashboard" in html
        assert "workflows" in html.lower()

    def test_dashboard_includes_scripts(self, client: TestClient) -> None:
        """Test that dashboard includes required scripts."""
        response = client.get("/")
        html = response.text

        # Check for HTMX and other scripts
        assert "htmx" in html.lower() or "hx-" in html


class TestCreateWorkflowRoute:
    """Tests for create workflow page route."""

    def test_create_workflow_returns_html(self, client: TestClient) -> None:
        """Test that create workflow page returns HTML response."""
        response = client.get("/workflows/create")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_create_workflow_contains_form(self, client: TestClient) -> None:
        """Test that create workflow page contains form elements."""
        response = client.get("/workflows/create")
        html = response.text

        assert "<form" in html
        assert "instructions" in html.lower()

    def test_create_workflow_has_submit_button(self, client: TestClient) -> None:
        """Test that create workflow page has submit button."""
        response = client.get("/workflows/create")
        html = response.text

        assert 'type="submit"' in html or "submit" in html.lower()


class TestWorkflowDetailRoute:
    """Tests for workflow detail page route."""

    def test_workflow_detail_returns_html(self, client: TestClient) -> None:
        """Test that workflow detail page returns HTML response."""
        response = client.get("/workflows/test-workflow-123")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_workflow_detail_contains_workflow_id(self, client: TestClient) -> None:
        """Test that workflow detail page contains the workflow ID."""
        workflow_id = "test-workflow-abc"
        response = client.get(f"/workflows/{workflow_id}")
        html = response.text

        assert workflow_id in html

    def test_workflow_detail_has_plan_section(self, client: TestClient) -> None:
        """Test that workflow detail page has plan section."""
        response = client.get("/workflows/test-workflow")
        html = response.text

        assert "plan" in html.lower()

    def test_workflow_detail_has_activity_log(self, client: TestClient) -> None:
        """Test that workflow detail page has activity log section."""
        response = client.get("/workflows/test-workflow")
        html = response.text

        assert "activity" in html.lower() or "log" in html.lower()

    def test_workflow_detail_has_approval_buttons(self, client: TestClient) -> None:
        """Test that workflow detail page has approval buttons."""
        response = client.get("/workflows/test-workflow")
        html = response.text

        assert "approve" in html.lower()


class TestTemplatesDirectory:
    """Tests for templates directory configuration."""

    def test_templates_dir_is_path(self) -> None:
        """Test that TEMPLATES_DIR is a Path object."""
        from pathlib import Path
        assert isinstance(TEMPLATES_DIR, Path)

    def test_templates_dir_exists(self) -> None:
        """Test that templates directory exists."""
        assert TEMPLATES_DIR.exists(), f"Templates directory not found: {TEMPLATES_DIR}"

    def test_templates_dir_contains_base_template(self) -> None:
        """Test that templates directory contains base.html."""
        base_template = TEMPLATES_DIR / "base.html"
        assert base_template.exists(), f"base.html not found in {TEMPLATES_DIR}"

    def test_templates_dir_contains_index_template(self) -> None:
        """Test that templates directory contains index.html."""
        index_template = TEMPLATES_DIR / "index.html"
        assert index_template.exists(), f"index.html not found in {TEMPLATES_DIR}"

    def test_templates_dir_contains_workflow_templates(self) -> None:
        """Test that templates directory contains workflow templates."""
        workflow_dir = TEMPLATES_DIR / "workflow"
        assert workflow_dir.exists(), f"workflow directory not found in {TEMPLATES_DIR}"

        create_template = workflow_dir / "create.html"
        assert create_template.exists(), f"create.html not found in {workflow_dir}"

        detail_template = workflow_dir / "detail.html"
        assert detail_template.exists(), f"detail.html not found in {workflow_dir}"


class TestRouterConfiguration:
    """Tests for router configuration."""

    def test_router_has_correct_routes(self) -> None:
        """Test that router has the correct routes defined."""
        routes = {route.path for route in router.routes}

        assert "/" in routes
        assert "/workflows/create" in routes
        assert "/workflows/{workflow_id}" in routes

    def test_router_routes_are_get(self) -> None:
        """Test that all frontend routes are GET requests."""
        for route in router.routes:
            if hasattr(route, "methods"):
                assert "GET" in route.methods


class TestHTMLContent:
    """Tests for HTML content validity."""

    def test_dashboard_has_valid_html_structure(self, client: TestClient) -> None:
        """Test that dashboard has valid HTML structure."""
        response = client.get("/")
        html = response.text

        # Check for basic HTML structure
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()
        assert "<html" in html
        assert "</html>" in html
        assert "<head" in html
        assert "</head>" in html
        assert "<body" in html
        assert "</body>" in html

    def test_create_workflow_has_valid_html_structure(
        self, client: TestClient
    ) -> None:
        """Test that create workflow page has valid HTML structure."""
        response = client.get("/workflows/create")
        html = response.text

        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()
        assert "<html" in html
        assert "</html>" in html

    def test_workflow_detail_has_valid_html_structure(
        self, client: TestClient
    ) -> None:
        """Test that workflow detail page has valid HTML structure."""
        response = client.get("/workflows/test-id")
        html = response.text

        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()
        assert "<html" in html
        assert "</html>" in html


class TestResponsiveDesign:
    """Tests for responsive design elements."""

    def test_dashboard_has_viewport_meta(self, client: TestClient) -> None:
        """Test that dashboard has viewport meta tag for mobile."""
        response = client.get("/")
        html = response.text

        assert 'name="viewport"' in html

    def test_dashboard_uses_tailwind_classes(self, client: TestClient) -> None:
        """Test that dashboard uses Tailwind CSS classes."""
        response = client.get("/")
        html = response.text

        # Check for common Tailwind classes
        tailwind_indicators = [
            "flex",
            "grid",
            "bg-",
            "text-",
            "px-",
            "py-",
            "rounded",
        ]

        found = any(indicator in html for indicator in tailwind_indicators)
        assert found, "No Tailwind CSS classes found"


class TestStaticFileReferences:
    """Tests for static file references."""

    def test_dashboard_references_app_js(self, client: TestClient) -> None:
        """Test that dashboard references app.js."""
        response = client.get("/")
        html = response.text

        assert "app.js" in html or "/static/js/app.js" in html

    def test_workflow_detail_references_ag_ui_js(self, client: TestClient) -> None:
        """Test that workflow detail references ag-ui.js."""
        response = client.get("/workflows/test-id")
        html = response.text

        assert "ag-ui.js" in html or "/static/js/ag-ui.js" in html

    def test_dashboard_references_app_css(self, client: TestClient) -> None:
        """Test that dashboard references app.css."""
        response = client.get("/")
        html = response.text

        assert "app.css" in html or "/static/css/app.css" in html
