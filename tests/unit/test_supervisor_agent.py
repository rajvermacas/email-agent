"""
Unit tests for Supervisor Agent.

Tests the SupervisorAgent class with mocked dependencies
(ExecutionPlanner, A2A, LangGraph workflow).
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from info_agent.agents.supervisor.agent import SupervisorAgent
from info_agent.agents.supervisor.state import WorkflowStatus
from info_agent.config import Settings
from info_agent.utils.exceptions import ValidationError, WorkflowError, WorkflowNotFoundError


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=Settings)
    settings.a2a_registry_url = "http://registry:8000"
    return settings


@pytest.fixture
def mock_compiled_workflow():
    """Create mock compiled workflow."""
    workflow = Mock()
    workflow.get_state = Mock()
    workflow.update_state = Mock()
    return workflow


@pytest.fixture
def mock_planner():
    """Create mock ExecutionPlanner."""
    planner = Mock()
    planner.generate_plan = AsyncMock()
    return planner


class TestSupervisorAgentInit:
    """Tests for SupervisorAgent initialization."""

    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.get_compiled_workflow")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    def test_init_success(self, mock_a2a_class, mock_get_workflow, mock_planner_class, mock_settings):
        """Test successful agent initialization."""
        mock_workflow = Mock()
        mock_get_workflow.return_value = mock_workflow
        mock_planner_class.return_value = Mock()

        agent = SupervisorAgent(settings=mock_settings)

        assert agent.settings == mock_settings
        assert agent.planner is not None
        assert agent.compiled_workflow is not None
        assert agent.a2a_client is not None

        mock_planner_class.assert_called_once()
        mock_a2a_class.assert_called_once_with("http://registry:8000")

    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.get_compiled_workflow")
    @patch("info_agent.agents.supervisor.agent.get_settings")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    def test_init_with_default_settings(self, mock_a2a, mock_get_settings, mock_get_workflow, mock_planner_class):
        """Test initialization with default settings."""
        mock_settings = Mock(spec=Settings)
        mock_settings.a2a_registry_url = "http://default:8000"
        mock_get_settings.return_value = mock_settings

        agent = SupervisorAgent()

        assert agent.settings == mock_settings
        mock_get_settings.assert_called_once()

    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    def test_init_with_custom_workflow(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test initialization with custom workflow."""
        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        assert agent.compiled_workflow == mock_compiled_workflow


