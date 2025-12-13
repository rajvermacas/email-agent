"""Tests for static files configuration."""

from pathlib import Path

import pytest


# Static files directory
STATIC_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "static"


class TestStaticFilesExist:
    """Tests to verify static files exist."""

    def test_static_directory_exists(self) -> None:
        """Test that static directory exists."""
        assert STATIC_DIR.exists(), f"Static directory not found: {STATIC_DIR}"

    def test_js_directory_exists(self) -> None:
        """Test that js directory exists."""
        js_dir = STATIC_DIR / "js"
        assert js_dir.exists(), f"JS directory not found: {js_dir}"

    def test_css_directory_exists(self) -> None:
        """Test that css directory exists."""
        css_dir = STATIC_DIR / "css"
        assert css_dir.exists(), f"CSS directory not found: {css_dir}"


class TestJavaScriptFiles:
    """Tests for JavaScript files."""

    def test_app_js_exists(self) -> None:
        """Test that app.js exists."""
        app_js = STATIC_DIR / "js" / "app.js"
        assert app_js.exists(), f"app.js not found: {app_js}"

    def test_ag_ui_js_exists(self) -> None:
        """Test that ag-ui.js exists."""
        ag_ui_js = STATIC_DIR / "js" / "ag-ui.js"
        assert ag_ui_js.exists(), f"ag-ui.js not found: {ag_ui_js}"

    def test_app_js_has_content(self) -> None:
        """Test that app.js has content."""
        app_js = STATIC_DIR / "js" / "app.js"
        content = app_js.read_text()
        assert len(content) > 0, "app.js is empty"

    def test_ag_ui_js_has_content(self) -> None:
        """Test that ag-ui.js has content."""
        ag_ui_js = STATIC_DIR / "js" / "ag-ui.js"
        content = ag_ui_js.read_text()
        assert len(content) > 0, "ag-ui.js is empty"


class TestAppJsContent:
    """Tests for app.js content."""

    @pytest.fixture
    def app_js_content(self) -> str:
        """Load app.js content."""
        app_js = STATIC_DIR / "js" / "app.js"
        return app_js.read_text()

    def test_app_js_is_valid_javascript(self, app_js_content: str) -> None:
        """Test that app.js is valid JavaScript (basic syntax check)."""
        # Check for basic JavaScript patterns
        assert "function" in app_js_content or "=>" in app_js_content

    def test_app_js_has_iife(self, app_js_content: str) -> None:
        """Test that app.js uses IIFE pattern."""
        assert "(function()" in app_js_content

    def test_app_js_has_use_strict(self, app_js_content: str) -> None:
        """Test that app.js uses strict mode."""
        assert "'use strict'" in app_js_content

    def test_app_js_handles_dom_ready(self, app_js_content: str) -> None:
        """Test that app.js handles DOMContentLoaded."""
        assert "DOMContentLoaded" in app_js_content

    def test_app_js_exports_info_agent(self, app_js_content: str) -> None:
        """Test that app.js exports InfoAgent global."""
        assert "window.InfoAgent" in app_js_content

    def test_app_js_has_htmx_handlers(self, app_js_content: str) -> None:
        """Test that app.js sets up HTMX handlers."""
        assert "htmx" in app_js_content.lower()

    def test_app_js_has_format_timestamp(self, app_js_content: str) -> None:
        """Test that app.js has formatTimestamp function."""
        assert "formatTimestamp" in app_js_content

    def test_app_js_has_format_relative_time(self, app_js_content: str) -> None:
        """Test that app.js has formatRelativeTime function."""
        assert "formatRelativeTime" in app_js_content

    def test_app_js_has_copy_to_clipboard(self, app_js_content: str) -> None:
        """Test that app.js has copyToClipboard function."""
        assert "copyToClipboard" in app_js_content

    def test_app_js_has_debounce(self, app_js_content: str) -> None:
        """Test that app.js has debounce function."""
        assert "debounce" in app_js_content

    def test_app_js_loads_dashboard_stats(self, app_js_content: str) -> None:
        """Test that app.js loads dashboard stats."""
        assert "loadDashboardStats" in app_js_content


