"""
Unit tests for the SupervisorAgent.
"""

import tempfile
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock

from info_agent.supervisor.agent import SupervisorAgent
from info_agent.supervisor.planner import PlanGenerator
from info_agent.supervisor.delegator import StubTaskDelegator
from info_agent.workflow import InfoAgentWorkflow, WorkflowStatus


class TestSupervisorAgentInit:
    """Tests for SupervisorAgent initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        agent = SupervisorAgent()

        assert agent._workflow is not None
        assert agent._planner is not None
        assert isinstance(agent._delegator, StubTaskDelegator)

    def test_init_with_components(self) -> None:
        """Test initialization with provided components."""
        workflow = InfoAgentWorkflow()
        planner = PlanGenerator(use_llm=False)
        delegator = StubTaskDelegator()

        agent = SupervisorAgent(
            workflow=workflow,
            planner=planner,
            delegator=delegator,
        )

        assert agent._workflow is workflow
        assert agent._planner is planner
        assert agent._delegator is delegator

    def test_init_no_llm_by_default(self) -> None:
        """Test LLM is disabled by default."""
        agent = SupervisorAgent()

        assert agent._planner._use_llm is False


class TestSupervisorAgentCreate:
    """Tests for async factory method."""

    @pytest.mark.asyncio
    async def test_create_without_checkpoint(self) -> None:
        """Test create without checkpoint path."""
        agent = await SupervisorAgent.create()

        assert agent.workflow is not None
        assert agent.workflow.checkpointer is None

    @pytest.mark.asyncio
    async def test_create_with_checkpoint(self) -> None:
        """Test create with checkpoint path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            agent = await SupervisorAgent.create(checkpoint_db_path=db_path)

            assert agent.workflow.checkpointer is not None


class TestSupervisorAgentWorkflow:
    """Tests for workflow operations."""

    @pytest.fixture
    def agent(self) -> SupervisorAgent:
        """Create a supervisor agent."""
        return SupervisorAgent(use_stub_delegator=True)

    @pytest.mark.asyncio
    async def test_start_workflow(self, agent: SupervisorAgent) -> None:
        """Test starting a workflow."""
        result = await agent.start_workflow(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="Q: Format? A: Excel",
            escalation_rules="Escalate after 48 hours",
            validation_criteria="Must have 10 rows",
        )

        assert result is not None
        assert result["workflow_id"] == "wf-test"
        assert result["status"] == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_stream_workflow(self, agent: SupervisorAgent) -> None:
        """Test streaming workflow events."""
        events = []
        async for node_name, state in agent.stream_workflow(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="FAQ content",
            escalation_rules="Rules content",
            validation_criteria="Criteria content",
        ):
            events.append((node_name, state))

        assert len(events) > 0
        assert events[0][0] == "parse_inputs"


class TestSupervisorAgentPlan:
    """Tests for plan generation."""

    @pytest.fixture
    def agent(self) -> SupervisorAgent:
        """Create a supervisor agent."""
        return SupervisorAgent(use_llm=False, use_stub_delegator=True)

    @pytest.mark.asyncio
    async def test_generate_plan(self, agent: SupervisorAgent) -> None:
        """Test generating an execution plan."""
        plan = await agent.generate_plan(
            instructions="Send email to test@example.com",
            faq="Q: Format? A: Excel",
            escalation_rules="Escalate after 48 hours",
            validation_criteria="Must have 10 rows",
        )

        assert len(plan) == 4
        assert plan[0]["action"] == "send_initial_request"

    @pytest.mark.asyncio
    async def test_generate_plan_with_agents(self, agent: SupervisorAgent) -> None:
        """Test generating plan with custom agents."""
        available_agents = [
            {
                "name": "custom-agent",
                "description": "Custom agent",
                "skills": [{"id": "custom_skill", "name": "Custom Skill"}],
            }
        ]

        plan = await agent.generate_plan(
            instructions="Send email to test@example.com",
            faq="",
            escalation_rules="",
            validation_criteria="",
            available_agents=available_agents,
        )

        assert len(plan) > 0

    def test_rearticulate_plan(self, agent: SupervisorAgent) -> None:
        """Test rearticulating plan."""
        plan = [
            {
                "step_number": 1,
                "action": "test",
                "agent": "test-agent",
                "skill": "test_skill",
                "description": "Test step",
            }
        ]

        result = agent.rearticulate_plan(plan)

        assert "## Execution Plan" in result
        assert "Test step" in result


