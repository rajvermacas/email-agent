"""
A2A (Agent-to-Agent) protocol implementation.

This module provides a complete implementation of the A2A protocol for
agent-to-agent communication, including:

- Pydantic models for A2A protocol data structures
- SQLite storage for agent registry
- FastAPI router for registry endpoints
- HTTP client for agent communication

Usage:
    # Models
    from info_agent.a2a import AgentCard, AgentSkill, A2ATaskRequest

    # Storage
    from info_agent.a2a import A2AStorage

    # Registry
    from info_agent.a2a import create_a2a_router, init_registry, cleanup_registry

    # Client
    from info_agent.a2a import A2AClient

Example:
    # Setup registry
    from info_agent.a2a import init_registry, create_a2a_router

    await init_registry()
    router = create_a2a_router()

    # Register agent
    from info_agent.a2a import AgentCard, AgentSkill

    skill = AgentSkill(
        id="convert",
        name="Convert Currency",
        description="Converts between currencies",
        input_schema={"type": "object", "properties": {}}
    )

    card = AgentCard(
        name="currency-agent",
        description="Currency conversion agent",
        version="1.0",
        url="http://localhost:8001/a2a",
        capabilities={},
        skills=[skill],
        defaultInputModes=["text"],
        defaultOutputModes=["text"]
    )

    # Use client
    from info_agent.a2a import A2AClient

    client = A2AClient("http://localhost:8001/a2a")
    result = await client.send_task(
        agent_name="currency-agent",
        skill_id="convert",
        payload={"amount": 100, "from": "USD", "to": "EUR"}
    )
"""

from info_agent.a2a.client import A2AClient
from info_agent.a2a.models import (
    A2ATaskRequest,
    A2ATaskResponse,
    AgentCard,
    AgentSkill,
    RegisterAgentResponse,
)
from info_agent.a2a.registry import (
    cleanup_registry,
    create_a2a_router,
    get_a2a_router,
    init_registry,
)
from info_agent.a2a.storage import A2AStorage

__all__ = [
    # Models
    "AgentSkill",
    "AgentCard",
    "A2ATaskRequest",
    "A2ATaskResponse",
    "RegisterAgentResponse",
    # Storage
    "A2AStorage",
    # Registry
    "init_registry",
    "cleanup_registry",
    "create_a2a_router",
    "get_a2a_router",
    # Client
    "A2AClient",
]
