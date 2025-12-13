"""
Unit tests for A2A Agent Registry.
"""

import pytest

from info_agent.a2a.models import AgentCard, AgentSkill
from info_agent.a2a.registry import AgentRegistry
from info_agent.utils.exceptions import A2AError


@pytest.fixture
def sample_skill() -> AgentSkill:
    """Create a sample skill."""
    return AgentSkill(
        id="email-send",
        name="Send Email",
        description="Sends an email",
        tags=["email", "communication"],
    )


@pytest.fixture
def sample_agent(sample_skill: AgentSkill) -> AgentCard:
    """Create a sample agent."""
    return AgentCard(
        id="mail-agent-001",
        name="Mail Agent",
        description="Handles email operations",
        endpoint="http://localhost:8001/a2a",
        skills=[sample_skill],
        capabilities=["streaming"],
    )


class TestAgentRegistryRegister:
    """Tests for agent registration."""

    def test_register_agent(self, sample_agent: AgentCard) -> None:
        """Test registering an agent."""
        registry = AgentRegistry()

        result = registry.register(sample_agent)

        assert result.id == sample_agent.id
        assert registry.count() == 1

    def test_register_without_id_raises(self) -> None:
        """Test registering agent without ID raises error."""
        registry = AgentRegistry()
        agent = AgentCard(
            id="",  # Empty ID
            name="Test",
            description="Test",
            endpoint="http://localhost:8000",
        )

        with pytest.raises(A2AError) as exc_info:
            registry.register(agent)

        assert "required" in str(exc_info.value).lower()

    def test_register_without_endpoint_raises(self) -> None:
        """Test registering agent without endpoint raises error."""
        registry = AgentRegistry()
        agent = AgentCard(
            name="Test",
            description="Test",
            endpoint="",  # Empty endpoint
        )

        with pytest.raises(A2AError) as exc_info:
            registry.register(agent)

        assert "endpoint" in str(exc_info.value).lower()

    def test_register_duplicate_raises(self, sample_agent: AgentCard) -> None:
        """Test registering duplicate agent raises error."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        with pytest.raises(A2AError) as exc_info:
            registry.register(sample_agent)

        assert "already registered" in str(exc_info.value).lower()

    def test_register_indexes_skills(self, sample_agent: AgentCard) -> None:
        """Test registration indexes skills."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.find_by_skill("email-send")

        assert len(agents) == 1
        assert agents[0].id == sample_agent.id

    def test_register_indexes_tags(self, sample_agent: AgentCard) -> None:
        """Test registration indexes skill tags."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.find_by_tag("email")

        assert len(agents) == 1


class TestAgentRegistryUnregister:
    """Tests for agent unregistration."""

    def test_unregister_agent(self, sample_agent: AgentCard) -> None:
        """Test unregistering an agent."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        result = registry.unregister(sample_agent.id)

        assert result is True
        assert registry.count() == 0

    def test_unregister_nonexistent(self) -> None:
        """Test unregistering nonexistent agent returns False."""
        registry = AgentRegistry()

        result = registry.unregister("nonexistent")

        assert result is False

    def test_unregister_removes_from_indexes(
        self, sample_agent: AgentCard
    ) -> None:
        """Test unregistration removes from indexes."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        registry.unregister(sample_agent.id)

        agents = registry.find_by_skill("email-send")
        assert len(agents) == 0


class TestAgentRegistryGet:
    """Tests for getting agents."""

    def test_get_agent(self, sample_agent: AgentCard) -> None:
        """Test getting an agent by ID."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        result = registry.get(sample_agent.id)

        assert result is not None
        assert result.name == "Mail Agent"

    def test_get_nonexistent(self) -> None:
        """Test getting nonexistent agent returns None."""
        registry = AgentRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_get_by_name(self, sample_agent: AgentCard) -> None:
        """Test getting agent by name."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        result = registry.get_by_name("Mail Agent")

        assert result is not None
        assert result.id == sample_agent.id

    def test_get_by_name_case_insensitive(
        self, sample_agent: AgentCard
    ) -> None:
        """Test get by name is case insensitive."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        result = registry.get_by_name("mail agent")

        assert result is not None