class TestSupervisorAgentApproval:
    """Tests for plan approval operations."""

    @pytest.mark.asyncio
    async def test_approve_plan(self) -> None:
        """Test approving a plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            agent = await SupervisorAgent.create(checkpoint_db_path=db_path)

            # First run workflow
            await agent.start_workflow(
                workflow_id="wf-test",
                instructions="Send email to test@example.com",
                faq="FAQ",
                escalation_rules="Rules",
                validation_criteria="Criteria",
            )

            # Approve should work
            result = await agent.approve_plan("wf-test")

            assert result is not None

    @pytest.mark.asyncio
    async def test_reject_plan(self) -> None:
        """Test rejecting a plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            agent = await SupervisorAgent.create(checkpoint_db_path=db_path)

            # First run workflow
            await agent.start_workflow(
                workflow_id="wf-test",
                instructions="Send email to test@example.com",
                faq="FAQ",
                escalation_rules="Rules",
                validation_criteria="Criteria",
            )

            # Reject should work
            result = await agent.reject_plan("wf-test", "Need more details")

            assert result is not None


class TestSupervisorAgentState:
    """Tests for workflow state operations."""

    @pytest.mark.asyncio
    async def test_get_state_without_checkpoint(self) -> None:
        """Test get_workflow_state without checkpointer."""
        agent = SupervisorAgent()

        result = await agent.get_workflow_state("wf-test")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_state_with_checkpoint(self) -> None:
        """Test get_workflow_state with checkpointer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            agent = await SupervisorAgent.create(checkpoint_db_path=db_path)

            # Run workflow
            await agent.start_workflow(
                workflow_id="wf-test",
                instructions="Send email to test@example.com",
                faq="FAQ",
                escalation_rules="Rules",
                validation_criteria="Criteria",
            )

            # Get state
            state = await agent.get_workflow_state("wf-test")

            assert state is not None


class TestSupervisorAgentDelegation:
    """Tests for task delegation."""

    @pytest.fixture
    def agent(self) -> SupervisorAgent:
        """Create a supervisor agent with stub delegator."""
        return SupervisorAgent(use_stub_delegator=True)

    @pytest.mark.asyncio
    async def test_delegate_to_mail_agent(self, agent: SupervisorAgent) -> None:
        """Test delegating to Mail Agent."""
        task = await agent.delegate_to_mail_agent(
            agent_endpoint="http://localhost:8001",
            skill_id="send_email",
            parameters={"to": "test@example.com"},
        )

        assert task is not None
        assert len(task.artifacts) > 0
        assert task.artifacts[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_delegate_to_validation_agent(self, agent: SupervisorAgent) -> None:
        """Test delegating to Validation Agent."""
        task = await agent.delegate_to_validation_agent(
            agent_endpoint="http://localhost:8002",
            skill_id="validate_document",
            parameters={"criteria": "Must have 10 rows"},
        )

        assert task is not None
        assert len(task.artifacts) > 0
        assert task.artifacts[0].data["passed"] is True


class TestSupervisorAgentDefaultAgents:
    """Tests for default agent configuration."""

    @pytest.fixture
    def agent(self) -> SupervisorAgent:
        """Create a supervisor agent."""
        return SupervisorAgent()

    def test_get_default_agents(self, agent: SupervisorAgent) -> None:
        """Test getting default agents."""
        agents = agent._get_default_agents()

        assert len(agents) == 2

        # Check mail agent
        mail_agent = next(a for a in agents if a["name"] == "mail-agent")
        assert mail_agent["endpoint"] == "http://localhost:8001"
        assert len(mail_agent["skills"]) > 0

        # Check validation agent
        validation_agent = next(a for a in agents if a["name"] == "validation-agent")
        assert validation_agent["endpoint"] == "http://localhost:8002"
        assert len(validation_agent["skills"]) > 0


class TestSupervisorAgentClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Test closing the agent."""
        agent = SupervisorAgent()

        await agent.close()

        # Should not raise
        assert True

    @pytest.mark.asyncio
    async def test_close_with_checkpoint(self) -> None:
        """Test closing agent with checkpointer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            agent = await SupervisorAgent.create(checkpoint_db_path=db_path)

            await agent.close()

            # Should not raise
            assert True
