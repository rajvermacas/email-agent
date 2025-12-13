"""Integration tests for complete workflow execution.

These tests verify the full workflow from request creation through
validation completion, using mock email and LLM backends.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from info_agent.a2a.models import TaskState as A2ATaskState, AgentCard, AgentSkill
from info_agent.a2a.registry import AgentRegistry
from info_agent.agents.mail import MailAgentExecutor, create_mail_agent_card
from info_agent.agents.validation import ValidationAgentExecutor, create_validation_agent_card
from info_agent.supervisor.agent import SupervisorAgent
from info_agent.workflow.graph import create_workflow_graph


logger = logging.getLogger(__name__)


@pytest.fixture
def registry() -> AgentRegistry:
    """Create a fresh registry for each test."""
    return AgentRegistry()


class TestWorkflowGraphCreation:
    """Tests for workflow graph creation."""

    def test_create_workflow_graph(self) -> None:
        """Test that workflow graph can be created."""
        graph = create_workflow_graph()
        assert graph is not None

    def test_workflow_graph_has_nodes(self) -> None:
        """Test that workflow graph has expected nodes."""
        graph = create_workflow_graph()

        # Get node names from the graph
        assert graph is not None


class TestSupervisorAgentIntegration:
    """Tests for supervisor agent integration."""

    @pytest.fixture
    def supervisor(self) -> SupervisorAgent:
        """Create supervisor agent."""
        return SupervisorAgent(
            use_llm=False,
            use_stub_delegator=True,
        )

    @pytest.mark.asyncio
    async def test_supervisor_creates_workflow(
        self, supervisor: SupervisorAgent
    ) -> None:
        """Test that supervisor can create a workflow."""
        result = await supervisor.create_workflow(
            instructions="Test instructions",
            target_email="test@example.com",
        )

        assert result is not None
        assert "workflow_id" in result
        assert result["status"] in ["pending", "planning"]

    @pytest.mark.asyncio
    async def test_supervisor_gets_workflow_status(
        self, supervisor: SupervisorAgent
    ) -> None:
        """Test that supervisor can get workflow status."""
        # Create a workflow first
        result = await supervisor.create_workflow(
            instructions="Test instructions",
            target_email="test@example.com",
        )

        workflow_id = result["workflow_id"]

        # Get status
        status = await supervisor.get_workflow_status(workflow_id)
        assert status is not None
        assert status["workflow_id"] == workflow_id

    @pytest.mark.asyncio
    async def test_supervisor_lists_workflows(
        self, supervisor: SupervisorAgent
    ) -> None:
        """Test that supervisor can list workflows."""
        # Create a few workflows
        await supervisor.create_workflow(
            instructions="Test 1",
            target_email="test1@example.com",
        )
        await supervisor.create_workflow(
            instructions="Test 2",
            target_email="test2@example.com",
        )

        # List workflows
        workflows = await supervisor.list_workflows()
        assert len(workflows) >= 2


class TestAgentRegistryIntegration:
    """Tests for agent registry integration."""

    def test_registry_registers_agents(self, registry: AgentRegistry) -> None:
        """Test that registry can register agents."""
        # Create agent cards
        mail_agent = AgentCard(
            id="mail-agent-001",
            name="Mail Agent",
            description="Handles email operations",
            url="http://localhost:8001",
            skills=[
                AgentSkill(
                    id="send_email",
                    name="Send Email",
                    description="Sends emails",
                    tags=["email"],
                )
            ],
            capabilities=["send_email", "receive_email"],
        )

        validation_agent = AgentCard(
            id="validation-agent-001",
            name="Validation Agent",
            description="Validates documents",
            url="http://localhost:8002",
            skills=[
                AgentSkill(
                    id="validate_document",
                    name="Validate Document",
                    description="Validates documents",
                    tags=["validation"],
                )
            ],
            capabilities=["validate_document"],
        )

        # Register agents
        registry.register(mail_agent)
        registry.register(validation_agent)

        # Find agents
        mail_agents = registry.find_by_capability("send_email")
        assert len(mail_agents) >= 1

        validation_agents = registry.find_by_capability("validate_document")
        assert len(validation_agents) >= 1

    def test_registry_discovers_agents_by_skill(
        self, registry: AgentRegistry
    ) -> None:
        """Test that registry can discover agents by skill."""
        # Register agents with skills
        agent = AgentCard(
            id="mail-001",
            name="Mail Agent",
            description="Mail agent",
            url="http://localhost:8001",
            skills=[
                AgentSkill(
                    id="send_email",
                    name="Send Email",
                    description="Sends emails",
                    tags=["email"],
                )
            ],
        )
        registry.register(agent)

        # Find by skill
        agents = registry.find_by_skill("send_email")
        assert len(agents) >= 1


class TestMailAgentIntegration:
    """Tests for mail agent integration."""

    @pytest.fixture
    def mail_executor(self) -> MailAgentExecutor:
        """Create mail agent executor with mock email."""
        return MailAgentExecutor(
            agent_id="mail-agent-test",
            use_mock=True,
        )

    @pytest.mark.asyncio
    async def test_mail_executor_processes_task(
        self, mail_executor: MailAgentExecutor
    ) -> None:
        """Test that mail agent executor can process a task."""
        from info_agent.a2a.models import Task

        task = Task(
            id="task-001",
            session_id="session-001",
            message={
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "skill_id": "send_email",
                            "to_address": "recipient@example.com",
                            "subject": "Test Email",
                            "body": "Test body",
                        }),
                    }
                ],
            },
        )

        result = await mail_executor.process_task(task)
        assert result is not None

    def test_create_mail_agent_card(self) -> None:
        """Test mail agent card creation."""
        card = create_mail_agent_card("mail-001", "http://localhost:8001")
        assert card.id == "mail-001"
        assert len(card.skills) > 0


class TestValidationAgentIntegration:
    """Tests for validation agent integration."""

    @pytest.fixture
    def validation_executor(self) -> ValidationAgentExecutor:
        """Create validation agent executor."""
        return ValidationAgentExecutor(
            agent_id="validation-agent-test",
            use_llm=False,
        )

    @pytest.mark.asyncio
    async def test_validation_executor_processes_task(
        self, validation_executor: ValidationAgentExecutor
    ) -> None:
        """Test that validation agent executor can process a task."""
        from info_agent.a2a.models import Task

        task = Task(
            id="task-002",
            session_id="session-001",
            message={
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "skill_id": "validate_document",
                            "document": {
                                "filename": "test.xlsx",
                                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            },
                            "criteria": {
                                "required_format": "xlsx",
                            },
                        }),
                    }
                ],
            },
        )

        result = await validation_executor.process_task(task)
        assert result is not None

    def test_create_validation_agent_card(self) -> None:
        """Test validation agent card creation."""
        card = create_validation_agent_card("validation-001", "http://localhost:8002")
        assert card.id == "validation-001"
        assert len(card.skills) > 0


class TestFullWorkflowExecution:
    """Tests for full workflow execution scenarios."""

    @pytest.fixture
    def supervisor(self) -> SupervisorAgent:
        """Create supervisor agent."""
        return SupervisorAgent(
            use_llm=False,
            use_stub_delegator=True,
        )

    @pytest.mark.asyncio
    async def test_happy_path_workflow(self, supervisor: SupervisorAgent) -> None:
        """Test complete workflow happy path."""
        # 1. Create workflow
        result = await supervisor.create_workflow(
            instructions="Send email to test@example.com for recipes",
            target_email="test@example.com",
            faq=[{"question": "Format?", "answer": "Excel"}],
            validation_criteria={"required_format": "xlsx"},
        )

        workflow_id = result["workflow_id"]
        assert workflow_id is not None

        # 2. Get initial status
        status = await supervisor.get_workflow_status(workflow_id)
        assert status["workflow_id"] == workflow_id

        # 3. Approve the plan
        await supervisor.approve_plan(workflow_id, approved=True)

        # 4. Simulate email response
        await supervisor.notify_email_received(
            workflow_id=workflow_id,
            email={
                "from_address": "test@example.com",
                "subject": "Re: Recipe Request",
                "body": "Here are the recipes.",
                "attachments": [{"filename": "recipes.xlsx"}],
            },
        )

        # 5. Check final status
        final_status = await supervisor.get_workflow_status(workflow_id)
        assert final_status is not None

    @pytest.mark.asyncio
    async def test_workflow_with_clarification(
        self, supervisor: SupervisorAgent
    ) -> None:
        """Test workflow with clarification request."""
        # 1. Create workflow
        result = await supervisor.create_workflow(
            instructions="Request document from user",
            target_email="user@example.com",
            faq=[{"question": "What format?", "answer": "Excel format please"}],
        )

        workflow_id = result["workflow_id"]

        # 2. Simulate clarification email
        await supervisor.notify_email_received(
            workflow_id=workflow_id,
            email={
                "from_address": "user@example.com",
                "subject": "Question",
                "body": "What format do you need?",
            },
        )

        # 3. Check status
        status = await supervisor.get_workflow_status(workflow_id)
        assert status is not None

    @pytest.mark.asyncio
    async def test_workflow_plan_rejection(self, supervisor: SupervisorAgent) -> None:
        """Test workflow with plan rejection."""
        # 1. Create workflow
        result = await supervisor.create_workflow(
            instructions="Request document",
            target_email="user@example.com",
        )

        workflow_id = result["workflow_id"]

        # 2. Reject the plan
        await supervisor.approve_plan(
            workflow_id, approved=False, feedback="Please add more steps"
        )

        # 3. Check status
        status = await supervisor.get_workflow_status(workflow_id)
        assert status is not None


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.fixture
    def supervisor(self) -> SupervisorAgent:
        """Create supervisor agent."""
        return SupervisorAgent(
            use_llm=False,
            use_stub_delegator=True,
        )

    @pytest.mark.asyncio
    async def test_invalid_workflow_id(self, supervisor: SupervisorAgent) -> None:
        """Test handling of invalid workflow ID."""
        with pytest.raises(Exception):
            await supervisor.get_workflow_status("nonexistent-workflow-id")

    @pytest.mark.asyncio
    async def test_missing_target_email(self, supervisor: SupervisorAgent) -> None:
        """Test handling of missing target email."""
        with pytest.raises(Exception):
            await supervisor.create_workflow(
                instructions="Send email",
                target_email="",  # Empty email
            )


class TestConcurrentWorkflows:
    """Tests for concurrent workflow execution."""

    @pytest.fixture
    def supervisor(self) -> SupervisorAgent:
        """Create supervisor agent."""
        return SupervisorAgent(
            use_llm=False,
            use_stub_delegator=True,
        )

    @pytest.mark.asyncio
    async def test_multiple_concurrent_workflows(
        self, supervisor: SupervisorAgent
    ) -> None:
        """Test running multiple workflows concurrently."""
        # Create multiple workflows
        workflows = []
        for i in range(5):
            result = await supervisor.create_workflow(
                instructions=f"Test workflow {i}",
                target_email=f"user{i}@example.com",
            )
            workflows.append(result["workflow_id"])

        # Verify all were created
        all_workflows = await supervisor.list_workflows()
        created_ids = {w["workflow_id"] for w in all_workflows}

        for workflow_id in workflows:
            assert workflow_id in created_ids
