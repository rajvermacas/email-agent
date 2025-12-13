"""
Validation Agent standalone runner.

Run the Validation Agent as a standalone A2A server.

Usage:
    python -m info_agent.agents.validation
    python -m info_agent.agents.validation --port 8003
    python -m info_agent.agents.validation --host 0.0.0.0 --port 8003
"""

import argparse
import signal
import sys
from types import FrameType

import structlog

from info_agent.a2a.server import AgentServer
from info_agent.agents.validation.executor import ValidationAgentExecutor
from info_agent.agents.validation.python_executor import PythonExecutor

logger = structlog.get_logger(__name__)


def run_validation_agent(host: str, port: int) -> None:
    """
    Run the Validation Agent server (blocking).

    Args:
        host: Host address to bind to.
        port: Port number to listen on.

    Raises:
        Exception: If server fails to start.
    """
    logger.info(
        "validation_agent_starting",
        host=host,
        port=port,
    )

    # Create dependencies
    python_executor = PythonExecutor()
    logger.info("python_executor_initialized")

    # Create executor with endpoint matching server address
    endpoint = f"http://{host}:{port}"
    executor = ValidationAgentExecutor(
        python_executor=python_executor,
        agent_id="validation-agent",
        endpoint=endpoint,
    )
    logger.info(
        "validation_agent_executor_created",
        agent_id="validation-agent",
        endpoint=endpoint,
    )

    # Create server
    server = AgentServer(executor=executor, host=host, port=port)
    logger.info("agent_server_created")

    # Signal handling for graceful shutdown
    def signal_handler(sig: int, frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        logger.info("shutdown_signal_received", signal=sig)
        print("\nShutting down Validation Agent...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # User-friendly console output
    print(f"\n{'=' * 60}")
    print("Validation Agent Running")
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
        "validation_agent_ready",
        host=host,
        port=port,
        skills=[s.id for s in executor.agent_card.skills],
    )

    # Start server (blocking call)
    server.run()


def main() -> None:
    """Parse arguments and run the Validation Agent."""
    parser = argparse.ArgumentParser(
        description="Run the Validation Agent as a standalone A2A server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m info_agent.agents.validation
  python -m info_agent.agents.validation --port 8003
  python -m info_agent.agents.validation --host 0.0.0.0 --port 8003
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
        default=8003,
        help="Port number to listen on (default: 8003)",
    )

    args = parser.parse_args()

    run_validation_agent(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
