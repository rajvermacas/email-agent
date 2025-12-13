"""
A2A Agent Registry implementation.

Provides registration and discovery of A2A agents.
"""

import threading
from typing import Any

import structlog

from info_agent.a2a.models import AgentCard, AgentSkill
from info_agent.utils.exceptions import A2AError
from info_agent.utils.helpers import get_current_timestamp

logger = structlog.get_logger(__name__)


class AgentRegistry:
    """
    Registry for A2A agents.

    Provides thread-safe agent registration, discovery, and lookup.

    Attributes:
        _agents: Dictionary mapping agent ID to AgentCard.
        _skills_index: Index mapping skill ID to agent IDs.
        _lock: Threading lock for thread-safe operations.
    """

    def __init__(self) -> None:
        """Initialize empty agent registry."""
        self._agents: dict[str, AgentCard] = {}
        self._skills_index: dict[str, list[str]] = {}
        self._tags_index: dict[str, list[str]] = {}
        self._lock = threading.RLock()

        logger.info("agent_registry_initialized")

    def register(self, agent: AgentCard) -> AgentCard:
        """
        Register an agent with the registry.

        Args:
            agent: Agent card to register.

        Returns:
            Registered agent card.

        Raises:
            A2AError: If registration fails or agent already exists.
        """
        with self._lock:
            if not agent.id:
                raise A2AError(
                    message="Agent ID is required",
                    details={"agent_name": agent.name},
                )

            if not agent.endpoint:
                raise A2AError(
                    message="Agent endpoint is required",
                    details={"agent_id": agent.id},
                )

            if agent.id in self._agents:
                raise A2AError(
                    message=f"Agent already registered: {agent.id}",
                    details={"agent_id": agent.id},
                )

            # Store the agent
            self._agents[agent.id] = agent

            # Index by skills
            for skill in agent.skills:
                if skill.id not in self._skills_index:
                    self._skills_index[skill.id] = []
                self._skills_index[skill.id].append(agent.id)

                # Index by skill tags
                for tag in skill.tags:
                    if tag not in self._tags_index:
                        self._tags_index[tag] = []
                    if agent.id not in self._tags_index[tag]:
                        self._tags_index[tag].append(agent.id)

            logger.info(
                "agent_registered",
                agent_id=agent.id,
                agent_name=agent.name,
                endpoint=agent.endpoint,
                skills_count=len(agent.skills),
            )

            return agent

    def unregister(self, agent_id: str) -> bool:
        """
        Unregister an agent from the registry.

        Args:
            agent_id: ID of agent to unregister.

        Returns:
            True if unregistered, False if not found.
        """
        with self._lock:
            agent = self._agents.pop(agent_id, None)
            if not agent:
                logger.debug("agent_not_found", agent_id=agent_id)
                return False

            # Remove from skills index
            for skill in agent.skills:
                if skill.id in self._skills_index:
                    if agent_id in self._skills_index[skill.id]:
                        self._skills_index[skill.id].remove(agent_id)
                    if not self._skills_index[skill.id]:
                        del self._skills_index[skill.id]

                # Remove from tags index
                for tag in skill.tags:
                    if tag in self._tags_index:
                        if agent_id in self._tags_index[tag]:
                            self._tags_index[tag].remove(agent_id)
                        if not self._tags_index[tag]:
                            del self._tags_index[tag]

            logger.info("agent_unregistered", agent_id=agent_id)
            return True

    def get(self, agent_id: str) -> AgentCard | None:
        """
        Get an agent by ID.

        Args:
            agent_id: Agent identifier.

        Returns:
            AgentCard if found, None otherwise.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent:
                logger.debug("agent_retrieved", agent_id=agent_id)
            return agent

    def get_by_name(self, name: str) -> AgentCard | None:
        """
        Get an agent by name.

        Args:
            name: Agent name to search for.

        Returns:
            First matching AgentCard if found, None otherwise.
        """
        with self._lock:
            for agent in self._agents.values():
                if agent.name.lower() == name.lower():
                    return agent
            return None

    def list_all(self, status: str | None = None) -> list[AgentCard]:
        """
        List all registered agents.

        Args:
            status: Optional status filter.

        Returns:
            List of agent cards.
        """
        with self._lock:
            agents = list(self._agents.values())
            if status:
                agents = [a for a in agents if a.status == status]
            return agents

    def find_by_skill(self, skill_id: str) -> list[AgentCard]:
        """
        Find agents that provide a specific skill.

        Args:
            skill_id: Skill identifier to search for.

        Returns:
            List of agents with the skill.
        """
        with self._lock:
            agent_ids = self._skills_index.get(skill_id, [])
            agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

            logger.debug(
                "agents_found_by_skill",
                skill_id=skill_id,
                count=len(agents),
            )

            return agents

    def find_by_tag(self, tag: str) -> list[AgentCard]:
        """
        Find agents by skill tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of agents with skills matching the tag.
        """
        with self._lock:
            agent_ids = self._tags_index.get(tag, [])
            agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

            logger.debug(
                "agents_found_by_tag",
                tag=tag,
                count=len(agents),
            )

            return agents

    def find_by_capability(self, capability: str) -> list[AgentCard]:
        """
        Find agents that have a specific capability.

        Args:
            capability: Capability to search for.

        Returns:
            List of agents with the capability.
        """
        with self._lock:
            agents = [a for a in self._agents.values() if capability in a.capabilities]

            logger.debug(
                "agents_found_by_capability",
                capability=capability,
                count=len(agents),
            )

            return agents

    def update(self, agent: AgentCard) -> AgentCard:
        """
        Update an existing agent's registration.

        Args:
            agent: Updated agent card.

        Returns:
            Updated agent card.

        Raises:
            A2AError: If agent not found.
        """
        with self._lock:
            if agent.id not in self._agents:
                raise A2AError(
                    message=f"Agent not found: {agent.id}",
                    details={"agent_id": agent.id},
                )

            # Get old agent to update indexes
            old_agent = self._agents[agent.id]

            # Remove old skill indexes
            for skill in old_agent.skills:
                if skill.id in self._skills_index:
                    if agent.id in self._skills_index[skill.id]:
                        self._skills_index[skill.id].remove(agent.id)

            # Update agent
            agent.updated_at = get_current_timestamp()
            self._agents[agent.id] = agent

            # Rebuild skill indexes
            for skill in agent.skills:
                if skill.id not in self._skills_index:
                    self._skills_index[skill.id] = []
                if agent.id not in self._skills_index[skill.id]:
                    self._skills_index[skill.id].append(agent.id)

            logger.info(
                "agent_updated",
                agent_id=agent.id,
                agent_name=agent.name,
            )

            return agent

    def update_status(self, agent_id: str, status: str) -> AgentCard | None:
        """
        Update an agent's status.

        Args:
            agent_id: Agent to update.
            status: New status value.

        Returns:
            Updated agent card if found, None otherwise.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return None

            agent.status = status
            agent.updated_at = get_current_timestamp()

            logger.info(
                "agent_status_updated",
                agent_id=agent_id,
                status=status,
            )

            return agent

    def count(self) -> int:
        """
        Get count of registered agents.

        Returns:
            Number of registered agents.
        """
        with self._lock:
            return len(self._agents)

    def count_by_status(self, status: str) -> int:
        """
        Count agents with a specific status.

        Args:
            status: Status to count.

        Returns:
            Number of agents with the status.
        """
        with self._lock:
            return sum(1 for a in self._agents.values() if a.status == status)

    def clear(self) -> int:
        """
        Clear all registered agents.

        Returns:
            Number of agents cleared.
        """
        with self._lock:
            count = len(self._agents)
            self._agents.clear()
            self._skills_index.clear()
            self._tags_index.clear()
            logger.info("agent_registry_cleared", count=count)
            return count

    def get_stats(self) -> dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with registry stats.
        """
        with self._lock:
            status_counts: dict[str, int] = {}
            skill_counts: dict[str, int] = {}

            for agent in self._agents.values():
                status_counts[agent.status] = status_counts.get(agent.status, 0) + 1
                for skill in agent.skills:
                    skill_counts[skill.id] = skill_counts.get(skill.id, 0) + 1

            return {
                "total_agents": len(self._agents),
                "total_skills": len(self._skills_index),
                "total_tags": len(self._tags_index),
                "status_counts": status_counts,
                "skill_counts": skill_counts,
            }

    def get_all_skills(self) -> list[str]:
        """
        Get all registered skill IDs.

        Returns:
            List of unique skill IDs.
        """
        with self._lock:
            return list(self._skills_index.keys())

    def get_all_tags(self) -> list[str]:
        """
        Get all registered tags.

        Returns:
            List of unique tags.
        """
        with self._lock:
            return list(self._tags_index.keys())
