"""
Email server runner.

Provides a unified runner that starts both SMTP and REST API servers.
"""

import asyncio
import signal
import sys
import threading
from typing import Any

import structlog
import uvicorn

from info_agent.email_server.rest_api import create_email_server_app
from info_agent.email_server.smtp_server import MockSMTPServer
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.webhooks import WebhookManager
from info_agent.utils.exceptions import EmailServerError

logger = structlog.get_logger(__name__)


class EmailServerRunner:
    """
    Combined runner for SMTP and REST API servers.

    Manages the lifecycle of both servers and provides unified
    control interface.

    Attributes:
        _smtp_host: Host for SMTP server.
        _smtp_port: Port for SMTP server.
        _api_host: Host for REST API server.
        _api_port: Port for REST API server.
        _storage: Shared email storage.
        _webhook_manager: Shared webhook manager.
        _smtp_server: SMTP server instance.
        _api_thread: Thread running the API server.
    """

    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 2525,
        api_host: str = "localhost",
        api_port: int = 8025,
        storage: EmailStorage | None = None,
        webhook_manager: WebhookManager | None = None,
    ) -> None:
        """
        Initialize email server runner.

        Args:
            smtp_host: Host for SMTP server.
            smtp_port: Port for SMTP server.
            api_host: Host for REST API server.
            api_port: Port for REST API server.
            storage: Shared email storage.
            webhook_manager: Shared webhook manager.
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._api_host = api_host
        self._api_port = api_port

        self._storage = storage or EmailStorage()
        self._webhook_manager = webhook_manager or WebhookManager()

        self._smtp_server: MockSMTPServer | None = None
        self._api_thread: threading.Thread | None = None
        self._uvicorn_server: uvicorn.Server | None = None
        self._running = False

        logger.info(
            "email_server_runner_initialized",
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            api_host=api_host,
            api_port=api_port,
        )

    @property
    def storage(self) -> EmailStorage:
        """Get shared email storage."""
        return self._storage

    @property
    def webhook_manager(self) -> WebhookManager:
        """Get shared webhook manager."""
        return self._webhook_manager

    @property
    def is_running(self) -> bool:
        """Check if servers are running."""
        return self._running

    @property
    def smtp_server(self) -> MockSMTPServer | None:
        """Get SMTP server instance."""
        return self._smtp_server

    def _run_api_server(self) -> None:
        """Run the API server in a thread."""
        app = create_email_server_app(self._storage, self._webhook_manager)

        config = uvicorn.Config(
            app=app,
            host=self._api_host,
            port=self._api_port,
            log_level="warning",
        )

        self._uvicorn_server = uvicorn.Server(config)

        # Run the server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._uvicorn_server.serve())

    def start(self) -> None:
        """
        Start both SMTP and REST API servers.

        Raises:
            EmailServerError: If servers fail to start.
        """
        if self._running:
            logger.warning("email_server_already_running")
            return

        try:
            # Start SMTP server
            self._smtp_server = MockSMTPServer(
                host=self._smtp_host,
                port=self._smtp_port,
                storage=self._storage,
                webhook_manager=self._webhook_manager,
            )
            self._smtp_server.start()

            # Start API server in background thread
            self._api_thread = threading.Thread(
                target=self._run_api_server,
                daemon=True,
            )
            self._api_thread.start()

            self._running = True

            logger.info(
                "email_server_started",
                smtp_url=f"smtp://{self._smtp_host}:{self._smtp_port}",
                api_url=f"http://{self._api_host}:{self._api_port}",
                web_ui_url=f"http://{self._api_host}:{self._api_port}/",
            )

        except Exception as e:
            logger.error("email_server_start_failed", error=str(e))
            self.stop()
            raise EmailServerError(
                message=f"Failed to start email server: {e}",
                details={"error": str(e)},
            ) from e

    def stop(self) -> None:
        """Stop both servers."""
        if not self._running:
            return

        try:
            # Stop SMTP server
            if self._smtp_server:
                self._smtp_server.stop()
                self._smtp_server = None

            # Stop API server
            if self._uvicorn_server:
                self._uvicorn_server.should_exit = True

            self._running = False
            logger.info("email_server_stopped")

        except Exception as e:
            logger.error("email_server_stop_failed", error=str(e))

    def __enter__(self) -> "EmailServerRunner":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()


def run_email_server(
    smtp_host: str = "localhost",
    smtp_port: int = 2525,
    api_host: str = "localhost",
    api_port: int = 8025,
) -> None:
    """
    Run the email server (blocking).

    Args:
        smtp_host: Host for SMTP server.
        smtp_port: Port for SMTP server.
        api_host: Host for REST API server.
        api_port: Port for REST API server.
    """
    runner = EmailServerRunner(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        api_host=api_host,
        api_port=api_port,
    )

    def signal_handler(sig: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info("shutdown_signal_received", signal=sig)
        runner.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    runner.start()

    print(f"\n{'=' * 60}")
    print("Mock Email Server Running")
    print(f"{'=' * 60}")
    print(f"SMTP Server: smtp://{smtp_host}:{smtp_port}")
    print(f"REST API: http://{api_host}:{api_port}/api")
    print(f"Web UI: http://{api_host}:{api_port}/")
    print(f"{'=' * 60}")
    print("Press Ctrl+C to stop\n")

    # Keep main thread alive
    try:
        while runner.is_running:
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Mock Email Server")
    parser.add_argument("--smtp-host", default="localhost", help="SMTP host")
    parser.add_argument("--smtp-port", type=int, default=2525, help="SMTP port")
    parser.add_argument("--api-host", default="localhost", help="API host")
    parser.add_argument("--api-port", type=int, default=8025, help="API port")

    args = parser.parse_args()

    run_email_server(
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        api_host=args.api_host,
        api_port=args.api_port,
    )