class TestSupervisorAgentCreateWorkflow:
    """Tests for SupervisorAgent.create_workflow method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.run_workflow")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_create_workflow_success(self, mock_a2a, mock_run_workflow, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test successful workflow creation."""
        # Mock run_workflow to return a completed state
        mock_final_state = {
            "workflow_id": "wf-123",
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "workflow_name": "Test Workflow",
        }
        mock_run_workflow.return_value = mock_final_state

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        workflow_id = await agent.create_workflow(
            workflow_name="Test Workflow",
            instructions="Please collect information from john@example.com",
            instructions_filename="request.txt",
        )

        assert workflow_id is not None
        assert workflow_id.startswith("wf-")

        # Verify run_workflow was called
        mock_run_workflow.assert_called_once()
        call_kwargs = mock_run_workflow.call_args.kwargs
        assert call_kwargs["workflow_id"] == workflow_id
        assert "initial_state" in call_kwargs

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_create_workflow_missing_name(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test workflow creation fails with missing name."""
        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(ValidationError) as exc_info:
            await agent.create_workflow(
                workflow_name="",
                instructions="Test instructions",
                instructions_filename="test.txt",
            )

        assert "workflow_name is required" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_create_workflow_missing_instructions(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test workflow creation fails with missing instructions."""
        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(ValidationError) as exc_info:
            await agent.create_workflow(
                workflow_name="Test",
                instructions="",
                instructions_filename="test.txt",
            )

        assert "instructions are required" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.run_workflow")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_create_workflow_execution_failure(self, mock_a2a, mock_run_workflow, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test workflow creation handles execution failure."""
        mock_run_workflow.side_effect = Exception("Workflow execution failed")

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(WorkflowError) as exc_info:
            await agent.create_workflow(
                workflow_name="Test",
                instructions="Instructions",
                instructions_filename="test.txt",
            )

        assert "Failed to create workflow" in str(exc_info.value)


class TestSupervisorAgentGetWorkflowState:
    """Tests for SupervisorAgent.get_workflow_state method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_get_workflow_state_success(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test successful workflow state retrieval."""
        mock_state_obj = Mock()
        mock_state_obj.values = {
            "workflow_id": "wf-123",
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "workflow_name": "Test",
        }

        mock_compiled_workflow.get_state = Mock(return_value=mock_state_obj)

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        state = await agent.get_workflow_state("wf-123")

        assert state["workflow_id"] == "wf-123"
        assert state["status"] == WorkflowStatus.AWAITING_APPROVAL.value

        # Verify get_state was called with correct config
        mock_compiled_workflow.get_state.assert_called_once()
        call_args = mock_compiled_workflow.get_state.call_args[0][0]
        assert call_args["configurable"]["thread_id"] == "wf-123"

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_get_workflow_state_missing_id(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test get_workflow_state fails with missing workflow_id."""
        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(ValidationError) as exc_info:
            await agent.get_workflow_state("")

        assert "workflow_id is required" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_get_workflow_state_not_found(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test get_workflow_state handles workflow not found."""
        mock_state_obj = Mock()
        mock_state_obj.values = None

        mock_compiled_workflow.get_state = Mock(return_value=mock_state_obj)

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(WorkflowNotFoundError) as exc_info:
            await agent.get_workflow_state("wf-nonexistent")

        assert "wf-nonexistent" in str(exc_info.value)


class TestSupervisorAgentApprovePlan:
    """Tests for SupervisorAgent.approve_plan method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.resume_workflow")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_approve_plan_success(self, mock_a2a, mock_resume_workflow, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test successful plan approval."""
        # Mock current state
        current_state = {
            "workflow_id": "wf-123",
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "plan": [{"step": 1, "action": "send_email", "description": "Send", "status": "pending"}],
            "audit_log": [],
        }

        mock_state_obj = Mock()
        mock_state_obj.values = current_state
        mock_compiled_workflow.get_state = Mock(return_value=mock_state_obj)

        # Mock resumed state
        resumed_state = {
            **current_state,
            "status": WorkflowStatus.EXECUTING.value,
            "plan_approved": True,
        }
        mock_resume_workflow.return_value = resumed_state

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        result = await agent.approve_plan("wf-123")

        assert result["plan_approved"] is True
        assert result["status"] == WorkflowStatus.EXECUTING.value

        # Verify resume_workflow was called
        mock_resume_workflow.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_approve_plan_wrong_status(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test approve_plan fails if workflow not awaiting approval."""
        current_state = {
            "workflow_id": "wf-123",
            "status": WorkflowStatus.COMPLETED.value,
        }

        mock_state_obj = Mock()
        mock_state_obj.values = current_state
        mock_compiled_workflow.get_state = Mock(return_value=mock_state_obj)

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(WorkflowError) as exc_info:
            await agent.approve_plan("wf-123")

        assert "not awaiting approval" in str(exc_info.value)


class TestSupervisorAgentRejectPlan:
    """Tests for SupervisorAgent.reject_plan method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.resume_workflow")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_reject_plan_success(self, mock_a2a, mock_resume_workflow, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test successful plan rejection."""
        current_state = {
            "workflow_id": "wf-123",
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "audit_log": [],
        }

        mock_state_obj = Mock()
        mock_state_obj.values = current_state
        mock_compiled_workflow.get_state = Mock(return_value=mock_state_obj)

        resumed_state = {
            **current_state,
            "plan_rejected": True,
            "approval_feedback": "Be more specific",
        }
        mock_resume_workflow.return_value = resumed_state

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        result = await agent.reject_plan("wf-123", feedback="Be more specific")

        assert result["plan_rejected"] is True
        assert result["approval_feedback"] == "Be more specific"

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_reject_plan_missing_feedback(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test reject_plan fails without feedback."""
        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(ValidationError) as exc_info:
            await agent.reject_plan("wf-123", feedback="")

        assert "feedback is required" in str(exc_info.value)


class TestSupervisorAgentCancelWorkflow:
    """Tests for SupervisorAgent.cancel_workflow method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.resume_workflow")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_cancel_workflow_success(self, mock_a2a, mock_resume_workflow, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test successful workflow cancellation."""
        current_state = {
            "workflow_id": "wf-123",
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "audit_log": [],
        }

        mock_state_obj = Mock()
        mock_state_obj.values = current_state
        mock_compiled_workflow.get_state = Mock(return_value=mock_state_obj)

        cancelled_state = {
            **current_state,
            "status": WorkflowStatus.CANCELLED.value,
            "plan_cancelled": True,
        }
        mock_resume_workflow.return_value = cancelled_state

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        result = await agent.cancel_workflow("wf-123")

        assert result["status"] == WorkflowStatus.CANCELLED.value
        assert result["plan_cancelled"] is True


class TestSupervisorAgentHandleEmailReceived:
    """Tests for SupervisorAgent.handle_email_received method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.resume_workflow")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_handle_email_received_success(self, mock_a2a, mock_resume_workflow, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test successful email response handling."""
        current_state = {
            "workflow_id": "wf-123",
            "status": WorkflowStatus.WAITING_FOR_RESPONSE.value,
            "audit_log": [],
        }

        mock_state_obj = Mock()
        mock_state_obj.values = current_state
        mock_compiled_workflow.get_state = Mock(return_value=mock_state_obj)

        completed_state = {
            **current_state,
            "status": WorkflowStatus.COMPLETED.value,
            "received_response": "Here is the information you requested",
        }
        mock_resume_workflow.return_value = completed_state

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        result = await agent.handle_email_received(
            workflow_id="wf-123",
            email_id="msg-456",
            subject="Re: Information Request",
            body="Here is the information you requested",
            sender="john@example.com",
        )

        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert result["received_response"] == "Here is the information you requested"

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_handle_email_received_missing_params(self, mock_a2a, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test handle_email_received fails with missing parameters."""
        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(ValidationError):
            await agent.handle_email_received(
                workflow_id="",
                email_id="msg-123",
                subject="Test",
                body="Body",
                sender="sender@example.com",
            )


class TestSupervisorAgentSendEmail:
    """Tests for SupervisorAgent.send_email_via_mail_agent method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_send_email_success(self, mock_a2a_class, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test successful email sending via Mail Agent."""
        mock_a2a_client = Mock()
        mock_a2a_client.send_task = AsyncMock(return_value={
            "email_id": "msg-123",
            "status": "sent",
        })
        mock_a2a_class.return_value = mock_a2a_client

        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        result = await agent.send_email_via_mail_agent(
            workflow_id="wf-123",
            to_email="client@example.com",
            subject="Information Request",
            body="Dear Client,\n\nPlease send the reports.",
        )

        assert result["email_id"] == "msg-123"
        assert result["status"] == "sent"

        # Verify A2A client was called
        mock_a2a_client.send_task.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.agent.ExecutionPlanner")
    @patch("info_agent.agents.supervisor.agent.A2AClient")
    async def test_send_email_missing_params(self, mock_a2a_class, mock_planner_class, mock_settings, mock_compiled_workflow):
        """Test send_email fails with missing parameters."""
        agent = SupervisorAgent(settings=mock_settings, compiled_workflow=mock_compiled_workflow)

        with pytest.raises(ValidationError):
            await agent.send_email_via_mail_agent(
                workflow_id="wf-123",
                to_email="",
                subject="Test",
                body="Body",
            )
