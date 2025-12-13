"""
Unit tests for the PlanGenerator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from info_agent.supervisor.planner import PlanGenerator


class TestPlanGeneratorInit:
    """Tests for PlanGenerator initialization."""

    def test_init_without_llm(self) -> None:
        """Test initialization without LLM."""
        planner = PlanGenerator(use_llm=False)

        assert planner._provider is None
        assert planner._use_llm is False

    def test_init_with_provider(self) -> None:
        """Test initialization with provided LLM provider."""
        mock_provider = MagicMock()

        planner = PlanGenerator(
            llm_provider=mock_provider,
            use_llm=True,
        )

        assert planner._provider is mock_provider
        assert planner._use_llm is True


class TestPlanGeneratorStubPlan:
    """Tests for stub plan generation."""

    @pytest.fixture
    def planner(self) -> PlanGenerator:
        """Create a planner instance."""
        return PlanGenerator(use_llm=False)

    @pytest.mark.asyncio
    async def test_generate_stub_plan(self, planner: PlanGenerator) -> None:
        """Test generating stub plan."""
        plan = await planner.generate_plan(
            instructions="Send email to test@example.com",
            faq="Q: Format? A: Excel",
            escalation_rules="Escalate after 24 hours",
            validation_criteria="Must have 10 rows",
            available_agents=[],
        )

        assert len(plan) == 4
        assert plan[0]["action"] == "send_initial_request"
        assert plan[0]["agent"] == "mail-agent"
        assert plan[0]["skill"] == "send_email"

    @pytest.mark.asyncio
    async def test_stub_plan_extracts_email(self, planner: PlanGenerator) -> None:
        """Test stub plan extracts target email from instructions."""
        plan = await planner.generate_plan(
            instructions="Please request data from john.doe@company.com",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=[],
        )

        assert plan[0]["parameters"]["to"] == "john.doe@company.com"

    @pytest.mark.asyncio
    async def test_stub_plan_extracts_timeout(self, planner: PlanGenerator) -> None:
        """Test stub plan extracts timeout from escalation rules."""
        plan = await planner.generate_plan(
            instructions="Send email to test@example.com",
            faq="",
            escalation_rules="Escalate to admin after 72 hours of no response",
            validation_criteria="",
            available_agents=[],
        )

        assert plan[1]["parameters"]["timeout_hours"] == 72

    @pytest.mark.asyncio
    async def test_stub_plan_default_timeout(self, planner: PlanGenerator) -> None:
        """Test stub plan uses default timeout when not specified."""
        plan = await planner.generate_plan(
            instructions="Send email to test@example.com",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=[],
        )

        assert plan[1]["parameters"]["timeout_hours"] == 48

    @pytest.mark.asyncio
    async def test_stub_plan_step_structure(self, planner: PlanGenerator) -> None:
        """Test stub plan steps have correct structure."""
        plan = await planner.generate_plan(
            instructions="Send email to test@example.com",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=[],
        )

        for step in plan:
            assert "step_number" in step
            assert "action" in step
            assert "agent" in step
            assert "skill" in step
            assert "description" in step
            assert "parameters" in step
            assert "status" in step
            assert step["status"] == "pending"


class TestPlanGeneratorLLM:
    """Tests for LLM-powered plan generation."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock_chat_model = MagicMock()
        mock_chat_model.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='[{"step_number": 1, "action": "test", "agent": "mail-agent", "skill": "send_email", "description": "Test step", "parameters": {}}]'
            )
        )

        provider = MagicMock()
        provider.get_chat_model = MagicMock(return_value=mock_chat_model)
        return provider

    @pytest.fixture
    def planner_with_llm(self, mock_provider: MagicMock) -> PlanGenerator:
        """Create a planner with mock LLM."""
        return PlanGenerator(
            llm_provider=mock_provider,
            use_llm=True,
        )

    @pytest.mark.asyncio
    async def test_llm_plan_calls_provider(
        self,
        planner_with_llm: PlanGenerator,
        mock_provider: MagicMock,
    ) -> None:
        """Test LLM plan generation calls the provider."""
        await planner_with_llm.generate_plan(
            instructions="Send email to test@example.com",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=[],
        )

        mock_provider.get_chat_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_plan_parses_response(
        self,
        planner_with_llm: PlanGenerator,
    ) -> None:
        """Test LLM plan parses the response."""
        plan = await planner_with_llm.generate_plan(
            instructions="Send email to test@example.com",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=[],
        )

        assert len(plan) == 1
        assert plan[0]["action"] == "test"

    @pytest.mark.asyncio
    async def test_llm_plan_handles_json_object_response(self) -> None:
        """Test LLM plan handles JSON object with plan key."""
        mock_chat_model = MagicMock()
        mock_chat_model.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"plan": [{"step_number": 1, "action": "wrapped", "agent": "mail-agent", "skill": "send_email", "description": "Wrapped step", "parameters": {}}]}'
            )
        )

        mock_provider = MagicMock()
        mock_provider.get_chat_model = MagicMock(return_value=mock_chat_model)

        planner = PlanGenerator(
            llm_provider=mock_provider,
            use_llm=True,
        )

        plan = await planner.generate_plan(
            instructions="Send email",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=[],
        )

        assert len(plan) == 1
        assert plan[0]["action"] == "wrapped"

    @pytest.mark.asyncio
    async def test_llm_plan_fallback_on_parse_error(self) -> None:
        """Test LLM plan falls back to stub on parse error."""
        mock_chat_model = MagicMock()
        mock_chat_model.ainvoke = AsyncMock(
            return_value=MagicMock(content="invalid json")
        )

        mock_provider = MagicMock()
        mock_provider.get_chat_model = MagicMock(return_value=mock_chat_model)

        planner = PlanGenerator(
            llm_provider=mock_provider,
            use_llm=True,
        )

        plan = await planner.generate_plan(
            instructions="Send email to test@example.com",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=[],
        )

        # Should fall back to stub plan
        assert len(plan) == 4
        assert plan[0]["action"] == "send_initial_request"


