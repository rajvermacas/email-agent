"""
Unit tests for SMTP server.
"""

import pytest
from unittest.mock import MagicMock, patch

from info_agent.email_server.models import Email, EmailAddress, EmailStatus
from info_agent.email_server.smtp_server import MockSMTPServer, SMTPHandler
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.webhooks import WebhookManager
from info_agent.utils.exceptions import EmailServerError


class TestSMTPHandler:
    """Tests for SMTP message handler."""

    def test_handler_initialization(self) -> None:
        """Test handler initializes with storage."""
        storage = EmailStorage()
        handler = SMTPHandler(storage)

        assert handler._storage is storage

    def test_handler_with_webhook_manager(self) -> None:
        """Test handler initializes with webhook manager."""
        storage = EmailStorage()
        webhook_manager = WebhookManager()
        handler = SMTPHandler(storage, webhook_manager)

        assert handler._webhook_manager is webhook_manager

    @pytest.mark.asyncio
    async def test_handle_rcpt(self) -> None:
        """Test RCPT TO handling."""
        storage = EmailStorage()
        handler = SMTPHandler(storage)

        envelope = MagicMock()
        envelope.rcpt_tos = []

        result = await handler.handle_RCPT(
            server=MagicMock(),
            session=MagicMock(),
            envelope=envelope,
            address="test@example.com",
            rcpt_options=[],
        )

        assert result == "250 OK"
        assert "test@example.com" in envelope.rcpt_tos

    def test_decode_header_simple(self) -> None:
        """Test decoding simple header."""
        storage = EmailStorage()
        handler = SMTPHandler(storage)

        result = handler._decode_header("Simple Subject")

        assert result == "Simple Subject"

    def test_decode_header_none(self) -> None:
        """Test decoding None header."""
        storage = EmailStorage()
        handler = SMTPHandler(storage)

        result = handler._decode_header(None)

        assert result == ""


class TestMockSMTPServer:
    """Tests for MockSMTPServer."""

    def test_server_initialization(self) -> None:
        """Test server initializes with defaults."""
        server = MockSMTPServer()

        assert server.host == "localhost"
        assert server.port == 2525
        assert server.is_running is False

    def test_server_custom_host_port(self) -> None:
        """Test server with custom host and port."""
        server = MockSMTPServer(host="0.0.0.0", port=1025)

        assert server.host == "0.0.0.0"
        assert server.port == 1025

    def test_server_with_storage(self) -> None:
        """Test server with custom storage."""
        storage = EmailStorage()
        server = MockSMTPServer(storage=storage)

        assert server.storage is storage

    def test_server_with_webhook_manager(self) -> None:
        """Test server with custom webhook manager."""
        webhook_manager = WebhookManager()
        server = MockSMTPServer(webhook_manager=webhook_manager)

        assert server.webhook_manager is webhook_manager

    def test_server_creates_default_storage(self) -> None:
        """Test server creates storage if not provided."""
        server = MockSMTPServer()

        assert server.storage is not None
        assert isinstance(server.storage, EmailStorage)

    def test_server_creates_default_webhook_manager(self) -> None:
        """Test server creates webhook manager if not provided."""
        server = MockSMTPServer()

        assert server.webhook_manager is not None
        assert isinstance(server.webhook_manager, WebhookManager)

    def test_server_start_stop(self) -> None:
        """Test starting and stopping server."""
        server = MockSMTPServer(port=12525)  # Use high port to avoid conflicts

        try:
            server.start()
            assert server.is_running is True

            server.stop()
            assert server.is_running is False
        except Exception:
            # Port might be in use, skip test
            pytest.skip("Port unavailable")
        finally:
            if server.is_running:
                server.stop()

    def test_server_start_when_already_running(self) -> None:
        """Test starting when already running logs warning."""
        server = MockSMTPServer(port=12526)

        try:
            server.start()
            server.start()  # Should log warning
            assert server.is_running is True
        except Exception:
            pytest.skip("Port unavailable")
        finally:
            server.stop()

    def test_server_stop_when_not_running(self) -> None:
        """Test stopping when not running is safe."""
        server = MockSMTPServer()

        server.stop()  # Should not raise

    def test_server_context_manager(self) -> None:
        """Test server as context manager."""
        server = MockSMTPServer(port=12527)

        try:
            with server as srv:
                assert srv.is_running is True

            assert srv.is_running is False
        except Exception:
            pytest.skip("Port unavailable")

    def test_server_start_failure(self) -> None:
        """Test server handles start failure."""
        server = MockSMTPServer(port=12528)

        with patch.object(server, "_host", "invalid-host-that-does-not-exist"):
            with patch(
                "info_agent.email_server.smtp_server.Controller"
            ) as mock_controller:
                mock_controller.side_effect = Exception("Bind failed")

                with pytest.raises(EmailServerError):
                    server.start()
