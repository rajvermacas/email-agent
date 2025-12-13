"""
A2A Protocol implementation package.

Provides A2A (Agent-to-Agent) communication capabilities including:
- Agent registry for registration and discovery
- Agent cards defining capabilities
- Client for communicating with A2A agents
- Base classes for implementing A2A-compatible agents
- Server components for hosting A2A agents
"""

from info_agent.a2a.models import (
    AgentCard,
    AgentSkill,
    Artifact,
    MessagePart,
    Task,
    TaskRequest,
    TaskState,
)
from info_agent.a2a.registry import AgentRegistry
from info_agent.a2a.client import A2AClient
from info_agent.a2a.executor import (
    BaseAgentExecutor,
    EventQueue,
    RequestContext,
)
from info_agent.a2a.server import (
    AgentServer,
    TaskStore,
    create_agent_app,
    create_agent_router,
)

__all__ = [
    # Models
    "AgentCard",
    "AgentSkill",
    "Artifact",
    "MessagePart",
    "Task",
    "TaskRequest",
    "TaskState",
    # Registry
    "AgentRegistry",
    # Client
    "A2AClient",
    # Executor
    "BaseAgentExecutor",
    "EventQueue",
    "RequestContext",
    # Server
    "AgentServer",
    "TaskStore",
    "create_agent_app",
    "create_agent_router",
]