class TestPlanGeneratorRearticulate:
    """Tests for plan rearticulation."""

    @pytest.fixture
    def planner(self) -> PlanGenerator:
        """Create a planner instance."""
        return PlanGenerator(use_llm=False)

    def test_rearticulate_empty_plan(self, planner: PlanGenerator) -> None:
        """Test rearticulating empty plan."""
        result = planner.rearticulate_plan([])

        assert "## Execution Plan" in result

    def test_rearticulate_single_step(self, planner: PlanGenerator) -> None:
        """Test rearticulating single step plan."""
        plan = [
            {
                "step_number": 1,
                "action": "send_email",
                "agent": "mail-agent",
                "skill": "send_email",
                "description": "Send initial request",
            }
        ]

        result = planner.rearticulate_plan(plan)

        assert "### Step 1: Send initial request" in result
        assert "- Agent: mail-agent" in result
        assert "- Skill: send_email" in result

    def test_rearticulate_multi_step(self, planner: PlanGenerator) -> None:
        """Test rearticulating multi-step plan."""
        plan = [
            {
                "step_number": 1,
                "action": "send_email",
                "agent": "mail-agent",
                "skill": "send_email",
                "description": "Send request",
            },
            {
                "step_number": 2,
                "action": "validate",
                "agent": "validation-agent",
                "skill": "validate_document",
                "description": "Validate response",
            },
        ]

        result = planner.rearticulate_plan(plan)

        assert "### Step 1: Send request" in result
        assert "### Step 2: Validate response" in result


class TestPlanGeneratorFormatAgents:
    """Tests for agent formatting."""

    @pytest.fixture
    def planner(self) -> PlanGenerator:
        """Create a planner instance."""
        return PlanGenerator(use_llm=False)

    def test_format_empty_agents(self, planner: PlanGenerator) -> None:
        """Test formatting empty agent list."""
        result = planner._format_agents([])

        assert result == ""

    def test_format_single_agent(self, planner: PlanGenerator) -> None:
        """Test formatting single agent."""
        agents = [
            {
                "name": "mail-agent",
                "description": "Email agent",
                "skills": [
                    {"id": "send_email", "name": "Send Email"},
                ],
            }
        ]

        result = planner._format_agents(agents)

        assert "- mail-agent: Email agent" in result
        assert "- send_email: Send Email" in result

    def test_format_multiple_agents(self, planner: PlanGenerator) -> None:
        """Test formatting multiple agents."""
        agents = [
            {
                "name": "mail-agent",
                "description": "Email agent",
                "skills": [],
            },
            {
                "name": "validation-agent",
                "description": "Validation agent",
                "skills": [],
            },
        ]

        result = planner._format_agents(agents)

        assert "mail-agent" in result
        assert "validation-agent" in result


class TestPlanGeneratorNormalize:
    """Tests for plan normalization."""

    @pytest.fixture
    def planner(self) -> PlanGenerator:
        """Create a planner instance."""
        return PlanGenerator(use_llm=False)

    def test_normalize_adds_missing_fields(self, planner: PlanGenerator) -> None:
        """Test normalization adds missing fields."""
        plan = [{"action": "test"}]

        result = planner._normalize_plan(plan)

        assert result[0]["step_number"] == 1
        assert result[0]["agent"] == "system"
        assert result[0]["skill"] == ""
        assert result[0]["description"] == ""
        assert result[0]["parameters"] == {}
        assert result[0]["status"] == "pending"

    def test_normalize_preserves_existing_fields(self, planner: PlanGenerator) -> None:
        """Test normalization preserves existing fields."""
        plan = [
            {
                "step_number": 5,
                "action": "custom",
                "agent": "custom-agent",
                "skill": "custom_skill",
                "description": "Custom step",
                "parameters": {"key": "value"},
            }
        ]

        result = planner._normalize_plan(plan)

        assert result[0]["step_number"] == 5
        assert result[0]["agent"] == "custom-agent"
        assert result[0]["skill"] == "custom_skill"
        assert result[0]["description"] == "Custom step"
        assert result[0]["parameters"] == {"key": "value"}
