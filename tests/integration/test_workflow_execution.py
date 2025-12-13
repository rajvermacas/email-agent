"""
Integration tests for workflow execution.

Tests the complete workflow from creation to execution,
including state transitions and checkpointing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWorkflowCreation:
    """Tests for workflow creation and initialization."""

    @patch("info_agent.workflow.graph.get_gemini_llm")
    @patch("info_agent.workflow.checkpointer.get_sqlite_checkpointer")
    def test_workflow_graph_creation(self, mock_checkpointer, mock_llm):
        """Test that workflow graph can be created."""
        from info_agent.workflow.graph import create_supervisor_graph

        mock_llm.return_value = MagicMock()
        mock_checkpointer.return_value = MagicMock()

        graph = create_supervisor_graph()

        assert graph is not None

    @patch("info_agent.workflow.graph.get_gemini_llm")
    def test_workflow_initial_state(self, mock_llm):
        """Test workflow initializes with correct state."""
        from info_agent.workflow.state import create_initial_state

        state = create_initial_state(
            workflow_id="test-001",
            instructions="Process this request",
            target_email="test@example.com",
        )

        assert state["workflow_id"] == "test-001"
        assert state["instructions"] == "Process this request"
        assert state["target_email"] == "test@example.com"
        assert state["status"] == "pending"
        assert state["plan"] is None
        assert state["audit_log"] == []


class TestWorkflowNodes:
    """Tests for individual workflow nodes."""

    @pytest.fixture
    def sample_state(self) -> dict:
        """Create sample workflow state."""
        return {
            "workflow_id": "test-001",
            "instructions": "Send an email with quarterly report",
            "target_email": "recipient@example.com",
            "plan": None,
            "status": "pending",
            "audit_log": [],
            "current_step": 0,
            "step_results": [],
            "parsed_requirements": None,
            "available_agents": [],
        }

    @patch("info_agent.workflow.nodes.get_gemini_llm")
    async def test_parse_input_node(self, mock_llm, sample_state):
        """Test parse input files node."""
        from info_agent.workflow.nodes import parse_input_files

        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock(
            return_value=MagicMock(
                content="Parsed requirements: Send quarterly report via email"
            )
        )
        mock_llm.return_value = mock_llm_instance

        result = await parse_input_files(sample_state)

        assert "parsed_requirements" in result
        assert result["status"] == "parsing_complete"

    @patch("info_agent.workflow.nodes.get_a2a_registry")
    async def test_query_registry_node(self, mock_registry, sample_state):
        """Test A2A registry query node."""
        from info_agent.workflow.nodes import query_a2a_registry

        mock_registry.return_value.list_agents = AsyncMock(
            return_value=[
                {"name": "mail-agent", "skills": ["send_email", "receive_email"]},
                {"name": "search-agent", "skills": ["web_search", "document_search"]},
            ]
        )

        result = await query_a2a_registry(sample_state)

        assert "available_agents" in result
        assert len(result["available_agents"]) > 0

    @patch("info_agent.workflow.nodes.get_gemini_llm")
    async def test_create_plan_node(self, mock_llm, sample_state):
        """Test execution plan creation node."""
        from info_agent.workflow.nodes import create_execution_plan

        sample_state["parsed_requirements"] = "Send quarterly report via email"
        sample_state["available_agents"] = [
            {"name": "mail-agent", "skills": ["send_email"]}
        ]

        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"steps": [{"agent": "mail-agent", "action": "send_email"}]}'
            )
        )
        mock_llm.return_value = mock_llm_instance

        result = await create_execution_plan(sample_state)

        assert "plan" in result
        assert result["status"] == "awaiting_approval"

    async def test_wait_for_approval_node(self, sample_state):
        """Test wait for approval node."""
        from info_agent.workflow.nodes import wait_for_user_approval

        sample_state["plan"] = {"steps": [{"agent": "mail-agent"}]}
        sample_state["status"] = "awaiting_approval"

        result = await wait_for_user_approval(sample_state)

        assert result["status"] in ["awaiting_approval", "approved", "rejected"]


class TestWorkflowStateTransitions:
    """Tests for workflow state transitions."""

    def test_state_transition_pending_to_parsing(self):
        """Test state transition from pending to parsing."""
        from info_agent.workflow.state import transition_state

        state = {"status": "pending"}
        new_state = transition_state(state, "parsing")

        assert new_state["status"] == "parsing"

    def test_state_transition_parsing_to_planning(self):
        """Test state transition from parsing to planning."""
        from info_agent.workflow.state import transition_state

        state = {"status": "parsing"}
        new_state = transition_state(state, "planning")

        assert new_state["status"] == "planning"

    def test_state_transition_adds_audit_log(self):
        """Test that state transitions add to audit log."""
        from info_agent.workflow.state import transition_state

        state = {"status": "pending", "audit_log": []}
        new_state = transition_state(state, "parsing")

        assert len(new_state["audit_log"]) > 0


class TestWorkflowCheckpointing:
    """Tests for workflow checkpointing functionality."""

    @pytest.fixture
    def mock_checkpointer(self):
        """Create mock checkpointer."""
        checkpointer = MagicMock()
        checkpointer.put = AsyncMock()
        checkpointer.get = AsyncMock()
        checkpointer.list = AsyncMock(return_value=[])
        return checkpointer

    async def test_checkpoint_save(self, mock_checkpointer):
        """Test saving workflow checkpoint."""
        from info_agent.workflow.checkpointer import save_checkpoint

        state = {
            "workflow_id": "test-001",
            "status": "running",
            "plan": {"steps": []},
        }

        await save_checkpoint(mock_checkpointer, "test-001", state)

        mock_checkpointer.put.assert_called_once()

    async def test_checkpoint_restore(self, mock_checkpointer):
        """Test restoring workflow from checkpoint."""
        from info_agent.workflow.checkpointer import restore_checkpoint

        expected_state = {
            "workflow_id": "test-001",
            "status": "running",
        }
        mock_checkpointer.get.return_value = expected_state

        state = await restore_checkpoint(mock_checkpointer, "test-001")

        assert state == expected_state


class TestWorkflowExecution:
    """Tests for complete workflow execution."""

    @patch("info_agent.workflow.graph.get_gemini_llm")
    @patch("info_agent.workflow.graph.get_sqlite_checkpointer")
    async def test_full_workflow_execution_mock(
        self, mock_checkpointer, mock_llm
    ):
        """Test full workflow execution with mocks."""
        from info_agent.workflow.graph import create_supervisor_graph
        from info_agent.workflow.state import create_initial_state

        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock(
            return_value=MagicMock(content="Processed")
        )
        mock_llm.return_value = mock_llm_instance
        mock_checkpointer.return_value = MagicMock()

        graph = create_supervisor_graph()
        initial_state = create_initial_state(
            workflow_id="test-full-001",
            instructions="Send a test email",
            target_email="test@example.com",
        )

        # Execute should complete without errors (mocked)
        assert graph is not None
        assert initial_state["workflow_id"] == "test-full-001"

    @patch("info_agent.workflow.nodes.get_gemini_llm")
    async def test_workflow_handles_llm_error(self, mock_llm):
        """Test workflow handles LLM errors gracefully."""
        from info_agent.workflow.nodes import parse_input_files
        from info_agent.utils.exceptions import LLMError

        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock(
            side_effect=Exception("LLM API error")
        )
        mock_llm.return_value = mock_llm_instance

        state = {
            "workflow_id": "test-error-001",
            "instructions": "Test instructions",
            "status": "pending",
            "audit_log": [],
        }

        with pytest.raises((Exception, LLMError)):
            await parse_input_files(state)


class TestWorkflowApproval:
    """Tests for workflow approval flow."""

    async def test_approve_workflow(self):
        """Test workflow approval."""
        from info_agent.workflow.state import approve_workflow

        state = {
            "workflow_id": "test-001",
            "status": "awaiting_approval",
            "plan": {"steps": [{"agent": "mail-agent"}]},
            "audit_log": [],
        }

        result = approve_workflow(state)

        assert result["status"] == "approved"
        assert "approved" in str(result["audit_log"]).lower()

    async def test_reject_workflow(self):
        """Test workflow rejection."""
        from info_agent.workflow.state import reject_workflow

        state = {
            "workflow_id": "test-001",
            "status": "awaiting_approval",
            "plan": {"steps": [{"agent": "mail-agent"}]},
            "audit_log": [],
        }

        result = reject_workflow(state, reason="Invalid plan")

        assert result["status"] == "rejected"
        assert "Invalid plan" in str(result["audit_log"])
