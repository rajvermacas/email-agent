"""
Info-Agent: Multi-agent information retrieval system.

This package provides a multi-agent system for collecting information from external
parties via email, using the Google A2A protocol for agent communication and
LangGraph for workflow orchestration.

Phase 1 MVP Backend Components:
- FastAPI Gateway: Main API entry point
- Supervisor Agent: Central orchestrator (embedded in gateway)
- Mail Agent: Email operations (A2A worker server)
- A2A Registry: Agent discovery (embedded in gateway)
- Mock Email Server: SMTP + REST API for development
"""

__version__ = "0.1.0"
__author__ = "Info-Agent Team"

from info_agent.config import get_settings, Settings

__all__ = [
    "__version__",
    "get_settings",
    "Settings",
]
