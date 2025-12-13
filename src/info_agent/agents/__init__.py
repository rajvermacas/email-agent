"""
Agents module for Info-Agent.

This module provides the AI agents that handle specific tasks:
- Supervisor Agent: Orchestrates workflows and delegates tasks
- Mail Agent: Handles email-related operations via A2A protocol
"""

from info_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Exports will be added as agent modules are implemented
__all__: list[str] = []
