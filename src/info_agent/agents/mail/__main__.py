"""
Mail Agent standalone runner.

Run the Mail Agent as a standalone A2A server.

Usage:
    python -m info_agent.agents.mail
    python -m info_agent.agents.mail --port 8002
    python -m info_agent.agents.mail --host 0.0.0.0 --port 8002
"""

import argparse
import signal
import sys
from types import FrameType

import structlog

from info_agent.a2a.server import AgentServer
from info_agent.agents.mail.executor import MailAgentExecutor
from info_agent.email_server.storage import EmailStorage

logger = structlog.get_logger(__name__)


def run_mail_agent(host: str, port: int) -> None:
    """
    Run the Mail Agent server (blocking).

    Args:
        host: Host address to bind to.
        port: Port number to listen on.

    Raises:
        Exception: If server fails to start.
    """
    logger.info(
        "mail_agent_starting",
        host=host,
        port=port,
    )

    # Create dependencies
    storage = EmailStorage()
    logger.info("email_storage_initialized")

    # Create executor with endpoint matching server address
    endpoint = f"http://{host}:{port}"
    executor = MailAgentExecutor(
        storage=storage,
        agent_id="mail-agent",
        endpoint=endpoint,
    )
    logger.info(
        "mail_agent_executor_created",
        agent_id="mail-agent",
        endpoint=endpoint,
    )

    # Create server
    server = AgentServer(executor=executor, host=host, port=port)
    logger.info("agent_server_created")

    # Signal handling for graceful shutdown
    def signal_handler(sig: int, frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        logger.info("shutdown_signal_received", signal=sig)
        print("\nShutting down Mail Agent...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # User-friendly console output
    print(f"\n{'=' * 60}")
    print("Mail Agent Running")
    print(f"{'=' * 60}")
    print(f"A2A Endpoint:  http://{host}:{port}/tasks")
    print(f"Agent Card:    http://{host}:{port}/.well-known/agent.json")
    print(f"Health Check:  http://{host}:{port}/health")
    print(f"Statistics:    http://{host}:{port}/stats")
    print(f"{'=' * 60}")
    print("Skills available:")
    for skill in executor.agent_card.skills:
        print(f"  - {skill.id}: {skill.description}")
    print(f"{'=' * 60}")
    print("Press Ctrl+C to stop\n")

    logger.info(
        "mail_agent_ready",
        host=host,
        port=port,
        skills=[s.id for s in executor.agent_card.skills],
    )

    # Start server (blocking call)
    server.run()


def main() -> None:
    """Parse arguments and run the Mail Agent."""
    parser = argparse.ArgumentParser(
        description="Run the Mail Agent as a standalone A2A server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m info_agent.agents.mail
  python -m info_agent.agents.mail --port 8002
  python -m info_agent.agents.mail --host 0.0.0.0 --port 8002
        """,
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port number to listen on (default: 8002)",
    )

    args = parser.parse_args()

    run_mail_agent(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
