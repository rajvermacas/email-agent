#!/usr/bin/env python3
"""
Demo runner for Info-Agent system.

This script starts all required services for the demo:
1. Mock Email Server (HTTP :8080, SMTP :1025)
2. FastAPI Gateway with embedded Supervisor + Registry (:8000)
3. Mail Agent - A2A worker for email operations (:8002)
4. Validation Agent - A2A worker for document validation (:8003)

Usage:
    python scripts/run_demo.py

The demo will open 3 browser tabs:
- Tab 1: System Dashboard (http://localhost:8000)
- Tab 2: Target Person Inbox (http://localhost:8080/inbox/raj@gmail.com)
- Tab 3: End User Inbox (http://localhost:8080/inbox/mrinal@gmail.com)
"""

import asyncio
import logging
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Service configurations
# Services are started in order: Email Server -> Gateway -> Agents
SERVICES = [
    {
        "name": "Mock Email Server",
        "module": "info_agent.email_server.runner",
        "args": ["--api-port", "8080", "--smtp-port", "1025"],
        "port": 8080,
        "health_url": "http://localhost:8080/health",
    },
    {
        "name": "FastAPI Gateway",
        "script": "scripts/run_server.py",
        "port": 8000,
        "health_url": "http://localhost:8000/health",
    },
    {
        "name": "Mail Agent",
        "module": "info_agent.agents.mail",
        "args": ["--port", "8002"],
        "port": 8002,
        "health_url": "http://localhost:8002/health",
    },
    {
        "name": "Validation Agent",
        "module": "info_agent.agents.validation",
        "args": ["--port", "8003"],
        "port": 8003,
        "health_url": "http://localhost:8003/health",
    },
]

# Demo URLs to open in browser
DEMO_URLS = [
    ("System Dashboard", "http://localhost:8000"),
    ("Target Inbox (raj@gmail.com)", "http://localhost:8080/inbox/raj@gmail.com"),
    ("End User Inbox (mrinal@gmail.com)", "http://localhost:8080/inbox/mrinal@gmail.com"),
]


def check_port_available(port: int) -> bool:
    """Check if a port is available."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def wait_for_service(url: str, timeout: int = 30) -> bool:
    """Wait for a service to be healthy."""
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
            pass
        time.sleep(1)
    return False


def start_service(service: dict) -> subprocess.Popen:
    """Start a service as a subprocess."""
    logger.info(f"Starting {service['name']} on port {service['port']}...")

    if not check_port_available(service["port"]):
        logger.warning(f"Port {service['port']} is already in use for {service['name']}")
        raise RuntimeError(f"Port {service['port']} is already in use")

    # Determine command based on service config
    if "script" in service:
        # Run as script
        cmd = [sys.executable, service["script"]]
    elif "module" in service:
        # Run as module
        cmd = [sys.executable, "-m", service["module"]]
    else:
        raise ValueError(f"Service {service['name']} must have 'script' or 'module' key")

    # Add any additional arguments
    if "args" in service:
        cmd.extend(service["args"])

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent,
    )

    return process


def open_browser_tabs() -> None:
    """Open demo URLs in browser tabs."""
    logger.info("Opening browser tabs...")
    time.sleep(2)  # Give services time to fully initialize

    for name, url in DEMO_URLS:
        logger.info(f"Opening {name}: {url}")
        webbrowser.open_new_tab(url)
        time.sleep(0.5)  # Small delay between tabs


def main() -> None:
    """Run the demo."""
    logger.info("=" * 60)
    logger.info("Info-Agent Demo Runner")
    logger.info("=" * 60)

    processes: list[subprocess.Popen] = []

    try:
        # Start all services
        for service in SERVICES:
            process = start_service(service)
            processes.append(process)

            # Wait for service to be healthy
            logger.info(f"Waiting for {service['name']} to be ready...")
            if wait_for_service(service["health_url"]):
                logger.info(f"{service['name']} is ready!")
            else:
                logger.error(f"{service['name']} failed to start")
                raise RuntimeError(f"Service {service['name']} failed to start")

        logger.info("=" * 60)
        logger.info("All services started successfully!")
        logger.info("=" * 60)

        # Open browser tabs
        open_browser_tabs()

        logger.info("")
        logger.info("Demo is running. Press Ctrl+C to stop all services.")
        logger.info("")

        # Keep running until interrupted
        while True:
            time.sleep(1)

            # Check if any process has died
            for i, (process, service) in enumerate(zip(processes, SERVICES)):
                if process.poll() is not None:
                    logger.error(f"{service['name']} has stopped unexpectedly")
                    stdout, stderr = process.communicate()
                    if stderr:
                        logger.error(f"Error output: {stderr.decode()}")
                    raise RuntimeError(f"{service['name']} stopped")

    except KeyboardInterrupt:
        logger.info("\nShutting down demo...")

    finally:
        # Terminate all processes
        for process, service in zip(processes, SERVICES):
            if process.poll() is None:
                logger.info(f"Stopping {service['name']}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

        logger.info("Demo stopped.")


if __name__ == "__main__":
    main()
