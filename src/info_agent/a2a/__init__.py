"""
A2A (Agent-to-Agent) protocol implementation using official a2a-sdk.

This module provides A2A protocol support using the official a2a-sdk,
along with custom registry implementation for agent discovery.

Components:
- SDK Types: Re-exported from a2a-sdk for convenience
- Custom Registry: SQLite-backed agent registry (not part of A2A spec)
- SDK Client Wrapper: Simplified API over SDK client
- Custom Models: Registry-specific response models

Usage:
    # SDK Types (re-exported from a2a-sdk)
    from info_agent.a2a import AgentCard, AgentSkill, Message, Task

    # Custom Registry
    from info_agent.a2a import A2AStorage, init_registry, create_a2a_router

    # SDK Client Wrapper
    from info_agent.a2a import SDKClientWrapper, get_sdk_client

Example:
    # Setup registry
    await init_registry()
    router = create_a2a_router()

    # Register agent using SDK AgentCard
    from info_agent.a2a import AgentCard, AgentSkill

    skill = AgentSkill(
        id="convert",
        name="Convert Currency",
        description="Converts between currencies",
        tags=["currency"],
        input_schema={"type": "object", "properties": {}}
    )

    card = AgentCard(
        name="currency-agent",
        description="Currency conversion agent",
        version="1.0",
        url="http://localhost:8001",
        skills=[skill],
        default_input_modes=["text"],  # SDK uses snake_case
        default_output_modes=["text"]
    )

    # Use SDK client wrapper
    from info_agent.a2a import get_sdk_client

    client = get_sdk_client()
    result = await client.send_task(
        agent_url="http://localhost:8001",
        skill_id="convert",
        payload={"amount": 100, "from": "USD", "to": "EUR"}
    )
"""

# Re-export SDK types for convenience
from a2a.types import (
    AgentCard,
    AgentSkill,
    DataPart,
    Message,
    Role,
    Task,
    TaskStatus,
)

# Custom registry components
from info_agent.a2a.registry import (
    cleanup_registry,
    create_a2a_router,
    get_a2a_router,
    init_registry,
)

# Custom storage
from info_agent.a2a.storage import A2AStorage

# SDK client wrapper
from info_agent.a2a.sdk_client_wrapper import (
    SDKClientWrapper,
    cleanup_sdk_client,
    get_sdk_client,
)

# Custom models (keep RegisterAgentResponse for registry API)
# Note: A2ATaskRequest and A2ATaskResponse are replaced by SDK Message and Task
from info_agent.a2a.registry_models import RegisterAgentResponse

__all__ = [
    # SDK Types (re-exported)
    "AgentCard",
    "AgentSkill",
    "Message",
    "Task",
    "TaskStatus",
    "DataPart",
    "Role",
    # Custom Registry
    "A2AStorage",
    "init_registry",
    "cleanup_registry",
    "create_a2a_router",
    "get_a2a_router",
    # SDK Client Wrapper
    "SDKClientWrapper",
    "get_sdk_client",
    "cleanup_sdk_client",
    # Custom Models
    "RegisterAgentResponse",
]