class TestAgUiJsContent:
    """Tests for ag-ui.js content."""

    @pytest.fixture
    def ag_ui_js_content(self) -> str:
        """Load ag-ui.js content."""
        ag_ui_js = STATIC_DIR / "js" / "ag-ui.js"
        return ag_ui_js.read_text()

    def test_ag_ui_js_is_valid_javascript(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js is valid JavaScript."""
        assert "function" in ag_ui_js_content or "=>" in ag_ui_js_content

    def test_ag_ui_js_exports_info_agent_sse(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js exports InfoAgentSSE global."""
        assert "InfoAgentSSE" in ag_ui_js_content

    def test_ag_ui_js_has_connect_function(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js has connect function."""
        assert "connect" in ag_ui_js_content

    def test_ag_ui_js_has_disconnect_function(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js has disconnect function."""
        assert "disconnect" in ag_ui_js_content

    def test_ag_ui_js_uses_event_source(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js uses EventSource for SSE."""
        assert "EventSource" in ag_ui_js_content

    def test_ag_ui_js_handles_reconnection(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js handles reconnection."""
        assert "reconnect" in ag_ui_js_content.lower()

    def test_ag_ui_js_has_event_types(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js defines event types."""
        # Check for AG-UI event types
        event_types = [
            "RUN_STARTED",
            "RUN_FINISHED",
            "RUN_ERROR",
            "PLAN_GENERATED",
        ]
        for event_type in event_types:
            assert event_type in ag_ui_js_content, f"Missing event type: {event_type}"

    def test_ag_ui_js_has_notification_function(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js has notification function."""
        assert "showNotification" in ag_ui_js_content

    def test_ag_ui_js_updates_connection_status(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js updates connection status."""
        assert "updateConnectionStatus" in ag_ui_js_content

    def test_ag_ui_js_handles_errors(self, ag_ui_js_content: str) -> None:
        """Test that ag-ui.js handles errors."""
        assert "onerror" in ag_ui_js_content


class TestCssFiles:
    """Tests for CSS files."""

    def test_app_css_exists(self) -> None:
        """Test that app.css exists."""
        app_css = STATIC_DIR / "css" / "app.css"
        assert app_css.exists(), f"app.css not found: {app_css}"

    def test_app_css_has_content(self) -> None:
        """Test that app.css has content."""
        app_css = STATIC_DIR / "css" / "app.css"
        content = app_css.read_text()
        assert len(content) > 0, "app.css is empty"


class TestAppCssContent:
    """Tests for app.css content."""

    @pytest.fixture
    def app_css_content(self) -> str:
        """Load app.css content."""
        app_css = STATIC_DIR / "css" / "app.css"
        return app_css.read_text()

    def test_app_css_has_root_variables(self, app_css_content: str) -> None:
        """Test that app.css defines CSS custom properties."""
        assert ":root" in app_css_content

    def test_app_css_has_status_styles(self, app_css_content: str) -> None:
        """Test that app.css has status badge styles."""
        assert "status-" in app_css_content

    def test_app_css_has_notification_styles(self, app_css_content: str) -> None:
        """Test that app.css has notification styles."""
        assert "notification" in app_css_content.lower()

    def test_app_css_has_loading_animation(self, app_css_content: str) -> None:
        """Test that app.css has loading animations."""
        assert "@keyframes" in app_css_content

    def test_app_css_has_workflow_card_styles(self, app_css_content: str) -> None:
        """Test that app.css has workflow card styles."""
        assert "workflow-card" in app_css_content

    def test_app_css_has_responsive_styles(self, app_css_content: str) -> None:
        """Test that app.css has responsive media queries."""
        assert "@media" in app_css_content

    def test_app_css_has_connection_status_styles(self, app_css_content: str) -> None:
        """Test that app.css has connection status styles."""
        assert "connection-" in app_css_content

    def test_app_css_has_plan_step_styles(self, app_css_content: str) -> None:
        """Test that app.css has plan step styles."""
        assert "plan-step" in app_css_content

    def test_app_css_has_email_styles(self, app_css_content: str) -> None:
        """Test that app.css has email thread styles."""
        assert "email-" in app_css_content

    def test_app_css_has_validation_styles(self, app_css_content: str) -> None:
        """Test that app.css has validation result styles."""
        assert "validation-" in app_css_content


class TestFileSizes:
    """Tests for reasonable file sizes."""

    def test_app_js_reasonable_size(self) -> None:
        """Test that app.js has reasonable size."""
        app_js = STATIC_DIR / "js" / "app.js"
        size = app_js.stat().st_size

        # Should be between 1KB and 100KB
        assert size > 1000, f"app.js too small: {size} bytes"
        assert size < 100000, f"app.js too large: {size} bytes"

    def test_ag_ui_js_reasonable_size(self) -> None:
        """Test that ag-ui.js has reasonable size."""
        ag_ui_js = STATIC_DIR / "js" / "ag-ui.js"
        size = ag_ui_js.stat().st_size

        # Should be between 1KB and 100KB
        assert size > 1000, f"ag-ui.js too small: {size} bytes"
        assert size < 100000, f"ag-ui.js too large: {size} bytes"

    def test_app_css_reasonable_size(self) -> None:
        """Test that app.css has reasonable size."""
        app_css = STATIC_DIR / "css" / "app.css"
        size = app_css.stat().st_size

        # Should be between 1KB and 100KB
        assert size > 1000, f"app.css too small: {size} bytes"
        assert size < 100000, f"app.css too large: {size} bytes"