class TestAgentRegistryList:
    """Tests for listing agents."""

    def test_list_all(self, sample_agent: AgentCard) -> None:
        """Test listing all agents."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.list_all()

        assert len(agents) == 1

    def test_list_by_status(self, sample_agent: AgentCard) -> None:
        """Test listing agents by status."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.list_all(status="active")

        assert len(agents) == 1

    def test_list_by_status_filters(self, sample_agent: AgentCard) -> None:
        """Test status filter excludes non-matching agents."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.list_all(status="inactive")

        assert len(agents) == 0


class TestAgentRegistryFind:
    """Tests for finding agents."""

    def test_find_by_skill(self, sample_agent: AgentCard) -> None:
        """Test finding agents by skill."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.find_by_skill("email-send")

        assert len(agents) == 1

    def test_find_by_skill_not_found(self) -> None:
        """Test finding by nonexistent skill returns empty."""
        registry = AgentRegistry()

        agents = registry.find_by_skill("nonexistent")

        assert len(agents) == 0

    def test_find_by_tag(self, sample_agent: AgentCard) -> None:
        """Test finding agents by tag."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.find_by_tag("email")

        assert len(agents) == 1

    def test_find_by_capability(self, sample_agent: AgentCard) -> None:
        """Test finding agents by capability."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.find_by_capability("streaming")

        assert len(agents) == 1

    def test_find_by_capability_not_found(
        self, sample_agent: AgentCard
    ) -> None:
        """Test finding by nonexistent capability returns empty."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        agents = registry.find_by_capability("unknown")

        assert len(agents) == 0


class TestAgentRegistryUpdate:
    """Tests for updating agents."""

    def test_update_agent(self, sample_agent: AgentCard) -> None:
        """Test updating an agent."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        sample_agent.name = "Updated Mail Agent"
        result = registry.update(sample_agent)

        assert result.name == "Updated Mail Agent"

    def test_update_nonexistent_raises(self) -> None:
        """Test updating nonexistent agent raises error."""
        registry = AgentRegistry()
        agent = AgentCard(
            name="Test",
            description="Test",
            endpoint="http://localhost:8000",
        )

        with pytest.raises(A2AError):
            registry.update(agent)

    def test_update_status(self, sample_agent: AgentCard) -> None:
        """Test updating agent status."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        result = registry.update_status(sample_agent.id, "inactive")

        assert result is not None
        assert result.status == "inactive"

    def test_update_status_nonexistent(self) -> None:
        """Test updating status of nonexistent agent returns None."""
        registry = AgentRegistry()

        result = registry.update_status("nonexistent", "inactive")

        assert result is None


class TestAgentRegistryCounts:
    """Tests for count methods."""

    def test_count(self, sample_agent: AgentCard) -> None:
        """Test counting agents."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        assert registry.count() == 1

    def test_count_empty(self) -> None:
        """Test counting empty registry."""
        registry = AgentRegistry()

        assert registry.count() == 0

    def test_count_by_status(self, sample_agent: AgentCard) -> None:
        """Test counting agents by status."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        assert registry.count_by_status("active") == 1
        assert registry.count_by_status("inactive") == 0


class TestAgentRegistryClear:
    """Tests for clearing registry."""

    def test_clear(self, sample_agent: AgentCard) -> None:
        """Test clearing all agents."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        count = registry.clear()

        assert count == 1
        assert registry.count() == 0


class TestAgentRegistryStats:
    """Tests for registry statistics."""

    def test_get_stats(self, sample_agent: AgentCard) -> None:
        """Test getting registry stats."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        stats = registry.get_stats()

        assert stats["total_agents"] == 1
        assert stats["total_skills"] == 1
        assert "active" in stats["status_counts"]

    def test_get_all_skills(self, sample_agent: AgentCard) -> None:
        """Test getting all registered skills."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        skills = registry.get_all_skills()

        assert "email-send" in skills

    def test_get_all_tags(self, sample_agent: AgentCard) -> None:
        """Test getting all registered tags."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        tags = registry.get_all_tags()

        assert "email" in tags
        assert "communication" in tags
